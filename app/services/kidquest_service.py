"""KidQuest world state, theme selection, and the Q001 quest/challenge/answer flow.

The service is told which child is active; it never decides that from request data. Reads build one
consistent snapshot inside a transaction. Every mutation is one BEGIN IMMEDIATE unit of work
(`_idempotent`) that resolves its idempotency key, validates, writes, stores its response, and
commits once.
"""

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app import clock, config
from app.api.kidquest_schemas import AnswerRequest, PlacementRequest, ThemeRequest
from app.db.kidquest_repo import KidQuestRepo
from app.db.sqlite import transaction
from app.domain.kidquest.content import RESOURCES, Catalog, Quest
from app.domain.kidquest.placement import WorldFacts, footprint, placement_problems, problem_message
from app.domain.kidquest.roads import road_asset_id, road_mask, shore_asset_id, shore_mask
from app.domain.kidquest.state import QuestStatus, transition

# Idempotency operations; a key is scoped to (child, operation).
THEME_OPERATION = "theme.change"
START_OPERATION = "quest.start"
CHALLENGE_OPERATION = "quest.challenge"
ANSWER_OPERATION = "challenge.answer"
PLACE_OPERATION = "building.place"
REWARD_SOURCE = "quest_reward"
SPEND_SOURCE = "placement"


class KidQuestError(Exception):
    """A structured KidQuest failure, rendered as the PRD 12.10 error envelope."""

    def __init__(self, code: str, message: str, status_code: int, **details):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status_code, self.details = code, message, status_code, details

    def body(self) -> dict:
        return error_body(self.code, self.message, **self.details)


def error_body(code: str, message: str, **details) -> dict:
    return {"ok": False, "error": {"code": code, "message": message, **details}}


