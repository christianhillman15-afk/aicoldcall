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

from ..config import settings
from ..logging import get_logger
from .humanizer import TURN_TAKING
from .persona import CallContext, build_opening_line, build_system_prompt
from .tools import TOOL_SCHEMAS, CallActions

log = get_logger("coldy.voice.bot")


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
    from pipecat.frames.frames import EndFrame, LLMRunFrame, TTSSpeakFrame
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
    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
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
    opening = build_opening_line(meta.context)
    context = OpenAILLMContext(
        messages=[{"role": "system", "content": system_prompt}],
        tools=tools,
    )
    aggregator = llm.create_context_aggregator(context)

    # --- Pipeline ----------------------------------------------------------
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            aggregator.user(),
            llm,
            tts,
            transport.output(),
            aggregator.assistant(),
        ]
    )
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
    await runner.run(task)
    log.info("Call %s pipeline finished (outcome=%s)", meta.call_id, actions.final_outcome.value)
