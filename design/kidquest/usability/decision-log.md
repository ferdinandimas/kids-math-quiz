# KidQuest first-house usability findings and design decision log

> **PROXY REVIEW. NOT USER TESTING.**
> Everything below comes from a structured heuristic walkthrough by the UI/UX designer agent and an automated headless-browser check. No child or parent took part. These results **do not** satisfy the household usability gate in PRD AC-23 / pipeline §9.5 ("at least 4 of 5 representative child tasks without adult correction"). **Household testing is pending** and is required before KQ-005 can move from `IN_REVIEW` to `DONE` (lead-approved exception, 2026-11-21).

- **Prototype:** `design/kidquest/prototypes/first-house/`, revision in this working tree, 2026-11-22: dark app shell (pipeline §8.2a) and canonical `pulau_tunas_v1`.
- **Method:**
  1. A scripted cognitive walkthrough per task, using the persona below.
  2. `walkthrough-check.mjs`: 72 automated checks at each of 360×780, 768×1024 and 1280×820. Two consecutive clean runs gave **216/216** each (see the KQ-005 packet log).
  3. 54 captures per run. About 20 were reviewed visually in detail and 34 are kept in `wireframes/renders/`, plus 4 side-by-side sheets comparing KidQuest with the real app (`/home`, `/quiz/math`, quiz popups).
- **Proxy persona:** a 6-year-old early reader (the hardest case in the 6–9 range), on a phone at 360 px, reading short Indonesian sentences slowly, with no audio support.
- **Privacy:** no child data is stored. Household sessions should record only de-identified task outcomes (pipeline §9.5).

## 1. Proxy walkthrough against AC-23 tasks

"Taps" counts the minimum activations from the starting point. "Reading load" is the number of words the child must read to choose the right control.

| # | AC-23 task | Path in prototype | Taps | Reading load | Proxy outcome | Main risk for a real child |
|---|---|---|---|---|---|---|
| T1 | Find the current objective | World Home → objective card "Misi sekarang · Rumah Pertama" → [Mulai Misi] | 1 | ~10 words; the only filled (teal) button on screen | Traceable without help | A non-reader may not know which card is "the mission". Mitigated by the single primary button, the accent border and the board badge "! Misi" |
| T2 | Explain a locked reason | Misi tab → "Kebun Tunas" card: "Terkunci · Kenapa? Selesaikan misi Rumah Pertama dulu." | 1 | 7 words | Traceable; the reason is visible text, not a tooltip | Explaining it aloud depends on reading; needs household observation |
| T3 | Complete Q001 placement | Quest → Mulai Tantangan → 4 → Kirim → reward popup [Bangun Rumah] → Pilih Tempat → any striped cell → Bangun di Sini | 8 with a correct first answer (one more per wrong answer: Coba Lagi) | Prompt 10 words; placement instruction 5 words | Traceable. Validity is shown by outline, icon and text. Every striped cell now works (D11). Confirm is always visible on phone (D1). Question, hint, answer box and Kirim fit one phone screen after a mistake (F3 fixed) | The owl popup adds one tap per mistake; it needs household observation (F13) |
| T4 | Cancel a theme preview | Checkpoint → Coba Tema Dunia → tap another card → [Batal] | 3 | Banner "Pratinjau … Belum dipakai" | Traceable; cancel restores, asserted automatically | The child may not notice the preview banner; "Batal" sits beside a large teal button |
| T5 | Recover from an invalid/stale action | Tap the tree at the top-left → "Tidak bisa di sini: ada pohon. Coba kotak bergaris yang kosong." → tap a striped cell → Bangun di Sini. Stale: info alert → press again | 2 | ~10 words | Traceable; nothing is lost and the reason is concrete | The stale message is long for a 6-year-old (F11) |

**Proxy result:** all five tasks can be traced through visible, labelled controls, with no hidden gesture and no adult-only step. This is a designer's heuristic judgement, not a measured completion rate, so it cannot be compared with the "4 of 5 without adult correction" threshold. The threshold stays **UNVERIFIED** until household sessions are recorded.

### Comprehension prompts (pipeline §9.5) still to ask in household sessions

