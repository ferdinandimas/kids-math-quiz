# KidQuest first-house wireframes (Stage C)

Low fidelity, graybox. The clickable source of truth is [`../prototypes/first-house/`](../prototypes/README.md). The PNGs in [`renders/`](renders/) are headless-Chrome captures of that prototype, taken by `walkthrough-check.mjs --shots` and `compare-with-app.mjs`. They show layout only; none of them is production art.

**Product-owner constraint (pipeline §8.2a, 2026-11-22).** KidQuest sits inside the existing Kids Math Quiz and must look like it. Every element around the world canvas reuses the app's tokens, layout and components from `static/css/{base,home,quiz,stats}.css` and `app/web/templates/{home,quiz,stats}.html`:

- the dark navy shell;
- a `.quiz-header`-style header card;
- a `.quiz-workspace` panel with a `.quiz-tabs` tab row;
- the quiz question card, owl tutor, answer box and keypad;
- the quiz popups;
- the per-child blue/purple accent.

The world canvas alone keeps natural, light and earthy art: ground, water, trees, rock, board and buildings in the Kampung, Kerajaan and Kota packs.

## 1. Layout capacity (PRD §11.12, pipeline §6.1, quiz.css breakpoints 960/620/440)

| Width | Layout | Panels | Navigation |
|---|---|---|---|
| ≤440 | Header card (avatar 64 px, name, "Pulau: Pulau Tunas", full-width Menu link, then the "Bahanmu" card once the child owns something), then the workspace: tab row, banners, objective (home only), world, panel | Task views (Misi, quest, challenge, reward, catalog, help) hide the world. Placement and theme pin their decision controls in a fixed **action bar** at the bottom. Nothing else is fixed. | Tab row, 3 tabs (Dunia / Misi / Bangun), icon tile above label |
| 441–620 | Same, larger avatar (96 px) and type | Same | Same |
| 621–959 | Header card stacked (quiz.css ≤960), world tiles reach 64 px | Same action bars | Tab row, icon beside label |
| ≥960 | Header card in one row. The workspace has the tab row on top, then the world on the left and the objective plus contextual panel on the right | Placement controls sit at the top of the right panel (status, confirm, cancel), above the tip and nudge pad | Tab row, max 310 px per tab |

World tiles always use `clamp(38px, 10vw, 64px)`: 38 px at 360, 64 px at 640 and up. The grid sits in a navy `.quiz-question`-style frame (6 px padding). At 360 px the frame is exactly the workspace width, so there is no horizontal overflow.

## 2. Screens

Every screen below exists in the prototype. Each sketch shows the phone layout first; the note under it says what changes at ≥960.

### 2.1 Entry: profile, then Quiz or KidQuest (mirrors `home.html`)
```text
+------------------------------+
|        (★ star mascot)       |
|       Pilih akun dulu        |
|  Siapa yang main hari ini?   |
| +-----------+ +-----------+  |   blue / purple .profile-card,
| | (avatar)  | | (avatar)  |  |   round avatar, "Lanjutkan ›"
| |Althafandra| |  Alleia   |  |
| |[Lanjutkan›]| |[Lanjutkan›]| |
| +-----------+ +-----------+  |
+------------------------------+  →  "Mau main apa, Althafandra?"
                                     [🏝 KidQuest  Belajar matematika sambil membangun pulaumu]
                                     [▤ Kuis       Latihan soal seperti biasa]
                                     Bukan Althafandra? Ganti akun
```
Renders: `phone-360-00-profiles.png`, `phone-360-01-entry.png`, `compare-360-home-vs-entry.png`

### 2.2 World Home (header card + workspace, mirrors `quiz.html`)
```text
+------------------------------+        ≥960
| (avatar) Nama                |        +-------------------------------------------+
|          Althafandra         |        | (avatar) Nama / Althafandra / Pulau  [≡ Menu]|
|          Pulau: Pulau Tunas  |        +-------------------------------------------+
| [         ≡ Menu          ]  |        | [Dunia] [Misi] [Bangun]                    |
+------------------------------+        | +-------------+  +-----------------------+ |
| [Dunia*] [ Misi ] [Bangun ]  |        | |  8×8 WORLD  |  | Misi sekarang + CTA   | |
| MISI SEKARANG                |        | |             |  | Lihat pulau/inspector | |
| Rumah Pertama                |        | +-------------+  +-----------------------+ |
| Bantu siapkan kayu …         |        +-------------------------------------------+
| [       Mulai Misi        ]  |
| 8×8 world in a navy frame,   |
| board "! Misi" (one badge)   |
| Tema: Kampung Ceria [Graybox]|
+------------------------------+
```
After the reward, the header also shows the "Bahanmu" card (`.today-card`): wood count, blueprint, and the gift art. The active tab is the quiz's purple tab with its glow bar. The objective card uses the child's accent border, as `.profile-card` does.
Renders: `phone-360-02-world-home.png`, `tablet-768-02-world-home.png`, `desktop-1280-02-world-home.png`, `compare-360-quiz-vs-world.png` (both children)

