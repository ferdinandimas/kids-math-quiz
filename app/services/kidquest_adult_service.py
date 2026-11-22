"""Adult authentication, Ringkasan, and per-child scoped reset operations."""

from __future__ import annotations

import hashlib
import json

from app import clock, config
from app.db.kidquest_repo import KidQuestRepo
from app.db.sqlite import transaction
from app.security.adult_session import (
    AdultSessionClaims,
    AdultSessionInvalid,
    issue_adult_token,
    nonce_hash,
    verify_adult_token,
)
from app.services.kidquest_service import KidQuestError, StoredResponse, request_hash, to_json
from app.services.parent_auth_service import verify_parent_pin


RESET_EVENT = "child_data_reset"
RESET_OPERATION = "adult.child.reset"
RESET_CONFIRMATIONS = {
    "legacy_history": "HAPUS-KUIS",
    "kidquest_progress": "HAPUS-DUNIA",
    "all_child_data": "HAPUS-SEMUA",
}


def adult_auth_required() -> KidQuestError:
    return KidQuestError("ADULT_AUTH_REQUIRED", "Masukkan PIN orang tua untuk melanjutkan.", 401)


class KidQuestAdultService:
    def __init__(self, repo: KidQuestRepo | None = None):
        self.repo = repo or KidQuestRepo()

    def login(self, pin: str) -> str:
        if not verify_parent_pin(pin, config.PARENT_PIN_HASH):
            raise adult_auth_required()
        return issue_adult_token(config.SESSION_SIGNING_KEY, config.KIDQUEST_ADULT_SESSION_MAX_AGE)

    def authenticate(self, token: str | None) -> AdultSessionClaims:
        try:
            claims = verify_adult_token(token or "", config.SESSION_SIGNING_KEY)
        except AdultSessionInvalid:
            raise adult_auth_required() from None
        with transaction(immediate=False) as conn:
            if self.repo.is_adult_session_revoked_in(conn, nonce_hash(claims.nonce)):
                raise adult_auth_required()
        return claims

    def logout(self, claims: AdultSessionClaims) -> None:
        with transaction() as conn:
            self.repo.revoke_adult_session_in(
                conn, nonce_hash(claims.nonce), claims.expires_at, clock.now_str()
            )

    def overview(self) -> dict:
        with transaction(immediate=False) as conn:
            children = self.repo.adult_overview_in(conn, config.CHILDREN)
        return {"ok": True, "children": children}

    def reset_child(self, child: str, scope: str, confirm: str, idempotency_key: str) -> StoredResponse:
        if child not in config.CHILDREN:
            raise KidQuestError("NOT_FOUND", "Akun anak tidak ditemukan.", 404)
        required = RESET_CONFIRMATIONS.get(scope)
        if required is None or confirm != required:
            raise KidQuestError(
                "INVALID_CONFIRMATION", "Teks konfirmasi tidak cocok untuk pilihan penghapusan ini.", 422,
                required_confirmation=required,
            )
        logical_body = {"child": child, "scope": scope, "confirm": confirm}
        fingerprint = request_hash(RESET_OPERATION, logical_body)
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        now = clock.now_str()
        with transaction() as conn:
            stored = self.repo.get_reset_audit_in(conn, child, RESET_EVENT, key_hash)
            if stored:
                if stored["request_hash"] != fingerprint:
                    raise KidQuestError(
                        "IDEMPOTENCY_CONFLICT", "Kode permintaan ini sudah dipakai untuk permintaan lain.", 409
                    )
                return StoredResponse(int(stored["response_status"]), stored["response_json"])

            deleted: dict[str, int] = {}
            if scope in {"legacy_history", "all_child_data"}:
                deleted.update(self.repo.reset_legacy_history_in(conn, child))
            if scope in {"kidquest_progress", "all_child_data"}:
                deleted.update(self.repo.reset_kidquest_progress_in(conn, child))
            payload = {"ok": True, "child": child, "scope": scope, "deleted": deleted}
            response = StoredResponse(200, to_json(payload))
            self.repo.insert_reset_audit_in(
                conn,
                child=child,
                event_type=RESET_EVENT,
                scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=fingerprint,
                response_status=response.status_code,
                response_json=response.body,
                details_json=json.dumps({"deleted": deleted}, sort_keys=True, separators=(",", ":")),
                created_at=now,
            )
            return response