| Prompt | Where to ask | Proxy expectation |
|---|---|---|
| "Apa yang terjadi kalau kamu tekan tombol ini?" | Bangun di Sini, Gunakan Tema, Kirim | Labels state the effect; the build button shows the cost "· 4 kayu" |
| "Kalau ganti tema, rumahmu pindah atau hilang?" | Theme preview | Copy says "Rumah, kayu, dan misimu tidak berubah"; every card says "Gratis" |
| "Ini mirip Kuis yang biasa kamu main?" | World Home, challenge | The same header, tabs, owl and keypad as the quiz (D12); confirm that children recognise it as the same app |
| Economy, payout and paused-building prompts | n/a | Out of first-house scope (KQ-016+) |

## 2. AC coverage (design specification level)

| AC | What KQ-005 specifies | Evidence | Gap |
|---|---|---|---|
| AC-22 Progressive onboarding and resume | Q001 teaches only quest, answer, blueprint/starter kit and placement. Theme is promoted only after the checkpoint. No Dompet, Rp, XP or supply anywhere, and the "Bahanmu" header card appears only once the child owns something. The resume summary has one Resume action; completed tips are not replayed; no streak or absence language | `flows/first-house-flow.md` §2, `flows/calm-resume-flow.md`; walkthrough checks "Child nav … (no Dompet)" and three "Calm resume …" checks | Wallet, supply and cash-out onboarding are later tasks |
| AC-23 Child task and state comprehension | The 5 tasks above; at most one badge per object (quest board only); the inspector holds detail | §1 above; render `phone-360-02-world-home.png` | **Household 4-of-5 result pending** |
| AC-25 Responsive and accessibility parity | Phone, tablet and desktop layouts with the same action order; loading/empty/error/stale/offline/success states; keyboard, focus return, modal focus traps, screen-reader labels, 200% text, reduced motion; dark-shell contrast re-measured | `components/README.md` §1.1–3, `wireframes/README.md`; 216 automated checks per run | A real screen-reader pass (VoiceOver/TalkBack) and browser 200% *page* zoom on devices are not yet run (F12) |

## 3. Requirement conflicts and their resolution

