# KidQuest first-house component and state contract (Stage E draft)

Status: KQ-005 draft for review. Names match the CSS classes in [`../prototypes/first-house/prototype.css`](../prototypes/first-house/prototype.css), so KQ-010 can keep them in production. Economy components (balance card, split preview, store review, supply/XP meters, request timeline, ledger row) are listed in pipeline §8.3 but belong to KQ-016 and are out of scope here.

**Product-owner constraint (pipeline §8.2a, 2026-11-22):** KidQuest is part of the existing Kids Math Quiz. Header, tabs, panels, buttons, action bars, popups and the theme-picker chrome use the existing app's tokens and components. Only the **world canvas** keeps natural, light and earthy art, and the world themes skin only that canvas and the theme thumbnails. The sources are read-only: `static/css/base.css`, `home.css`, `quiz.css`, `stats.css`, and `app/web/templates/{home,quiz,stats}.html`.

## 1. Token layers (pipeline §8.1–8.2)

| Layer | Prefix | Values | Theme may override? |
|---|---|---|---|
| Foundation = **the app's tokens** | `--bg --panel --panel2 --border --text --muted` copied verbatim from `base.css :root`; `--kq-*` aliases for the values in `home.css`, `quiz.css` and `stats.css` (page `#030916`/`#050c1c`, shell gradient `#11234d→#09132f`, card `#243a71→#192a54`, tab `#1f3668`, active tab `#5a4bae→#3b3984`/`#9d80ff`, option `#133a81`, selected `#6f39d6`/`#bd7bff`, key `#263c70`, answer `#1a3468`/`#85b9ff`, bubble `#3e569e`, gold `#ffbd16`/`#ffe17b`, pink `#ff89ae`, red `#ff555d`, mint `#55f3bf`, correct `#62f1a9`, teal action line `#39c9b9`, danger `#5a2a4d`/`#e65589`); `--f-*` spacing, radii (card 24, panel 20, inner 14, small 8), target 44, `--tile: clamp(38px, 10vw, 64px)` | No |
| Per-child accent | `.profile-theme-blue` / `.profile-theme-purple`, same names and values as `quiz.css` (`--profile-card-accent`, `--profile-avatar-bg`, `--profile-header-*`) plus `--kq-accent-text` and `--kq-accent-solid` | Althafandra `#13bbf6`; Alleia `#9a64d5` for borders and `#c9a7ff` for text (`#9a64d5` is only 4.35:1 on `--panel`) | No (it follows the active child) |
| Semantic | `--s-*` | dark shell: ink `--text`, muted `--muted`, focus `#ffe17b` + `#030916` halo, info `#7fd0ff`, learn (gold), success `#9ff5c8`, attention (pink), disabled `#9aa6c4` on `#1a2547` | **Never** |
| World semantic | `--w-*` on `.world-frame`, `.theme-thumb`, `.thumb` | focus `#0a2a66` + white halo, valid `#1c6b38`, invalid `#a3301f`, white labels on the natural ground | **Never** |
| World theme | `--t-*` + silhouette tokens | ground, ground-alt, water, roof, accent, secondary, `--roof-*`, `--body-*`, `--awning` | Yes, set on any `[data-theme]` element. It applies **only** inside the world canvas and the theme thumbnails |
| Component | `--c-*` | primary button `#177a82→#10626a` (the quiz teal action, darkened for 5:1 text) | Never by a theme |

Wherever a gradient is used, `background-color` is set to its lightest stop, so the automated audit measures the worst case.

### 1.1 Contrast on the dark base (WCAG 2.2 AA: text 4.5:1, large text and UI 3:1)

