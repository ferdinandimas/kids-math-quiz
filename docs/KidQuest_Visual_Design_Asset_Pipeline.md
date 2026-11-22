# KidQuest Visual Design and Asset Production Pipeline

**Companion PRD:** `docs/KidQuest_Build_Your_World_PRD_v1.4.md`  
**Version:** 2.0  
**Date:** 2026-11-21  
**Scope:** Child and parent information architecture, responsive interaction design, three
interchangeable MVP themes, six buildings, road and economy experiences, accessible component
system, usability validation, visual assets, and production integration

## 1. Outcome

This document converts the KidQuest visual direction into independently assignable design and
engineering work. A completed pipeline produces three visually distinct but logically identical
world packs:

- `perkampungan` — Kampung Ceria, the default.
- `kingdom` — Kerajaan Ceria.
- `city` — Kota Ceria.

A child can switch theme without changing coordinates, buildings, roads, inventory, quests, or
learning data. Designers create one visual variant per logical asset; engineers consume those
variants through validated manifests rather than theme-specific conditionals.

## 2. Locked decisions

| Decision | Contract |
| --- | --- |
| World model | One 8×8 logical square grid |
| Projection | Three-quarter/2.5D art on square interactive cells; not true isometric |
| Default theme | `perkampungan` |
| Theme access | All three available from first load; switching is free |
| Theme scope | Whole world; no mixed per-building skins in MVP |
| Theme effect | Presentation only; no economy, quest, skill, or topology variation |
| Runtime rendering | Existing Jinja, CSS Grid, vanilla JavaScript |
| Base display cell | 38–64 CSS px, responsive |
| Base export cell | 128×128 px transparent image at `@2x` |
| Runtime format | WebP; PNG fallback only where browser/testing requirements demand it |
| Source quality | Layered/vector master at least 4× target display size |
| Direction | Buildings face south unless the logical definition explicitly supports rotation |
| Animation | Optional subtle idle only; never required for understanding |
| Theme source of truth | Versioned `content/kidquest/themes.json` manifest |
| Child navigation | Dunia, Misi, Bangun, then Dompet only after parent-enabled economy onboarding |
| Parent navigation | Separate adult-gated shell; never a child tab or child-mode action |
| Onboarding | One concept at a time; Q001 quest/answer/build first, theme after house, economy from Q002 |
| Objective hierarchy | One recommended next action; explicit lock reason; at most one badge per world object |
| Financial confirmation | Exact server-authoritative amounts; Requested, Approved, and Paid remain distinct |
| Notifications/live operations | No push, streak, limited-time event, remote live-ops, or urgency badge in MVP |

Any proposal that changes a footprint, entrance, collision cell, road connection, cost, quest, or
building behavior is a product/content change, not an art variant. It must update the PRD and logical
content before asset production continues.

## 3. Visual architecture

The renderer composes the same authoritative state through a selected visual manifest:

```text
SQLite world state + logical content definitions
                    |
                    v
           theme_id + manifest version
                    |
        +-----------+-----------+
        |           |           |
     Kingdom       City       Kampung
        |           |           |
        +-----------+-----------+
                    |
                    v
 terrain -> shore/water -> roads -> shadows -> buildings/props -> semantic overlays -> UI
```

Theme manifests may supply paths, colors, texture tokens, and labels. They cannot override logical
geometry or behavior. Semantic overlays—focus, selected, valid, invalid, locked, connected,
disconnected, supply low/empty, production paused, income ready, quest available, and quest
complete—come from a shared accessible UI layer.

## 4. Experience design principles

### 4.1 Experience promise

The interface should make a child feel capable, calm, and proud. It should feel like building a
personal world through learning—not operating a dashboard, shopping application, or financial
product. At every decision point the child should be able to answer:

1. Where am I?
2. What can I do now?
3. What will happen if I continue?
4. What will it cost or change?
5. How do I go back or get help?

### 4.2 Interaction principles

- **One primary action per view.** Secondary actions are visually quieter and never compete with
  the learning/build objective.
- **Progressive disclosure.** Show the child's current task first; reveal detailed ledgers, rules,
  and parent controls only when requested or relevant.
- **No hidden gestures.** Every drag, swipe, or long press has an equivalent visible tap/click and
  keyboard action. Core placement never depends on dragging.
- **Preview before commitment.** Theme, placement, investment, purchase, refill, and cash-out flows
  show an exact preview before the authoritative mutation.
- **State before decoration.** Loading, focus, selection, validity, supply, pause, and error states
  remain clear even with images disabled.
- **Mistakes remain recoverable.** Error messages explain what happened and the next available
  action; they do not blame the child.
- **No urgency mechanics.** No expiring cash offers, streak loss, flashing warnings, countdown sales,
  or shame for an empty building.
- **Financial celebration is restrained.** Celebrate learning and creation. Do not use casino-like
  reveals, showers of money, or confetti for investment and cash-out actions.
- **No attention extraction.** MVP has no push notifications, streaks, limited-time events, remote
  live-ops banners, or badge counts designed to manufacture urgency.

### 4.3 Child and adult separation

Child and parent experiences share data and component foundations but not navigation or tone:

| Dimension | Child experience | Parent experience |
| --- | --- | --- |
| Purpose | Learn, build, understand choices | Authorize, fund, reconcile, interpret progress |
| Navigation | Four-item, icon-and-label bottom navigation | Adult-gated sections and data-focused navigation |
| Density | One task, short cards, large targets | Tables/cards with source detail and audit history |
| Financial action | Request or preview | Configure limits, approve/reject, mark externally paid |
| Tone | Warm, concrete Indonesian | Clear operational Indonesian; exact amounts and states |

Parent functions never appear as an unlocked child action. Entry to parent mode sits behind an adult
gate in the profile/menu area and visibly changes the shell so the user knows which mode is active.

## 5. Information architecture and screen inventory

### 5.1 Child navigation

The mobile child shell uses at most four persistent destinations, each with icon and text:

1. **Dunia** — world, buildings, roads, current world status.
2. **Misi** — available/in-progress/completed quests and learning challenges.
3. **Bangun** — blueprints, materials, building catalog, placement, and later road editing.
4. **Dompet** — unlocked with the economy; Available Rp, Savings, Builder Credits, Building Income,
   Store, and cash-out request history.

Before Dompet unlocks, the fourth position is not an empty tab; the three destinations remain
balanced and Dompet is introduced contextually after Q001/economy activation. Theme selection,
sound, accessibility preferences, legacy quiz navigation, profile switching, and parent entry live
under a clearly labelled menu rather than occupying the primary navigation.

### 5.2 Parent navigation

After the adult gate, the shell exposes:

1. **Ringkasan** — child cards, learning status, world/economy health, pending actions.
2. **Belajar** — attempts, skills, hints, quests, and deterministic suggestions.
3. **Ekonomi** — balances, sources, savings, supply/income projection, and funded limits.
4. **Pencairan** — requested/approved/paid/rejected/cancelled requests and external-payment audit.
5. **Pengaturan** — feature flags exposed as safe settings, limits, goals, and scoped reset/export.

Adult navigation is not theme-skinned beyond modest brand accents. Financial state colors and labels
remain stable across themes.