### 2.3 Misi list
- **Q001 card:** status badge with icon and text (Bisa dimulai / Sedang dikerjakan / Siap dibangun / Selesai).
- **Q002 "Kebun Tunas" card, before the house:** **Terkunci · Kenapa? Selesaikan misi Rumah Pertama dulu.** plus a [Ke Misi Rumah Pertama] button.
- **Q002 after the house, economy off:** "Belum dibuka · Bangunan berikutnya belum dibuka. Orang tuamu yang bisa membukanya nanti." This uses a clock icon, not a lock (C6).

### 2.4 Quest detail
```text
[< Kembali]
MISI · PENGURANGAN
Rumah Pertama            (★ Bisa dimulai)
Kita butuh 10 kayu untuk membangun rumah. Sudah ada 6 kayu.     ← quests.json story
▣ Hadiah: kayu yang kurang + Cetak biru Rumah                   ← quests.json reward_preview
[        Mulai Tantangan        ]
```
Render: `phone-360-03-quest-detail.png`

### 2.5 Challenge with wrong-answer hint (mirrors `.quiz-question` + `.quiz-pad`)
```text
+----------------------------------+
| Langkah 1 dari 2   (bubble) (owl)|   progress strip; owl tutor speech bubble
| ▬▬▬▬▬▬░░░░░░       "Belum tepat. |
| [💡 Petunjuk]       Coba lagi!"  |
| Kita butuh 10 kayu. Sudah ada 6. |   prompt (quests.json)
| Berapa lagi?                     |
| [▤][▤][▤][▤][▤][▤][ ][ ][ ][ ]   |   2nd mistake: empty slots show 7 8 9 10
|      Butuh 10   Ada 6            |
| Jawabanmu                        |
| [              –               ] |   .quiz-answer box (real input)
| 💡 Kita sudah punya 6 kayu. …    |   help line carries the hint (gold outline)
| [ 1 ][ 2 ][ 3 ]                  |
| [ 4 ][ 5 ][ 6 ]                  |   .keypad-grid
| [ 7 ][ 8 ][ 9 ]                  |
| [Hapus][ 0 ][✓ Kirim]            |   Kirim = teal primary, disabled until a digit
+----------------------------------+
```
A wrong answer opens the quiz-style popup. It uses the pink attention line and the wrong-popup background, with the **owl tutor in place of the red ✕**. The title reads "Belum tepat. Coba lagi, ya!" and the body shows the hint, followed by [Coba Lagi].

Closing the popup returns focus to the answer box and scrolls the card's top to the viewport top. At 360×780 that keeps the question, hint, answer box, whole keypad and Kirim on screen together. The challenge view has no fixed bar (lead finding 1).
Renders: `phone-360-04a-wrong-popup.png`, `phone-360-04-challenge-hint.png`, `tablet-768-04a-wrong-popup.png`, `tablet-768-04-challenge-hint.png`, `desktop-1280-04-challenge-hint.png`, `compare-360-quiz-vs-challenge.png`

### 2.6 Reward (quiz "correct" popup)
Confetti icon and correct-popup background. Title "Benar!", then "10 − 6 = 4. Hebat! Kamu dapat 4 kayu dan cetak biru Rumah." (`reward_message`).

Two mint reward pills follow: **4 kayu** (wood icon on a tan disc) and **Cetak biru Rumah** (blueprint icon on a blue disc). The Rp coin art (`popup-reward-coin.png`) is deliberately **not** used, because wood never reuses a currency symbol (pipeline §8.4).

The popup ends with "Hadiahmu sudah tersimpan." and the buttons [Bangun Rumah] [Nanti saja].
Renders: `phone-360-05-reward.png`, `tablet-768-05-reward.png`, `compare-360-popups.png`

### 2.7 Build catalog
The house card shows:
- a graybox thumbnail and the name **Rumah**;
- a status: Terkunci with its reason, Siap dibangun, or Sudah dibangun;
- "Tempat tinggal pertamamu di pulau.";
- facts: Ukuran 2 × 2 kotak · Biaya 4 kayu · Pintu sisi bawah;
- a [Pilih Tempat] or [Lihat di Dunia] button.

The first time the child arrives from the reward, a one-time tip reads "Ini menu Bangun. Cetak biru Rumah sekarang ada di sini."
Render: `phone-360-06-catalog.png`