def to_json(payload: dict) -> str:
    """The exact bytes Starlette's JSONResponse would send; stored so a replay is identical."""
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def request_hash(operation: str, body: dict) -> str:
    canonical = json.dumps({"operation": operation, "body": body}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredResponse:
    """The outcome of an idempotent mutation: replayed byte-for-byte for the same key and body."""

    status_code: int
    body: str


class KidQuestService:
    def __init__(self, catalog: Catalog, repo: KidQuestRepo | None = None):
        self.catalog = catalog
        self.repo = repo or KidQuestRepo()
        # Presentation only. `art_reference_names` (PRD 11.7) is for artists and is never sent.
        self._themes = {
            theme_id: {
                "id": theme_id,
                "name": theme["name"],
                "manifest_version": catalog.manifest_version,
                "labels": theme["labels"],
                "assets": catalog.asset_paths(theme_id),
            }
            for theme_id, theme in catalog.themes.items()
        }

    # --- Reads ---------------------------------------------------------------------------------

    def get_or_create_state(self, child: str) -> dict:
        """GET /api/kidquest/state. The first read creates the child's starter world exactly once."""
        return self._read_world(child, self._state_in)

    def list_themes(self, child: str) -> dict:
        """GET /api/kidquest/themes: every theme is available and free (PRD 11.3)."""

        def build(conn, child: str) -> dict:
            world = self.repo.get_world_in(conn, child)
            return {
                "ok": True,
                "manifest_version": self.catalog.manifest_version,
                "default_theme_id": self.catalog.raw["themes"]["default_theme_id"],
                "current_theme_id": world["theme_id"],
                "world_version": world["version"],
                "themes": [
                    {
                        "id": theme["id"],
                        "name": theme["name"],
                        "manifest_version": theme["manifest_version"],
                        "asset_count": len(theme["assets"]),
                        "thumbnail": theme["assets"]["theme_thumbnail--base"],
                        "labels": theme["labels"],
                        "assets": theme["assets"],
                    }
                    for theme in self._themes.values()
                ],
            }

        return self._read_world(child, build)

    def _read_world(self, child: str, build: Callable) -> dict:
        # Ordinary reads take no write lock. Only a missing world needs BEGIN IMMEDIATE, and
        # initialization is INSERT OR IGNORE, so two racing first reads still create one world.
        with transaction(immediate=False) as conn:
            if self.repo.get_world_in(conn, child):
                return build(conn, child)
        with transaction() as conn:
            self.repo.initialize_world_in(conn, child, self.catalog, clock.now_str())
            return build(conn, child)

    # --- Theme change --------------------------------------------------------------------------

    def _idempotent(self, child: str, operation: str, key: str, body: dict, apply: Callable) -> StoredResponse:
        """Run one mutation as a single BEGIN IMMEDIATE unit of work.

        The same key and body replay the stored response byte-for-byte without touching anything
        else; the same key with another body is IDEMPOTENCY_CONFLICT. `apply(conn, now)` returns
        `(status, payload)`, which is stored and returned, or raises KidQuestError for a refusal that
        is not stored (and rolls everything back) because it may stop applying later, for example
        after the daily reset.
        """
        fingerprint = request_hash(operation, body)
        now = clock.now_str()
        with transaction() as conn:
            self.repo.initialize_world_in(conn, child, self.catalog, now)
            stored = self.repo.get_idempotency_in(conn, child, operation, key)
            if stored:
                if stored["request_hash"] != fingerprint:
                    raise KidQuestError(
                        "IDEMPOTENCY_CONFLICT", "Kode permintaan ini sudah dipakai untuk permintaan lain.", 409
                    )
                return StoredResponse(int(stored["status"]), stored["response_json"])

            status_code, payload = apply(conn, now)
            response = StoredResponse(status_code, to_json(payload))
            self.repo.save_idempotency_in(conn, child, operation, key, fingerprint, status_code, response.body, now)
            return response

    def change_theme(self, child: str, request: ThemeRequest, idempotency_key: str) -> StoredResponse:
        """PATCH /api/kidquest/theme (PRD 12.4, 14.3). INVALID_THEME and WORLD_VERSION_CONFLICT are stored."""
        return self._idempotent(
            child, THEME_OPERATION, idempotency_key, request.model_dump(),
            lambda conn, now: self._apply_theme_in(conn, child, request, now),
        )

    def _apply_theme_in(self, conn, child: str, request: ThemeRequest, now: str) -> tuple[int, dict]:
        if request.theme_id not in self._themes or request.manifest_version != self.catalog.manifest_version:
            return 422, error_body(
                "INVALID_THEME", "Tema ini tidak tersedia. Muat ulang daftar tema.",
                manifest_version=self.catalog.manifest_version,
            )
        world = self.repo.get_world_in(conn, child)
        if request.world_version != world["version"]:
            return 409, error_body(
                "WORLD_VERSION_CONFLICT", "Duniamu baru saja berubah. Muat ulang, lalu coba lagi.",
                world_version=world["version"],
            )
        # Choosing the theme already in use changes nothing, so the version stays put.
        if (request.theme_id, request.manifest_version) != (world["theme_id"], world["theme_manifest_version"]):
            self.repo.set_theme_in(conn, child, request.theme_id, request.manifest_version, world["version"], now)
        state = self._state_in(conn, child)
        return 200, {"ok": True, "theme_id": state["world"]["theme_id"], "world_version": state["world"]["version"],
                     **{key: value for key, value in state.items() if key != "ok"}}

    # --- State snapshot ------------------------------------------------------------------------

    def _state_in(self, conn, child: str) -> dict:
        """Logical entities plus the selected theme's labels and asset paths.

        Every entity carries a theme-neutral `asset_id`; `theme.assets[asset_id]` resolves it. A theme
        change therefore alters only `world.theme_id`, `world.version`, and the `theme` block.
        """
        world = self.repo.get_world_in(conn, child)
        layout, raw_layout = self.catalog.layout, self.catalog.raw["layout"]
        paths = self.repo.get_paths_in(conn, child)
        road_cells = {(path["x"], path["y"]) for path in paths}
        quest_rows = self.repo.get_quests_in(conn, child)
        challenge = self.repo.get_active_challenge_in(conn, child)

        return {
            "ok": True,
            "world": {
                "layout_version": world["layout_version"],
                "width": world["width"],
                "height": world["height"],
                "version": world["version"],
                "theme_id": world["theme_id"],
                "theme_manifest_version": world["theme_manifest_version"],
                "terrain": {
                    "ground_asset_id": f"{raw_layout['default_terrain']}--base",
                    "water": [
                        {"x": x, "y": y, "shore_mask": (mask := shore_mask((x, y), layout)), "asset_id": shore_asset_id(mask)}
                        for x, y in sorted(layout.water, key=lambda cell: (cell[1], cell[0]))
                    ],
                    "fixed_objects": [
                        {"id": obj["id"], "kind": obj["kind"], "x": obj["x"], "y": obj["y"], "asset_id": f"{obj['kind']}--base"}
                        for obj in raw_layout["fixed_objects"]
                    ],
                    "zones": [
                        {"id": zone_id, "x": zone["x"], "y": zone["y"], "width": zone["width"], "height": zone["height"],
                         "unlocked_by_quest": zone.get("unlocked_by_quest")}
                        for zone_id, zone in raw_layout["zones"].items()
                    ],
                },
            },
            "theme": self._themes[world["theme_id"]],
            "buildings": [self._building_payload(row) for row in self.repo.get_buildings_in(conn, child)],
            "paths": [
                {"id": path["id"], "x": path["x"], "y": path["y"], "path_type": path["path_type"],
                 "mask": (mask := road_mask((path["x"], path["y"]), road_cells)), "asset_id": road_asset_id(mask)}
                for path in paths
            ],
            "inventory": self._inventory_in(conn, child),
            "quests": [
                {"id": quest_id, "version": quest_rows[quest_id]["quest_version"], "status": quest_rows[quest_id]["status"],
                 "title": self.catalog.quests[quest_id].title, "building_id": self.catalog.quests[quest_id].building_id,
                 "playable": self.catalog.quests[quest_id].playable}
                for quest_id in self.catalog.quest_order
                if quest_id in quest_rows
            ],
            "active_challenge": challenge,
            "daily_attempts": self._daily_attempts_in(conn, child),
            "next_action": self._recommended_action(quest_rows, challenge),
        }

    def _recommended_action(self, quest_rows: dict[str, dict], challenge: dict | None) -> dict:
        """PRD 7.1 priority: resume the active challenge, place a READY_TO_BUILD building, continue an
        IN_PROGRESS quest, start an AVAILABLE playable quest; otherwise nothing is waiting."""
        if challenge:
            return self._next_action(self.catalog.quests[challenge["quest_id"]], QuestStatus.IN_PROGRESS.value, challenge["id"])
        playable = [(quest, quest_rows[quest.id]["status"]) for quest in self.catalog.quests.values()
                    if quest.playable and quest.id in quest_rows]
        for wanted in (QuestStatus.READY_TO_BUILD, QuestStatus.IN_PROGRESS, QuestStatus.AVAILABLE):
            for quest, status in playable:
                if status == wanted.value:
                    return self._next_action(quest, status)
        return {"type": "none"}

    def _building_payload(self, row: dict) -> dict:
        building = self.catalog.buildings[row["type"]]
        return {
            "id": row["id"], "type": row["type"], "x": row["x"], "y": row["y"], "rotation": row["rotation"],
            "width": building.width, "height": building.height, "entrances": list(building.entrances),
            "asset_id": building.visual_asset_key,
        }

    # --- Q001 quest, challenge, and answer (PRD 8.1, 9.1, 10.2, 12.1-12.2, 14.1) -------------------

    def start_quest(self, child: str, quest_id: str, idempotency_key: str) -> StoredResponse:
        """POST /api/kidquest/quests/{quest_id}/start: AVAILABLE -> IN_PROGRESS, otherwise resume."""

        def apply(conn, now):
            quest, status = self._begin_quest_in(conn, child, quest_id, now)
            return 200, {"ok": True, "quest": self._quest_payload(quest, status), "next_action": self._next_action(quest, status)}

        return self._idempotent(child, START_OPERATION, idempotency_key, {"quest_id": quest_id}, apply)

    def issue_or_resume_challenge(self, child: str, quest_id: str, idempotency_key: str) -> StoredResponse:
        """POST /api/kidquest/quests/{quest_id}/challenge: the one active challenge, created on first use.

        Starts an AVAILABLE quest first. Once the challenge is solved (READY_TO_BUILD or COMPLETED),
        `challenge` is null and `next_action` points at the building.
        """

        def apply(conn, now):
            quest, status = self._begin_quest_in(conn, child, quest_id, now)
            challenge = None
            if status == QuestStatus.IN_PROGRESS.value:
                row = self.repo.get_active_challenge_for_quest_in(conn, child, quest.id)
                if row and row["quest_version"] != quest.version:  # Content changed: retire the old instance.
                    self.repo.finish_challenge_in(conn, row["id"], "EXPIRED", now)
                    row = None
                if row is None:
                    challenge_id = f"ch_{secrets.token_hex(8)}"
                    content_ref = f"{quest.id}#{quest.raw['challenge']['id']}"
                    self.repo.insert_challenge_in(conn, challenge_id, child, quest.id, quest.version, content_ref, now)
                    row = self.repo.get_challenge_in(conn, child, challenge_id)
                challenge = self._challenge_payload(quest, row["id"], self.repo.count_attempts_in(conn, row["id"]))
            return 200, {
                "ok": True,
                "challenge": challenge,
                "quest": self._quest_payload(quest, status),
                "daily_attempts": self._daily_attempts_in(conn, child),
                "next_action": self._next_action(quest, status, challenge["id"] if challenge else None),
            }

        return self._idempotent(child, CHALLENGE_OPERATION, idempotency_key, {"quest_id": quest_id}, apply)

    def submit_answer(self, child: str, challenge_id: str, request: AnswerRequest, idempotency_key: str) -> StoredResponse:
        """POST /api/kidquest/challenges/{challenge_id}/answers: one accepted attempt per key (PRD 14.1).

        Only accepted attempts are stored for replay. Refusals (unknown or finished challenge, daily
        cap) change nothing and are not stored, so the same key works once the refusal no longer applies.
        """
        # The logical request: " 04" and "4" are the same answer.
        body = {"challenge_id": challenge_id, "answer": int(request.answer.strip()), "hint_count": request.hint_count}
        return self._idempotent(
            child, ANSWER_OPERATION, idempotency_key, body,
            lambda conn, now: (200, self._answer_in(conn, child, challenge_id, request, idempotency_key, now)),
        )

    def _answer_in(self, conn, child: str, challenge_id: str, request: AnswerRequest, key: str, now: str) -> dict:
        row = self.repo.get_challenge_in(conn, child, challenge_id)  # Another child's ID is simply not found.
        if row is None:
            raise KidQuestError("NOT_FOUND", "Tantangan ini tidak ditemukan.", 404)
        quest = self.catalog.quests.get(row["quest_id"])
        if row["status"] != "ACTIVE" or quest is None or quest.version != row["quest_version"]:
            raise KidQuestError(
                "CHALLENGE_EXPIRED", "Tantangan ini sudah selesai. Lihat duniamu untuk langkah berikutnya.", 409,
                challenge_status=row["status"],
            )
        day = clock.today_str()
        used = self.repo.get_daily_usage_in(conn, child, day)
        if used >= config.KIDQUEST_DAILY_ATTEMPT_LIMIT:
            raise KidQuestError(
                "DAILY_CAP_REACHED", "Latihan hari ini sudah cukup. Duniamu tetap bisa dilihat. Lanjut besok, ya!", 429,
                daily_attempts=self._daily_attempts(used),
            )

        content = quest.raw["challenge"]
        earlier = self.repo.count_attempts_in(conn, challenge_id)  # All wrong: a correct one completes the challenge.
        correct = int(request.answer.strip()) == content["answer"]
        hints_seen = min(earlier, len(content["hints"]))  # Server-derived; the client's hint_count is not stored.
        self.repo.insert_attempt_in(conn, child, key, challenge_id, content["skill_id"], quest.version, correct, hints_seen, now)
        self.repo.add_daily_usage_in(conn, child, day, now)
        attempts = earlier + 1
        daily = self._daily_attempts(used + 1)

        if not correct:  # PRD 10.2: no credit, no status change, same challenge stays retryable.
            return {
                "ok": True,
                "correct": False,
                "hint": self._hint(content, attempts),
                "challenge": {"id": challenge_id, "status": "ACTIVE", "attempt_count": attempts},
                "quest": self._quest_payload(quest, QuestStatus.IN_PROGRESS.value),
                "daily_attempts": daily,
                "next_action": self._next_action(quest, QuestStatus.IN_PROGRESS.value, challenge_id),
            }

        self.repo.finish_challenge_in(conn, challenge_id, "COMPLETED", now)
        current = QuestStatus(self.repo.get_quest_in(conn, child, quest.id)["status"])
        ready = transition(current, QuestStatus.READY_TO_BUILD)  # Raises (and rolls back) on an impossible state.
        self.repo.set_quest_status_in(conn, child, quest.id, current.value, ready.value, now)
        reward = quest.raw["reward"]
        for item in reward["resources"]:
            self.repo.credit_resource_in(conn, child, item["resource"], item["amount"], REWARD_SOURCE, quest.id, now)
        for building_type in reward["blueprints"]:
            self.repo.grant_blueprint_in(conn, child, building_type, REWARD_SOURCE, quest.id, quest.version, now)
        return {
            "ok": True,
            "correct": True,
            "challenge": {"id": challenge_id, "status": "COMPLETED", "attempt_count": attempts},
            "quest": self._quest_payload(quest, ready.value),
            "reward": {
                "resources": {item["resource"]: item["amount"] for item in reward["resources"]},
                "blueprints": list(reward["blueprints"]),
            },
            "reward_message": quest.raw["reward_message"],
            "inventory": self._inventory_in(conn, child),
            "daily_attempts": daily,
            "next_action": self._next_action(quest, ready.value),
        }

    def _begin_quest_in(self, conn, child: str, quest_id: str, now: str) -> tuple[Quest, str]:
        """The playable quest and its status, moving AVAILABLE -> IN_PROGRESS (never backward)."""
        quest = self.catalog.quests.get(quest_id)
        row = self.repo.get_quest_in(conn, child, quest_id) if quest else None
        if row is None:
            raise KidQuestError("NOT_FOUND", "Misi ini tidak ditemukan.", 404)
        if row["status"] == QuestStatus.LOCKED.value or not quest.playable:
            raise KidQuestError("QUEST_LOCKED", "Misi ini belum terbuka.", 409, quest_id=quest_id)
        if row["status"] == QuestStatus.AVAILABLE.value:
            started = transition(QuestStatus.AVAILABLE, QuestStatus.IN_PROGRESS).value
            self.repo.set_quest_status_in(conn, child, quest_id, row["status"], started, now)
            return quest, started
        return quest, row["status"]

    def _challenge_payload(self, quest: Quest, challenge_id: str, wrong_attempts: int) -> dict:
        """PRD 12.1. Never contains the answer, the reward amounts, or a child ID."""
        content = quest.raw["challenge"]
        return {
            "id": challenge_id,
            "quest_id": quest.id,
            "content_version": quest.version,
            "skill_id": content["skill_id"],
            "type": content["type"],
            "prompt": content["prompt"],
            "visual_context": content["visual_context"],
            "attempt_count": wrong_attempts,
            "status": "ACTIVE",
            "story": quest.raw["story"],
            "reward_preview": quest.raw["reward_preview"],
            "hint": self._hint(content, wrong_attempts),  # On resume, the latest hint already earned.
        }

    @staticmethod
    def _hint(content: dict, wrong_attempts: int) -> dict | None:
        """Content hints in order: a neutral hint first, the last one is the worked decomposition.

        The worked level adds `visual` (the prompt's own quantities) so the client can draw the
        filled and empty slots; it never states the answer.
        """
        hints = content["hints"]
        level = min(wrong_attempts, len(hints))
        if level == 0:
            return None
        worked = level == len(hints) and level > 1
        hint = {"level": level, "kind": "worked_example" if worked else "hint", "text": hints[level - 1]}
        if worked:
            hint["visual"] = content["visual_context"]
        return hint

    @staticmethod
    def _quest_payload(quest: Quest, status: str) -> dict:
        return {
            "id": quest.id, "version": quest.version, "status": status, "title": quest.title,
            "building_id": quest.building_id, "story": quest.raw.get("story"), "reward_preview": quest.raw.get("reward_preview"),
        }

    @staticmethod
    def _next_action(quest: Quest, status: str, challenge_id: str | None = None) -> dict:
        if status == QuestStatus.AVAILABLE.value:
            return {"type": "start_quest", "quest_id": quest.id}
        if status == QuestStatus.IN_PROGRESS.value:
            return {"type": "answer_challenge", "quest_id": quest.id, "challenge_id": challenge_id}
        if status == QuestStatus.READY_TO_BUILD.value:
            return {"type": "place_building", "quest_id": quest.id, "building_id": quest.building_id}
        return {"type": "none"}

    def _inventory_in(self, conn, child: str) -> dict:
        balances = self.repo.get_resource_balances_in(conn, child)
        return {
            "resources": {resource: balances.get(resource, 0) for resource in RESOURCES},
            "blueprints": self.repo.get_blueprints_in(conn, child),
        }

    def _daily_attempts_in(self, conn, child: str) -> dict:
        return self._daily_attempts(self.repo.get_daily_usage_in(conn, child, clock.today_str()))

    @staticmethod
    def _daily_attempts(used: int) -> dict:
        """Accepted attempts today (PRD 8.3); the day and its reset are Jakarta time from app/clock.py."""
        now = clock.now()
        limit = config.KIDQUEST_DAILY_ATTEMPT_LIMIT
        resets_at = datetime.combine(now.date() + timedelta(days=1), time(0), tzinfo=now.tzinfo)
        return {"day": now.date().isoformat(), "used": used, "limit": limit, "remaining": max(limit - used, 0),
                "resets_at": resets_at.isoformat()}

    # --- Building placement (PRD 8.2, 9.13, 12.3, 14.2) ------------------------------------------------

    def preview_placement(self, child: str, building_type: str, x: int, y: int, rotation: int) -> dict:
        """GET /api/kidquest/buildings/preview: the same rules as placement, read-only, no key needed."""

        def build(conn, child: str) -> dict:
            facts = self._placement_facts_in(conn, child, building_type)
            rules = placement_problems(self.catalog, building_type, x, y, rotation, facts)
            known = building_type in self.catalog.buildings
            return {
                "ok": True,
                "valid": not rules,
                "building_type": building_type, "x": x, "y": y, "rotation": rotation,
                "cells": [[cx, cy] for cx, cy in sorted(footprint(self.catalog, building_type, x, y).cells(),
                                                         key=lambda cell: (cell[1], cell[0]))] if known else [],
                "cost": dict(self.catalog.buildings[building_type].cost) if known else {},
                "problems": [{"rule": rule, "message": problem_message(self.catalog, building_type, rule, facts)} for rule in rules],
                "world_version": self.repo.get_world_in(conn, child)["version"],
            }

        return self._read_world(child, build)

    def place_building(self, child: str, request: PlacementRequest, idempotency_key: str) -> StoredResponse:
        """POST /api/kidquest/buildings: validate, spend, build, complete the quest, bump the version.

        Everything happens in one transaction or not at all. Refusals are not stored (like the other
        quest routes), so the database, the idempotency table included, is untouched by a failure.
        """

        def apply(conn, now):
            world = self.repo.get_world_in(conn, child)
            if request.world_version != world["version"]:
                raise KidQuestError(
                    "WORLD_VERSION_CONFLICT", "Duniamu baru saja berubah. Muat ulang, lalu coba lagi.", 409,
                    rule="world_version", rules=["world_version"], world_version=world["version"],
                )
            facts = self._placement_facts_in(conn, child, request.building_type)
            rules = placement_problems(self.catalog, request.building_type, request.x, request.y, request.rotation, facts)
            if rules:
                code = "INSUFFICIENT_RESOURCES" if rules[0] == "insufficient_resources" else "INVALID_PLACEMENT"
                raise KidQuestError(code, problem_message(self.catalog, request.building_type, rules[0], facts), 422,
                                    rule=rules[0], rules=rules)

            building = self.catalog.buildings[request.building_type]
            quest = self.catalog.quests[building.quest_id]
            building_id = self.repo.insert_building_in(conn, child, building.id, request.x, request.y, request.rotation, now)
            for resource, amount in building.cost.items():
                self.repo.debit_resource_in(conn, child, resource, amount, SPEND_SOURCE, f"building:{building_id}", now)
            completed = transition(QuestStatus(facts.quest_status), QuestStatus.COMPLETED)
            if not self.repo.set_quest_status_in(conn, child, quest.id, facts.quest_status, completed.value, now) \
                    or not self.repo.bump_world_version_in(conn, child, world["version"], now):
                raise RuntimeError(f"World of {child} changed inside the placement transaction")
            return 200, {
                "ok": True,
                "building": self._building_payload(self.repo.get_building_in(conn, child, building_id)),
                "spent": dict(building.cost),
                "world_version": world["version"] + 1,
                "quest": self._quest_payload(quest, completed.value),
                "inventory": self._inventory_in(conn, child),
                "next_action": self._next_action(quest, completed.value),
            }

        return self._idempotent(child, PLACE_OPERATION, idempotency_key, request.model_dump(), apply)

    def _placement_facts_in(self, conn, child: str, building_type: str) -> WorldFacts:
        buildings = self.repo.get_buildings_in(conn, child)
        occupied = {cell for row in buildings for cell in footprint(self.catalog, row["type"], row["x"], row["y"]).cells()}
        occupied |= {(path["x"], path["y"]) for path in self.repo.get_paths_in(conn, child)}
        building = self.catalog.buildings.get(building_type)
        quest_row = self.repo.get_quest_in(conn, child, building.quest_id) if building else None
        return WorldFacts(
            quest_status=quest_row["status"] if quest_row else None,
            blueprints=frozenset(self.repo.get_blueprints_in(conn, child)),
            balances=self.repo.get_resource_balances_in(conn, child),
            built_types=frozenset(row["type"] for row in buildings),
            occupied=frozenset(occupied),
        )