| Pair | Ratio | Use |
|---|---|---|
| `--text #e9f0ff` / `--panel #0f1730` | 15.5 | body text in the shell |
| `--text` / card `#243a71` (lightest card stop) | 9.6 | card text |
| `--muted` (75% `#e9f0ff`) / card `#243a71` | 6.2 | secondary text |
| help `#b4c2df` / card | 6.1 | `.quiz-help` line, labels |
| white / primary `#177a82` | 5.1 | primary buttons, Kirim |
| `#f5f7ff` / secondary `#133a81` | 10.1 | secondary buttons, theme cards |
| tab ink `#b6c4e2` / tab `#1f3668` | 6.7 | inactive tabs |
| white / active tab `#5a4bae` | 6.9 | active tab |
| accent blue `#13bbf6` / card | 4.9 | eyebrow, "Pulau Tunas" (Althafandra) |
| accent purple text `#c9a7ff` / card | 5.5 | the same, for Alleia |
| `#13bbf6` / header link `#12335f` · `#c9a7ff` / `#31297a` | 5.7 · 6.1 | Menu link |
| gold-light `#ffe17b` / card | 8.5 | "Bisa dimulai" badge, reward preview |
| `#fff8e0` / hint `#2b2a4a` | 12.9 | hint text (gold outline, not red) |
| info `#7fd0ff` / alert `#132650` | 8.7 | info alerts, "Sedang dikerjakan" |
| success `#9ff5c8` / `#0e3a4a` | 9.5 | valid placement status, saved |
| `#ffbfcc` / `#3a1d3d` | 9.5 | load and save error text |
| pink line `#ff89ae` / card | 4.9 | invalid status, error outline (UI ≥3:1) |
| mint `#55f3bf` / pill `#0e4c53` | 6.9 | reward pills |
| `#f7f8ff` / bubble `#3e569e` | 6.5 | owl speech bubble |
| answer `#85b9ff` / `#1a3468` | 6.0 | answer digits |
| input border `#7aa7f5` / `#1a3468` | 5.0 | answer box boundary (1.4.11) |
| disabled `#9aa6c4` / `#1a2547` | 6.2 | disabled label, still legible; also dashed border |
| `#1d2420` / gold badge `#ffbd16` | 9.5 | "! Misi" badge on the world |
| **Focus** `#ffe17b` / panel, tab, card | 11.9–13.1 measured | gold ring + dark halo in the shell |
| **Focus** `#ffe17b` / primary button | 3.9 (and 8.5 against the card behind it) | the ring sits outside the button, offset 2 px, on the card |
| **World focus** `#0a2a66` / ground `#cfe0b4` | 9.8 | ring on cells, plus a white inner halo |
| world valid / ground · invalid / ground | 4.7 · 5.0 | placement outlines (≥3:1) |
| adult `#c7cfe0` / `#122136` · `#32aaff` / `#10233c` · `#ff555d` / `#321525` | 10.4 · 6.3 · 5.3 | adult muted, current section, reset button |
| adult input border `#7d93b3` / `#0c182a` | 5.7 | adult field boundary |

The automated audit in `walkthrough-check.mjs` measures every visible text node except the reviewer panel. It covers world, Misi, quest, catalog (with the "Bahanmu" card), theme, help, challenge, the wrong-answer popup and the reward popup. Minimum **4.93:1** at all three widths (273 nodes at 360 and 768, 314 at 1280). Entry minimum is 9.42:1, adult gate 12.58:1, adult shell 6.16:1.

The focus-ring check measures the outline against the opaque background behind four controls: Menu link, tab, primary button and text button. Results: 8.5–13.1:1, each ring 3 px solid.

**Known gap in the existing app, not copied:** `home.css .continue-button` text `#bfe3ff` on its blue is 3.3:1, and the quiz's teal action with white text is 2.0–3.3:1. KidQuest uses the same shapes with darker fills (`--kq-accent-solid`, `#177a82`). This is a suggestion for the app owners, not a KidQuest change.

## 2. Global interaction rules

- **Targets:** every control except grid cells is at least 44×44 CSS px, measured at 360, 768 and 1280 in child mode, both popups and adult mode. Keypad keys are 44 px at ≤440 and 56 px above. Grid cells are 38–64 px, an approved exception (C1 FINAL) with 48 px nudge buttons, arrow keys and an explicit ≥44 px confirm.
- **Focus:** a 3 px gold `#ffe17b` outline, 2 px offset, and a 6 px `#030916` halo through `:focus-visible`. On world cells the ring is navy `#0a2a66` with a white inner halo.
  - After a view change, focus moves to the new view's heading.
  - A popup takes focus on its main button (Coba Lagi) or its title (Benar!). Closing the wrong-answer popup returns focus to the answer box.
  - Closing an inspector or menu returns focus to the invoking cell or button. After a successful build, focus moves to the new house's cell.