### 5.3 Screen inventory and release ownership

| Screen / surface | Primary job | Release |
| --- | --- | --- |
| KidQuest entry | Choose Quiz or KidQuest without hiding legacy behavior | First house |
| World Home | Inspect world, see current objective, open building | First house |
| Quest List/Detail | Understand objective, skill, reward, prerequisite, and resume state | First house |
| Challenge/Feedback | Answer explicitly, receive hint, retry, continue | First house |
| Build Catalog | See owned/locked blueprint, cost, footprint, and eligibility | First house |
| Placement Mode | Select cell, understand validity, confirm/cancel | First house |
| Session Checkpoint | Explain what changed and next available action | First house |
| Theme Picker | Preview full-world theme, compare, confirm/cancel | First house |
| Wallet Overview | Understand each balance and allowed use | Economy |
| Investment Review | Show exact Rp → Savings + Builder Credit split | Economy |
| Store/Item Detail | Buy one known material, supply, or eligible blueprint | Economy |
| Blueprint Discovery | Show meter, guarantee, eligibility, and non-duplicate award | Economy |
| Building Operations | Practice, supply, income status/history, pause reason | Productive buildings |
| Cash-out Request/Detail | Select eligible sources, review, submit, track parent status | Economy |
| Parent Overview | Show pending decisions and exceptions, not vanity metrics | Economy/insights |
| Parent Cash-out Queue/Detail | Separate approval from externally marked payment | Economy |
| Parent Limits/Ledger | Configure funded limits and inspect/reconcile sources | Economy |

Every screen requires loading, empty, success, recoverable error, offline/network-lost, disabled,
and stale-state behavior where applicable. These states are designed before polished illustration.

### 5.4 Progressive onboarding and resume

Teach one new system at the moment it first becomes useful:

| Moment | Teach | Do not introduce yet |
| --- | --- | --- |
| First world entry | Current objective and Q001 quest | Wallet, supplies, road graph, blueprint chance |
| Q001 correct | Blueprint, starter kit, and Build entry | Store or productive income |
| First placement | Valid/invalid cells and explicit confirmation | Free-form road editing |
| After first house | Theme preview from the menu; session checkpoint | Forced theme choice |
| Economy activation | Available Rp, Cash-out versus Use for World, 25/75 split | Productive-building maintenance |
| First productive building | Supply, active days, pause, and income collection | Every future supply type at once |
| First cash-out eligibility | Requested versus Approved versus Paid | Parent controls inside child mode |
| Q002 Garden sequence | 25/75 split, material purchase, Garden placement; one free starter supply pack only when income is enabled | XP blueprint shop/discovery |
| Q003 Bakery sequence | Stone, mixed material cost, road editing and entrance guidance | Income optimization by roads |
| Q004 Park sequence | Pattern activity and nonproductive community value | Supply or income expectation |
| Q005 Bridge sequence | Special-zone placement and opening the next area | Free-form bridge placement |
| Q006 Market sequence | Stock supply and multi-resource planning | Optional blueprint systems before core onboarding completes |

The World objective card contains one recommended next action. Other destinations remain available,
but the interface does not present several equal-priority prompts. Locked items always state the
specific requirement and, when possible, link to the action that satisfies it.

Leaving mid-task creates no special penalty. On return, a checkpoint states what was last completed,
what is still authoritative, and one Resume action. A tutorial that was completed is not replayed
automatically; it remains available from Help.

After an absence, show a calm **Sejak Kunjungan Terakhir** summary: completed authoritative changes,
income/supply state, and the current objective. It does not count missed days, mention a broken
streak, or use guilt language. The summary is dismissible and never covers Resume.

### 5.5 Feature-combination presentation

- Economy off: Q001 remains complete and usable; Dompet, Store, supplies, and cash-out are absent,
  not shown as broken or indefinitely locked promises.
- Economy on and cash-out off: world investment, materials, and operations may appear, while payout
  actions and language remain absent or carry a parent-controlled explanation.
- Building income off: productive buildings retain practice/world functions; supply and income
  controls are absent rather than permanently paused.
- Wallet appears only after parent-enabled economy introduction. Optional XP blueprint shop and
  Discovery Meter appear after Q006/core onboarding, not during the first-house or Garden tutorial.

The shell adapts without empty navigation slots, misleading badges, or links to unavailable routes.

## 6. Responsive application shell

### 6.1 Breakpoints and behavior

Breakpoints describe layout capacity, not particular devices:

| Range | World/UI layout |
| --- | --- |
| 360–599 px | Single-column child flow; compact top HUD; world centered; bottom navigation; contextual bottom sheets |
| 600–1023 px | World and contextual panel may sit side by side; bottom navigation remains acceptable |
| 1024 px and wider | Left navigation/objective, centered world, right contextual inspector; same action order as mobile |

The application honors safe-area insets, browser zoom, on-screen keyboards, and dynamic viewport
height. Desktop layout may reveal panels simultaneously but cannot introduce actions unavailable on
mobile.

### 6.2 Child World Home wireframe

```text
+--------------------------------------------------+
| Profile       Level / XP              Menu       |
+--------------------------------------------------+
| Current objective + one primary CTA              |
+--------------------------------------------------+
|                                                  |
|                 8 x 8 WORLD                      |
|        building badges remain tappable           |
|                                                  |
+--------------------------------------------------+
| Context card / selected building / next action   |
+--------------------------------------------------+
| Dunia        Misi        Bangun       Dompet*     |
+--------------------------------------------------+
* appears after economy introduction
```

On a phone, only the most relevant two balance chips are shown in context; the interface never tries
to fit Available Rp, Savings, Builder Credits, Building Income, wood, stone, XP, and supplies into a
single permanent HUD. The full balance explanation belongs in Dompet or the relevant purchase flow.

### 6.3 Context surfaces

- Phone uses a bottom sheet with a visible title, close/back control, drag handle as decoration only,
  and a tap/keyboard method for every action.
- Tablet/desktop uses the same content model in a side inspector.
- Destructive or irreversible actions use a review screen or modal with explicit Confirm and Cancel;
  toasts never ask for a decision.
- Bottom sheets stop below the app bar and may expand to at most 90% of the safe viewport. Internal
  scrolling does not trap keyboard focus.
- Opening a building, quest, or tile preserves world position; closing returns focus to the invoking
  object.

### 6.4 Parent responsive layout

Parent tables become labelled cards below 720 px. Amount, source, state, and action remain visible
without horizontal scrolling. Audit detail may expand within a row/card, while approve/reject and
mark-paid remain separate controls with separate confirmation copy.

## 7. Primary UX flows

### 7.1 First-house flow

```text
World objective → Q001 detail → challenge → incorrect hint/retry or correct reward
→ blueprint ready → placement preview → confirmation → constructed house → checkpoint
```

- The objective card always offers Resume rather than creating another challenge.
- Correct feedback names the earned blueprint and starter kit before offering Build.
- Placement starts with an instructional pulse on the tutorial area, not a forced animation.
- Confirmation repeats footprint and cost; success moves focus to the constructed house.
- Refresh at any step restores the authoritative state and next action.

### 7.2 Theme-switch flow