| ID | Conflict | Sources | Resolution (dated, by whom) | Prototype state |
|---|---|---|---|---|
| C1 | At 360 px the PRD tile size `clamp(38px, 10vw, 64px)` gives 38 px cells, below the PRD's own 44×44 target rule | PRD §11.2 vs §11.4 | **FINAL, product owner, 2026-11-22:** 38 px grid cells are approved as an exception (PRD §11.4). Conditions: nudge controls ≥44 px, arrow keys, and an explicit confirm ≥44 px. Every other target stays ≥44 px | Nudge buttons 48 px; arrows + Enter + Esc on the grid; "Bangun di Sini" ≥48 px; all other controls measured ≥44 px in child mode, both popups and adult mode |
| C2 | Q001's reward (4 wood) equals the answer (10 − 6 = 4), so "Hadiah: 4 kayu" on quest detail would give the answer away | PRD §8.1, §11.1 | **Accepted, lead, 2026-11-22:** the preview says "kayu yang kurang". KQ-004 content now carries it as `reward_preview` | Quest detail shows `reward_preview` "Hadiah: kayu yang kurang + Cetak biru Rumah"; "4 kayu" appears only after a correct answer (checked) |
| C3 | The `pulau_tunas_v1` geometry and the placement origin convention were undefined in the PRD | PRD §8.2, §11.5, §12.3 | **Reconciled to KQ-004, lead, 2026-11-22.** Source: `content/kidquest/layouts/pulau_tunas_v1.json` and `content/kidquest/README.md` | (0,0) is the north-west corner, x grows east, y grows south; a position is the footprint's top-left cell. Trees (0,0) (7,0) (7,7); rock (0,7); quest board (4,3); water rows 4–5 x3–7 plus (3,6) (3,7); `tutorial_zone` x1–4, y1–2 (valid origins (1,1) (2,1) (3,1)); `bridge_zone` (5,4)–(5,5); `expansion_zone` x4–7, y6–7, locked. Q001 strings are verbatim from `quests.json`; theme labels come from `themes.json` |
| C4 | The return-summary title differs: "Sejak terakhir bermain" vs "Sejak Kunjungan Terakhir" | PRD §7.1 vs §11.11, pipeline §5.4 | **Decided, lead, 2026-11-22:** "Sejak Kunjungan Terakhir" | As decided |
| C5 | "All themes available from first world load … select from World Settings" vs "theme preview is introduced only after the first house" | PRD §11.3 vs §8.4, §11.11 | **Accepted, lead, 2026-11-22:** Tema Dunia is in the Menu from the start and promoted only after the house | As decided |
| C6 | After Q001 with the economy off: "explain the next building is not yet enabled" vs "features absent, not shown as indefinitely locked promises" | PRD §8.4 vs pipeline §5.5 | **Accepted, lead, 2026-11-22:** "Belum dibuka" plus an explanation that a parent enables it, with no lock | Q002 card: clock icon, dotted badge "Belum dibuka", "Orang tuamu yang bisa membukanya nanti." |
| C7 | The adult shell lists five sections, but in the first-house release Ekonomi and Pencairan have nothing to operate; pipeline §5.5 says no "links to unavailable routes" | PRD §11.10 vs pipeline §5.5 | **Decided, lead, 2026-11-22:** hide the sections entirely while the economy is disabled; no empty states (PRD §9.12) | Economy off: Ringkasan / Belajar / Pengaturan only (checked). Economy on (reviewer toggle): all five |
| C8 | Wrong-PIN throttling or lockout is unspecified | PRD §4.4, KQ-011 | **FINAL, product owner, 2026-11-22:** no wrong-PIN lockout for the pilot | Neutral retry message only; checked that no lockout or wait text appears |
| C9 | The pipeline §6.2 World Home wireframe shows "Level / XP" in the HUD, but XP is not introduced in Q001 | pipeline §6.2 vs PRD §8.4, §11.11 | **Accepted, lead, 2026-11-22:** no XP in the header | The header context line is "Pulau: Pulau Tunas" (see C10) |
| C10 | The quiz header shows "Tingkat: <level>", and the 2026-11-22 consistency brief asks for "name and level" in the header card. This conflicts with C9 | pipeline §8.2a / quiz.html vs C9 | **Open, lead.** Prototype choice: keep C9 and use the same line for "Pulau: Pulau Tunas". The quiz "Tingkat" is a quiz level, not KidQuest progress, and showing it here would suggest it changes in KidQuest | As described |
| C11 | §8.2a says pink/red for "wrong" as in the quiz popups (red ✕, "Yah kamu salah", the correct answer revealed). PRD §10.2 requires neutral, non-punitive hints and must not reveal the answer | pipeline §8.2a vs PRD §10.2, D4 | **Open, product owner.** Prototype choice: the quiz popup frame with the pink `#ff89ae` line and the wrong-popup background, but the owl tutor instead of the red ✕, "Belum tepat. Coba lagi, ya!" and the hint instead of the answer. No `#ff555d` red | As described |
| C12 | The quiz keypad auto-submits after a pause; Q001 answers can have two digits, and PRD §10 needs a deliberate submit | quiz.js vs PRD §10.1 | **Open, lead.** Prototype choice: the quiz keypad grid, with the empty last-row cells holding Hapus and Kirim | As described |
| C13 | §8.2a lists `popup-reward-coin` for rewards, but it is an Rp coin, and pipeline §8.4 forbids currency symbols on wood | pipeline §8.2a vs §8.4 | **Open, lead (confirm).** Prototype choice: the quiz reward pill with wood and blueprint icons on tan and blue discs; the coin is not used | As described |