- **Modal dialogs** (Menu, wrong-answer popup, reward popup): `role=dialog`, `aria-modal`, Tab trapped, Esc closes. Esc on the reward popup equals "Nanti saja".
- **Live region:** one polite `#live` region carries short status changes (validity, preview, saved, cancelled). The owl bubble is also a polite region. The grid is never re-read in full.
- **Colour independence:** every state has an icon and text.
  - Placement adds solid versus dashed-and-hatched outlines.
  - The active tab adds weight, a glow bar under the tab, and `aria-current`.
  - The theme selection adds a 3 px outline plus "Dipakai" or "Dilihat".
  - Disabled controls add a dashed border.
  - Wrong-answer feedback adds the owl and the words "Belum tepat".
- **Motion:** the tutorial-zone pulse (2 iterations), the build flash (0.9 s) and the sheet slide (200 ms). `prefers-reduced-motion` or the in-app "Kurangi Gerakan" removes all of them; text and icon confirmation stays. The decorative sparkles in the "Bahanmu" card are static.
- **Text scaling:** rem-based type, wrapping rows, no fixed-height text containers. At 200% root text, the walkthrough found no horizontal overflow at 360 px in placement, world, Misi, catalog, theme or challenge. In that mode the header link wraps, the gift art hides, the keypad reflows to fewer, wider keys and the theme cards stack.
- **Preview versus mutation:** Back, Batal, Esc, or leaving through a tab never commits. Only Kirim, Mulai Tantangan, Bangun di Sini and Gunakan Tema call the server.

## 3. Component state matrix

Legend: **L** loading · **E** empty · **S** success · **R** retry · **Lk** locked · **Er** error · **Off** offline · **St** stale · **D** disabled. A dash means not applicable, with the reason given.