1. Open Theme from the world menu.
2. See three large cards with name, thumbnail, and selected state.
3. Selecting a card applies a local full-world preview and announces it to assistive technology.
4. **Gunakan Tema** persists; **Batal** restores the authoritative theme.
5. A failed save restores the prior theme and offers Retry without losing world position.

Theme choice never appears to charge currency. Buildings, roads, and props visibly transform
together; mixing themes is not implied.

### 7.3 Build and road flow

- Catalog cards show image, name, purpose, footprint, owned/locked status, exact cost, and missing
  requirement—not merely a grey lock.
- Selecting Build enters a visually distinct mode with Cancel always visible.
- Tap/click selects an origin cell; keyboard arrows move the preview; Enter/Space selects; Escape
  cancels.
- Validity uses shape/pattern, icon, and short text in addition to color.
- Confirm calls the server. A stale world shows what changed and returns to a refreshed preview.
- Road editing uses the same preview/confirm language and explains disconnected entrances without
  blocking learning access.
- Core buildings are unique. An owned catalog card changes to **Lihat di Dunia**, not another Build
  action. MVP exposes no Demolish, Upgrade, or Repair control.
- Construction is instant after server confirmation. Move is free and previews unchanged
  supply/income state. Road connectivity guidance does not imply an income bonus or penalty in MVP.

### 7.4 Building inspection and operations

Tapping a building opens one consistent surface:

1. Name, theme artwork, purpose, quest completion, and road status.
2. Primary **Latihan di Sini** learning action.
3. For productive buildings: supply days, production state, income ready, and pause reason.
4. Contextual **Isi Persediaan** or **Ambil Pendapatan** action when eligible.
5. History/details behind a secondary disclosure.

Empty supply is a neutral operational state, not damage. The building stays colorful and usable for
learning; a badge and panel explain how to refill.

World objects show at most one high-priority status badge: required action/error, income ready,
supply low/empty, quest state, then connectivity guidance. Lower-priority states remain in the
inspector so the map does not become competing notification bubbles.

### 7.5 Investment flow

```text
Dompet → choose amount → exact split preview → explain both destinations
→ review irreversible choice → confirm → success with ledger reference
```

Required preview copy pattern:

```text
Dari Rp1.000:
Rp250 masuk ke Tabungan.
750 menjadi Kredit Bangun.
```

The interface never calls the 25% a fee or interest. Confirm is disabled until the full split and
irreversibility explanation are visible. Success celebrates the plan, not the movement of money.

### 7.6 Store and supply flow

- Store separates Materials, Supplies, and Blueprints; it does not resemble a real-money shop.
- Each item shows one fixed Builder Credit price and what it enables.
- Purchase review shows balance before, price, and balance after.
- Supply purchase and loading are distinct: purchase adds inventory; loading names the target
  building and active-day capacity.
- If production is paused by parent limits, the UI explains that loading is unnecessary and does not
  encourage spending supply.

### 7.7 Blueprint discovery flow

- The Discovery Meter shows current progress and guaranteed threshold numerically and visually.
- Optional early discovery is described as a surprise, not as a purchasable chance.
- Reveal animation lasts briefly, is skippable, respects reduced motion, and includes the blueprint
  name/purpose as text.
- A received blueprint immediately offers View in Catalog; it does not force construction.
- No duplicate, rarity pressure, odds manipulation, or near-miss animation is permitted.

### 7.8 Child cash-out flow

1. Choose **Minta Dicairkan** from eligible balance details.
2. Select allowed source(s) and amount; unavailable/reserved value is explained.
3. Review total and the statement that a parent will pay outside the application after approval.
4. Submit request; show `REQUESTED`, not Paid or Success Payment.
5. Request detail uses a timeline: Requested → Approved → Paid, or the explicit alternate state.

Submission receives calm confirmation, not payment confetti. Approval and payment are visibly
different. A rejection explains that the amount returned to its original balance.

### 7.9 Parent cash-out flow

1. Adult gate and mode switch.
2. Queue shows child, amount, source mix, request age, and funded-budget effect.
3. Detail shows ledger sources, current balances, reserved liability, paid this month, and notes.
4. Approve or Reject with confirmation. Approval does not expose Mark Paid in the same modal.
5. After external payment, open the approved request and choose **Tandai Sudah Dibayar** with payment
   date and optional safe reference.
6. Final Paid state becomes read-only and remains in audit history.

## 8. UI design system

### 8.1 Token architecture

Use four token layers so themes cannot break semantics:

1. **Foundation:** spacing, type scale, radii, border widths, motion duration, base neutrals.
2. **Semantic:** text, surface, focus, success, warning, error, disabled, selected, valid/invalid.
3. **Theme alias:** primary, secondary, accent, world materials, decorative surfaces.
4. **Component:** button, card, chip, sheet, navigation, tile overlay, meter, ledger row.

Semantic error/success/focus colors do not change meaning across themes. Theme tokens may decorate a
component but may not override its contrast, focus, disabled, or financial-state semantics.

### 8.2 Foundation tokens

- Spacing uses a 4 px base with primary steps 4, 8, 12, 16, 24, 32, and 48 px.
- Minimum child body text is 16 px with comfortable line height; important instructions start at
  18 px. Balance numerals use tabular figures where available.
- Touch targets are at least 44×44 CSS px with at least 8 px separation for unrelated actions.
- Child cards use 12–20 px radii; parent data surfaces use more restrained 8–12 px radii.
- Focus ring is at least 2 CSS px with offset and sufficient contrast against every theme.
- Use a self-hosted, licensed font or robust system stack; no third-party font request is required at
  runtime. Indonesian diacritics, numerals, and currency strings must render correctly.

### 8.2a Consistency with the existing Kids Math Quiz (product-owner constraint)

KidQuest is part of the existing app, not a separate product. Its application shell, panels,
buttons, navigation, popups and typography must look like the current Quiz/Statistics screens, using
the real tokens in `static/css/base.css`, `home.css`, `quiz.css` and `stats.css`:

- **Dark navy base:** page `#070b14`/`#030916`, panels `#0f1730`/`#101c3b` and navy gradients, borders
  `#21305b` and `rgba(74, 137, 231, 0.65)`, text `#e9f0ff`, muted text `rgba(233, 240, 255, 0.75)`.
  No light/cream shell.
- **Per-child accents:** `althafandra` = blue (`#13bbf6`, avatar `#4ca8ff → #1765c9 → #113b8d`);
  `alleia` = purple (`#9a64d5`, avatar `#a766ec → #7149c6 → #392b83`). KidQuest reuses these as the
  active child's accent (the quiz pages already switch on `profile-theme-blue|purple`).
- **Highlights:** warm yellow/gold (`#ffbd16`, `#ffe17b`) for rewards and stars, pink/red
  (`#ff89ae`, `#ff555d`) for wrong/attention, as in the quiz popups.
- **Shape and surface:** 24 px card radius (12–20 px for inner elements, 8 px for small buttons,
  circular avatars), diagonal navy gradients with a faint top inner highlight and deep soft shadows,
  playful but tidy; the same `system-ui` font stack, bold (750–850) headings.
