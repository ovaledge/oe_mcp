"""Unauthenticated well-known routes required by assistant plugin directories."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from server.config import settings

OPENAI_APPS_CHALLENGE_PATH = "/.well-known/openai-apps-challenge"

router = APIRouter()


@router.get(OPENAI_APPS_CHALLENGE_PATH)
async def openai_apps_challenge() -> PlainTextResponse:
    """Return the OpenAI plugin domain-verification token (exact body, no JSON)."""
    token = (settings.openai_apps_challenge or "").strip()
    if not token:
        raise HTTPException(status_code=404, detail="openai_apps_challenge is not set")
    return PlainTextResponse(content=token, headers={"Cache-Control": "no-store"})
