---
id: KQ-005
title: Produce UX foundation and prototype
status: IN_REVIEW
owner: ui-ux-designer
depends_on: [KQ-004]
milestone: M3A
updated: 2026-11-22
---

# KQ-005 — Produce UX foundation and prototype

## Outcome

The child and parent journeys are specified and testable before production UI implementation begins.

## Source references

- [PRD — child journey, parent journey, Q001, accessibility](../KidQuest_Build_Your_World_PRD_v1.4.md)
- [Visual design pipeline — UX gates and component states](../KidQuest_Visual_Design_Asset_Pipeline.md)

## Scope

1. Map child and parent information architecture and all first-house task flows.
2. Create responsive low-fidelity wireframes for world, quest, challenge, reward, build, theme switch, calm resume, and adult gate.
3. Specify empty, loading, success, retry, locked, error, offline, and reduced-motion states.
4. Define reusable component contracts and accessible interaction behavior.
5. Test the prototype with representative users or structured proxy review and record decisions.

## Deliverables

- Flow map and responsive wireframes/prototype.
- Component/state specification.
- Usability findings and design decision log.

## Acceptance criteria

- [ ] A child can complete Q001 and place the starter house without reading dense instructions. **Proxy evidence only; household testing pending (F10).** The path is traceable in 8 taps with instructions of 5–10 words per step, on the canonical `pulau_tunas_v1` layout. The automated walkthrough completes it at 360/768/1280. See `design/kidquest/usability/decision-log.md` §1 (T3).
- [x] Theme switching visibly changes building design but not game state or hit areas. Walkthrough checks: the roof silhouette changes during preview; the four house cells' grid-relative rectangles are identical; a confirm leaves buildings, coordinates, wood, blueprints, quest, and attempts unchanged and adds exactly 1 to the world version; cancel and save failure restore the authoritative theme. See `flows/theme-switch-flow.md`.
- [x] Parent-only actions are clearly separated behind the adult gate.
  - A separate `parent.html` shell, styled like the app's Statistics page, with a gold "Mode Orang Tua aktif" flag and no child nav.
  - The only child entry is one Menu item under "Untuk orang tua".
  - Checks: a wrong PIN stays locked (no lockout, C8); with the economy off, only Ringkasan, Belajar and Pengaturan appear after the PIN (C7: Ekonomi and Pencairan are hidden); with it on, all five appear; scoped reset needs a scope-specific word.
  - See `flows/adult-gate-flow.md`.
- [x] Keyboard, touch-target, contrast, text scaling, reduced-motion, and audio-independent feedback are specified, re-measured on the dark app shell (pipeline §8.2a). See `design/kidquest/components/README.md` §1–3. Measured:
  - all non-grid controls ≥44×44 (child, both popups, adult);
  - text contrast minimum 4.93:1 in child views and popups, 9.42:1 entry, 12.58:1 adult gate, 6.16:1 adult shell;
  - focus ring 8.5–13.1:1;
  - no overflow at 200% text at 360 px;
  - reduced motion removes the pulse;
  - every state has icon + text.
  - Grid cells are 38 px at 360 px, approved as an exception (C1 FINAL, product owner) with ≥44 px nudge controls, arrow keys and a ≥44 px confirm.
- [x] Open usability findings have explicit owners or documented acceptance. See decision log §3 (C1–C9 decided by lead or product owner; new C10–C13 open with owners), §5 (findings F1–F14 with owner and status), and §6 (copy suggestions).

## Verification

- Run the documented prototype walkthrough for child and parent journeys on phone and tablet/desktop widths.
- Record participant/proxy results against the PRD usability thresholds.

## Out of scope