- **Illustration language:** reuse the existing mascots and icons (`owl-tutor`, `star-mascot`,
  `popup-reward-coin`, `reward-gift`, popup backgrounds) for feedback and rewards instead of new styles.

**Layout.** KidQuest screens reuse the existing screen anatomy so they feel like the same app:

- A header card like `.quiz-header`: round child avatar (`alleia-avatar.png` / `althafandra-avatar.png`)
  with name and level, plus a compact "today" card and link area; on phones the same stacked header.
- A main workspace panel like `.quiz-workspace` below it, with a tab row like `.quiz-tabs`
  (icon + label, active tab highlighted) used for Dunia / Misi / Bangun, and the same panel, progress
  bar, tutor-bubble (`owl-tutor`), prompt, answer box, hint line and keypad treatment for the Q001
  challenge.
- Feedback and rewards use the existing popup pattern (`popup-correct-*`, `popup-wrong-*`,
  `popup-reward-coin`, `reward-gift`, sparkles).
- Same breakpoints (620 px, 960 px, 440 px) and the same page-level behavior (`touch-action`, no
  horizontal overflow).
- Where KidQuest needs something the existing app lacks (the world grid, placement bar, theme picker),
  compose it from the same cards, buttons, radii, gradients and type.

**World canvas (natural art, product-owner clarification).** The island itself keeps the natural,
illustrated look: green ground, blue water, trees, rocks, roads and buildings in each theme pack. It is
the one place that may use light or earthy colors. The canvas sits inside a dark-navy frame like the
quiz workspace, and everything around it (header, tabs, panels, buttons, action bars, popups, the
theme picker chrome) uses the existing app's colors and layout. The PRD §11.3 per-theme "UI
character" colors apply only to accents inside the world canvas and the theme thumbnails; they must
not repaint the app shell. Contrast requirements (WCAG 2.2 AA) still apply to every token pair,
including world overlays (selection, validity, focus) on the natural ground.

### 8.3 Required components

| Component | Required states/behavior |
| --- | --- |
| App Shell / Top HUD | Child and parent modes, safe areas, compact contextual balances |
| Bottom Navigation | Selected, focus, disabled/locked explanation; icon plus text |
| Primary/Secondary/Text Button | Default, hover, pressed, focus, loading, disabled; stable width while loading |
| Quest Card | Locked reason, available, active, ready-to-build, completed |
| Building/Catalog Card | Theme image, footprint, purpose, cost, owned/locked/missing requirement |
| World Tile/Building Target | Focus, selected, valid, invalid, connected/disconnected, badges |
| Bottom Sheet / Side Inspector | Same information hierarchy across responsive modes |
| Balance Card / Chip | Name, amount, allowed use; never icon-only |
| Split Preview | Source, Savings amount, Builder Credits, total conservation |
| Store Item / Purchase Review | Fixed price, before/after balance, disabled reason |
| Supply Meter | Remaining active days, empty/low/full/paused, text equivalent |
| Discovery/XP Meter | Numeric current/threshold plus visual progress |
| Status Badge | Icon, text, stable semantic color, accessible name |
| Request Timeline | Requested, approved, paid/rejected/cancelled with dates |
| Ledger Row | Signed amount, source, state, timestamp, reference disclosure |
| Inline Alert / Toast | Alert explains outcome; toast never carries the only recovery action |
| Skeleton / Empty / Error State | Preserves layout, labels cause, offers relevant next action |

Each component is specified once at phone and desktop density, with keyboard sequence, screen-reader
name, truncation behavior, localization stress case, and all interactive states.

### 8.4 Icon and illustration rules

- Primary navigation icons use one 24 px grid, 2 px apparent stroke, rounded joins, and text labels.
- Resource/economy icons remain distinguishable in monochrome and at 20 px.
- Rupiah amounts always include `Rp` text; wood, stone, supply, XP, and Builder Credit never reuse a
  currency symbol.
- Interactive illustration never contains essential text. HTML supplies names, amounts, status, and
  actions.
- Locked, paused, empty, and error icons describe different concepts and cannot reuse one padlock.

## 9. Content design, motion, accessibility, and research

### 9.1 Child-facing terminology

| Backend/product term | Indonesian child label | Explanation pattern |
| --- | --- | --- |
| `available_rp` | Rp Milikmu | Bisa diminta untuk dicairkan atau digunakan untuk membangun |
| `savings_rp` | Tabungan | Bagian yang kamu simpan untuk nanti |
| `builder_credit` | Kredit Bangun | Hanya untuk bahan, persediaan, dan cetak biru di dunia |
| `building_income_rp` | Pendapatan Bangunan | Bisa diminta untuk dicairkan; tidak bisa dipakai mengisi persediaan |
| Supply | Persediaan | Membantu bangunan produktif bekerja selama beberapa hari aktif |
| Cash-out request | Minta Dicairkan | Orang tua membayar di luar aplikasi setelah menyetujui |

Final Indonesian strings require content review with a parent and child. Avoid `investasi` as an
unexplained promise of profit; introduce it as **Gunakan untuk Dunia** first, then teach the term in
context. Never call Savings a bank account or the 25% allocation interest.

### 9.2 Number and status formatting

- Indonesian currency uses `Rp1.000`, whole Rupiah, and no misleading decimal precision.
- Builder Credit and resources use plain whole numbers plus visible unit names/icons.
- Relative time supplements but never replaces an exact Jakarta date/time in parent audit views.
- Status labels use verbs children understand: Menunggu Orang Tua, Disetujui, Sudah Dibayar,
  Ditolak, Dibatalkan, Persediaan Habis, and Dijeda.

### 9.3 Motion and feedback

- Standard transitions target 120–220 ms; no essential state waits for animation.
- Quest/build completion may use one short celebratory motion and optional sound.
- Investment, store purchase, income collection, and cash-out use restrained confirmation without
  money showers, slot-machine motion, or near-miss effects.
- Reduced motion removes parallax, bouncing, reveal travel, and repeated ambient animation while
  preserving immediate text/icon confirmation.
- Audio is supplementary, individually controllable, and never the only instruction or feedback.

### 9.4 Accessibility and cognitive load

- Meet WCAG 2.2 AA for web UI; support keyboard, screen readers, 200% zoom, reduced motion, and
  reflow without loss of actions.
- Do not put instructions solely in placeholder text, hover, color, animation, or audio.
- Use short sentences, one instruction per step, familiar Indonesian, and examples for money splits.
- Wrong answers use neutral language and hints; red is reserved for destructive/error meaning, not
  ordinary learning feedback.
- Keep consistent button placement and terminology across child flows. Back never commits a
  mutation.
- Announce dynamic balance/status changes through an appropriate polite live region without reading
  the entire world grid again.

### 9.5 Prototype and usability research

Test structure before polished art:

1. Paper/low-fidelity walkthrough with an adult proxy for navigation and wording risks.
2. Clickable phone prototype for Q001, theme preview, placement, Wallet split, supply, and cash-out.
3. Moderated sessions with the intended household children and parent, with consent and no recording
   by default.
4. Observe task completion and comprehension; do not coach unless the child is blocked.
5. Revise flows/components, then validate the revised task before high-fidelity asset production.