### 2.8 Placement mode (canonical `pulau_tunas_v1`)
```text
| ⚒ Mode Bangun: Rumah. Belum ada yang berubah … [Batal] |   gold-outlined mode banner
| world: tutorial_zone x1–4, y1–2 striped + legend;      |
| tree (0,0) (7,0) (7,7), rock (0,7), board (4,3);       |
| water rows 4–5 x3–7 + (3,6) (3,7); expansion x4–7,     |
| y6–7 fogged (locked)                                   |
| valid = solid outline ✓ Pintu · invalid = dashed ✕     |
=== fixed action bar (phone/tablet) =====================
| ✓ Bisa dibangun di sini.                               |
| [ Bangun di Sini · 4 kayu ]  [Batal]                   |
```
Tapping **any** striped cell selects the 2×2 footprint that covers that cell and fits the zone (D11, a proposal). For example, (4,2) selects origin (3,1). Valid origins are only (1,1), (2,1) and (3,1). Outside the zone, the tapped cell is the top-left corner, so the child sees the concrete reason: tree, rock, water, board, locked area, or "pilih di dalam zona bergaris".
Renders: `phone-360-07-place-invalid.png` (tree), `phone-360-08-place-valid.png`, `tablet-768-08-place-valid.png`, `desktop-1280-07-place-invalid.png`, `desktop-1280-08-place-valid.png`

### 2.9 House checkpoint
- "Rumah Pertama selesai!"
- Yang berubah: Rumahmu berdiri di pulau. 4 kayu dipakai.
- Semua sudah tersimpan otomatis. Kamu boleh berhenti kapan saja.
- Berikutnya: …
- Baru: Tema Dunia (gratis, rumah tetap di tempatnya).
- [Selesai] [Coba Tema Dunia] · Main Kuis.

The world stays visible above, with focus on the new house at (2,1).
Renders: `phone-360-09-checkpoint.png`, `desktop-1280-09-checkpoint.png`

### 2.10 Theme picker (preview, cancel, confirm, failure)
On phone, a preview banner sits above the world, and the world shows the previewed skin. A fixed action bar holds the three radio cards and [Gunakan Tema] [Batal]. The cards are `.knowledge-option` cards; the selected card uses the quiz's purple `.is-selected` glow and reads Dipakai, Dilihat or Gratis.

The theme repaints only the world canvas and the card thumbnails, never the shell.
Renders: `phone-360-10-theme-preview.png`, `tablet-768-10-theme-preview.png`, `desktop-1280-10-theme-preview.png`, `phone-360-11-theme-failed.png`

### 2.11 Calm resume
The "Sejak Kunjungan Terakhir" card (accent border) replaces the objective card. It shows the last completed change, then "Sekarang: …", then "Semua sudah tersimpan otomatis.", with [Lanjutkan: Bangun Rumah] [Tutup].
Renders: `phone-360-12-resume.png`, `desktop-1280-12-resume.png`

### 2.12 System states
| State | Treatment | Render |
|---|---|---|
| Loading | Navy skeleton objective, skeleton grid, and "Memuat duniamu…" (`aria-busy`) | none (transient; asserted in the check) |
| Load error | Pink-outlined alert, "Tidak ada yang hilang.", and Coba Lagi | reviewer panel → "Tampilkan gagal memuat" |
| Offline | Dashed neutral banner. Mutating buttons are disabled with the visible reason "Butuh internet untuk menyimpan. Duniamu tetap aman." | `phone-360-14-offline.png` |
| Network-uncertain | "Memeriksa perubahan…" card and Periksa Lagi (same key) | `phone-360-13-checking.png` |
| Stale world | Info alert in placement: world refreshed, choice still valid, confirm again | asserted in the check |
| Daily cap | Owl bubble "Latihan hari ini sudah cukup."; the help line explains. Keypad, Kirim and input are disabled; the world is still viewable | reviewer toggle |

### 2.13 Adult gate and shell (mirrors `stats.html`)
The adult page uses the stats page backdrop, `.stats-card` cards and `.stats-action` buttons. The current section has the blue account outline. A gold "Mode Orang Tua aktif" flag sits in the bar, so the adult mode never looks like a child screen.

Below 960 px the nav wraps into a grid of buttons with no horizontal scroll. Ekonomi and Pencairan are **absent** while the economy is disabled (C7).
Renders: `phone-360-15-adult-gate.png`, `phone-360-16-adult-shell.png`, `tablet-768-16-adult-shell.png`, `desktop-1280-15-adult-gate.png`, `desktop-1280-16-adult-shell.png`

## 3. Consistency renders

`compare-with-app.mjs` starts nothing itself. Run the real app on a temporary database first:

```bash
DB_PATH=$(mktemp -d)/app.sqlite3 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 &
node design/kidquest/wireframes/compare-with-app.mjs http://127.0.0.1:8765 design/kidquest/wireframes/renders
```

| Sheet | Left (existing app) | Right (KidQuest) |
|---|---|---|
| `compare-360-home-vs-entry.png` | `/home` | Entry profile choice |
| `compare-360-quiz-vs-world.png` | `/quiz/math` for Althafandra and Alleia | World Home for each child (blue and purple accent) |
| `compare-360-quiz-vs-challenge.png` | `/quiz/math` | Q001 challenge after a wrong answer |
| `compare-360-popups.png` | Quiz wrong and correct popups | KidQuest wrong-answer and reward popups |

The quiz popups are opened with the page's own `showPopup()`, and its auto-continue timer is cleared, so the comparison submits no extra answers.