| Component | Phone ↔ desktop | States | Keyboard / screen reader |
|---|---|---|---|
| `kq-app` shell: `kq-header` + `kq-workspace` | Header card stacked ≤960, one row ≥960. The workspace holds the tabs, banners, world and panel; ≥960 puts the world left and the panel right | L: skeleton objective and grid · Er: load error card with Coba Lagi · Off: offline banner in `banner-slot` · S/E: n/a | `header` landmark; skip link to `#main`; no fixed header |
| Header: `learner-avatar`, `learner-copy`, `header-link`, `today-card` | Avatar 102/96/64 px by breakpoint; Menu link full width at ≤620 | "Bahanmu" card only once the child owns wood or a blueprint, or on the catalog (AC-22); hidden in placement, theme and challenge | Avatar is decorative; Menu link `aria-haspopup=dialog`; the card is `section aria-label="Bahanmu"` |
| `nav` / `nav-item` (tab row) | 3 equal tabs; icon above label ≤620 | Selected (`aria-current`, purple, bold, glow bar) · D: none in first house (no locked tabs; Dompet absent) | `nav` "Navigasi utama"; leaving placement or theme through a tab cancels the preview and announces it |
| `btn-primary / -secondary / -text / -danger` | Same | D: dashed navy with a visible reason next to it · L: label changes ("Memeriksa…", "Membangun…", "Menyimpan…") and other mutations are blocked · pressed: 1 px down | Native buttons; a disabled button always has adjacent explanatory text |
| Objective card (`objective`, `card-accent`) | Home: full card with CTA; desktop non-home: compact, no CTA; hidden in placement, theme and reward | L: skeleton · per quest state per IA table · S: "Lengkap untuk sekarang" · Lk: n/a | `section` labelled by its `h2`; heading is the focus target on Dunia |
| Resume summary (`resume`) | Replaces the objective card | Incomplete: one Resume CTA + Tutup · Complete: Tutup only · never shows absence, streak or urgency | Focus to the "Sejak Kunjungan Terakhir" heading on load |
| Quest card + `status` badge | Stacked cards | Available / active / ready / done · Lk: dashed badge with lock icon + "Kenapa? …" + link to the satisfying action · "Belum dibuka" (clock, dotted) for economy-off Q002 | Badge text is part of the card; the locked reason is visible text, not a tooltip |
| Quest detail | Panel | AVAILABLE: Mulai Tantangan (L "Menyiapkan…", Off disabled + reason) · IN_PROGRESS: Lanjutkan · READY: Bangun Rumah · COMPLETED: Lihat di Dunia | Back button "Kembali"; heading focus |
| Challenge (`challenge`, `question-head`, `tutor-area`, `answer-input`, `quiz-help`, `keypad-grid`) | One card; nothing fixed. After feedback the card top is scrolled to the viewport top so question, hint, answer box, keypad and Kirim fit at 360×780 | E: Kirim disabled + help line "Tekan angka, lalu tekan Kirim." · L: "Memeriksa…" · R: wrong-answer popup, then the hint in the help line (level 1 count-on; level 2 numbered empty slots) · cap: owl and help line explain; input, keys and Kirim disabled · Off: disabled + reason · uncertain: Checking card | Native input (`inputmode=numeric`, digits only, max 2) plus the on-screen keypad; Enter submits; the illustration's `role=img` names 10 and 6 but not the answer; the input is described by the bubble and the hint |
| Wrong-answer popup (`kq-popup`, `kq-popup-card is-learn`) | Centred card, max 520 px | Shows level 1 or 2 hint text; one action, Coba Lagi | Dialog; focus on Coba Lagi; Esc = Coba Lagi; focus returns to the answer box |
| Reward popup (`kq-popup-card is-correct`, `reward-pill`) | Centred card | S only (from the authoritative response); "Hadiahmu sudah tersimpan." | Dialog; heading focus; Esc = Nanti saja; wood/blueprint icons, never an Rp coin |
| Catalog card (`catalog-card`, `thumb`) | Panel | Lk: "Butuh cetak biru dari misi Rumah Pertama" + link · insufficient wood: "Butuh 4 kayu. Kamu punya n." · ready: Pilih Tempat · owned: Sudah dibangun + Lihat di Dunia (no rebuild, demolish or upgrade) | Facts in a `dl` (Ukuran, Biaya, Pintu); thumbnail decorative |
| World grid (`world-frame`, `world-grid`, `cell`) | Tile = clamp(38, 10vw, 64), in a navy frame | Loading: skeleton block · Er: hidden behind the error card · per-cell labels · build mode shows the zone pattern and fogged expansion zone | `role=grid`, one roving tab stop; arrows move; Enter/Space activates; Esc cancels placement or closes the inspector; each cell label is "<isi> di kolom x, baris y[, zona rumah]" |
| Building target (house) | 2×2 cells | Art is `pointer-events:none`; the 4 logical cells are the target in every theme (measured identical before and after preview) | Each footprint cell is labelled "<nama rumah>, rumahmu. Pintu di sisi bawah" |
| Quest-board badge | 1 per object max | Shown while Q001 is AVAILABLE or IN_PROGRESS; hidden in build mode | Included in the cell label ("ada misi") |
| Placement preview (`preview.valid / .invalid / .hover`) | Overlay on natural ground | Hover (keyboard cursor, fitted footprint): dotted · valid: solid + ✓ + "Pintu" · invalid: dashed + hatch + ✕ | Validity is announced; the status is also visible text in `place-status` |
| Placement controls (`action-bar`, `nudge`, `place-status`) | Fixed bottom bar ≤959; at the top of the right panel ≥960 | E: "Belum memilih tempat." · invalid reason + "Coba kotak bergaris yang kosong." · L: "Membangun…" · St: info alert "Duniamu baru saja diperbarui…" · Er: message + "Tidak ada yang berubah." · Off: disabled + reason · uncertain: Checking card | A tap on any striped cell fits the 2×2 house inside the zone (D11); nudge buttons are 48 px with aria-labels; Batal is always visible (mode banner + bar) |
| Inspector (`panel-slot` content) | Panel below the world on phone; right column ≥960 | E: "Ketuk benda di pulau untuk melihatnya." · object detail with at most one action | Heading focus on open; Tutup returns focus to the invoking cell |
| Checkpoint | Panel; world visible with focus on the house | S only; economy on/off variants for "Berikutnya" | Heading reachable by Tab after focus lands on the house |
| Theme card / picker (`theme-card`) | Cards + buttons in the phone action bar; in the right panel ≥960 | Dipakai / Dilihat / Gratis · D: Gunakan Tema disabled until a different theme is previewed · L: "Menyimpan…" · Er: restore + Coba Lagi · S: confirmation text · Off: disabled + reason · uncertain: Checking card | `role=radiogroup`/`radio`; arrows move the selection and preview; the preview is announced |
| Menu sheet (`scrim`, `sheet`) | Bottom sheet on phone; centred dialog ≥621 | Kurangi Gerakan shows Nyala/Mati text | `role=dialog`, `aria-modal`; focus to the first item; Tab trapped; Esc and Tutup return focus to Menu; a scrim click closes |
| Inline alert (`alert-*`) | Same | info (blue line), learn (gold), success (mint), error (pink), offline (dashed), mode (gold, 2 px) | Errors use `role=alert`, status uses `role=status`; no toast ever carries the only recovery action |
| Checking card | Replaces the panel of the affected view | "Memeriksa perubahan…" + Periksa Lagi (disabled offline) | Heading focus; same idempotency key on recheck |
| Skeleton | Matches the final layout | L only | `aria-busy=true` + visible "Memuat duniamu…" |
| Adult bar + nav (`adult-*`) | Nav wraps to a button grid below 960; left column ≥960 | Gold "Mode Orang Tua aktif" flag always visible · Ekonomi and Pencairan absent while the economy is off (C7) · session expiry returns to the gate with a message | `nav` "Bagian orang tua"; section heading focus |
| Adult gate form | Centred, max 440 px | Er: "PIN tidak cocok. Coba lagi." (`aria-invalid`, `aria-describedby`) · L: "Memeriksa…" · expired note · no lockout (C8) | Labelled password field, `inputmode=numeric`; focus returns to the field on error |
| Data card (`kv`) | Label/value rows, cards wrap | E: "Belum membuka KidQuest" / "Belum ada latihan … 7 hari terakhir" | `dl` semantics |
| Scoped reset review | Card | D: Hapus disabled until the exact scope word is typed · Batal announces "Tidak ada yang dihapus" · S: simulated result + audit note | Radio group with a legend; review heading focus |