Required comprehension prompts:

- “What will happen if you press this button?”
- “Where will this Rp go?”
- “Is this request already paid?”
- “Why is this building paused?”
- “Will changing the theme move or remove your building?”

Usability gate targets for the household pilot:

- At least 4 of 5 representative child tasks complete without adult correction.
- 100% of tested children distinguish Savings from Builder Credits after the split explanation.
- 100% of tested child/parent pairs distinguish Requested, Approved, and Paid.
- No child believes theme switching costs Rp or changes progress.
- Parent can find, approve, and later mark paid without confusing the two actions.

These are design gates for a small household pilot, not population-level research claims.

## 10. Theme art bibles

### 10.1 Shared style

- Friendly, optimistic, tactile, and readable for children aged 6–9.
- Rounded forms, clear value separation, restrained surface detail, and strong silhouettes.
- No weapons, realistic danger, scary ruins, commercial brands, real-money cues, or stereotyped
  cultural caricature.
- Lighting comes from upper-left at one shared angle. Shadows are soft and visually consistent.
- Doors and active entrances remain visible at minimum size.
- Decorative detail stays inside approved overhang bounds and never implies extra collision.
- Text is HTML, not baked into image assets, except approved non-verbal decorative marks.

### 10.2 Kampung Ceria

Use Indonesian village architecture as a warm, lived-in, contemporary visual language: timber,
bamboo details, clay roof tiles, stone foundations, planted edges, woven accents, baskets, and
community space. Avoid treating the village as primitive, impoverished, or tied to one regional
costume. The world should feel cared for and active.

Suggested base palette:

| Token | Starting color | Use |
| --- | --- | --- |
| `--kq-primary` | `#367A4A` | Primary action and selected theme |
| `--kq-secondary` | `#C76D3A` | Roof and warm emphasis |
| `--kq-accent` | `#F2C14E` | Reward/highlight, with dark text |
| `--kq-surface` | `#FFF4D8` | Panels |
| `--kq-ink` | `#26352B` | Text and strong outlines |

### 10.3 Kerajaan Ceria

Use storybook civic kingdom forms: warm stone, timber, colored banners, rounded towers, small
gardens, and welcoming arches. Avoid battle architecture, weapons, flags linked to real nations,
dark dungeons, or class hierarchy as a reward metaphor.

| Token | Starting color | Use |
| --- | --- | --- |
| `--kq-primary` | `#3558A8` | Primary action |
| `--kq-secondary` | `#8B4A83` | Roof/banner emphasis |
| `--kq-accent` | `#E7B93F` | Reward/highlight, with dark text |
| `--kq-surface` | `#FFF2CF` | Parchment-like panels |
| `--kq-ink` | `#252A45` | Text and strong outlines |

### 10.4 Kota Ceria

Use colorful contemporary civic forms: simple masonry, safe pedestrian paving, awnings, planters,
community gardens, broad windows, and visible entrances. Do not make traffic, cars, large roads,
pollution, advertising, or corporate branding the identity of the city.

| Token | Starting color | Use |
| --- | --- | --- |
| `--kq-primary` | `#167A91` | Primary action |
| `--kq-secondary` | `#E66A5A` | Shopfront/emphasis |
| `--kq-accent` | `#F3C64E` | Reward/highlight, with dark text |
| `--kq-surface` | `#F5FAFC` | Clean panels |
| `--kq-ink` | `#20343E` | Text and strong outlines |

The colors are starting tokens, not automatic accessibility approval. Text and interactive state
combinations must meet WCAG 2.2 AA contrast. The shared error, success, focus, and disabled tokens
remain semantically consistent across themes and include icon/text cues.

## 11. Geometry and production templates

### 11.1 Coordinate template

Every asset master uses a visible grid and metadata guide:

- Cell origin and 128×128 px cell bounds.
- Footprint rectangle and collision cells.
- Bottom-center anchor.
- Entrance anchor(s) on N/E/S/W cell edges.
- Maximum top/left/right overhang.
- Shadow-safe region.
- Interaction-safe region that cannot be hidden by decoration.
- Minimum-size preview at a 38 px cell.

Building canvases scale by footprint plus approved overhang. The image may visually extend beyond
the logical footprint, but its pointer target and collision never do. The exact canvas and anchor are
declared in the manifest, so theme variants align without per-theme CSS adjustments.

### 11.2 Layer ownership

| Layer | Owned by | Notes |
| --- | --- | --- |
| Terrain, water, shore | Theme asset | Must preserve logical mask |
| Road/path | Theme asset | Selected by 4-bit adjacency mask |
| Ground shadow | Shared CSS by default | Custom image requires explicit manifest entry |
| Building/prop | Theme asset | Transparent background |
| Placement/focus/connectivity | Shared CSS/SVG UI | Never baked into theme image |
| Quest/reward labels | HTML UI | Localized and screen-reader accessible |

### 11.3 Responsive proof sizes

Every golden asset and final building is reviewed at:

- 38 px per cell in a 360 px phone viewport.
- 48 px per cell in a common tablet/narrow desktop layout.
- 64 px per cell in the maximum world view.

An asset that looks attractive at source size but loses its entrance, category, or selection state at
38 px fails review.

## 12. Required MVP asset inventory

This inventory is exhaustive for the six-quest MVP. A thumbnail is generated from the base asset and
is not a separately illustrated file unless cropping cannot meet the catalog requirement.

### 12.1 Per-theme deliverables

| Package | Logical deliverables per theme | Count |
| --- | --- | ---: |
| Base terrain | `ground_buildable`, `water`, `blocked_tree`, `blocked_rock` | 4 |
| Shore autotile | All N/E/S/W edge masks `00`–`15` | 16 |
| Fixed interactive feature | `quest_board` | 1 |
| Road autotile | All `basic_road` masks `00`–`15` | 16 |
| Buildings | `starter_house`, `garden`, `bakery`, `park`, `bridge`, `market_stall` | 6 |
| Small plant variations | Two non-colliding variations | 2 |
| Standalone props | `bench`, `light`, `water_feature`, `signpost`, `supply_cluster` | 5 |
| Fence set | `fence_end`, `fence_straight`, `fence_corner` | 3 |
| Resource icons | `wood`, `stone` | 2 |
| Theme selector | One representative thumbnail | 1 |
| **Required total per theme** |  | **56** |

The three complete packs therefore contain 168 required theme-specific runtime assets. In addition,
the shared UI owns focus/selection/validity/connectivity/quest overlays and generic action icons.
Flipped or rotated copies may be produced at runtime only when the art lead confirms lighting and
asymmetry remain correct; otherwise each orientation becomes an explicit asset and manifest entry.

### 12.2 Shared economy UI assets

The later economy milestone adds shared, theme-independent accessible SVG/UI assets rather than
inflating each theme pack: Available Rp, Savings, Builder Credits, Building Income, XP, Blueprint,
cash-out status, Garden supply, Bakery supply, Market supply, supply-low/empty, production-paused,
and income-ready indicators. Amounts and statuses remain HTML text; no monetary value is baked into
art. Productive status uses a badge/panel, not a damaged or alternate building sprite.

### 12.3 Building visual brief