- Production frontend implementation and final asset rendering.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | lead | NOT_STARTED | **Approved dependency exception:** KQ-005 may start before KQ-004 is `DONE`. Plan §3 makes M3A depend only on the M3 *logical catalog*, which is already fixed in PRD §8.1, §9.9, §11.3, §11.7 and pipeline §5, §12. Condition: if KQ-004's content files differ from those sections, KQ-005 must be reconciled before it is marked `DONE`. Real household usability testing cannot run inside an agent session, so KQ-005 ends at `IN_REVIEW` with a structured proxy review until household testing is recorded. |
| 2026-11-21 | ui-ux-designer | IN_PROGRESS | Claimed under the lead-approved dependency exception above. Deliverables go to `design/kidquest/` per pipeline §14.1. Reading PRD §4.4, §7, §8 Q001, §10, §11.1–11.3, §11.10–11.14, AC-22/23/25 and pipeline §2–§9, §14.1, §15, §18 before creating files. |
| 2026-11-21 | ui-ux-designer | IN_PROGRESS | Decisions: `content/kidquest/` does not exist yet (KQ-004 not done), so the prototype uses an **illustrative** `pulau_tunas_v1`-like layout (tutorial zone x1–4, y2–5; tapped cell = top-left origin). It must be reconciled with KQ-004 before `DONE` (conflict C3). Requirement conflicts C1–C9 recorded in `design/kidquest/usability/decision-log.md` §3 rather than resolved silently. Most material: C1 (38 px grid cells vs the 44 px target rule) and C2 (the Q001 reward amount equals the answer). |
| 2026-11-21 | ui-ux-designer | IN_PROGRESS | Built the prototype (`design/kidquest/prototypes/first-house/`) and `walkthrough-check.mjs` (headless Chrome via DevTools Protocol, no npm deps). The first visual review of captures found the placement confirm, theme cards, and "Gunakan Tema" below the fold at 360 px (F1). Fixed with a fixed phone action bar (D1). Also fixed the desktop world-frame stretch and the HUD name truncation caused by the graybox tag, and disabled the keypad under the daily cap. |
| 2026-11-21 | ui-ux-designer | IN_REVIEW | Verification: `node design/kidquest/prototypes/first-house/walkthrough-check.mjs` → **174/174 checks passed** (58 checks each at 360×780, 768×1024, 1280×820). It covers: entry with Quiz/KidQuest; 3-item nav without Dompet; one primary action; tile clamp; locked reason; no answer leak; wrong → neutral hint → worked decomposition; correct → 4 wood + blueprint once; catalog; invalid (rock / outside zone) and valid placement; cancel commits nothing; keyboard arrows/Enter/Esc; visible focus; build focus return; checkpoint with theme intro; theme preview local, silhouette change, identical hit areas, cancel, confirm invariance, failure restore; calm resume with one Resume and no streak language; lost response → recheck with no double reward; daily cap; stale world; offline banner; reduced motion; 200% text without overflow; all non-grid controls ≥44 px; text contrast ≥4.5 (min 4.71); adult gate separation, PIN error, 5 sections, scoped-reset word. Visual review of 48 captures; 23 saved to `design/kidquest/wireframes/renders/`. **Proxy only:** the household 4-of-5 threshold (AC-23) is UNVERIFIED and household testing is pending (F10), so the status stays `IN_REVIEW` per the exception. |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | Took over from the previous design agent to finish the lead's review fixes 1–6 and the product-owner consistency requirement (pipeline §8.2a). Verified each earlier fix rather than assuming it was done. `child.js` layout constants already matched `pulau_tunas_v1`; `parent.js` already hid the economy sections; the walkthrough still used the old coordinates, so its baseline was 69/75 with placement failures. |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | **Fix 1 (challenge at 360 after a wrong answer):** the challenge has no fixed bar. A wrong answer opens a quiz-style popup (owl tutor, hint, Coba Lagi). Closing it returns focus to the answer box and scrolls the card's top to the viewport top. The hint stays in the 💡 line under the answer box. At 360×780 the question, hint, answer box, whole keypad and Kirim are on screen together. The walkthrough asserts this after the first and second mistakes with an `elementFromPoint` occlusion test (it catches any fixed or sticky cover) plus a negative control. **Fix 3 (C7):** confirmed `parent.js` hides Ekonomi/Pencairan while the economy is off; both states are checked. |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | **Fix 4 (C3):** prototype geometry checked against `content/kidquest/layouts/pulau_tunas_v1.json` and the README convention: trees (0,0) (7,0) (7,7), rock (0,7), board (4,3), water, tutorial_zone x1–4 y1–2, bridge_zone, and a locked, fogged expansion_zone. Q001 story, prompt, hints, `reward_preview` and `reward_message` are verbatim from `quests.json`; theme labels are synced to the Indonesian labels now in `themes.json` (`Rumah Warna-Warni`). New **D11 (proposal):** a tap on any striped cell fits the 2×2 house inside the zone, because a strict top-left mapping makes 5 of 8 striped cells invalid; requests still send the top-left origin. Walkthrough placement cases: tree (0,0), rock, outside the zone (6,1), fit (4,2)→(3,1), keyboard (2,2)→(2,1), build at (2,1). Copy suggestions are in decision log §6; nothing was changed silently. |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | **Product-owner consistency requirement (pipeline §8.2a, D12):** re-skinned the child and adult shells to the existing Kids Math Quiz. Foundation tokens are the app's own (`base.css :root` verbatim, plus `--kq-*` aliases of home/quiz/stats values). Child shell components:<br>• `.quiz-header`-style header card with the app's avatars, "Pulau: Pulau Tunas" instead of a level (C9/C10), Menu as the header link, and a `.today-card`-style "Bahanmu" card;<br>• `.quiz-workspace` with a `.quiz-tabs` tab row (Dunia/Misi/Bangun, no Dompet);<br>• quiz question anatomy (progress, owl bubble, prompt, answer box, 💡 line, 3-column keypad with Hapus and Kirim in the last row, C12);<br>• quiz popups for wrong answer (owl instead of the red ✕, C11) and reward (wood and blueprint pills, no Rp coin, C13);<br>• `.knowledge-option` theme cards; per-child blue/purple accent; breakpoints 960/620/440.<br>Adult gate and shell mirror `stats.html`. The world canvas keeps the natural Kampung/Kerajaan/Kota art; themes never repaint the shell. Where the app itself is below AA, KidQuest darkens the fill (D13). Contrast was re-measured; `components/README.md` has the dark contrast table and a "Consistency with the existing app" mapping (§5). |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | **Fix 2 (walkthrough reliability):** the runner waits on selectors or state (no fixed sleeps), holds a single-instance lock, fails loudly with the step name, and always prints `N/M checks passed`. One remaining nondeterminism was found and fixed: a lone synthetic Shift key press (used for `:focus-visible`) stalled headless Chrome frame production, so every later `--shots` capture hung (it reproduced 3 of 3 times with `--shots`). It now uses Tab. New checks: occlusion-based visibility, wrong-popup look and focus, canonical placement and fit, entry/popup/adult contrast, and focus-ring contrast. There are now 72 checks per width. |
| 2026-11-22 | ui-ux-designer | IN_REVIEW | **Fix 6 (renders):** removed all 23 stale renders. Added 34 new captures (all 18 phone screens; tablet 02, 04, 04a, 05, 08, 10, 16; desktop 02, 04, 07, 08, 09, 10, 12, 15, 16) and 4 side-by-side sheets against the real app at 360×780 (`compare-360-home-vs-entry`, `-quiz-vs-world` for both children, `-quiz-vs-challenge`, `-popups`), made with the new `design/kidquest/wireframes/compare-with-app.mjs` against `uvicorn` on a temporary `DB_PATH` (stopped afterwards). Reviewed visually in detail: about 20 captures (every phone screen type touched by the fixes, plus the tablet and desktop challenge, placement, world home and adult shell) and all 4 sheets. **Fix 5:** decisions C1–C9 recorded in the decision log with date and lead or product-owner attribution, plus D11–D13 and F13–F14. **Verification (two consecutive clean runs, after the final code change):** `node design/kidquest/prototypes/first-house/walkthrough-check.mjs` → run 1 **216/216 checks passed** (exit 0); run 2, immediately after, **216/216 checks passed** (exit 0); 72 checks at each of 360×780, 768×1024 and 1280×820, 0 FAIL lines. The renders came from an identical earlier `--shots` run (216/216); the only later code change was a help-panel string that is not in any capture. Stays `IN_REVIEW`: household testing pending (F10). |
| 2026-11-22 | lead | IN_REVIEW | Lead review of fixes and the product-owner re-skin (pipeline §8.2a): independent walkthrough run = 216/216 (matches the two recorded runs); reviewed side-by-side sheets and phone captures — shell colors, header card, tab row, quiz-style challenge, popups and per-child accent match the existing app; hint, answer box, keypad and Kirim are all visible together at 360 px; adult Ekonomi/Pencairan hidden while economy is off. Lead decisions: **D11 accepted** (tapping any striped cell selects the covering 2×2 position that fits the tutorial zone; the request still sends the top-left cell, valid positions remain (1,1), (2,1), (3,1); KQ-010 must implement the same behavior); **C10** accepted ("Pulau: Pulau Tunas" instead of level/XP); **C11** accepted (PRD §10.2 neutral feedback wins over the quiz's "Yah kamu salah" wording; quiz popup frame reused); **C12** accepted (explicit Kirim, answers can have two digits); **C13** accepted (wood/blueprint icons, no Rp coin on wood). Copy suggestions (`reward_preview` "dan" instead of "+", one casing for "cetak biru Rumah", clearer hint 1) are forwarded to the product owner; content stays `pending_product_review`. D13 (existing app buttons below AA contrast) is noted as an app-owner follow-up. KQ-005 stays `IN_REVIEW` until real household testing (F10) is recorded. |

## Completion handoff

- **Summary:** Stage B–E UX foundation for the first-house release.
  - Child and parent IA; first-house, theme-switch, calm-resume and adult-gate flows.
  - Responsive low-fidelity wireframes with rendered captures and side-by-side comparisons against the real Kids Math Quiz.
  - A clickable, self-contained graybox prototype covering every first-house screen and system state, on the canonical `pulau_tunas_v1` layout. It is skinned with the existing app's dark navy tokens, header card, tab row, quiz question anatomy and popups (pipeline §8.2a); only the world canvas uses natural art.
  - A component/state/accessibility contract with re-measured dark-shell contrast and an existing-app mapping.
  - A clearly labelled **proxy** usability decision log with lead and product-owner decisions recorded.
  - Not production UI or art.
- **Files changed/artifacts:** `design/kidquest/README.md`; `design/kidquest/flows/{README,information-architecture,first-house-flow,theme-switch-flow,calm-resume-flow,adult-gate-flow}.md`; `design/kidquest/wireframes/README.md`, `wireframes/compare-with-app.mjs`, `wireframes/renders/*.png` (34 captures + 4 comparison sheets, 9.5 MB); `design/kidquest/prototypes/README.md`; `design/kidquest/prototypes/first-house/{index.html,child.js,parent.html,parent.js,prototype.css,walkthrough-check.mjs}`; `design/kidquest/components/README.md`; `design/kidquest/usability/decision-log.md`; this packet and the KQ-005 tracker row. `static/`, `app/`, `content/` and `tests/` are untouched; the prototype reads `static/images/` through relative paths.
- **Migrations/data impact:** None.
- **Verification performed:**
  - `node design/kidquest/prototypes/first-house/walkthrough-check.mjs`: two consecutive clean runs after the final code change, **216/216** and **216/216** (72 checks × 360/768/1280).
  - `node design/kidquest/wireframes/compare-with-app.mjs http://127.0.0.1:8765 design/kidquest/wireframes/renders`, against the real app on a temporary `DB_PATH`.
  - Visual review of the captures and comparison sheets; manual token contrast calculation.
  - Proxy walkthrough of the AC-23 tasks T1–T5. No household testing yet.
- **Commit/artifact revision:** Uncommitted; the lead commits after review.
- **Follow-ups:**
  1. Household sessions per decision log §7, which are required for `DONE`.
  2. Lead or product decisions on C10 (level line), C11 (wrong-answer look vs PRD §10.2), C12 (explicit Kirim), C13 (no Rp coin for wood) and D11 (fit-to-zone tap).
  3. Product content review of the copy suggestions in decision log §6 and of F9.
  4. Carry F6 and F8 into KQ-010 and F7 into KQ-006.
  5. Optional, for app owners: the AA gaps in the existing quiz/home buttons (D13).
