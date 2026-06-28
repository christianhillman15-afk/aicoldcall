from .base import CRMSink, CallOutcomePayload
from .webhook_sink import WebhookCRMSink, get_default_sink

__all__ = ["CRMSink", "CallOutcomePayload", "WebhookCRMSink", "get_default_sink"]