| Logical ID | Kingdom | City | Kampung | Must visibly communicate |
| --- | --- | --- | --- | --- |
| `starter_house` | Keeper's Cottage | Colorful Townhouse | Rumah Kampung | Safe home, clear south door, first achievement |
| `garden` | Royal Herb Garden | Community Garden | Kebun Tunas | Countable planting groups, accessible plot boundary |
| `bakery` | Castle Bakehouse | City Bakery | Warung Roti | Bread/oven purpose without text or brand, clear door |
| `park` | Royal Garden | City Park | Lapangan Kampung | Pattern-friendly open community space |
| `bridge` | Stone Story Bridge | Pedestrian City Bridge | Jembatan Kayu-Bambu | Two open connection ends, water-safe footprint |
| `market_stall` | Royal Bazaar Stall | City Kiosk | Kios Pasar | Countable displayed items, no cash/advertising emphasis |

For each building, the design ticket includes the matching PRD use and economic role. Garden,
Bakery, and Market may visually communicate their documented productive purpose; House, Park, and
Bridge must not imply cash generation. Decorative storytelling cannot promise an undocumented
supply, production, trading, upgrading, or payout mechanic.

Building production uses a fixed-layout sprite map generated once per theme. The shared contract
locks the same six building slots, canvas/cell dimensions, transparent padding, camera, scale,
lighting direction, anchors, entrances, shadows, and footprint metadata before any theme generation.
Kingdom, City, and Kampung each have one generation task containing all six buildings so the visual
language is consistent inside that theme. Per-building acceptance remains mandatory inside each
theme task. A separate extraction/QA task slices the maps, creates manifests, and overlays matching
building slots across themes to detect geometry drift. See KQ-025 through KQ-029 in
`KidQuest_Execution_Tasks.md`.

## 13. Road system specification

Use bits `N=1`, `E=2`, `S=4`, `W=8`. Filenames use zero-padded decimal masks. Each tile must join at
the midpoint of the relevant cell edge with matching width, color, border, and perspective.

| Mask | Connections | Shape |
| ---: | --- | --- |
| `00` | none | Isolated tile |
| `01` | N | North end cap |
| `02` | E | East end cap |
| `03` | N+E | North-east corner |
| `04` | S | South end cap |
| `05` | N+S | Vertical straight |
| `06` | E+S | South-east corner |
| `07` | N+E+S | East-facing T junction |
| `08` | W | West end cap |
| `09` | N+W | North-west corner |
| `10` | E+W | Horizontal straight |
| `11` | N+E+W | North-facing T junction |
| `12` | S+W | South-west corner |
| `13` | N+S+W | West-facing T junction |
| `14` | E+S+W | South-facing T junction |
| `15` | N+E+S+W | Four-way junction |

Road production acceptance:

- All connected edges meet with no gap or double-width seam.
- Disconnected edges read as a deliberate end, never as a clipped road.
- The path remains readable beneath selection and connectivity overlays.
- A 3×3 test map exercises every mask and a second screenshot proves theme switching leaves its
  coordinates unchanged.
- The bridge's two road anchors use the same edge width as mask connections.
- No painted path extends into an unconnected edge strongly enough to imply a connection.

## 14. Asset manifest and repository contract

### 14.1 Proposed locations

```text
content/kidquest/
  assets.schema.json
  buildings.json
  roads.json
  themes.json
design/kidquest/
  README.md
  flows/
  wireframes/
  components/
  prototypes/
  usability/decision-log.md
  templates/
  source-metadata.json
static/images/kidquest/
  shared/
  themes/
    perkampungan/{terrain,roads,buildings,props,icons}/
    kingdom/{terrain,roads,buildings,props,icons}/
    city/{terrain,roads,buildings,props,icons}/
scripts/
  validate_kidquest_assets.py
```

Large layered source masters may use Git LFS or an access-controlled design workspace after that
storage decision is made. The repository always includes export-ready runtime files, geometry
templates, a source/license record, and enough information to reproduce each export.

### 14.2 Naming

Use lowercase ASCII snake case for IDs and zero-padded masks:

```text
{asset_id}--{variant}@2x.webp
road_basic--mask_00@2x.webp
shore--mask_15@2x.webp
starter_house--base@2x.webp
small_plant--variant_02@2x.webp
```

Theme is represented by the containing directory, not duplicated in the filename. Do not use final,
new, latest, artist names, or ticket numbers in runtime filenames. Content version belongs in the
manifest and source metadata.

### 14.3 Required manifest fields

Each logical asset entry records:

- `asset_id`, `category`, `content_version`, and `required_in_themes`.
- Runtime path and optional fallback path.
- Pixel width/height and intended CSS cell dimensions.
- Footprint, anchor, overhang, collision reference, and entrance edges when applicable.
- Layer and local z-offset.
- Alpha requirement, maximum bytes, and export profile.
- Source record ID, creator, license/ownership status, review status, and checksum.
- Accessible label key for interactive objects; decorative assets are explicitly marked decorative.

The validator checks the file exists, dimensions and alpha match, byte budget is respected, hash is
current, all required themes are present, and visual variants do not redefine logical geometry.

## 15. UX, visual design, and asset production pipeline

### Stage A — Product, learning, and logical catalog freeze

Product, learning, engineering, and design approve user roles, building purpose, economy meaning,
footprints, entrances, road rules, terrain mask, child-facing terminology, and asset inventory.

**Gate:** the PRD, content definitions, task list, and source-of-truth terminology agree; every
experience and asset has an owner. Unresolved behavior stays in Remaining Decisions.

### Stage B — Information architecture and task flows

Map the child and parent navigation, screen inventory, first-house journey, theme/build/road flows,
and all later economy flows. Define state diagrams for loading, empty, error, retry, cancellation,
and refresh recovery before drawing polished screens.

**Gate:** product, engineering, learning, and parent representative can trace every task from entry
to completion without a dead end, hidden gesture, or child-accessible adult action.

### Stage C — Low-fidelity responsive wireframes

Create phone-first wireframes for every first-house screen plus representative tablet/desktop shells.
Add economy and parent wireframes before their milestones. Use real Indonesian-length strings and
worst-case amounts rather than placeholder text.

**Gate:** Q001, theme preview, placement, Wallet split, building operation, cash-out, and adult payout
flows have explicit action hierarchy, back/cancel behavior, and responsive transformations.

### Stage D — Clickable prototype and comprehension test

Prototype task transitions without backend integration. Test intended household children and parent
on the required comprehension prompts in section 9.5. Record observations, failure point, assistance,
and revised design decision without storing unnecessary child data.

**Gate:** usability targets pass on the revised prototype; children distinguish Savings from Builder
Credits and adults distinguish approval from payment. Failed tasks return to Stage B or C.

### Stage E — UI design system and content contract

Approve foundation/semantic/theme/component tokens, type and number rules, component inventory,
interactive states, Indonesian terminology, focus behavior, motion, reduced motion, and responsive
specifications. Build components in a design library and an engineering gallery using matching names.

**Gate:** components cover every state in the screen inventory; contrast and keyboard specifications
pass; no screen invents a private balance chip, button, status, or modal pattern.

### Stage F — Art direction boards