## 4. Design decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | Phone and tablet (≤959): task views hide the world. World-centric views (placement, theme) keep the world visible and pin the decision controls in a fixed action bar at the bottom. Nothing else is fixed (the tab row scrolls like the quiz). ≥960: the placement controls sit at the top of the right panel | The first visual pass showed confirm and Gunakan Tema below the fold at 360 px. At 1280×820 the confirm was below the fold until it moved to the top of the panel (2026-11-22) |
| D2 | Reward → Bangun (catalog) once, then Pilih Tempat. Objective and Resume "Bangun Rumah" go straight to placement | Teaches where Bangun lives (PRD §11.11 "Build entry") without slowing later visits |
| D3 | The placement confirm is inline (status + "Bangun di Sini · 4 kayu" + Batal), not a second modal | One fewer step for young children; still shows the exact cost, footprint, Confirm and Cancel (PRD §11.12) |
| D4 (revised 2026-11-22) | Wrong answer: the quiz popup frame with the owl tutor and neutral copy (C11). After Coba Lagi the hint stays in the 💡 help line with a gold outline. A second mistake numbers the empty slots 7–10 without stating "4" | PRD §10.2, pipeline §9.4, §8.2a |
| D5 | Hit areas are the logical cells; building art is `pointer-events:none` and may overhang only upward | PRD §11.4; keeps targets identical across themes (measured) |
| D6 | Theme silhouettes are driven by tokens on any `[data-theme]` element | Lets picker thumbnails render other themes inside the current theme |
| D7 | Adult mode is a separate page with its own header, flag and navigation, styled like the app's Statistics page. Its session lives in page memory, so a reload asks for the PIN again | PRD §11.10, pipeline §4.3, §8.2a |
| D8 | The grid is one tab stop (roving tabindex); arrows move a dotted footprint preview, Enter selects, Esc cancels | Pipeline §7.3 |
| D9 | At ≥960 the objective card is compact (no button) beside non-home task views, and absent in placement, theme and reward | Keeps one primary action per view (pipeline §4.2) and the placement confirm above the fold |
| D10 | The resume summary replaces the objective card while shown | Exactly one Resume action (PRD §7.1) |
| D11 (proposal, 2026-11-22, needs lead approval) | In placement, a tap on **any** striped cell selects the 2×2 footprint that covers that cell and fits the tutorial zone, for example (4,2) → origin (3,1). Outside the zone, the tapped cell is the top-left origin. The request always sends the top-left origin (content convention) | With the canonical 4×2 zone, a strict top-left mapping makes 5 of the 8 striped cells invalid (the whole lower row and the x=4 column). That would undermine T3 for a 6-year-old and replace F5's abstract "pojok kiri atas" sentence. Server validation is unchanged |
| D12 (product owner, 2026-11-22) | **Consistency with the existing Kids Math Quiz** (pipeline §8.2a): dark navy shell; `.quiz-header`-style header card with the app's avatars; `.quiz-workspace` with a `.quiz-tabs` tab row for Dunia/Misi/Bangun; quiz question card anatomy (progress strip, owl tutor bubble, prompt, answer box, 💡 line, keypad); quiz popups; per-child blue/purple accent; 24/20/14/8 px radii; `system-ui` with 750–850 headings; quiz.css breakpoints 960/620/440. The world canvas alone keeps natural art, and themes never repaint the shell. Foundation tokens are the app's tokens | Product-owner requirement. The mapping is in `components/README.md` §5; renders `compare-360-*.png` |
| D13 | Where the existing app falls short of WCAG AA (continue-button text 3.3:1; white on the light teal action 2.0:1), KidQuest keeps the shape and darkens the fill (`--kq-accent-solid`, primary `#177a82→#10626a`, 5.1:1) | AA is a PRD requirement (§11.4); the visual difference is small (see the comparison sheets) |

## 5. Findings and owners

