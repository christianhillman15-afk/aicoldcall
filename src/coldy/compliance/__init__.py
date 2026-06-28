"""Compliance guardrails for US AI outbound calling.

The single entrypoint is ``ComplianceEngine.evaluate(lead)`` which returns a
``ComplianceDecision``. The dialer MUST call it before every dial and honor the
result. See docs/COMPLIANCE.md for the legal background.
"""

from .engine import ComplianceDecision, ComplianceEngine

__all__ = ["ComplianceEngine", "ComplianceDecision"]