Create one board per theme with palette, shapes, materials, lighting, safe cultural references,
prohibited motifs, UI examples, and minimum-size examples. Review theme decoration beside the shared
semantic component system.

**Gate:** themes feel distinct but one product; accessibility approves token pairings; Indonesian
cultural review approves Kampung representation; financial state meaning remains theme invariant.

### Stage G — Graybox world and golden experience slice

Build the real 8×8 graybox with neutral footprints, entrances, quest board, water, roads, semantic
overlays, responsive shell, Q001 flow, and theme picker. Produce the golden non-building art set in
all themes: ground/water/shore sample, quest board, 16 road masks, `wood` icon, thumbnail, and shared
states. Buildings are not part of the golden set; a non-production graybox building study proves the
anchor and footprint rules, and production buildings come from the per-theme sprite maps (Stage H,
KQ-025–KQ-029).

**Gate:** Q001 is understandable at 360 px without final decoration; theme switch and placement pass
prototype/device tests; geometry is corrected before the building sprite-map contract is frozen.

### Stage H — Theme-pack and economy-UI production

Produce terrain/shore, buildings, props, resources, shared economy icons, and parent/child UI from
approved templates. Buildings are produced as one six-building sprite map per theme with a fixed slot
order and identical slot resolution (KQ-025 contract). Review each complete theme map for internal
consistency first, then review all three variants of each logical building side by side during
extraction QA (KQ-029). Economy UI uses HTML text and shared semantic icons rather than values baked
in art.

**Gate:** silhouette, anchor, entrance, value range, economic role, and state readability match; all
required variants and shared economy assets have review approval.

### Stage I — Export, manifest, and automated validation

Export using named presets, remove unused metadata, compress at approved quality, update source
records/checksums, and run `validate_kidquest_assets.py`.

**Gate:** zero missing assets, schema errors, geometry mismatches, oversized files, unexpected opaque
backgrounds, unowned sources, or required states absent from the component gallery.

### Stage J — In-game integration and design QA

Integrate through manifests and reusable components, not theme-specific screen branches. Verify real
API loading/error/stale/retry behavior, long labels, keyboard focus restoration, server-confirmed
financial outcomes, and child/parent mode separation.

**Gate:** implemented flows match approved prototypes or carry an approved design change; theme
switch changes presentation only; investment and payout screens match authoritative ledger state.

### Stage K — Device, accessibility, performance, and release QA

Test supported mobile browser classes, tablet/desktop layouts, keyboard, screen readers, 200% zoom,
reduced motion, on-screen keyboard, slow/offline network, corrupt/missing image fallback, and refresh
during every important mutation.

**Gate:** section 18 passes, approved screenshots and usability evidence are attached, and no critical
accessibility, comprehension, data-authority, or financial-state defect remains.

### Stage L — Release and change control

Lock component, content, and asset-manifest versions; record release notes; deploy behind the relevant
profile/feature flags. Runtime art-only changes increment the asset patch version. Geometry,
interaction, content, or behavior changes update the PRD and repeat the affected design gates.

## 16. Ticket breakdown

Create tickets in dependency order. Each leaf ticket produces one reviewable artifact or asset batch.

| Epic / package | Suggested tickets | Depends on |
| --- | --- | --- |
| UX0 Foundation | Roles; experience principles; terminology; screen inventory; task success criteria | PRD |
| UX1 Architecture | Child navigation; parent navigation; first-house/theme/build/road/economy flow maps | UX0 |
| UX2 Wireframes | Phone Q001; responsive World; Build; Wallet; building operation; parent queue | UX1 |
| UX3 Prototype/research | Clickable child prototype; parent payout prototype; moderated test; revisions | UX2 |
| DS0 Design system | Foundation/semantic/theme tokens; typography; icons; motion; content rules | UX2 |
| DS1 Components | Shell, navigation, cards, sheets, meters, balances, split, timeline, ledger states | DS0 |
| UX4 Child screens | First-house high fidelity; theme/build/road; economy and productive-building screens | UX3, DS1 |
| UX5 Parent screens | Adult gate; overview; cash-out queue/detail; limits; ledger; responsive cards | UX3, DS1 |
| V0 Visual foundation | Shared geometry templates; three art bibles; cultural review | UX3, DS0 |
| V1 Golden slice | Graybox and graybox building study; Q001 non-building assets in all themes; road sets; shared state overlays | V0, UX4 |
| V2 Terrain packs | One complete terrain/shore ticket per theme | V1 |
| V3 Building sprite maps | Shared fixed map contract; one complete six-building map per theme; extraction/cross-theme QA | V1 |
| V4 Props and icons | Theme props/resources; shared economy and state icons; selector thumbnails | V1, DS1 |
| ENG0 Tooling | Design/component gallery; manifest schema; validator; screenshot matrix; CI job | DS1, V1 |
| ENG1 Integration | Responsive shell; manifests; theme persistence; API states; focus restoration | UX4, UX5, ENG0 |
| QA0 Release | Usability recheck; device/accessibility/cultural/performance pass; release manifest | All |

Review each complete theme sprite map first for internal palette, material, light, outline, camera,
and scale consistency. During extraction QA, review each logical building across all three themes for
geometry and functional consistency. Prefer reviewing a complete task across all its component
states rather than approving isolated polished screens with missing errors.

## 17. Design and asset handoff ticket template

Every screen/flow ticket contains:

1. User, job, entry point, success condition, and release milestone.
2. Linked PRD behavior and approved flow/prototype frame.
3. Phone layout plus tablet/desktop transformation.
4. Component names, token references, content strings, number/date format, and localization stress case.
5. Loading, empty, error, retry, stale, offline, disabled, success, and cancellation behavior.
6. Pointer, touch, keyboard, screen-reader, focus-return, reduced-motion, and live-region behavior.
7. Authoritative versus preview state and the exact mutation/confirmation boundary.
8. Local-only analytics/diagnostic event if approved, excluding raw child answers and unnecessary
   PII; MVP has no third-party analytics or remote live-ops dependency.
9. Acceptance screenshots and design/content/accessibility owners.

Every asset ticket contains:

1. Logical asset ID, child-facing purpose, economic role, and PRD reference.
2. Theme(s), exact deliverable count, and required minimum-size comparisons.
3. Footprint, direction, entrances, anchor, canvas, overhang, collision reference, and render layer.
4. Required visual cues, shared semantic overlays, and prohibited implied behavior.
5. Palette/material/lighting reference and cultural-review notes.
6. Source-master location, creator, ownership/license, export preset, filename, maximum bytes, and
   manifest entry/checksum.
7. Proof at 38, 48, and 64 px per cell plus side-by-side theme parity.
8. Acceptance owner and automated/manual checks.

No handoff is complete with only a happy-path image. Design source and engineering gallery use the
same component/state/asset identifiers to make review findings traceable.

## 18. QA and acceptance checklist

### 18.1 Task comprehension and financial clarity

