"""KidQuest HTTP API (PRD section 12): world state, theme selection, the Q001 quest flow, and placement.

Registered by create_app() only when KIDQUEST_ENABLED is true. With KidQuest off these routes do
not exist, so `/api/kidquest/*` gets the legacy API 404 (`{"ok": false, "message": "Not found"}`).
The routes are left out of the OpenAPI document, so `/openapi.json` is identical in both modes.

Every route, before doing anything else:
1. takes the child only from the `math_sess` server session (set by GET /home/{child}); no route
   reads a child from the path, query, header, or body;
2. returns 401 PROFILE_REQUIRED when no child is selected;
3. returns 403 KIDQUEST_DISABLED when the child is not in KIDQUEST_PROFILE_ALLOWLIST (empty
   allowlist = nobody, PRD 15).

Errors use the PRD 12.10 envelope `{"ok": false, "error": {"code": ..., "message": ...}}`; some add
fields inside `error` (`world_version`, `manifest_version`, `fields`).

| Route | Success | Errors |
| --- | --- | --- |
| GET /api/kidquest/state | 200 world state; the first read creates the world | 401, 403 |
| GET /api/kidquest/themes | 200 theme metadata with per-theme assets, current theme, world version | 401, 403 |
| PATCH /api/kidquest/theme | 200 new theme, world version, and unchanged state | 400 INVALID_REQUEST, 409 IDEMPOTENCY_CONFLICT, 409 WORLD_VERSION_CONFLICT, 422 INVALID_THEME |
| POST /api/kidquest/quests/{quest_id}/start | 200 quest (AVAILABLE -> IN_PROGRESS or resumed) and next action | 400, 404 NOT_FOUND, 409 QUEST_LOCKED, 409 IDEMPOTENCY_CONFLICT |
| POST /api/kidquest/quests/{quest_id}/challenge | 200 the active challenge (created once; null after it is solved), daily attempts | 400, 404 NOT_FOUND, 409 QUEST_LOCKED, 409 IDEMPOTENCY_CONFLICT |
| POST /api/kidquest/challenges/{challenge_id}/answers | 200 `correct` false + hint, or true + reward, inventory, READY_TO_BUILD | 400, 404 NOT_FOUND, 409 CHALLENGE_EXPIRED, 409 IDEMPOTENCY_CONFLICT, 429 DAILY_CAP_REACHED |
| GET /api/kidquest/buildings/preview?building_type=&x=&y=&rotation= | 200 `valid`, footprint `cells`, `cost`, `problems[{rule, message}]`, `world_version` (read-only, no key) | 400 INVALID_REQUEST |
| POST /api/kidquest/buildings | 200 building, spent, new world version, quest COMPLETED, inventory | 400, 409 WORLD_VERSION_CONFLICT, 409 IDEMPOTENCY_CONFLICT, 422 INVALID_PLACEMENT, 422 INSUFFICIENT_RESOURCES (all with `error.rule` and `error.rules`) |

Every mutation (PATCH and POST) requires the `Idempotency-Key` header (PRD 12). The same key and
body replay the stored response byte-for-byte; the same key with a different body is 409
IDEMPOTENCY_CONFLICT. The theme change also stores INVALID_THEME / WORLD_VERSION_CONFLICT outcomes;
the quest routes store only successful outcomes, so a refused request (locked quest, finished
challenge, daily cap) can be retried with the same key once the refusal no longer applies.

The page `GET /kidquest` (KQ-010, `build_kidquest_page_router`) is gated the same way, but answers
like a legacy page: when it may not be shown (no child, child not allowlisted) it returns the same
303 redirect to /home that the legacy app gives every unknown page, so with KidQuest off or closed
for a child, `/kidquest` is byte-identical to the legacy response.
"""

import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from app import config
from app.api.kidquest_schemas import (
    IDEMPOTENCY_KEY_PATTERN,
    AnswerRequest,
    EmptyRequest,
    PlacementRequest,
    PreviewQuery,
    ThemeRequest,
)
from app.services.kidquest_service import KidQuestError, KidQuestService
from app.domain.kidquest.content import Catalog
from app.services.session_service import SessionService
from app.web.templates import templates


async def kidquest_error_handler(request: Request, exc: KidQuestError) -> JSONResponse:
    return JSONResponse(exc.body(), status_code=exc.status_code)


def invalid_request(message: str, **details) -> KidQuestError:
    return KidQuestError("INVALID_REQUEST", message, 400, **details)


