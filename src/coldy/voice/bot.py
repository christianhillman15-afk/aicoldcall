"""The real-time voice agent.

Audio path (each direction is streaming, which is what keeps latency low):

    Twilio  --mu-law 8kHz-->  transport.input()
            -> Deepgram STT (streaming partials + finals)
            -> user context aggregator
            -> Claude (AnthropicLLMService, token-streaming + tool calls)
            -> Cartesia TTS (sentence-chunked, starts speaking on first sentence)
            -> transport.output()  --audio-->  Twilio
            -> assistant context aggregator (records what was said)

Silero VAD drives turn-taking and barge-in: when the human starts talking the
agent's audio is interrupted, exactly like a real conversation.

NOTE ON VERSIONS: Pipecat's function-calling and event names move between
releases. The imports/patterns here match pipecat-ai ~0.0.60. If you bump
Pipecat and see an AttributeError around `register_function`,
`FunctionCallParams`, or `on_bot_stopped_speaking`, check the current symbol in
that release — the wiring concept is unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ..compliance.disclosure import recording_disclosure
from ..config import settings
from ..db.models import Call
from ..db.session import session_scope
from ..logging import get_logger
from . import openers
from .brain import is_hard_turn
from .humanizer import TURN_TAKING
from .persona import CallContext, build_inbound_opening, build_system_prompt
from .tools import TOOL_SCHEMAS, CallActions

log = get_logger("coldy.voice.bot")


def _persist(call_id: int, **fields) -> None:
    """Best-effort write of a few fields onto the Call row."""
    if not call_id:
        return
    try:
        with session_scope() as s:
            call = s.get(Call, call_id)
            if call:
                for k, v in fields.items():
                    setattr(call, k, v)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not persist call %s fields: %s", call_id, e)


def _transcript_from_context(context) -> str:
    """Flatten the conversation context into a readable transcript."""
    try:
        messages = context.get_messages()
    except Exception:  # noqa: BLE001
        messages = getattr(context, "messages", []) or []
    lines: list[str] = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if role == "system":
            continue
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if content:
            speaker = {"assistant": "AI", "user": "Lead"}.get(role, str(role))
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


@dataclass
class CallMeta:
    """Everything the bot needs to run one call."""

    lead_id: int
    call_id: int
    stream_sid: str
    call_sid: str
    context: CallContext


async def run_bot(
    websocket,
    meta: CallMeta,
    on_transfer: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Run the conversation on an accepted Twilio media-stream websocket.

    ``on_transfer`` is invoked (if provided) when the model decides to warm-
    transfer to a human; the telephony layer redirects the live call.
    """
    # Imports are local so the rest of the package (CLI, compliance, tests) does
    # not require the heavy pipecat/torch stack to be installed.
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.frames.frames import (
        EndFrame,
        LLMRunFrame,
        LLMUpdateSettingsFrame,
        TranscriptionFrame,
        TTSSpeakFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.services.anthropic.llm import AnthropicLLMService
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )

    # --- Telephony transport (8kHz, mu-law, Twilio serializer) ----------
    serializer = TwilioFrameSerializer(
        stream_sid=meta.stream_sid,
        call_sid=meta.call_sid,
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    stop_secs=TURN_TAKING.vad_stop_secs,
                    start_secs=TURN_TAKING.vad_start_secs,
                )
            ),
            serializer=serializer,
        ),
    )

    # --- The three services -------------------------------------------------
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY", ""), model=settings.stt_model)
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY", ""), voice_id=settings.tts_voice_id
    )
    # "Smarter + faster": prompt-cache the large, stable system prompt so it's
    # near-free and low-latency across every call in the campaign, and keep
    # max_tokens small (spoken turns are short -> caps worst-case latency). The
    # model is configurable (fast model by default); voice/brain.py holds the
    # two-tier escalation classifier for switching to the smarter model on hard
    # turns.
    try:
        llm_params = AnthropicLLMService.InputParams(
            max_tokens=settings.llm_max_tokens,
            enable_prompt_caching=True,
        )
    except (AttributeError, TypeError):  # InputParams shape varies across versions
        llm_params = None
    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=settings.llm_model,
        params=llm_params,
    )

    # --- Tools (in-call actions) -------------------------------------------
    actions = CallActions(lead_id=meta.lead_id, call_id=meta.call_id)

    async def _tool_handler(params: "FunctionCallParams") -> None:
        result = actions.dispatch(params.function_name, params.arguments or {})
        await params.result_callback({"result": result})

    # Register a catch-all handler for every declared tool.
    llm.register_function(None, _tool_handler)

    tools = ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name=t["name"],
                description=t["description"],
                properties=t["input_schema"]["properties"],
                required=t["input_schema"].get("required", []),
            )
            for t in TOOL_SCHEMAS
        ]
    )

    # --- Conversation context ----------------------------------------------
    system_prompt = build_system_prompt(meta.context)
    if meta.context.inbound:
        # The person called us — greet, don't cold-open.
        opening = build_inbound_opening(meta.context)
        opener_id = "inbound_greeting"
    else:
        # Pick the opener explicitly so we can record which one ran (A/B analytics).
        # Seeded by call id -> consistent per call, varied across calls.
        opener = openers.choose(meta.context, seed=meta.call_id)
        opening = openers.render(opener, meta.context)
        if meta.context.requires_recording_notice:
            opening = f"{opening} {recording_disclosure()}"
        opener_id = opener.id
    _persist(meta.call_id, opener_id=opener_id)
    context = OpenAILLMContext(
        messages=[{"role": "system", "content": system_prompt}],
        tools=tools,
    )
    aggregator = llm.create_context_aggregator(context)

    # --- Two-tier escalation: switch to the smarter model on hard turns -----
    # Sits right before the user aggregator; when the final user transcription
    # looks high-stakes (objection/price/trust), it pushes an LLM settings
    # update so THIS turn is answered by the escalation model, then drops back
    # to the fast model on the next easy turn. Best of both: fast by default,
    # smart when it matters. Degrades to a no-op if the frame API differs.
    escalator = None
    if settings.llm_escalation_model and settings.llm_escalation_model != settings.llm_model:

        def _model_update_frame(model_id: str):
            try:
                return LLMUpdateSettingsFrame(settings={"model": model_id})
            except TypeError:
                try:
                    from pipecat.frames.frames import LLMSettings

                    return LLMUpdateSettingsFrame(delta=LLMSettings(model=model_id))
                except Exception:  # noqa: BLE001
                    return None

        class _ModelEscalator(FrameProcessor):
            def __init__(self):
                super().__init__()
                self._current = settings.llm_model

            async def process_frame(self, frame, direction):
                await super().process_frame(frame, direction)
                if isinstance(frame, TranscriptionFrame) and getattr(frame, "text", ""):
                    target = (
                        settings.llm_escalation_model
                        if is_hard_turn(frame.text)
                        else settings.llm_model
                    )
                    if target != self._current:
                        upd = _model_update_frame(target)
                        if upd is not None:
                            self._current = target
                            await self.push_frame(upd, FrameDirection.DOWNSTREAM)
                            log.info("Escalation: switched live model -> %s", target)
                await self.push_frame(frame, direction)

        escalator = _ModelEscalator()

    # --- Pipeline ----------------------------------------------------------
    processors = [transport.input(), stt]
    if escalator is not None:
        processors.append(escalator)
    processors += [
        aggregator.user(),
        llm,
        tts,
        transport.output(),
        aggregator.assistant(),
    ]
    pipeline = Pipeline(processors)
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=TURN_TAKING.allow_interruptions,
            audio_in_sample_rate=TURN_TAKING.sample_rate,
            audio_out_sample_rate=TURN_TAKING.sample_rate,
            enable_metrics=True,
        ),
    )

    # --- Lifecycle handlers ------------------------------------------------
    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):
        # Speak the mandatory disclosure + opening verbatim so the legally
        # required identity/AI/recording notice is always said exactly. Then
        # record it in context so the model continues naturally from there.
        log.info("Call %s connected; speaking opening", meta.call_id)
        context.add_message({"role": "assistant", "content": opening})
        await task.queue_frames([TTSSpeakFrame(opening)])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):
        log.info("Call %s websocket disconnected", meta.call_id)
        await task.cancel()

    # Hang up / transfer once the agent finishes its current sentence.
    @transport.event_handler("on_bot_stopped_speaking")
    async def _on_bot_idle(_transport):
        if actions.transfer_requested and on_transfer is not None:
            log.info("Executing warm transfer for call %s", meta.call_id)
            await on_transfer()
            actions.transfer_requested = False
            await task.queue_frames([EndFrame()])
        elif actions.ended:
            log.info("Ending call %s after sign-off", meta.call_id)
            await task.queue_frames([EndFrame()])

    runner = PipelineRunner(handle_sigint=False)
    try:
        await runner.run(task)
    finally:
        _persist(
            meta.call_id,
            transcript=_transcript_from_context(context),
            recorded=settings.record_calls,
        )
    log.info("Call %s pipeline finished (outcome=%s)", meta.call_id, actions.final_outcome.value)