- [ ] Child can identify the current objective and primary action without adult correction.
- [ ] Child understands theme preview is free and does not move/remove progress.
- [ ] Child can place the starter house and recover from an invalid cell without coaching.
- [ ] Child explains that 25% goes to Tabungan and 75% becomes non-cashable Kredit Bangun.
- [ ] Child understands empty supply pauses income but not learning access.
- [ ] Child understands a submitted cash-out request is waiting, not already paid.
- [ ] Parent distinguishes Approve from Mark Paid and can find the external-payment audit history.
- [ ] No wording or motion implies a bank account, guaranteed interest, paid chance, or automatic payout.

### 18.2 Interaction and authoritative state

- [ ] Focus, selected, valid/invalid, locked, connected/disconnected, supply-low/empty,
      production-paused, income-ready, available, and completed states use icon/text beyond color.
- [ ] Preview states never alter authoritative balance, theme, building, or request state.
- [ ] Every irreversible action has exact review, Confirm, Cancel, and recoverable server-error behavior.
- [ ] Pointer/keyboard targets match logical cells rather than transparent asset overhang.
- [ ] Refresh and duplicate-network retry restore the correct server state at every flow boundary.
- [ ] Theme preview cancels without mutation; confirmed theme persists and transforms every world asset.
- [ ] Financial success UI displays server-returned amounts and request state, never client arithmetic alone.

### 18.3 Responsive and accessible

- [ ] No horizontal page overflow from 360 px upward or in parent card/table transformations.
- [ ] Touch controls are at least 44×44 CSS px with adequate separation.
- [ ] Keyboard focus order is logical; bottom sheets/modals trap and restore focus correctly.
- [ ] Screen readers describe interactive objects and ignore decorative props.
- [ ] Text and controls meet WCAG 2.2 AA; state never relies only on color.
- [ ] 200% zoom, reflow, safe areas, and on-screen keyboard preserve all actions.
- [ ] Reduced motion removes nonessential movement without removing status feedback.
- [ ] Dynamic updates announce concise changes without rereading the entire world.

### 18.4 Visual and theme parity

- [ ] All 56 required assets exist in each theme; all shared UI/economy icons exist.
- [ ] Every building has the same footprint, anchor, entrance, perceived mass, and interactive target.
- [ ] Road and shore masks connect without seams; entrances remain readable beside roads.
- [ ] Theme identity is clear, while semantic focus/error/success/financial states remain consistent.
- [ ] Buildings remain distinct by silhouette at 38 px per cell.
- [ ] Decorative assets do not look interactive or imply undocumented income/supply behavior.

### 18.5 Content and motion

- [ ] Indonesian terminology is consistent across child, parent, API-derived status, and help text.
- [ ] Currency uses whole-Rupiah Indonesian formatting; source/allowed use accompanies every balance.
- [ ] Long names, large amounts, empty values, and all request states fit without truncating meaning.
- [ ] Wrong-answer, empty-supply, limit, and rejection language is neutral and actionable.
- [ ] Financial flows use restrained feedback and no casino-like or pressure-based motion.

### 18.6 Performance and resilience budgets

Initial budgets, measured after compression:

- Selected theme's critical first-world payload: at most 650 KB before optional props.
- Complete selected theme pack: at most 2.5 MB.
- Individual 2×2 building: target at most 180 KB.
- Individual tile or road mask: target at most 32 KB.
- Non-selected selector thumbnails combined: at most 180 KB; full packs load only after selection or
  approved idle prefetch.
- At most two ambient animations run concurrently; zero with reduced motion.
- Missing/corrupt assets show an approved placeholder and diagnostic event, never an invisible control.
- Slow/offline mutation retains the idempotency key, explains status, and avoids optimistic money changes.

Budgets change only with a measured device/network report and updated validation.

## 19. Engineering verification

Required automated and repeatable coverage:

- Manifest schema, file existence, alpha, dimensions, byte size, checksum, ownership, and exactly 56
  required logical entries per theme unless the inventory version intentionally changes.
- Asset parity, all road/shore masks 0–15, bridge anchors, and building geometry across themes.
- Component gallery covers every documented state at phone and desktop density, long Indonesian text,
  large amounts, keyboard focus, reduced motion, and high-contrast proofs.
- Automated accessibility scans on stable screens plus manual keyboard/screen-reader checks for the
  world grid, bottom sheet, placement, split preview, request timeline, and parent queue.
- Theme API and preview/persist/cancel flows are idempotent and logically invariant.
- Browser tests cover Q001, invalid/stale placement, theme failure, investment review, fixed purchase,
  supply pause, income collection, child request, parent approve, and separate mark-paid actions.
- Financial UI assertions use server-returned ledger/source totals and prove approval never renders Paid.
- Screenshot matrix covers empty/loading/error/happy states, three themes, and phone/tablet/desktop.
- No runtime request loads third-party fonts, unapproved analytics, or a payment/bank integration.

## 20. Production order

1. Freeze roles, terminology, screen inventory, logical geometry, and success criteria.
2. Approve child/parent information architecture and end-to-end task flows.
3. Approve low-fidelity phone wireframes and responsive transformations.
4. Test and revise clickable Q001, theme, build, Wallet, supply, and payout prototypes.
5. Approve semantic tokens, components, content rules, focus, motion, and accessibility contract.
6. Approve three art bibles, shared geometry, neutral graybox, and golden experience slice.
7. Build the engineering component/asset gallery and validators before bulk production.
8. Freeze the building sprite-map contract, generate one six-building sprite map per theme, extract
   and cross-check all 18 building sprites, then produce the remaining terrain, props, and economy
   icons.
9. Integrate real API states and run design QA continuously rather than after all art is complete.
10. Run usability recheck, state-invariance, device, accessibility, performance, and cultural review.
11. Lock component/content/asset versions and release behind profile/feature flags.

The first-house release requires approved Q001 flows/components, the golden non-building assets, and
the 18 extracted building sprites. Economy
screens are designed early enough to validate terminology, but do not ship before their backend and
liability milestones. Q002–Q006 cannot ship with incomplete theme variants or untested operation UI.

## 21. Definition of done

The UI/UX and visual system is ready for the six-quest economy when:

- Child and parent information architecture, responsive flows, and screen inventory are approved.
- Revised prototypes pass the household usability/comprehension gates, including Savings versus
  Builder Credits and Approved versus Paid.
- Foundation, semantic, theme, and component tokens are implemented consistently in design source and
  the engineering gallery.
- Every required component includes content, responsive, loading/error/stale, keyboard, screen-reader,
  focus, reduced-motion, and authoritative-state specifications.
- Three art bibles, shared geometry, 168 runtime theme assets, and shared semantic/economy assets pass
  cultural, geometry, ownership, performance, and manifest validation.
- Each building communicates its purpose/economic role without promising an undocumented mechanic.
- All 16 road masks, bridge connections, theme transforms, build states, and supply/income states work.
- Theme switching is free, persistent, idempotent, visually complete, and logically invariant.
- Investment, purchase, supply, income, and request screens show exact server-authoritative amounts;
  parent approval never appears as payment.
- The experience works from 360 px upward, by touch and keyboard, with WCAG 2.2 AA contrast, screen
  reader labels, 200% zoom, reflow, and reduced motion.
- Galleries, prototypes, research notes/decisions, source metadata, screenshot matrix, validators, and
  release manifests are stored in the approved project/design locations.
