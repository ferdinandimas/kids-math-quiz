# KidQuest first-house clickable prototype (Stage D)

Low-fidelity, graybox, Indonesian child-facing copy. The shell uses the existing Kids Math Quiz look: dark navy, a quiz-style header card and tab row, the quiz question card with the owl tutor and keypad, quiz popups, and the per-child blue or purple accent (pipeline §8.2a). It reads the app's images from `static/images/` without changing them. Only the world canvas uses natural, light art. No backend and no network: a small in-page "server" simulates the authoritative rules (quest state machine, one-time reward, placement validation, world version, idempotency keys) so reviewers can see success and recovery states. **This is not production code and not production art.**

## Open it

- Child mode: open `design/kidquest/prototypes/first-house/index.html` directly in a browser (double-click, or `open design/kidquest/prototypes/first-house/index.html` on macOS). It runs from `file://` with no CDN and no build.
- Profile select from scratch: add `?entry=1` to the URL.
- Adult gate: Menu → "Area Orang Tua", or open `parent.html`. The prototype PIN is **2468**.
- Phone check: in the browser's device toolbar, choose a width of 360 px. Tablet: 768 px. Desktop: 1280 px.

## Reviewer panel

At the bottom of each page, a dashed "Panel peninjau prototipe (bukan bagian UI anak)" section lets a reviewer:

- Jump to scenarios: fresh world; return mid-challenge; return ready to build; return with the house built; reload.
- Simulate: offline, a lost response on the next save, a theme save failure, a stale world on the next build, the daily cap reached, slow responses, a loading skeleton, a load error.
- Toggle the parent setting "economy enabled" (Q002 becomes the next objective; its flow is out of scope).
- Toggle 200% text and reduced motion.
- See the simulated authoritative state and a theme-invariance readout after a theme confirm.

State persists in `localStorage`, so a reload behaves like a return visit. Use "Mulai baru" to reset.

## Scripted walkthrough (for proxy or household sessions)

1. Start with `?entry=1` → pick a child → KidQuest.
2. **Find the current objective** → press "Mulai Misi".
3. **Explain a locked reason**: open Misi and read the "Kebun Tunas" card.
4. Open "Rumah Pertama" → Mulai Tantangan → tap a wrong answer (for example 5) → Kirim. Read the owl popup → Coba Lagi. The hint stays under the question. Tap 4 → Kirim.
5. In the reward popup: Bangun Rumah → Pilih Tempat → tap the tree at the top-left corner, or a cell to the right of the stripes (**recover from an invalid action**). Then tap any striped cell (the house fits itself inside the stripes) → Bangun di Sini.
6. At the checkpoint → Coba Tema Dunia → tap Kerajaan Ceria → **cancel the preview** with Batal → reopen → choose Kota Ceria → Gunakan Tema.
7. Reload the page from the reviewer panel → see the calm summary. Use "Kembali: siap membangun" to see the Resume action.
8. Menu → Area Orang Tua → enter a wrong PIN, then 2468 → browse the sections → Pengaturan → Tinjau a reset → Batal → Keluar.

## Automated walkthrough check

```bash
node design/kidquest/prototypes/first-house/walkthrough-check.mjs            # 72 checks × 3 widths (216)
node design/kidquest/prototypes/first-house/walkthrough-check.mjs --shots <dir>
```

The script needs Node ≥ 22 and local Google Chrome (override the location with `CHROME=/path`). It drives the prototype through the DevTools Protocol at 360×780, 768×1024 and 1280×820 and checks:

- flow outcomes and state invariants, including canonical `pulau_tunas_v1` placement (tree, rock, outside the zone, fit-to-zone tap, (2,1));
- keyboard placement, popup focus and focus return;
- that question, hint, answer box and Kirim are fully visible and **not covered** (`elementFromPoint` occlusion test) after a wrong answer;
- horizontal overflow, including at 200% text;
- 44 px control sizes in child mode, both popups and adult mode;
- WCAG text contrast on the dark shell (child, popups, entry, adult gate and adult shell) and focus-ring contrast;
- the reduced-motion effect;
- adult-gate separation and hidden economy sections.

Determinism:
- Every step waits on a selector or app state, never on a fixed sleep.
- A step that cannot finish fails with its name.
- The final `N/M checks passed` line is always printed.
- A lock file prevents two concurrent runs.

Only one instance may run at a time.

This is automated proxy verification. It is **not** usability testing with children.

## Files

| File | Purpose |
|---|---|
| `first-house/index.html`, `child.js` | Child shell and all first-house screens/states |
| `first-house/parent.html`, `parent.js` | Separate adult gate and adult shell |
| `first-house/prototype.css` | App tokens (foundation, from `static/css`), semantic dark-shell tokens, per-child accent, world-only theme tokens, component styles, graybox world |
| `first-house/walkthrough-check.mjs` | Headless walkthrough and accessibility checks |

## Known limits

- The layout mirrors `content/kidquest/layouts/pulau_tunas_v1.json` (content_version 1) as constants in `child.js`. If the content file changes, the prototype must change with it.
- The tab icons are SVG stand-ins for PNG icon tiles in the style of the app's tab icons; the art is out of scope.
- Graybox silhouettes only prove that the theme swap leaves footprints and hit areas unchanged. Production building art comes from the KQ-025 to KQ-029 sprite maps.
- The PIN check, session, and scoped reset are UI simulations; KQ-011 owns the real security.
- There is no audio (post-slice per PRD §11.2).