## 4. Copy rules

- Short sentences, one instruction per step: "Ketuk kotak di zona bergaris."
- Mistakes are neutral: "Belum tepat. Coba lagi, ya!" No blame, no red ✕, no "salah".
- Lock reasons name the requirement: "Selesaikan misi Rumah Pertama dulu."
- Saved state is explicit and calm: "Semua sudah tersimpan otomatis. Kamu boleh berhenti kapan saja."
- Resource units are always words, never a currency symbol: "4 kayu". No Rp text or Rp art appears in the first-house release.
- Q001 child-facing strings (story, prompt, hints, `reward_preview`, `reward_message`) come verbatim from `content/kidquest/quests.json`. Theme building labels come from `content/kidquest/themes.json`, in Indonesian for every theme.

## 5. Consistency with the existing app

| KidQuest component | Mirrors (existing app) | Notes / deliberate differences |
|---|---|---|
| Page background | `quiz.css .quiz-page` (`#050c1c` + radial glow); `base.css` font stack | Same `touch-action: manipulation` |
| Header card `kq-header` | `quiz.html .quiz-header` (clouds art, gradient, 20 px top radius; stacked ≤960/620/440) | The context line reads "Pulau: Pulau Tunas" instead of "Tingkat" (no level/XP in first house, C9) |
| Avatar `learner-avatar` | `quiz.css .learner-avatar` + the app's `althafandra-avatar.png` / `alleia-avatar.png` | Same accent ring and avatar gradient per child |
| Menu link `header-link` | `quiz.css .header-stats-link` ("Lihat Statistik") | Text colour is `--kq-accent-text` (purple text lightened for AA) |
| "Bahanmu" card `today-card` | `quiz.css .today-card` + `reward-gift.png` + gift sparkles | Shows wood and blueprint, never Rp; static sparkles |
| Workspace `kq-workspace` | `quiz.css .quiz-workspace` | Holds the tab row, world and panel; no school doodles (they compete with the world) |
| Tab row `nav` / `nav-item` | `quiz.css .quiz-tabs` / `.quiz-tab` / `.quiz-tab.is-active` + glow bar | Three equal tabs (Dunia / Misi / Bangun) instead of a horizontal scroller, so no tab is ever hidden; SVG icon tiles stand in for the PNG tab icons (graybox) |
| Cards `card` | `quiz.css .quiz-question` (gradient, 20 px radius) | Same for quest, catalog, inspector, checkpoint, resume |
| Accent card `card-accent`, objective | `home.css .profile-card` (per-child accent border and gradient) | Used for the one current objective |
| Primary button `btn-primary` | `quiz.css .quiz-actions button` (teal, `#39c9b9` line) | Fill darkened to `#177a82→#10626a` for 5.1:1 white text |
| Secondary button `btn-secondary` | `quiz.css .knowledge-option` | Same gradient and line |
| Danger button `btn-danger` | `quiz.css .quiz-actions .danger` (child) · `stats.css .stats-action-clear` (adult reset) | |
| Text button `btn-text` | `base.css a` link colour | Underlined, ≥44 px target |
| Challenge card | `quiz.html .quiz-question`: `.question-progress` + `.progress-track`, `.tutor-area` with `owl-tutor.png` and `.tutor-bubble`, `.quiz-prompt` | Progress shows "Langkah 1 dari 2" (answer, then build); the bubble speaks the feedback |
| Answer field `answer-input` | `quiz.css .quiz-answer` | A real labelled `<input>` with a 5:1 border, not a div |
| Hint line `quiz-help` | `quiz.css .quiz-help` ("💡 …") | Carries the hint at 16 px (the quiz uses 13 px at ≤440) with a gold outline |
| Keypad `keypad-grid` | `quiz.css .quiz-pad` / `.keypad-grid` (3 columns, 44 px keys at ≤440) | The quiz's empty last-row cells hold **Hapus** and **Kirim**: KidQuest submits explicitly instead of auto-submitting, because answers can have two digits |
| Wrong-answer popup | `quiz.html .quiz-popup` / `.quiz-popup-card` + `popup-wrong-background.png` (pink line) | **Owl tutor instead of the red ✕**, title "Belum tepat. Coba lagi, ya!" instead of "Yah kamu salah", and the hint instead of the answer (PRD §10.2, D4) |
| Reward popup | `.quiz-popup-card.is-correct` + `popup-correct-background.png` + `popup-correct-icon.png` + `.quiz-popup-reward` pill | Wood and blueprint icons on tan and blue discs; **`popup-reward-coin.png` is not used** (Rp art; pipeline §8.4) |
| Menu sheet | `home.css .home-card` on the `.quiz-popup` scrim | |
| Theme cards | `quiz.css .knowledge-option` / `.knowledge-option.is-selected` | Thumbnails show the natural world art for each theme |
| Placement action bar | Bottom of `.quiz-workspace` (≤620 gradient, 20 px top radius) | Fixed only in placement and theme views |
| Alerts, mode banner, status badges | Popup accent lines (pink, mint), `stats.css` value colours (gold, green, blue) | Every state has an icon + text |
| Entry (profile, mode choice) | `home.html .home-card`, `.star-mascot`, `.profile-card-blue/purple`, `.continue-button` | Continue button uses the darker accent solid (AA) |
| World frame | `.quiz-question` card around the canvas | The canvas inside keeps the natural Kampung, Kerajaan and Kota art |
| Adult gate and shell | `stats.html`: `.stats-page` backdrop, `.stats-card`, `.stats-action`, `.stats-action-account` (current section), `.stats-action-clear` (reset) | Gold "Mode Orang Tua aktif" flag keeps it unmistakable |
| Reviewer panel | none (tool only) | Dark with a dashed outline; never shown to a child in production |

Side-by-side renders: `../wireframes/renders/compare-360-*.png` (see [wireframes §3](../wireframes/README.md#3-consistency-renders)).
