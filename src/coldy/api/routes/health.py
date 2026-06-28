from __future__ import annotations

from fastapi import APIRouter

from ...config import settings

router = APIRouter()


@router.get("/")
def root() -> dict:
    return {"service": "coldy", "status": "ok"}


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "public_base_url": settings.public_base_url,
        "llm_model": settings.llm_model,
        "require_written_consent": settings.require_written_consent,
    }
