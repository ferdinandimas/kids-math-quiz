"""Adult-only KidQuest API: session, Ringkasan, and per-child scoped reset."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.api.kidquest_routes import idempotency_key, parse_body, stored
from app.security.adult_session import (
    ADULT_COOKIE_NAME,
    AdultSessionClaims,
    clear_adult_session_cookie,
    set_adult_session_cookie,
)
from app.services.kidquest_adult_service import KidQuestAdultService


class ParentPinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pin: str = Field(strict=True, min_length=1, max_length=128)


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: Literal["legacy_history", "kidquest_progress", "all_child_data"]
    confirm: str = Field(strict=True, min_length=1, max_length=64)


def build_kidquest_adult_router(service: KidQuestAdultService) -> APIRouter:
    router = APIRouter(prefix="/api/kidquest/adult", include_in_schema=False)

    def adult_claims(request: Request) -> AdultSessionClaims:
        return service.authenticate(request.cookies.get(ADULT_COOKIE_NAME))

    @router.post("/session")
    async def create_adult_session(request: Request):
        body = parse_body(await request.body(), ParentPinRequest)
        token = await run_in_threadpool(service.login, body.pin)
        response = JSONResponse({"ok": True, "expires_in": config.KIDQUEST_ADULT_SESSION_MAX_AGE})
        set_adult_session_cookie(
            response,
            token,
            max_age=config.KIDQUEST_ADULT_SESSION_MAX_AGE,
            secure=config.SESSION_COOKIE_SECURE,
        )
        return response

    @router.delete("/session")
    async def delete_adult_session(claims: AdultSessionClaims = Depends(adult_claims)):
        await run_in_threadpool(service.logout, claims)
        response = JSONResponse({"ok": True})
        clear_adult_session_cookie(response, secure=config.SESSION_COOKIE_SECURE)
        return response

    @router.get("/overview")
    async def overview(_: AdultSessionClaims = Depends(adult_claims)):
        return JSONResponse(await run_in_threadpool(service.overview))

    @router.post("/children/{child}/reset")
    async def reset_child(request: Request, child: str, _: AdultSessionClaims = Depends(adult_claims)):
        key = idempotency_key(request)
        body = parse_body(await request.body(), ResetRequest)
        result = await run_in_threadpool(service.reset_child, child, body.scope, body.confirm, key)
        return stored(result)

    return router