| ID | Finding | Severity | Status | Owner |
|---|---|---|---|---|
| F1 | At 360 px, "Bangun di Sini", the theme cards and "Gunakan Tema" were below the fold | High | **Fixed** (D1), re-verified after the re-skin; the walkthrough asserts they are fully visible and not covered | ui-ux-designer |
| F2 | The child's name truncated in the old HUD at 360 px | Low | **Resolved** by the quiz-style header card (name on its own line, wraps) | ui-ux-designer |
| F3 | At 360×780 after a wrong answer, the hint was clipped behind the fixed bar and the answer field was off screen, so the child saw a disabled Kirim with nowhere visible to type (lead review) | High | **Fixed 2026-11-22.** No fixed bar in the challenge. The hint lives in the 💡 line under the answer box. Closing the wrong-answer popup returns focus to the answer box and scrolls the card's top to the viewport top. Question, hint, answer box and Kirim are then fully visible at 360×780, 768×1024 and 1280×820, and at 360 the whole keypad fits too. Checked with an `elementFromPoint` occlusion test after the first and the second mistake, plus a negative control | ui-ux-designer |
| F4 | Text-only instructions are a barrier for non-readers (6-year-olds); audio is post-slice | Medium | Open: depends on the audio decision in PRD §22 | Product / lead |
| F5 | "Kotak yang kamu pilih menjadi pojok kiri atas rumah" was abstract | Medium | **Mitigated** by D11; the copy is now "Rumah menutupi kotak yang kamu ketuk." Validate in household test T3 | ui-ux-designer |
| F6 | The desktop resume card is cramped in a narrow column | Low | Improved (the right panel is now ≥300 px); re-check in KQ-010 | ui-ux-designer |
| F7 | The graybox Kerajaan dome reads heavier than the Kampung and Kota roofs (silhouette mass) | Low | Open: input to the KQ-006 graybox study and the KQ-025 contract | ui-ux-designer (KQ-006) |
| F8 | After building, focus lands on one of the house's four cells; the focus ring outlines one cell, not the footprint | Low | Open: specify a footprint-level focus outline for KQ-010 | ui-ux-designer → KQ-010 |
| F9 | Theme house and quest-board names are drafts: Rumah Kampung, Pondok Penjaga, Rumah Warna-Warni, Papan Pengumuman, Papan Berita Kerajaan, Kios Info Kota (now Indonesian in every theme in `themes.json`) | Medium | Open: household parent/child content review (pipeline §9.1) | Product + household |
| F10 | All comprehension and task-completion evidence is proxy only | High | Open: **household sessions required** | Lead (schedule) + ui-ux-designer (moderate) |
| F11 | The stale-world message is long (≈25 words) | Low | Open: shorten after household test | ui-ux-designer |
| F12 | No real screen reader (VoiceOver/TalkBack) or device page-zoom pass has been run; only DOM label and text-scaling checks | Medium | Open: run on household devices during testing; formal pass in KQ-011 | ui-ux-designer / KQ-011 |
| F13 | The wrong-answer popup adds a tap per mistake and briefly covers the question | Low | Open: observe in household T3. The fallback is an inline owl bubble only, without the popup | ui-ux-designer |
| F14 | Walkthrough reliability (lead review: "100/103" with a thrown error). The runner now waits on selectors and state, holds a lock, and always prints a count. One remaining nondeterminism was found and fixed: a lone synthetic Shift key press (used to trigger `:focus-visible`) stalled headless Chrome frame production, so every later screenshot hung. Tab is used instead | High | **Fixed 2026-11-22**; two consecutive clean runs, 216/216 each | ui-ux-designer |

## 6. Copy suggestions for product review (`copy_review_status: pending_product_review`)

The prototype uses `content/kidquest/quests.json` verbatim. These are suggestions only; nothing was changed silently.

| String | Current | Suggestion | Why |
|---|---|---|---|
| `reward_preview` | "Hadiah: kayu yang kurang + Cetak biru Rumah" | "Hadiah: kayu yang kurang dan cetak biru Rumah" | In a subtraction lesson a "+" can read as an operation. Also aligns the casing with `reward_message` |
| `reward_message` vs `reward_preview` | "cetak biru Rumah" vs "Cetak biru Rumah" | Pick one casing | Consistency |
| `hints[0]` | "… Hitung terus sampai 10. Berapa kali kamu menghitung?" | "… Hitung terus: 7, 8, … sampai 10. Berapa angka yang kamu sebut?" | "Berapa kali kamu menghitung" is ambiguous for a 6-year-old. Starting the count models count-on without stating 4 |
| Prototype-only strings (not in content) | "Langkah 1 dari 2", "Ayo hitung kayunya!", "Pulau: Pulau Tunas", "Bahanmu" | Content review | These should move into content (or UI strings) before KQ-010 |

## 7. Household session plan (pending)

1. Participants: the two household children (`althafandra`, `alleia`) and one parent, with consent. No recording by default.
2. Device: the family phone at its real width, plus one tablet or laptop.
3. Run tasks T1–T5 in order, then the theme comprehension prompt and the "mirip Kuis?" prompt. Do not coach unless the child is blocked, and note any assistance as "adult correction".
4. Parent: open Area Orang Tua, find learning progress, open and cancel a reset review, then exit.
5. Record per task: completed without correction (Y/N), point of failure, a de-identified quote, and the design change.
6. Gate: at least 4 of 5 child tasks without adult correction, and no child believes a theme costs anything or moves the house. Failures go back to flows or wireframes (Stage B/C), not to visual polish.
