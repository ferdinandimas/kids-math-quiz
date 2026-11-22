"""Typed KidQuest request bodies (PRD section 12).

Every model rejects unknown fields, so a request can never smuggle in a child ID: the child always
comes from the server-side session.
"""

import re

from pydantic import BaseModel, ConfigDict, Field

# Header `Idempotency-Key`: 8-128 characters, letters, digits, and . _ : - (a UUID fits).
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
MAX_VERSION = 1_000_000_000


class ThemeRequest(BaseModel):
    """PATCH /api/kidquest/theme (PRD 12.4): `{"theme_id": "kingdom", "world_version": 3, "manifest_version": 1}`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theme_id: str = Field(strict=True, min_length=1, max_length=32)
    world_version: int = Field(strict=True, ge=1, le=MAX_VERSION)
    manifest_version: int = Field(strict=True, ge=1, le=MAX_VERSION)


class EmptyRequest(BaseModel):
    """POST .../quests/{quest_id}/start and .../challenge take no fields; an empty body is fine."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnswerRequest(BaseModel):
    """POST /api/kidquest/challenges/{challenge_id}/answers (PRD 12.2): `{"answer": "4", "hint_count": 0}`.

    `answer` is the digits the child typed (1-4 digits, surrounding spaces allowed). `hint_count` is
    the client's view of hints seen; it is validated and part of the idempotency hash, but the stored
    hint count is derived by the server from the challenge's earlier attempts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(strict=True, max_length=8, pattern=r"^\s*\d{1,4}\s*$")
    hint_count: int = Field(default=0, strict=True, ge=0, le=10)


class PlacementRequest(BaseModel):
    """POST /api/kidquest/buildings (PRD 12.3):
    `{"building_type": "starter_house", "x": 2, "y": 3, "rotation": 0, "world_version": 1}`.

    (x, y) is the footprint's top-left cell. Out-of-map coordinates in range are a placement rule
    (`out_of_bounds`), not a malformed request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    building_type: str = Field(strict=True, min_length=1, max_length=32)
    x: int = Field(strict=True, ge=-64, le=64)
    y: int = Field(strict=True, ge=-64, le=64)
    rotation: int = Field(default=0, strict=True, ge=-360, le=360)
    world_version: int = Field(strict=True, ge=1, le=MAX_VERSION)


class PreviewQuery(BaseModel):
    """GET /api/kidquest/buildings/preview?building_type=starter_house&x=2&y=1&rotation=0 (read-only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    building_type: str = Field(min_length=1, max_length=32)
    x: int = Field(ge=-64, le=64)
    y: int = Field(ge=-64, le=64)
    rotation: int = Field(default=0, ge=-360, le=360)