def build_kidquest_router(kidquest_svc: KidQuestService, session_svc: SessionService) -> APIRouter:
    r = APIRouter(prefix="/api/kidquest", include_in_schema=False)

    def active_child(request: Request) -> str:
        if not config.KIDQUEST_ENABLED:  # Defense in depth; the router is normally not registered.
            raise KidQuestError("KIDQUEST_DISABLED", "Dunia KidQuest belum tersedia.", 404)
        child = session_svc.selected_child(request)
        if not child:
            raise KidQuestError("PROFILE_REQUIRED", "Pilih akun dulu.", 401)
        if child not in config.KIDQUEST_PROFILE_ALLOWLIST:
            raise KidQuestError("KIDQUEST_DISABLED", "Dunia KidQuest belum dibuka untuk akun ini.", 403)
        return child

    @r.get("/state")
    def get_state(child: str = Depends(active_child)):
        return JSONResponse(kidquest_svc.get_or_create_state(child))

    @r.get("/themes")
    def get_themes(child: str = Depends(active_child)):
        return JSONResponse(kidquest_svc.list_themes(child))

    @r.patch("/theme")
    async def change_theme(request: Request, child: str = Depends(active_child)):
        key = idempotency_key(request)
        body = parse_body(await request.body(), ThemeRequest)
        return stored(await run_in_threadpool(kidquest_svc.change_theme, child, body, key))

    @r.post("/quests/{quest_id}/start")
    async def start_quest(request: Request, quest_id: str, child: str = Depends(active_child)):
        key = idempotency_key(request)
        parse_body(await request.body(), EmptyRequest)
        return stored(await run_in_threadpool(kidquest_svc.start_quest, child, quest_id, key))

    @r.post("/quests/{quest_id}/challenge")
    async def quest_challenge(request: Request, quest_id: str, child: str = Depends(active_child)):
        key = idempotency_key(request)
        parse_body(await request.body(), EmptyRequest)
        return stored(await run_in_threadpool(kidquest_svc.issue_or_resume_challenge, child, quest_id, key))

    @r.post("/challenges/{challenge_id}/answers")
    async def answer_challenge(request: Request, challenge_id: str, child: str = Depends(active_child)):
        key = idempotency_key(request)
        body = parse_body(await request.body(), AnswerRequest)
        return stored(await run_in_threadpool(kidquest_svc.submit_answer, child, challenge_id, body, key))

    @r.get("/buildings/preview")
    def preview_building(request: Request, child: str = Depends(active_child)):
        # Unknown query parameters (a `child`, for example) are rejected, like unknown body fields.
        query = validate(dict(request.query_params), PreviewQuery)
        return JSONResponse(kidquest_svc.preview_placement(child, query.building_type, query.x, query.y, query.rotation))

    @r.post("/buildings")
    async def place_building(request: Request, child: str = Depends(active_child)):
        key = idempotency_key(request)
        body = parse_body(await request.body(), PlacementRequest)
        return stored(await run_in_threadpool(kidquest_svc.place_building, child, body, key))

    return r


def kidquest_allowed(child: str | None) -> bool:
    return config.KIDQUEST_ENABLED and child in config.KIDQUEST_PROFILE_ALLOWLIST


def kidquest_entry(request: Request, child: str | None, where: str) -> str | None:
    """The label of the KidQuest entry link on a legacy page, or None (render nothing).

    None unless KidQuest is enabled, its content is loaded, and `child` is allowlisted, so with
    KidQuest off the legacy templates render exactly as before.
    """
    catalog = getattr(request.app.state, "kidquest_catalog", None)
    if catalog is None or not kidquest_allowed(child):
        return None
    return catalog.ui_strings["entry"][where].format(name=child.capitalize())


def build_kidquest_page_router(catalog: Catalog, session_svc: SessionService) -> APIRouter:
    """GET /kidquest: the child's world page (KQ-010). Registered only when KidQuest is enabled."""
    r = APIRouter(include_in_schema=False)

    @r.get("/kidquest", response_class=HTMLResponse)
    def kidquest_page(request: Request):
        child = session_svc.selected_child(request) if config.KIDQUEST_ENABLED else None
        if not kidquest_allowed(child):
            # The legacy unknown-page answer (app.main._handle_404), byte for byte.
            return RedirectResponse(url="/home", status_code=303)
        boot = {
            "child": child,
            "name": child.capitalize(),
            "dev": not config.is_production(),
            "links": {"home": "/home", "quiz": "/quiz/math", "stats": "/stats"},
            "strings": catalog.ui_strings,
        }
        return templates.TemplateResponse(
            "kidquest_world.html",
            {
                "request": request,
                "child": child,
                "name": boot["name"],
                "accent": "purple" if child == "alleia" else "blue",  # Same rule as quiz.html profile-theme-*.
                "strings": catalog.ui_strings,
                "boot": boot,
            },
        )

    return r


def stored(result) -> Response:
    """Send a stored mutation result exactly as it will be replayed."""
    return Response(content=result.body, status_code=result.status_code, media_type="application/json")


def idempotency_key(request: Request) -> str:
    key = request.headers.get("Idempotency-Key", "")
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise invalid_request(
            "Header Idempotency-Key wajib: 8-128 karakter huruf, angka, atau . _ : -", fields=["Idempotency-Key"]
        )
    return key


def parse_body(raw: bytes, model):
    if not raw.strip() and not model.model_fields:  # Bodiless routes accept no body at all.
        return model()
    try:
        data = json.loads(raw)
    except ValueError:
        raise invalid_request("Isi permintaan harus JSON.") from None
    return validate(data, model)


def validate(data, model):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) or "body" for error in exc.errors()})
        raise invalid_request("Isi permintaan tidak valid.", fields=fields) from None
