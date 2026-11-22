---
id: KQ-010
title: Deliver the first-house frontend slice
status: IN_REVIEW
owner: senior-dev
depends_on: [KQ-005, KQ-006, KQ-007, KQ-008, KQ-009, KQ-029]
milestone: M5
updated: 2026-11-22
---

# KQ-010 — Deliver the first-house frontend slice

## Outcome

A child can complete the first playable KidQuest loop in the real application: enter world, finish Q001, build the starter house, and switch themes.

## Scope

1. Implement the responsive child shell and world canvas using the approved UX/component contracts.
2. Implement Q001 quest, challenge, feedback, reward, build preview, placement, and success states.
3. Integrate the three-theme switch with the golden asset set.
4. Preserve calm resume, loading/error/offline handling, reduced motion, keyboard use, text scaling, and touch targets.
5. Add frontend tests and end-to-end coverage for the complete first-house loop.

## Deliverables

- Production templates/styles/scripts/components for the first-house slice.
- Theme-aware world renderer and asset fallback behavior.
- Automated UI/end-to-end tests and responsive QA evidence.

## Acceptance criteria

- [x] A new child completes the first-house loop without manual database intervention. *(browser e2e, steps entry → build; `docs/evidence/kq-010/e2e-log.txt`)*
- [x] Refresh or interruption resumes at the correct safe point without duplicate rewards. *(e2e "resume after refresh" (wood stays 4) and "lost response" (same key replayed, attempt counted once))*
- [ ] Theme switching changes all available building/environment visuals but no game state. *(No game state change: verified (e2e "theme"). Visuals: the saved theme's art resolves from its own pack (verified with the KQ-006 terrain/props that have landed); building sprites are blocked on KQ-029, and a theme PREVIEW can show only neutral placeholders until `GET /themes` returns per-theme asset maps (API addition requested from the lead).)*
- [x] Required empty, loading, locked, retry, error, offline, and completion states exist. *(screens 01–19 in `docs/evidence/kq-010/`)*
- [ ] Phone, tablet, desktop, keyboard, reduced-motion, text-scaling, and contrast checks pass. *(Automated: 360/768/1280, grid arrow keys, focus ring, dialog focus trap/return, 44 px targets, reduced motion, 200% text without overflow at 360. Contrast values come from the KQ-005 token contract; a manual contrast and first-time-user walkthrough with the final art remain for re-verification after KQ-029.)*

## Verification

- Run unit, integration, and end-to-end suites.
- Capture the required viewport/theme matrix and complete a manual first-time-user walkthrough.

## Out of scope

- Wallet, cash-out, productive buildings, roads, and Q002–Q006.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-22 | lead | NOT_STARTED | **Approved start-before-dependencies exception:** KQ-010 may start with KQ-006 in progress and KQ-029 not done. KQ-029 needs the three AI-generated building sprite maps (KQ-026–KQ-028), which only the product owner can generate. PRD §11.4 allows the first playable to use approved graybox art with the same dimensions, anchors, manifests and layer rules, and PRD §11.3 defines the fallback order (selected-theme asset, approved neutral placeholder, visible development error). Conditions: (1) all building and terrain visuals resolve through `theme.assets` from the state API with the neutral placeholder fallback, never branching on theme or building; (2) KQ-010 may reach at most `IN_REVIEW` until KQ-006 and KQ-029 are `DONE`, the real sprites are in place, and the acceptance criterion about theme visuals and the viewport/theme matrix are re-verified with them; (3) KQ-006's golden terrain/road/overlay assets are consumed as they land, using only paths from the manifest. |
| 2026-11-22 | senior-dev | IN_PROGRESS | Claimed under the lead's start-before-dependencies exception (KQ-007–KQ-009 DONE; KQ-005 IN_REVIEW; KQ-006 and KQ-029 not done, so this task can reach at most IN_REVIEW). Scope extension from the lead for this task: may create `static/css/kidquest-tokens.css`, `static/css/kidquest.css`, `static/js/kidquest.js`, `app/web/templates/kidquest_world.html`, a KidQuest page route, a gated home entry, a UI copy content file, browser e2e tests, and `docs/evidence/kq-010/`; `design/` and `static/images/kidquest/` stay read-only. Lead review points: match the existing app (base/home/quiz tokens, header card, tab row, quiz challenge anatomy, quiz popups, `profile-theme-*`), gated entry with legacy pages byte-identical when off, plan §9 files, 8×8 grid with clamp tile and §11.4 layers, assets only from `state.theme.assets` with neutral fallback, D11 placement UX with server preview, idempotency keys kept across retries and no optimistic updates, every error code handled, no reward amount before a correct answer, copy from content, accessibility (keyboard, focus, 44 px, reduced motion, 200% text, aria-live), calm resume from `next_action`, screenshot evidence at 360/768/1280, no API or content-value changes without asking. |
| 2026-11-22 | senior-dev | IN_REVIEW | Implemented the first-house slice against the real API. New: `GET /kidquest` (`build_kidquest_page_router`, gated; when not allowed it returns the legacy unknown-page 303 → /home byte for byte), gated entry links on `/home` and `/quiz/*` (render nothing when off: HEAD-vs-working-tree render identical for home/quiz/stats), `app/web/templates/kidquest_world.html`, `static/css/kidquest-tokens.css` (aliases with sources), `static/css/kidquest.css` (KQ-005 classes; neutral placeholders; layers), `static/js/kidquest.js`, `content/kidquest/ui_strings.json` + validation in `content.py` (`_check_ui_strings`, `Catalog.ui_strings`). Tests: `tests/unit/kidquest/test_ui_strings.py` (13), `tests/integration/kidquest/test_pages.py` (22), byte-identity split into off-vs-closed (all 38 requests identical incl. `/kidquest`) and off-vs-on (only the entry link and the page differ), browser e2e `tests/browser/kidquest/` (70/70 checks, skips without Node 22/Chrome). Evidence: `docs/evidence/kq-010/` (57 screenshots at 360/768/1280, comparison.html, e2e-log.txt). Capped at IN_REVIEW: KQ-006/KQ-029 not DONE. |
| 2026-11-22 | lead | IN_REVIEW | **Lead review passed; stays `IN_REVIEW`** (blocked from `DONE` by KQ-006 and KQ-029, and by the two open acceptance criteria that need real sprites and a manual pass). Independently re-ran KQ-010 pages/unit/browser suites (36 passed) and the browser e2e log (70/70), and viewed evidence: the placement and quiz screens match the existing app (dark navy shell, accent colour, quiz-style cards/keypad/popups, Indonesian copy), with the world art left natural and neutral placeholders marked by a dev-only banner. **Decisions on the follow-ups:** (1) ACCEPTED: add per-theme `assets` maps to `GET /api/kidquest/themes` (additive; assigned to Codex as a small backend task after KQ-025, with a test that existing response fields are unchanged); (2) re-verification with KQ-029 sprites stays open; (3) `entrances` in the preview response: deferred, not needed for the first deliverable. |
| 2026-11-22 | codex-core | IN_REVIEW | Backend follow-up: added per-theme `assets` maps to `GET /api/kidquest/themes`; commit pending lead commit. |
| 2026-11-22 | lead | IN_REVIEW | **Verified the Codex backend follow-up** (per-theme `assets` in `GET /api/kidquest/themes`): one added line in `list_themes` (diff against the previous snapshot is exactly that line plus a doc-table line), response 1,287 → 17,014 bytes, theme API tests 32 passed, full suite 1014 passed / 3 skipped (run by the lead). Codex saw one browser-e2e timeout at its baseline run that did not recur; watch for e2e flakiness under load. Task status unchanged. |

## Completion handoff

- **Summary:** The child's KidQuest world page (`GET /kidquest`) with the full Q001 loop on the real API: world home with calm resume from `next_action`, quest, challenge (quiz anatomy, server hints, wrong popup with the owl), reward (amounts only after a correct answer), Bangun catalog, D11 placement with server preview and nudge buttons, checkpoint, and theme preview/confirm/restore. Gated entry links on home and quiz; legacy pages byte-identical when off or closed for the child. All copy from content; all world art from the theme manifest with neutral placeholders and a dev-only error.
- **Files changed:** `app/api/kidquest_routes.py` (page router, `kidquest_allowed`, `kidquest_entry`), `app/api/routes.py` (entry label in home/quiz context), `app/main.py` (one `include_router` line), `app/domain/kidquest/content.py` (ui_strings file + validation + `Catalog.ui_strings`), `app/web/templates/{home,quiz}.html` (gated entry link), new `app/web/templates/kidquest_world.html`, `static/css/kidquest-tokens.css`, `static/css/kidquest.css`, `static/js/kidquest.js`, `content/kidquest/ui_strings.json`, `content/kidquest/README.md`; tests `tests/unit/kidquest/test_ui_strings.py`, `tests/integration/kidquest/test_pages.py`, `tests/integration/kidquest/{conftest,test_feature_gating,test_state_api}.py`, `tests/unit/kidquest/test_content.py`, `tests/browser/kidquest/{first_house_e2e.mjs,test_first_house_browser.py}`; evidence `docs/evidence/kq-010/`.
- **Migrations/data impact:** None. No API or content-value changes.
- **Verification performed:** see the execution log row of 2026-11-22 (IN_REVIEW) and the report: KQ-010 suites (unit, `tests/integration/kidquest`, browser) green; browser e2e 70/70, stable over 5 consecutive runs; full-suite failures at the time are confined to concurrent KQ-011 (Migration 9 / `app/security`) and KQ-006 work.
- **Commit:** pending lead commit
- **Follow-ups:** (1) API addition for the lead to decide: per-theme `assets` maps in `GET /api/kidquest/themes` so a theme preview shows that theme's art (the page already reads it when present). (2) Re-verify theme visuals and the viewport/theme matrix with KQ-029 sprites (and the remaining KQ-006 assets), then a manual first-time-user walkthrough and contrast pass. (3) Optional: `entrances` in the preview response to draw the door marker before placement.

