# Product Requirements Document
# KidQuest: Build Your World

**Version:** 1.4  
**Date:** 2026-11-21  
**Status:** Repository-grounded draft for implementation  
**Product type:** Mobile-first educational world-building web game  
**Initial audience:** Children aged 6–9 in a supervised household pilot  
**Delivery strategy:** Incremental enhancement of Kids Math Quiz; no rewrite

## 1. Executive summary

KidQuest expands the existing Kids Math Quiz into a mathematics-focused world-building and financial
choice experience. Children solve contextual challenges, earn tracked Rp rewards and XP, decide
whether to request cash-out or invest part of those rewards into their world, acquire blueprints,
and construct persistent structures. Selected productive buildings require quiz-funded supplies and
generate bounded, cash-out-only income while active. The visible world consequence and money choice
are part of the learning interaction, not unrelated reward screens.

The first release is intentionally narrow: one child selects the KidQuest entry point, completes
`Q001`, earns exactly enough wood and one blueprint, places a starter house, refreshes the page, and
sees the same state. This loop must be safe under duplicate and concurrent requests before more
quests or richer artwork are added.

**Core promise:** Learn mathematics by building a world that is uniquely yours.

## 2. Product principles

1. **Learning is gameplay.** Every core quest connects the mathematical reasoning to a visible
   world need.
2. **Create, do not grind.** Progress comes from bounded quests, not repeating trivial questions for
   unlimited currency.
3. **Mistakes are safe.** Incorrect answers offer a hint and retry without removing resources.
4. **Children have agency.** The child chooses valid placement within age-appropriate boundaries.
5. **Existing behavior remains available.** Math, general-knowledge, statistics, and historical data
   continue to work throughout rollout.
6. **Server state is authoritative.** The browser may preview, but cannot decide correctness,
   rewards, balances, quest state, or valid placement.
7. **Privacy is the default.** No public profiles, advertising, chat, location data, or third-party
   child analytics.
8. **Ship vertically.** Complete and verify one learning-to-building loop before expanding content.
9. **One world, many looks.** Themes change presentation only; they never fork progression,
   topology, costs, coordinates, or learning behavior.
10. **Readable before decorative.** Footprints, entrances, paths, selection states, and interactive
    objects remain understandable at 360 px before visual detail is added.
11. **Money is explainable.** Every Rp, saving allocation, conversion, purchase, supply use,
    building-income credit, reservation, approval, and payout has a visible immutable ledger source.
12. **Cash-out remains parent controlled.** The application tracks requests and decisions; a parent
    pays outside the application and records completion. No bank or payment gateway is integrated.
13. **No self-funding loop.** Building income is cash-out only. Supplies must be funded from money
    earned by answering quizzes, so a building cannot fund its own operation indefinitely.

## 3. Verified repository baseline

This section supersedes unverified baseline claims from version 1.0.

### 3.1 Runtime and delivery

- Python FastAPI application with importable entrypoint `app.main:app`.
- Jinja templates with vanilla JavaScript and CSS; no SPA or game framework.
- SQLite database configured by `DB_PATH` and persisted on a Railway volume.
- Seven versioned, idempotent migrations run during image startup and application startup.
- Docker/Railway deployment uses a single Uvicorn process and `/health` health check.
- PWA manifest is present; the service worker contains no caching strategy, so offline support is
  not implemented.

### 3.2 Profiles and sessions

- Exactly two configured child identifiers: `althafandra` and `alleia`.
- Profile selection is stored against a random server-side session ID in the `math_sess` cookie.
- The cookie is `HttpOnly` and `SameSite=Lax`; it currently has no `Secure` flag or explicit expiry.
- Profile selection is household-trust based, not authenticated identity.
- Statistics for both children are currently visible without an adult gate.

### 3.3 Learning content

- `alleia` uses Math bank version 1: addition and subtraction.
- `althafandra` uses Math bank version 2: addition, subtraction, multiplication, and division.
- Each Math bank contains 400 deterministic questions generated per child and calendar day.
- General Knowledge is a separate quiz type with 200 validated multiple-choice questions.
- Daily banks are persisted, and one unfinished question is retained per session, child, and quiz
  type.
- Difficulty selection uses seven-day aggregate accuracy and served count, not per-skill evidence.
- Question payloads do not expose the answer; answer validation is performed on the backend.

### 3.4 Existing rewards and limits

- Math correct-answer reward: Rp50.
- General Knowledge correct-answer reward: Rp100.
- General Knowledge consumes two daily answer quota units; Math consumes one.
- Current daily quota is 400 units per child.
- These cash-style values remain legacy statistics and are never converted to KidQuest resources.

### 3.5 Existing compatibility surface

The following must remain usable:

- `GET /`, `/start`, `/home`, `/home/{child}`, `/quiz`, `/quiz/{quiz_type}`, `/stats`
- `GET /api/question`, `/api/stats`, `/health`
- `POST /api/answer`, `/api/admin/clear`
- `GET /manifest.json`, `/manifest.webmanifest`
- `/static/*`

`POST /api/logout` is mentioned in the legacy requirements but is not implemented. KidQuest work
must not silently claim that it exists; it may be added separately as a compatibility improvement.

## 4. Current constraints that shape the design

### 4.1 Mutation safety

Current answer processing validates the active question, increments answered count, increments
correct/reward totals, and clears the current question through separate SQLite connections and
commits. That flow is not safe as the basis for KidQuest resource awards: concurrent submissions
can both pass validation before the active question is cleared.

Before a reward-bearing KidQuest answer ships, answer acceptance, attempt recording, quest
progression, one-time reward credit, legacy daily counter reconciliation, and idempotency response
storage must share one database transaction.

### 4.2 Calendar

Current code relies on the server's `date.today()`. KidQuest and legacy day boundaries must use an
explicit `Asia/Jakarta` clock so Railway container timezone cannot change daily behavior.

### 4.3 Test baseline

The repository has no automated test suite. Characterization tests for existing migrations, quiz
issuance, answer validation, profile isolation, and statistics are a release prerequisite.

### 4.4 Adult authorization

The existing admin password is insufficient for a parent dashboard. The household pilot will use a
separate adult gate: a configured PBKDF2 password/PIN hash and an HMAC-signed, `HttpOnly`, `Secure`
in production, `SameSite=Strict`, short-lived adult session cookie. Public launch requires a
separate privacy and authentication review.

## 5. Goals and non-goals

### 5.1 First playable goals

- Preserve both profiles, all historical aggregates, both quiz types, and existing routes.
- Lazily initialize one independent 8×8 island for each child.
- Complete `Q001` using a contextual subtraction challenge.
- Provide a nonpunitive hint and retry after an incorrect answer.
- Credit wood and a starter-house blueprint exactly once.
- Place one 2×2 starter house inside a restricted tutorial area.
- Preview and select Kampung, Kingdom, or City without changing world progress.
- Restore quest, inventory, and building state after refresh or process restart.
- Make duplicate and concurrent answer/placement requests safe.
- Keep the original quiz visible as a separate navigation choice.

### 5.2 MVP pilot goals

- Expand to the first six buildings and quests after the vertical slice is stable.
- Track skill-tagged attempts and hint usage.
- Give an adult an understandable seven-day child progress view.
- Allow buildings to move without a resource refund or extra cost.
- Add the free, connectivity-guidance road system and Q005 bridge without making roads a learning
  access blocker.
- Let children choose between requesting cash-out of eligible earned Rp and investing earned Rp
  through a transparent 25% savings / 75% Builder Credit split.
- Track parent-approved, externally paid cash-out without integrating a bank or payment gateway.
- Introduce XP, level, blueprint, supply, and bounded productive-building income after Q001 is
  stable and the parent has enabled a funded cash-out budget.
- Validate all content definitions during startup and CI.

### 5.3 Non-goals

No multiplayer, public leaderboards, chat, child-to-child trading, advertising, purchased currency,
payment gateway, bank transfer, custody account, 3D graphics, procedural worlds, live LLM-generated
child content, social integration, quest authoring UI, full offline operation, multiple islands, or
free-form profile creation in the first pilot.

## 6. Target users and access model

### 6.1 Child learner

- Selects one of the two existing household profiles.
- May see and mutate only the selected child's KidQuest world.
- Uses large touch controls, short Indonesian instructions, visible hints, and explicit answer
  submission.
- Cannot access cross-child reporting or destructive administration without adult authorization.

### 6.2 Parent or guardian

- Enters the adult gate before viewing both children together or changing settings.
- Sees seven-day learning evidence, hint usage, completed quests, and a concrete practice
  suggestion.
- Confirms destructive operations by scope; clearing legacy quiz history and clearing KidQuest game
  state are separate explicit actions.
- Enables or pauses cash-out, configures a funded monthly liability limit, reviews reserved and
  projected liability, approves/rejects requests, pays outside the application, and marks approved
  requests paid with an optional note/reference.
- Configures savings goals and any explicitly parent-funded Savings Bonus. The application never
  represents the savings balance as a bank deposit or promises bank interest.

### 6.3 Operator

- Maintains versioned content files and deployment configuration.
- Backs up and restores SQLite data.
- Does not author live child-facing content through an admin UI in the MVP.

## 7. Core game loop

1. Open the active child's world.
2. Select an available quest.
3. Read or listen to a short contextual objective.
4. Start or resume a backend-issued challenge.
5. Submit explicitly.
6. If incorrect, see a hint and retry the same challenge.
7. If correct, receive the quest reward exactly once.
8. Preview an unlocked structure on the grid.
9. Confirm a valid placement.
10. See persistent world change and the next quest state.
11. After economy unlock, choose whether eligible earned Rp is requested for cash-out or invested.
12. Use Builder Credits for known materials, blueprints, or productive-building supplies.
13. Maintain productive buildings and collect bounded cash-out-only income for external parent
    fulfillment.

Exploration, inventory inspection, and moving an existing building do not consume the learning
quota. Only accepted challenge attempts do.

### 7.1 Session structure and return flow

KidQuest does not impose a fixed session length. Content is designed for a useful 5–10 minute visit
with natural stopping points after a challenge, quest reward, placement, refill, or collection.

On entry or return, the server restores the exact authoritative state and the UI presents:

1. A calm **Sejak terakhir bermain** summary containing only actual completed changes.
2. Exactly one recommended next objective.
3. A single Resume/Continue action when a challenge, placement, or tutorial is incomplete.
4. Secondary, non-urgent supply/income information without interrupting the learning objective.

Recommended-objective priority is: resume accepted unfinished challenge; finish `READY_TO_BUILD`
placement; continue the current core quest; start the next unlocked core quest; then optional
practice, maintenance, customization, or exploration. The interface does not present several red
badges competing for attention.

Every authoritative mutation is saved immediately. There is no manual Save action. Closing the
browser, losing network, or changing device width does not reset tutorial or quest progress. A
network-uncertain mutation enters **Memeriksa perubahan** and resolves through state refresh and the
original idempotency key rather than asking the child to repeat payment or construction blindly.

### 7.2 Guidance, locks, and stopping points

- Locked content states the concrete requirement: quest, level, blueprint, material, parent setting,
  area, or feature milestone. A grey padlock alone is insufficient.
- Tutorials are contextual, skippable after first completion, and never replay automatically after
  refresh. Help remains available from the relevant screen.
- A session checkpoint names what changed, what is safe to do later, and the next available action.
- Optional maintenance never replaces the primary learning CTA or blocks access to building-based
  practice.
- The child may leave after any committed mutation without losing the reward or being penalized.

### 7.3 Retention and content-operation boundary

The MVP has no streaks, login bonuses, push/email reminders, missed-day loss, limited-time offers,
rotating scarcity, seasonal passes, or remote live-operations console. Return motivation comes from
the persistent world, visible next quest, optional customization, and up to three safely accumulated
productive days. New quests, assets, economy rules, and events ship as reviewed versioned content,
not unreviewed remote changes.

## 8. First vertical slice: Q001

### 8.1 Quest definition

| Field | Value |
| --- | --- |
| ID/version | `Q001` / `1` |
| Title | Rumah Pertama |
| Skill | `SUB_BASIC` |
| Challenge type | Numeric answer |
| Story | Ten wood planks are needed; six are available |
| Expected reasoning | `10 - 6 = 4` |
| Correct reward | 4 wood plus `starter_house` blueprint |
| Completion | Starter house successfully placed |
| Prerequisite | None |

The first challenge is curated content, not a random legacy-bank question. It may reuse a shared
numeric validator, but it has its own challenge instance and retry semantics.

### 8.2 World and placement

- World size: 8×8 logical cells.
- Starter layout version: `pulau_tunas_v1`.
- Q001 placement uses a configured tutorial area rather than all buildable cells.
- Starter house footprint: 2×2.
- Rotation: fixed at `0` for the vertical slice.
- Placement validates bounds, buildable cells, tutorial area, blueprint, cost, and collisions.
- Invalid placement changes nothing and returns an actionable error.
- Successful placement spends four wood, creates one building, and completes Q001 atomically.

### 8.3 Daily limit

KidQuest has a separate configurable accepted-attempt cap, proposed default `20` per child per
Jakarta day. Every accepted incorrect or correct attempt counts once. Replaying an idempotency key
does not count again. Reaching the cap disables new rewarded attempts but leaves world inspection,
inventory, and building movement available. The legacy 400-unit policy remains unchanged initially.

### 8.4 Q001 completion handoff

Q001 deliberately teaches only entry, quest detail, explicit answering, safe retry, reward,
blueprint, placement, and persistence. It does not introduce Wallet, store, supplies, income, roads,
XP choices, or blueprint discovery.

After the house checkpoint:

1. The child may preview and select the three free themes; the theme system was technically
   available but is introduced only now to avoid first-session choice overload.
2. Legacy Quiz remains visibly available.
3. If the parent has not enabled the economy, the world remains complete at Q001 and explains that
   the next building is not yet enabled—without presenting an impossible task.
4. If the economy is enabled, Q002 becomes the next recommended objective and its contextual flow
   introduces the first investment/material purchase.

## 9. Progression and economy

### 9.1 Quest state machine

`LOCKED → AVAILABLE → IN_PROGRESS → READY_TO_BUILD → COMPLETED`

- Transitions are monotonic and backend validated.
- `Q001` begins `AVAILABLE` on initial world creation.
- Correct challenge completion moves Q001 to `READY_TO_BUILD` and grants its reward once.
- Successful starter-house placement moves Q001 to `COMPLETED`.
- A repair command may correct invalid state, but normal APIs cannot move a quest backward.

### 9.2 Value buckets and ownership

Every balance is server-authoritative, nonnegative, and backed by an immutable ledger. Child-facing
screens show where value came from, what it can become, and whether it can be requested as cash.

| Balance | Source | Allowed use |
| --- | --- | --- |
| `legacy_rp` | Opening snapshot of historical pre-economy rewards | Invest into the world; cash-out only after explicit parent migration approval |
| `available_rp` | Eligible correct quiz/KidQuest answers after economy activation | Request cash-out or invest into the world |
| `savings_rp` | 25% of each confirmed world investment | Cash-out after its goal/date or parent approval; cannot buy game items |
| `builder_credit` | 75% of each confirmed world investment | Buy wood, stone, supplies, and eligible known blueprints; never cash-out |
| `building_income_rp` | Bounded daily income from an active supplied productive building | Cash-out only; cannot buy supplies or be reinvested |
| `wood`, `stone` | Purchased with Builder Credits; Q001 starter kit is the exception | Construct buildings with an unlocked blueprint |
| Supply inventory | Purchased with Builder Credits earned from quiz-funded investments | Operate its matching productive building for configured active days |

The existing Rp50 Math and Rp100 General Knowledge rewards remain the initial earning inputs, but
eligibility and caps are configuration. Incorrect answers do not earn Rp. Every accepted answer has
one unique earning source so retries and concurrent submissions cannot credit twice.

### 9.3 Invest-or-cash-out choice

From `available_rp`, a child may:

1. Request cash-out of an eligible amount, subject to adult approval and remaining funded budget; or
2. Confirm a world investment. Exactly 25% moves to `savings_rp` and 75% becomes
   `builder_credit` in one transaction.

The UI shows the exact split before confirmation. Conversion denominations must divide cleanly into
whole Rupiah; the initial denomination and minimum are selected during economy calibration rather
than hard-coded into client code. A confirmed investment is not reversible. The 25% is an automatic
savings allocation, not interest and not a fee.

An optional **Savings Bonus** may later add parent-funded value to `savings_rp` on a published
schedule. It is recorded separately from the child's principal, is disabled by default, and is
never described as a bank account or guaranteed bank interest.

### 9.4 Resource and store rules

- Q001 remains a simple onboarding exception: its first correct completion guarantees the
  `starter_house` blueprint and a four-wood starter construction kit so the first house does not
  require an economy tutorial.
- From Q002 onward, construction materials normally come from Builder Credit purchases. Exact wood,
  stone, blueprint, and supply prices are versioned content tuned through simulation.
- A purchase names the exact item and price. There are no mystery resource packs, paid random
  chances, dynamic child-specific prices, countdown pressure, or real-money purchases.
- Owning materials never bypasses progression. A valid blueprint, prerequisites, footprint, and
  placement are still required.
- Resources, supplies, blueprints, and Builder Credits cannot be transferred between children.

### 9.5 XP, levels, and blueprint acquisition

XP is separate from money. It records learning progression and cannot be spent or cashed out. XP is
awarded from accepted learning actions and quest completion; answer speed is not used and hints do
not remove already earned XP.

Blueprint sources:

1. **Quest guarantee:** all progression-critical buildings are granted deterministically by their
   related quest.
2. **Level choice:** configured XP levels offer a choice from eligible optional blueprints.
3. **Blueprint shop:** the child buys a known eligible blueprint for a fixed Builder Credit price.
4. **Discovery meter:** accepted correct answers add progress; reaching the published threshold
   guarantees a non-duplicate optional blueprint. A transparent early-discovery chance may be added,
   but it cannot include progression-critical blueprints or be purchased with any currency.

Duplicate blueprints are never awarded. A blueprint catalog declares prerequisite level, source
eligibility, fixed price if purchasable, discovery eligibility, and duplicate fallback.

### 9.6 Productive buildings, supplies, and income

The first six buildings have two economic roles:

- **Infrastructure/community:** Starter House, Park, and Bridge provide world, learning, access, or
  creative benefits and do not directly generate cash-out income.
- **Productive:** Garden, Bakery, and Market Stall may generate configured `building_income_rp` only
  while built, unlocked, supplied, and not administratively paused.

Productive-building rules:

- Supplies are building-specific and may be purchased only with Builder Credits originating from
  quiz-earned investment. Savings and building income can never fund supplies.
- Initial supply capacity is proposed as three active Jakarta days. Supply is consumed once for each
  day on which income is successfully credited, not merely because midnight passed.
- Income credits use unique `(child, building_id, Jakarta day)` sources and are calculated by the
  server. Refresh, retry, and concurrency cannot credit a second daily income.
- Uncollected income may accumulate for up to three active days. There is no streak loss, urgent
  countdown, or requirement to open the application every day.
- When supply is empty, income pauses and the building remains usable for its learning activity.
- When the parent's funded liability budget is exhausted or cash-out is paused, income pauses and no
  supply is consumed. The child sees a neutral explanation rather than a failure or punishment.
- Building Income is cash-out only and cannot purchase its own supply. Continued production
  therefore requires continued quiz-funded choices.
- Construction cost, supply cost, supply duration, gross daily income, accumulation cap, and
  activation requirements are versioned economy content and identical across visual themes.

### 9.7 Trackable manual cash-out

The application never sends money. It records a request for a parent to pay outside the application.

`REQUESTED → APPROVED → PAID`, with terminal/alternate `REJECTED` and child/parent `CANCELLED`
transitions where allowed.

- A request may reserve eligible `available_rp`, matured/approved `savings_rp`, and
  `building_income_rp`. `legacy_rp` is excluded unless a parent explicitly migrates it.
- Request creation atomically reserves the source amounts so they cannot also be invested, spent,
  or included in another request.
- Approval does not mean payment. Only the adult can mark an approved request `PAID` after paying
  externally and may store a non-sensitive note/reference.
- Rejection or eligible cancellation atomically releases the exact reserved amounts to their
  original balances.
- Every transition records actor, Jakarta timestamp, source breakdown, prior/new state, and audit
  reason. Paid requests are immutable and never silently deleted.
- Parent views show available funded budget, reserved liability, paid this month, projected
  productive-building liability, and the maximum configured limit before approval.

### 9.8 Economy calibration and liability limits

Exact exchange rates and productive-building income are not locked until a simulator covers light
(5 correct/day), regular (15/day), heavy (50/day), historical-balance, and all-building scenarios
over 7, 30, and 90 days.

The deterministic simulator engine may be implemented before the pilot as isolated, non-production
core tooling. Its bundled parameters must be labelled draft, must not be imported by application
runtime code, and cannot authorize wallet, price, income, or liability values. Final calibration and
approval still require M6/Q001 observation and the parent-funded liability policy.

Draft sensitivity tooling may compare and rank parameter combinations before the pilot, but rankings
are decision support rather than approval. The analysis must expose its axes, integer rounding,
target penalties, warning counts, and baseline comparison; it cannot silently promote a candidate to
production configuration.

Initial product targets:

- Q001 remains completable in one short session without conversion.
- The first productive building requires roughly 3–5 normal learning sessions.
- One supply pack requires meaningful practice without encouraging trivial-question grinding.
- A productive building reaches illustrative payback only after approximately 14–30 active days;
  final values require parent liability approval.
- Parent-configured daily/monthly cash-out eligibility and building-income limits are enforced before
  value is credited, not only when withdrawal is requested.
- If a limit would prevent income, the system does not consume supply.
- The child sees whether a reward is cash-out eligible before making a financial choice.

### 9.9 First six content targets

| Quest | Building | Skill | Initial cost | Economic role / supply |
| --- | --- | --- | --- | --- |
| Q001 Rumah Pertama | Starter House 2×2 | SUB_BASIC | 4 starter-kit wood | Infrastructure; no supply or income |
| Q002 Kebun Tunas | Garden 2×2 | COUNT_GROUPS | 2 wood | Productive; seeds/water pack |
| Q003 Toko Roti | Bakery 2×2 | ADD_BASIC, SUB_BASIC | 3 wood, 1 stone | Productive; ingredients pack |
| Q004 Taman Warna | Park 2×2 | PATTERN_BASIC | 2 wood, 2 stone | Community; no supply or income |
| Q005 Jembatan Kecil | Bridge 1×2, special zone | SUB_BASIC | 3 wood, 2 stone | Infrastructure; no supply or income |
| Q006 Pasar Ceria | Market Stall 1×1 | ADD_BASIC | 2 wood, 1 stone | Productive; stock pack |

Only Q001 is required before the first playable release. COUNT_GROUPS and PATTERN_BASIC require
separately authored and validated content; they are not supported by the legacy arithmetic bank.

### 9.10 Economy and building-usage boundary

- A productive building creates no income while empty, paused, outside its activation rules, or
  blocked by a funded liability limit.
- Tapping any completed building still opens its quest memory, world interaction, or replayable
  practice activity even when production is paused.
- Theme choice is free. Switching theme never spends resources, consumes supply, changes income,
  moves an object, resets a quest, or changes a child's ledger or learning record.
- The six structures in section 11.7 are the exhaustive MVP building catalog. A new structure must
  add logical, learning, visual, economy, supply, liability, and acceptance-test definitions before
  it can be scheduled.

### 9.11 Core quest teaching ladder

Core quests are linear for the first household pilot so each new system is taught once before it is
combined with another. Every core blueprint remains guaranteed.

| Quest | Prerequisite | New concept taught | Completion and handoff |
| --- | --- | --- | --- |
| Q001 House | None | Quest, challenge, retry, starter kit, blueprint, placement, persistence | Place House; introduce free theme choice |
| Q002 Garden | Q001; economy parent-enabled | Exact 25/75 investment preview, Builder Credit, known wood purchase, Garden placement | When income is enabled, load one free starter seeds/water pack; otherwise keep Garden practice-only |
| Q003 Bakery | Q002 | Stone purchase, mixed construction cost, Bakery supply, road placement/connectivity guidance | Place Bakery and connect/inspect a first road without income penalty |
| Q004 Park | Q003 | Pattern challenge and nonproductive/community building value | Place Park; reinforce that useful buildings need not generate cash |
| Q005 Bridge | Q004 | Special-zone placement and infrastructure unlocking space | Place Bridge; open the configured next build area |
| Q006 Market | Q005 | Multi-resource planning, stock supply, comparison practice, second productive-building pattern | Place/supply Market; complete core onboarding |

The free Q002 starter supply pack teaches operation without requiring a second immediate conversion.
It has no cash value, cannot transfer, and is credited once. If building income is disabled when the
Garden is placed, the pack is deferred and credited once when the parent later enables a valid funded
income mode. Optional blueprint Shop and Discovery interfaces unlock only after Q006 so chance,
level, and store choices cannot distract from core onboarding. XP may be recorded earlier, but
optional blueprint decisions are not surfaced early.

### 9.12 Feature-mode combinations

| Enabled mode | Child experience |
| --- | --- |
| KidQuest off | Existing Quiz/statistics only; no usable KidQuest mutation surface |
| KidQuest on, economy off | Q001, themes after House, world inspection/movement; Q002 explains parent enablement |
| Economy on, cash-out off | Q002–Q006 construction economy may run; investment preview states Savings cannot yet be requested; no cash-out CTA |
| Economy + cash-out on, building income off | Earn/invest/request flow is available; productive buildings remain practice-only and need no supply |
| Economy + cash-out + building income on | Full supplied productive-building and manual payout flow within funded limits |

Building income cannot be enabled without economy, adult authorization, cash-out, and funded limits.
The server rejects invalid flag combinations at startup/readiness. Disabling a later feature hides
new mutations but preserves balances, requests, supplies, buildings, and audit history.

### 9.13 Building lifecycle and instance limits

- Each of the six core building types may be constructed at most once per child. This preserves
  world readability and prevents productive-building income multiplication.
- Construction completes immediately after the authoritative placement transaction; there are no
  real-time construction timers or pay-to-skip behavior.
- A placed building may move for free after movement unlocks. Moving retains its blueprint,
  operation state, loaded supply, income history, and daily uniqueness; it creates no refund or new
  reward.
- Theme and road connectivity never change supply consumption or income rate in the MVP. Roads are
  spatial guidance/infrastructure, not an economic multiplier.
- Core buildings cannot be sold, demolished, duplicated, upgraded, damaged, or repaired in the MVP.
  These absent actions must not be implied by UI or assets.
- Road segments remain free to place/remove after unlock and do not produce refunds or income.

### 9.14 Optional progression after core onboarding

After Q006, the child may receive level-choice blueprints, use the known-price Blueprint Shop, and
progress the guaranteed Discovery Meter for optional non-duplicate structures. These systems extend
creative choice but cannot gate the six core quests, alter cash-out eligibility, increase core
building instance limits, or introduce stronger income without a new PRD/economy version.

Optional content follows the same no-FOMO rules: no expiring blueprint, paid random chance,
near-miss animation, forced daily visit, or unannounced balance change.

## 10. Learning behavior

### 10.1 Challenge types

- First release: numeric answer with contextual illustration.
- Later MVP: multiple choice, count objects, and arrange pattern.
- All prompts, visual quantities, answer keys, skills, and hints are versioned content.
- Indonesian is the default language.
- No unsupervised generated child-facing content.

### 10.2 Incorrect answer

- Do not credit resources or advance quest status.
- Record one attempt and hint usage separately.
- Return a contextual hint without returning the final answer immediately.
- Allow another explicit submission against the same active challenge until it is completed,
  expired, or the daily cap is reached.
- After repeated mistakes, provide a worked visual decomposition; never remove prior resources.

### 10.3 Skill evidence

The first release records skill, difficulty, correctness, hint count, content version, and time for
every accepted attempt. Per-skill adaptation remains behind `KIDQUEST_ADAPTIVE_ENABLED` until enough
evidence and tests exist. Speed is not used as a punitive input.

## 11. Screens and interaction

### 11.1 Child screens

1. Existing Profile Select, enhanced with separate **Quiz** and **KidQuest** entry choices.
2. World Home with 8×8 CSS Grid, resource summary, Q001 spotlight, and legacy quiz navigation.
3. Quest Detail with story, objective, skill, reward, and start/resume action.
4. Math Challenge with illustration, numeric input, hint, and explicit Submit.
5. Feedback with retry or Continue.
6. Build Mode with tap-to-select placement and explicit confirmation.
7. Minimal session checkpoint after house placement.
8. Later MVP Wallet with source-labelled Available Rp, Savings, Builder Credits, Building Income,
   exact investment preview, and cash-out eligibility.
9. Blueprint/Store with guaranteed progression sources, fixed known prices, and Discovery Meter.
10. Productive Building panel with supply days, income history, pause reason, and refill action.
11. Cash-out Request detail with reserved sources and parent decision/payment status.

### 11.2 Accessibility

- Work from 360 px viewport width without horizontal overflow.
- Touch targets are at least 44×44 CSS px.
- Grid cells and buildings have screen-reader labels and keyboard focus behavior.
- Correctness never relies only on color.
- Respect `prefers-reduced-motion`.
- Audio prompts are optional post-vertical-slice enhancement; text is always present.

### 11.3 Theme system

KidQuest has one logical world and three interchangeable visual themes. All themes are available
from the first world load and remain free to switch. `perkampungan` is the default because it gives
the product a warm Indonesian identity; the child may select any theme from World Settings.

| Theme ID | Child-facing name | Art direction | Road treatment | UI character |
| --- | --- | --- | --- | --- |
| `perkampungan` | Kampung Ceria | Indonesian village forms, timber, bamboo details, clay tile roofs, gardens; respectful and contemporary rather than caricatured | Packed earth with embedded stone and grass edges | Warm earth, leaf green, woven-pattern accents |
| `kingdom` | Kerajaan Ceria | Friendly storybook stone, timber, banners, rounded towers; no weapons, conflict, or threatening fortifications | Rounded cobblestone with moss edge | Royal blue, berry, warm gold, parchment |
| `city` | Kota Ceria | Bright, clean civic architecture, colorful shopfronts, planters, safe pedestrian spaces; no dangerous traffic imagery | Paved pedestrian street with curb/sidewalk detail | Sky blue, coral, teal, clean light panels |

Theme rules:

- A theme is a complete skin for terrain, roads, buildings, props, resource icons, and world UI.
- All variants of one logical asset share its footprint, collision mask, entrance edge, anchor,
  orientation, interactive behavior, and approximate silhouette mass.
- MVP does not allow mixed per-building themes. The selected `theme_id` applies to the whole world.
- Previewing a theme is local and reversible. Confirming it persists through the backend; failed
  persistence restores the authoritative theme and shows a retry action.
- Fallback order is selected-theme asset, approved neutral placeholder, then a visible development
  error. CI rejects a release manifest with a required theme asset missing.
- High-contrast focus, placement validity, correctness, lock state, and connectivity are semantic
  UI overlays. They are not baked into theme artwork and never rely on color alone.
- Day/night, weather, seasons, damage states, and theme-specific gameplay are outside the MVP.

### 11.4 World projection, grid, and render layers

- The authoritative map is an 8×8 square grid. Artwork uses a friendly three-quarter, 2.5D look,
  but interaction and collision remain square cells rather than a true isometric coordinate system.
- Tile display size uses `clamp(38px, 10vw, 64px)` so eight cells fit a 360 px viewport without
  horizontal scrolling. The grid may be visually centered inside a larger desktop scene.
- Touch-target exception (product owner decision, 2026-11-21): world grid cells may be smaller than
  44×44 CSS px (38 px at 360 px). Placement must therefore never depend on precise cell tapping: a
  selected placement is adjustable with ≥44 px nudge controls and keyboard arrows, and nothing changes
  until an explicit ≥44 px confirm. Every other interactive target keeps the 44×44 minimum.
- The base authored/export tile is 128×128 px at `@2x`, displayed at up to 64×64 CSS px. A building
  may overhang its footprint only inside the asset manifest's bounding box; its anchor is
  bottom-center of the occupied footprint.
- Render order is: terrain, water/shore, paths, ground shadows, buildings, props, interaction
  overlays, then screen UI. Objects in the same layer are ordered by their footprint's lowest row.
- Buildings must remain identifiable by silhouette at the minimum tile size. Small decoration may
  not hide entrances, quest markers, resource counts, or placement feedback.
- The first playable may use deliberately simple approved graybox art, but it must use the same
  dimensions, anchors, manifests, and layer rules as final art.

### 11.5 Terrain and fixed world features

`pulau_tunas_v1` uses one terrain mask across all themes. The visual pack may change material and
color but not which cells are buildable or blocked.

| Logical asset | Placement/behavior | Required theme treatment |
| --- | --- | --- |
| `ground_buildable` | Default buildable cell | Grass/earth for Kampung and Kingdom; maintained green civic ground for City |
| `ground_tutorial` | Buildable Q001 zone; distinction shown only during tutorial/build mode | Soft patterned highlight supplied by UI overlay, not permanently painted terrain |
| `water` | Blocks ordinary buildings and roads | Calm, friendly water with low visual noise |
| `shore_edge` | Non-interactive transition around water | Edge set that joins ground and water without changing collision |
| `blocked_tree` | Fixed obstacle and decoration | Theme-specific mature tree with a clear one-cell trunk footprint |
| `blocked_rock` | Fixed obstacle and decoration | Rounded, non-threatening rock cluster |
| `bridge_zone` | The only Q005 bridge footprint | Water remains visible around the 1×2 bridge bounds |
| `quest_board` | Fixed 1×1 quest entry and road-network anchor | Herald Board / Civic Kiosk / Papan Pengumuman |

The map definition identifies terrain, fixed objects, tutorial cells, and bridge cells explicitly.
Decorative pixels never create collision that is absent from the logical layout.

### 11.6 Road and connectivity system

The logical road type is `basic_road`. It appears as kingdom cobblestone, a city pedestrian street,
or a kampung earth-and-stone path. Theme switching preserves every road coordinate and connection.

Road placement rules:

- One segment occupies one empty buildable cell. It cannot overlap a building, fixed obstacle, or
  water; the bridge is the only connection across its configured water zone.
- A road segment is free to place, move, or remove after Q003 unlocks road editing. The pilot limit
  is 48 segments per world, preventing accidental performance or usability problems without
  introducing grind.
- Q001 and Q002 do not require road access. From the road tutorial onward, connectivity is guidance:
  a disconnected building receives a clear badge and instruction, but an already placed building
  is not deleted and learning access is not blocked.
- Every building has one or more declared entrance edges. A building is connected when a road cell
  touches an active entrance and that road graph reaches `quest_board` or reaches it through the
  Q005 bridge.
- Rotation rotates both footprint and entrance edges. Buildings with fixed MVP rotation declare
  only their default entrance.
- Placing or removing one segment recalculates that segment and its north/east/south/west neighbors.
  It also recalculates connectivity only for affected road components and adjacent buildings.

Road art uses a four-direction bitmask in N-E-S-W order. Every theme supplies all 16 masks: isolated,
four end caps, two straights, four corners, four T-junctions, and one four-way junction. Valid,
invalid, hover/focus, selected, connected, and disconnected states are reusable UI overlays rather
than 16 additional painted sets. The bridge supplies entry anchors at both short ends and joins the
road graph only after Q005 placement succeeds.

### 11.7 Exhaustive MVP building catalog and use

All names below are visual labels for the same logical building ID. Costs, quests, and behavior are
identical in every theme.

| ID / quest | Footprint / entrance | Theme variants: Kingdom / City / Kampung | Cost | Building use after placement |
| --- | --- | --- | --- | --- |
| `starter_house` / Q001 | 2×2, fixed rotation, south entrance | Keeper's Cottage / Colorful Townhouse / Rumah Kampung | 4 starter-kit wood | World home and progress landmark. Tap shows welcome, progress, and the later Wallet/Savings entry. Infrastructure only; no supply or income. |
| `garden` / Q002 | 2×2, fixed rotation, south entrance | Royal Herb Garden / Community Garden / Kebun Tunas | 2 wood | Opens `COUNT_GROUPS`; when supplied with seeds/water, may credit one bounded daily Building Income entry. Empty production never blocks practice. |
| `bakery` / Q003 | 2×2, fixed rotation, south entrance | Castle Bakehouse / City Bakery / Warung Roti | 3 wood, 1 stone | Opens addition/subtraction and road editing; an ingredients pack enables bounded daily Building Income. Empty production never blocks practice. |
| `park` / Q004 | 2×2, fixed rotation, south entrance | Royal Garden / City Park / Lapangan Kampung | 2 wood, 2 stone | Opens accessible pattern practice and a cosmetic arrangement view. It has no production or stat bonus. |
| `bridge` / Q005 | 1×2 in `bridge_zone`, entrances at both short ends | Stone Story Bridge / Pedestrian City Bridge / Jembatan Kayu-Bambu | 3 wood, 2 stone | Connects road components across water and unlocks the next map area. It can be inspected but not moved outside its special zone. |
| `market_stall` / Q006 | 1×1, fixed rotation, south entrance | Royal Bazaar Stall / City Kiosk / Kios Pasar | 2 wood, 1 stone | Opens addition/comparison; a stock pack enables bounded daily Building Income. There is no child trading, advertising, or automatic payment. |

Building art is generated as one fixed-layout sprite map per theme so all six buildings within a
theme share a coherent palette, lighting, outline, material language, perspective, and scale. A
shared contract freezes cell order, dimensions, padding, footprint, anchor, entrance, shadow, and
transparent-background rules before generation. Kingdom, City, and Kampung are separate generation
tasks using the identical contract; extraction and cross-theme geometry validation are a final
independent task. Every theme task still contains mandatory acceptance checks for each building, and
no building is asset-complete until all three theme variants pass extraction and QA. Execution and
status are tracked in KQ-025 through KQ-029 in `docs/KidQuest_Execution_Tasks.md`.

`quest_board` is a fixed world feature, not an owned building: Herald Board in Kingdom, Civic Kiosk
in City, and Papan Pengumuman in Kampung. It opens the quest list and anchors road connectivity.

Each building definition must contain: ID, content version, localized names, footprint, collision
mask, allowed rotations, entrance edges, quest, costs, interaction type, visual asset key, shadow
bounds, and accessible label template. Visual variants cannot override logical fields.

### 11.8 Prop and decoration catalog

The MVP art pack contains the following supporting prop families so scenes can be composed without
inventing untracked assets during implementation:

| Prop family | MVP behavior | Kingdom / City / Kampung interpretation |
| --- | --- | --- |
| `tree` | Fixed obstacle; one-cell logical trunk | Storybook oak / maintained shade tree / fruit tree |
| `small_plant` | Non-colliding terrain decoration | Wildflowers / planter bed / shrubs and flowers |
| `bench` | Cosmetic, non-interactive | Timber-stone bench / civic bench / bamboo bench |
| `light` | Cosmetic, no day/night function | Banner torch / streetlamp / warm village lamp |
| `fence` | Cosmetic edge set: straight, corner, end | Low timber rail / painted civic rail / bamboo fence |
| `water_feature` | Cosmetic, non-interactive | Small fountain / civic fountain / village well |
| `signpost` | Cosmetic unless used as quest board | Carved sign / wayfinding sign / wooden direction sign |
| `supply_cluster` | Visual storytelling only | Barrel/crate / parcel/planter / basket/crate |

Player placement of cosmetic props is post-MVP. For the first six quests these props are composed
into fixed layouts or building artwork and must not obscure grid state. Adding interactive props
later requires its own persistence, collision, deletion, and accessibility contract.

### 11.9 Required visual states and asset boundaries

- Authored image states: base terrain/road/building/prop and, only where approved, a subtle idle
  loop. There are no separate damaged, ruined, sold, night, or seasonal variants in MVP.
- UI-derived states: locked silhouette, catalog thumbnail crop, selected, focused, valid preview,
  invalid preview, connected, disconnected, supply low/empty, production paused, income ready,
  quest available, and quest complete.
- Construction feedback is a short reduced-motion-safe overlay after authoritative placement; the
  building asset itself is immediately final and persistent.
- All runtime images use transparent WebP with PNG fallback where required. Source masters remain
  layered/vector and at least 4× intended display size.
- The normative production, naming, export, ticketing, QA, and performance contract is
  `docs/KidQuest_Visual_Design_Asset_Pipeline.md`.

### 11.10 Child and parent information architecture

The child mobile shell has at most four persistent icon-and-text destinations: **Dunia**, **Misi**,
**Bangun**, and—only after economy introduction—**Dompet**. Theme, sound/accessibility, legacy quiz,
profile, and parent entry live in a labelled menu. Parent functions never appear as child actions.

The adult-gated shell has **Ringkasan**, **Belajar**, **Ekonomi**, **Pencairan**, and **Pengaturan**.
It uses stable financial semantics and a data-focused presentation rather than full child theme
decoration. A visible mode change prevents a parent from believing they are still in child mode.

World Home presents one recommended next objective and one primary action. Locked quests,
blueprints, buildings, store items, and controls name the exact unmet requirement instead of using
an unexplained padlock.

### 11.11 Staged onboarding and session resume

- First entry teaches only the current Q001 objective and quest navigation.
- Q001 success teaches blueprint, starter kit, Build, valid/invalid placement, and confirmation.
- Theme preview is introduced after the first house; all themes remain available without forcing a
  choice or implying a cost.
- Wallet is introduced only when economy activates. Supply is introduced only with the first
  productive building. Cash-out state is introduced only when an eligible balance exists.
- Tutorials have visible Skip/Back where safe, never block later Help access, and are not replayed
  automatically after completion.
- Returning to an interrupted task shows a checkpoint with last completed change, authoritative
  current state, and one Resume action. There is no streak loss, FOMO, or missed-day punishment.
- Return summary uses calm “Sejak Kunjungan Terakhir” language for authoritative changes,
  income/supply status, and current objective; it never counts absences or implies guilt.
- MVP has no push notifications, streaks, limited-time events, remote live-ops banners, or urgency
  badge counts. Content changes arrive only through versioned releases.

### 11.12 Responsive and interaction contract

- At 360–599 px, use a compact top HUD, centered world, bottom navigation, and contextual bottom
  sheets. At 600–1023 px, a contextual panel may sit beside the world. At 1024 px and above, left
  navigation/objective, centered world, and right inspector may coexist without changing action order.
- Only context-relevant balances appear in the HUD; the application never compresses every currency,
  resource, XP, and supply into a permanently visible strip.
- A bottom sheet and desktop inspector expose the same information hierarchy. Closing returns focus
  to the invoking tile/building/control.
- Core actions are available by tap/click and keyboard; no hidden gesture or drag-only interaction.
- Preview precedes theme, placement, investment, purchase, refill, and cash-out mutations. Back or
  Cancel never commits.
- All irreversible actions show exact effect/cost, Confirm, Cancel, loading, stale, network failure,
  retry, and server-authoritative success behavior.
- A world object shows at most one priority badge. Lower-priority quest, supply, income, or road
  information remains available in the building inspector.
- An owned unique core-building card changes to “Lihat di Dunia.” MVP offers no Demolish, Upgrade,
  or Repair control. Free Move previews retained supply/income; road connectivity never implies an
  income change.

### 11.13 Economy and payout comprehension UX

- Child labels are `Rp Milikmu`, `Tabungan`, `Kredit Bangun`, `Pendapatan Bangunan`, `Persediaan`,
  and `Minta Dicairkan`; final Indonesian wording requires household parent/child review.
- Investment review renders the exact conservation statement, for example: “Dari Rp1.000, Rp250
  masuk ke Tabungan dan 750 menjadi Kredit Bangun.” The 25% is never described as interest or a fee.
- Store items show one known item, fixed Builder Credit price, allowed use, balance before, and
  balance after. No real-money-shop or mystery-purchase treatment is used.
- Productive-building detail keeps learning as the primary action and separately explains supply
  days, empty/paused reason, income ready, refill, and collection. Empty supply does not visually
  damage a building.
- Child cash-out confirmation says a parent pays outside the application. The request timeline keeps
  `REQUESTED`, `APPROVED`, and `PAID` visibly distinct; submission and approval never display Paid.
- Parent approval and `MARK_PAID` are separate screens/actions. Paid becomes read-only audit history.
- Financial actions use restrained confirmation without money showers, casino-like reveal, pressure,
  countdown, near miss, or confetti.

### 11.14 Design system, prototype, and handoff requirements

- KidQuest must look like a feature of the existing Kids Math App rather than a separate product.
  Application chrome—page background, header, navigation, workspace panels, cards, buttons, dialogs,
  typography, spacing, radii, shadows, breakpoints, and child-specific blue/purple accents—reuses the
  current Quiz/Home/Statistics tokens and layout anatomy. Theme selection must not repaint this UI.
- The world canvas is the deliberate exception: terrain, water, roads, buildings, plants, and props
  retain the approved natural illustrated theme art. The natural canvas sits inside the existing
  dark-navy application frame; controls and overlays around it still use the current app style and
  meet the same accessibility rules.
- Foundation, semantic, theme-alias, and component tokens are separate. Themes cannot override
  focus, error, success, valid/invalid, disabled, or financial-state meaning.
- Required reusable components include child/adult shells, navigation, quest/building cards, world
  targets, sheets/inspectors, balance cards, exact split preview, store review, supply and XP meters,
  status badges, request timeline, ledger row, alerts, skeletons, empty states, and errors.
- Every screen/flow is specified at phone and desktop capacity with real Indonesian-length strings,
  loading/empty/error/stale/offline/success behavior, keyboard/screen-reader/focus return, reduced
  motion, and the boundary between preview and server mutation.
- Low-fidelity flows and clickable prototypes for Q001, theme, build, Wallet, supply/income, child
  request, and parent payout are tested before bulk illustration. Failed comprehension returns to
  flow/wireframe design, not merely visual polish.
- The normative UX research, component, handoff, asset, QA, and production process is
  `docs/KidQuest_Visual_Design_Asset_Pipeline.md`.

## 12. API contract

New routes are namespaced to isolate them from the legacy quiz.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/kidquest` | Render active child's world application |
| GET | `/api/kidquest/state` | World, buildings, inventory, quests, active challenge summary |
| GET | `/api/kidquest/themes` | Available theme metadata and complete asset-manifest versions |
| PATCH | `/api/kidquest/theme` | Persist one whole-world theme without changing logical state |
| POST | `/api/kidquest/quests/{quest_id}/start` | Start or resume a quest |
| POST | `/api/kidquest/quests/{quest_id}/challenge` | Issue or resume a non-answer-leaking challenge |
| POST | `/api/kidquest/challenges/{challenge_id}/answers` | Submit one retry-safe answer attempt |
| POST | `/api/kidquest/buildings` | Place a building transactionally |
| PATCH | `/api/kidquest/buildings/{building_id}` | Move a building; post-vertical-slice |
| POST | `/api/kidquest/paths` | Place one road segment; after Q003 road unlock |
| DELETE | `/api/kidquest/paths/{path_id}` | Remove one road segment; after Q003 road unlock |
| POST | `/api/kidquest/economy/investments` | Split eligible Rp into 25% Savings and 75% Builder Credits |
| POST | `/api/kidquest/store/purchases` | Buy a known material, supply, or eligible blueprint |
| POST | `/api/kidquest/buildings/{building_id}/supply` | Load owned matching supply into a productive building |
| POST | `/api/kidquest/buildings/{building_id}/income/collect` | Accrue/collect eligible bounded daily income |
| GET | `/api/kidquest/cashout-requests` | List the active child's request history and status |
| POST | `/api/kidquest/cashout-requests` | Reserve eligible balances and create a manual payout request |
| POST | `/api/parent/session` | Establish short-lived adult session |
| DELETE | `/api/parent/session` | End adult session |
| GET | `/api/parent/kidquest/overview` | Adult-only cross-child progress; later MVP |
| GET | `/api/parent/kidquest/cashout-requests` | Adult-only pending/history and liability summary |
| PATCH | `/api/parent/kidquest/cashout-requests/{request_id}` | Approve, reject, cancel where allowed, or mark externally paid |

Every mutating KidQuest request requires an `Idempotency-Key` header. The backend stores a hash of
the logical request. Reusing the same key and request returns the original response; reusing the key
with different content returns HTTP 409.

### 12.1 Challenge response

```json
{
  "ok": true,
  "challenge": {
    "id": "ch_...",
    "quest_id": "Q001",
    "content_version": 1,
    "skill_id": "SUB_BASIC",
    "type": "numeric",
    "prompt": "Kita butuh 10 kayu. Sudah ada 6. Berapa lagi?",
    "visual_context": {"item": "wood", "required": 10, "available": 6},
    "attempt_count": 0
  }
}
```

The response never contains the answer, reward authority, balance authority, or a client-selectable
child identifier.

### 12.2 Answer request

```json
{"answer": "4", "hint_count": 0}
```

Correct response includes updated quest status, awarded resources, inventory, and next action.
Incorrect response includes `correct: false`, a hint, and remaining-attempt/cap information, but not
the final answer.

### 12.3 Placement request

```json
{"building_type": "starter_house", "x": 2, "y": 3, "rotation": 0, "world_version": 1}
```

### 12.4 Theme request

```json
{"theme_id": "kingdom", "world_version": 3, "manifest_version": 1}
```

The response returns the persisted theme and new world version. It may return resolved asset
metadata, but it must not rewrite buildings, paths, inventory, quests, or learning state.

### 12.5 Road request

```json
{"path_type": "basic_road", "x": 4, "y": 5, "world_version": 8}
```

The response returns the new segment, recalculated masks for it and affected neighbors, affected
building connectivity, and the new world version. Removing a path returns the same affected-state
shape. The server derives adjacency masks; the client cannot submit a chosen mask.

### 12.6 Investment request

```json
{"amount_rp": 1000, "quoted_economy_version": 1}
```

The server returns the exact debited source, Savings credit, Builder Credit credit, economy version,
and updated balances. The quote and commit use the same configured 25/75 rule; stale quote versions
fail without mutation.

### 12.7 Store and supply requests

```json
{"item_type": "supply", "item_id": "garden_seed_water_pack", "quantity": 1,
 "quoted_price": 120, "economy_version": 1}
```

Purchases return the immutable debit source and inventory credit. Loading supply names the inventory
item and building version; the server validates type compatibility, remaining capacity, ownership,
and productive status.

### 12.8 Income collection

The client sends no amount or rate. It identifies the building and last known version. The server
derives eligible Jakarta days, available supply, accumulation cap, funded liability budget, and the
versioned income rule, then returns every credited or paused day and current supply.

### 12.9 Cash-out request and parent transition

```json
{
  "sources": [
    {"balance_type": "available_rp", "amount_rp": 500},
    {"balance_type": "building_income_rp", "amount_rp": 200}
  ]
}
```

The parent transition contains only the requested next action (`APPROVE`, `REJECT`, `CANCEL`, or
`MARK_PAID`) and an optional non-sensitive note. The server enforces the state machine, adult
authorization, funded budget, and exact reserved sources. `MARK_PAID` never invokes an external
payment service.

### 12.10 Error format

```json
{
  "ok": false,
  "error": {"code": "INVALID_PLACEMENT", "message": "Pilih area kosong di zona rumah."}
}
```

Initial codes: `PROFILE_REQUIRED`, `KIDQUEST_DISABLED`, `QUEST_LOCKED`, `CHALLENGE_EXPIRED`,
`DAILY_CAP_REACHED`, `IDEMPOTENCY_CONFLICT`, `INVALID_PLACEMENT`, `WORLD_VERSION_CONFLICT`,
`INSUFFICIENT_RESOURCES`, `INVALID_THEME`, `ROAD_LIMIT_REACHED`, `ECONOMY_DISABLED`,
`STALE_ECONOMY_QUOTE`, `INSUFFICIENT_ELIGIBLE_RP`, `SUPPLY_MISMATCH`, `PRODUCTION_PAUSED`,
`LIABILITY_LIMIT_REACHED`, `INVALID_CASHOUT_SOURCE`, `INVALID_CASHOUT_TRANSITION`, and
`ADULT_AUTH_REQUIRED`.

## 13. Authoritative data model

Content definitions remain versioned JSON files. Player state is stored in SQLite.

| Table | Key fields and constraints |
| --- | --- |
| `kidquest_worlds` | `child` PK, layout version, `theme_id` default `perkampungan`, theme manifest version, width/height, optimistic `version`, timestamps |
| `kidquest_buildings` | ID PK, child FK, type, x/y, rotation, placed/updated time; unique `(child, type)` for six core buildings; no per-building theme |
| `kidquest_paths` | ID PK, child FK, x/y, path type; unique `(child, x, y)` and maximum enforced by service |
| `kidquest_child_quests` | PK `(child, quest_id)`, quest version, status, progress, timestamps |
| `kidquest_challenges` | ID PK, child, quest/version, content ref, status, issued/completed/expiry time |
| `kidquest_attempts` | ID PK, unique logical attempt key, challenge, skill, correctness, hint count, time |
| `kidquest_resource_balances` | PK `(child, resource_type)`, nonnegative balance |
| `kidquest_resource_ledger` | ID PK, child/resource/delta/source; unique reward/spend source |
| `kidquest_blueprints` | PK `(child, building_type)`, acquisition type/source, content version, and time |
| `kidquest_wallet_balances` | PK `(child, balance_type)`, nonnegative integer Rupiah/credit balance and updated time |
| `kidquest_wallet_ledger` | ID PK, child, balance type, delta, source type/ref, economy version, time; unique source |
| `kidquest_xp_progress` | Child PK, nonnegative XP, derived level/version, timestamps |
| `kidquest_blueprint_discovery` | Child PK, meter progress, threshold/version, last award time |
| `kidquest_supply_inventory` | PK `(child, supply_type)`, nonnegative quantity |
| `kidquest_building_operations` | Building PK, loaded supply type/remaining active days, production state/version, timestamps |
| `kidquest_building_daily_income` | PK `(child, building_id, Jakarta day)`, rule version, supply debit, income ledger source, state/reason |
| `kidquest_cashout_requests` | ID PK, child, total, state, requested/decided/paid timestamps, adult decision metadata |
| `kidquest_cashout_sources` | PK `(request_id, balance_type)`, exact reserved amount and ledger refs |
| `kidquest_cashout_events` | Append-only request transition audit with actor role, prior/new state, time, safe note |
| `kidquest_idempotency` | PK `(child, operation, key)`, request hash, status and response JSON |
| `kidquest_daily_usage` | PK `(child, Jakarta day)`, accepted attempt count |

All tables are additive. Legacy `sessions`, `child_daily`, `served_questions`, daily banks, and
current-question tables are not repurposed. SQLite foreign keys are enabled on every connection.

## 14. Transaction requirements

### 14.1 Answer transaction

1. `BEGIN IMMEDIATE`.
2. Resolve idempotency key and request hash.
3. Validate active child, challenge, quest, expiry, and Jakarta daily cap.
4. Insert exactly one attempt.
5. Update KidQuest daily usage and selected legacy daily counters according to the compatibility
   policy.
6. For an eligible correct answer after economy activation, insert one unique wallet earning and XP
   source within configured eligibility limits. Never derive a wallet credit by resumming mutable
   statistics later.
7. If first correct quest completion, advance quest and grant its deterministic reward/blueprint;
   Q001 credits the starter kit rather than requiring conversion.
8. After Q006/core-onboarding unlock only, update Discovery Meter once for an eligible correct
   answer and award a non-duplicate optional blueprint only under the versioned discovery rule.
9. Store the complete response in the idempotency record and commit once.

### 14.2 Placement transaction

1. `BEGIN IMMEDIATE` and resolve idempotency.
2. Load world/version, blueprint, quest, balance, existing buildings, and content definition.
3. Validate footprint, bounds, buildable/tutorial cells, collision, core-instance limit, balance,
   prerequisite sequence, and expected version.
4. Insert unique ledger debit, update balance, insert building, increment world version, and complete
   the quest. First Q002 Garden placement also credits the unique one-time starter supply pack only
   when a valid funded building-income mode is enabled; otherwise that credit remains pending until
   the first later enablement and is still granted at most once.
5. Store response and commit once.

Moving a building uses the same world-version/collision transaction but creates no spend, refund,
reward, or completion event. It retains building ID, loaded supply, operation state, and daily income
history. Core buildings cannot be deleted, sold, duplicated, upgraded, damaged, or repaired in the
MVP.

### 14.3 Theme and road transactions

For a theme change:

1. Resolve idempotency and validate that the theme ID and manifest version are supported.
2. Update only the world's `theme_id`, theme manifest version, optimistic version, and timestamp.
3. Return unchanged building coordinates, paths, inventory, resources, and quest state with the new
   theme metadata.
4. Store the response and commit once. A replay returns the same response without another version
   increment.

Road mutations use the same idempotency and optimistic-version rules as buildings. The transaction
validates buildable terrain, collision, the 48-segment limit, and affected connectivity before it
updates the world version.

### 14.4 Investment and purchase transactions

Investment conversion:

1. Resolve idempotency and load the quoted economy version.
2. Validate amount denomination, eligibility, available unreserved Rp, and current 25/75 rule.
3. Debit the exact source Rp, credit 25% Savings, and credit 75% Builder Credits using linked unique
   ledger sources.
4. Store the response and commit once. Any failure leaves all three balances unchanged.

Store purchase atomically validates a known item, unlock/level rules, quoted fixed price, quantity,
and Builder Credit balance; then it debits credits and credits exactly one inventory/blueprint
source. Loading supply separately validates building compatibility/capacity and moves owned supply
into `kidquest_building_operations` without creating or destroying value.

### 14.5 Daily building-income transaction

1. Resolve idempotency and load the building, production/economy versions, supply, Jakarta clock,
   prior daily rows, accumulation cap, and funded liability limit.
2. Determine eligible uncredited days. If production or liability is paused, record/return the
   reason without consuming supply.
3. For each eligible day within the accumulation cap, insert its unique daily row, consume exactly
   one configured supply day, and insert one linked `building_income_rp` ledger credit.
4. Return credited/paused days, updated supply, balance, and production version; commit once.

### 14.6 Cash-out transactions

Request creation validates source eligibility, maturity/parent approval where applicable, current
funded limit, and available unreserved balances; inserts the request and exact source reservations
atomically. Approval changes state but does not debit or claim payment. `MARK_PAID` is adult-only and
atomically finalizes the reserved ledger debits plus an append-only audit event after the parent has
paid externally. Rejection/cancellation releases the original reservations exactly once. No state
transition calls a payment gateway, bank, wallet, or messaging service.

Any validation failure rolls back all state. SQLite lock/contention errors return a retryable
response and never partially award or spend resources.

## 15. Configuration and feature flags

| Variable | Initial behavior |
| --- | --- |
| `KIDQUEST_ENABLED` | Default false |
| `KIDQUEST_PROFILE_ALLOWLIST` | Comma-separated existing child IDs; empty means none during pilot |
| `KIDQUEST_ADAPTIVE_ENABLED` | Default false |
| `KIDQUEST_PARENT_DASHBOARD_ENABLED` | Default false |
| `KIDQUEST_ECONOMY_ENABLED` | Default false; wallet/investment/store endpoints unavailable |
| `KIDQUEST_CASHOUT_ENABLED` | Default false; requires adult gate and funded parent limits |
| `KIDQUEST_BUILDING_INCOME_ENABLED` | Default false; requires calibrated economy and cash-out |
| `KIDQUEST_SAVINGS_BONUS_ENABLED` | Default false; parent-funded and separately versioned |
| `KIDQUEST_DAILY_ATTEMPT_LIMIT` | Proposed default 20 |
| `APP_TIMEZONE` | Default `Asia/Jakarta` |
| `SESSION_COOKIE_SECURE` | True in production |
| `SESSION_SIGNING_KEY` | Required for adult session signing |
| `PARENT_PIN_HASH` | Required before adult endpoints are enabled |

Feature-off behavior leaves all legacy routes unchanged. A rollback disables KidQuest code while
retaining additive tables and player data.

Startup/readiness rejects invalid combinations: building income requires economy, cash-out, adult
authorization, and funded limits; cash-out requires economy and the adult gate. Economy without
cash-out is allowed but must explain that Savings cannot yet be requested. With building income off,
productive buildings expose their learning use without supply purchase/loading or income controls.

## 16. Content definitions

The repository stores:

- `content/kidquest/quests.json`
- `content/kidquest/buildings.json`
- `content/kidquest/economy.json`
- `content/kidquest/levels.json`
- `content/kidquest/blueprints.json`
- `content/kidquest/supplies.json`
- `content/kidquest/themes.json`
- `content/kidquest/roads.json`
- `content/kidquest/assets.schema.json`
- `content/kidquest/layouts/pulau_tunas_v1.json`

Startup and CI validation checks schema version, unique IDs, known skills/resources/buildings,
acyclic quest prerequisites, exact linear Q001–Q006 teaching sequence, reachable quests, valid
footprints/costs/entrances, one core instance per type, layout bounds,
tutorial and bridge zones, exact Q001 starter-kit compatibility, supported challenge types, economy
versions, 25/75 split, fixed store prices, one-time/deferred Q002 starter supply, blueprint-source rules,
post-Q006 optional-discovery gating, duplicate fallback, supply/building
compatibility, positive caps, income/liability bounds, all 16 road masks per theme, asset parity
across themes, anchors, dimensions, and file-size budgets. Invalid
content prevents KidQuest startup while the legacy app remains diagnosable; production deployment
fails health/readiness until corrected.

## 17. Parent reporting and data policy

Phase 1 stores detailed internal attempts but does not expose a full dashboard. The later dashboard
shows evidence, not unsupported mastery claims:

- Attempts and accuracy by skill.
- Hint usage.
- Quest starts/completions.
- Most recent practice date.
- A deterministic practice suggestion based on configured rules.
- Available/legacy Rp, Savings principal/bonus, Builder Credits, Building Income, reserved liability,
  paid totals, productive-building projection, and source-labelled transaction history.
- Cash-out requests by state with source breakdown and append-only decision/payment events.

No third-party analytics receive raw answers or child identifiers. Initial product events are kept
locally and use the active child only as an internal reference. Backup, retention, export, and
deletion policies must be documented before any external pilot.

## 18. Operational safety

- Add a Python SQLite backup command using `Connection.backup()` and `PRAGMA integrity_check`.
- Back up the persistent database before the first KidQuest migration.
- Migrations are additive; destructive down migrations are not used by default.
- Keep a code rollback path through `KIDQUEST_ENABLED=false`.
- Separate legacy-history deletion from KidQuest-world deletion with adult authentication and
  explicit scope confirmation.
- Treat externally payable balances as financial liability in backup, reconciliation, migration,
  audit, and rollback procedures. Never reconstruct them from aggregate quiz statistics.
- Add a reconciliation command that proves wallet ledger sums, balance rows, reservations, paid
  requests, daily building credits, and parent limit usage agree before and after deployment.
- Log request IDs, operation, quest/content version, outcome, and error code without raw answer or
  unnecessary child PII.

### 18.1 Product telemetry and content operations

Product-flow events remain first-party and local. They support correctness and household usability,
not advertising, behavioral profiling, or pressure to increase screen time.

Minimum events include world opened/resumed, recommended objective shown, quest started/resumed/
completed, hint used, placement preview failure reason, building placed/moved, theme previewed/
confirmed/cancelled, tutorial completed/skipped, investment quote/confirmation, known-item purchase,
supply loaded, production credited/paused reason, income collected, and cash-out state transition.
Events store content/economy versions and pseudonymous internal child reference but never raw answers,
adult PIN, payment details, or free-form child text.

Operational views measure funnel breakage, state mismatch, duplicate prevention, comprehension tasks,
and funded liability. They do not rank children, optimize daily screen time, create streak prompts, or
trigger outbound notifications. New content is released through versioned repository definitions and
normal deployment/rollback, never through an unreviewed remote live-operations editor.

## 19. Acceptance criteria

### AC-01 Legacy compatibility

Given a populated pre-KidQuest database, after migration both profiles can use Math and General
Knowledge, and historical seven-day aggregates are unchanged.

### AC-02 First house

Given a new active world, completing Q001 correctly and placing a valid starter house persists the
house and completes Q001.

### AC-03 Incorrect retry

An incorrect answer records one attempt, awards nothing, returns a useful hint, and keeps the same
challenge retryable.

### AC-04 Idempotent answer

Replaying the same answer idempotency key returns the original response and does not add usage,
attempts, rewards, or counters.

### AC-05 Idempotent placement

Replaying a successful placement creates one building and spends one cost.

### AC-06 Collision and balance

Out-of-bounds, blocked, overlapping, unauthorized, stale-version, or unaffordable placement fails
without mutation.

### AC-07 Child isolation

World, challenge, inventory, ledger, and quest mutations for one child never alter the other child.

### AC-08 Day rollover

At the Jakarta day boundary, KidQuest daily usage resets while world, quest, inventory, and legacy
historical aggregates persist.

### AC-09 Adult authorization

A child session cannot access cross-child reporting, data deletion, or parent settings.

Pilot scope: this applies to all new KidQuest parent reporting, parent settings, and scoped resets.
The legacy household recap (`/stats` and `/api/stats`, which currently returns both children's
seven-day totals) remains unchanged as a compatibility surface during the household pilot. The
legacy `/api/admin/clear` keeps its contract and legacy-only scope behind a required non-default
production password. Gating the legacy recap is an open decision in section 22, not a first-house
requirement.

### AC-10 Content validation

Malformed, cyclic, unreachable, or internally inconsistent content produces actionable validation
failure before it can mutate player state.

### AC-11 Concurrent answer

Two concurrent submissions for the same logical answer result in one accepted mutation and one
idempotent replay/conflict response, never two rewards.

### AC-12 Concurrent placement

Two simultaneous placements cannot overlap, overspend, or both use a stale world version.

### AC-13 Theme invariance

Switching among Kampung, Kingdom, and City persists after refresh but leaves building IDs and
coordinates, road coordinates, resources, blueprints, quests, attempts, and learning totals exactly
unchanged. A duplicate theme request increments the world version at most once.

### AC-14 Theme completeness

The release manifest contains every required terrain, road-mask, building, prop, icon, and UI token
for all three themes. Missing assets, incompatible anchors, or mismatched logical footprints fail CI.

### AC-15 Road topology

All 16 N-E-S-W road masks render correctly in each theme. Placement, removal, neighbor updates,
building entrance connectivity, road limit, collision, and bridge connectivity pass unit and
integration tests; changing theme does not alter the graph.

### AC-16 Visual and responsive quality

At 360 px, tablet, and desktop widths, all six building silhouettes, entrances, focus, selection,
validity, lock, quest, and disconnected states remain understandable. There is no horizontal
overflow, essential information hidden by artwork, or required animation when reduced motion is on.

### AC-17 Atomic investment split

For every confirmed eligible investment, one source debit equals one 25% Savings credit plus one 75%
Builder Credit credit. Duplicate/concurrent requests apply once; stale quotes and insufficient or
reserved balances change nothing.

### AC-18 Manual cash-out lifecycle

A request reserves exact eligible sources once. Only an adult may approve/reject or mark it paid;
approval does not count as payment; paid finalization occurs only after external payment and is
immutable. Reject/cancel returns the exact original sources. No transition invokes a payment API.

### AC-19 Productive-building integrity

Garden, Bakery, and Market credit at most one configured income per eligible Jakarta day, consume
supply only with a successful credit, respect accumulation and parent liability caps, and remain
usable for learning when empty or paused. Building Income cannot be reinvested or buy supply.

### AC-20 Blueprint fairness

Progression-critical blueprints are guaranteed by quests. Level choices, fixed-price purchases, and
Discovery Meter awards enforce eligibility and duplicate prevention. Random discovery cannot be
purchased and always has a published guaranteed threshold.

### AC-21 Economy reconciliation and isolation

For each child, ledger sums equal stored balances, request reservations, income rows, resource
inventory, and paid totals after normal, duplicate, concurrent, backup/restore, and rollback tests.
No value or funded limit leaks between children.

### AC-22 Progressive onboarding and resume

Q001 teaches only quest, answer, blueprint/starter kit, and placement. Theme is introduced after the
house checkpoint; Wallet after parent-enabled economy; supply with the first productive building;
cash-out only with an eligible balance. Returning mid-flow shows a calm authoritative summary and one
Resume action without replaying completed tutorials or applying a missed-day/streak penalty.

### AC-23 Child task and state comprehension

In the household usability pass, representative children can find the current objective, explain a
locked reason, complete Q001 placement, cancel a theme preview, and recover from an invalid/stale
action without adult correction in at least four of five tasks. The world shows no more than one
priority badge per object; detailed states remain available in its inspector.

### AC-24 Financial and payout comprehension

Every tested child can explain that an investment sends 25% to Savings and 75% to non-cashable
Builder Credits after the review screen. Every tested child/parent pair distinguishes Requested,
Approved, and Paid. Parent approval never renders Paid, and only a separate externally-paid action
can finalize the request.

### AC-25 Responsive component and accessibility parity

Every required child and parent screen has phone and desktop-capacity specifications plus loading,
empty, error, stale, offline, success, keyboard, screen-reader, focus-return, 200% zoom/reflow, and
reduced-motion behavior. Desktop reveals no action unavailable on mobile; theme decoration never
changes semantic state meaning.

### AC-26 Core teaching ladder and feature modes

Q001–Q006 unlock only in their defined prerequisite order and introduce only the documented new
concept. Q002 credits one starter supply pack once when income is enabled, or defers that unique
credit until later valid enablement; optional Blueprint Shop/Discovery is absent until after Q006.
Every supported feature-flag combination exposes only usable actions, and invalid
income/cash-out/economy combinations fail readiness.

### AC-27 Core building lifecycle

Each child can own at most one of each core building. Construction is immediate; moving is free and
retains building ID, supply, operations, and income history. Theme and road changes never alter
income. No MVP UI/API offers core building sale, demolition, duplication, upgrade, damage, repair,
or pay-to-skip construction.

### AC-28 No-pressure return and content operation

Returning after zero, one, or more days shows actual saved changes, one recommended objective, and
at most three accumulated productive days without streak loss, missed-day punishment, urgent offer,
or forced maintenance. No MVP path sends a push/email reminder or loads unversioned remote content.

## 20. Success and guardrail metrics

| Metric | Pilot target |
| --- | --- |
| First-house completion | At least 80% of participating children |
| Median time to first house | At most 5 minutes |
| Q001 completion | At least 70% of starts |
| Data correctness | 100% of automated duplicate/concurrency cases |
| Legacy critical regressions | Zero |
| Parent interpretation | At least 80% identify one strength and one developing skill |
| Theme-switch state regressions | Zero across automated invariant tests |
| Required asset parity | 100% across all three theme manifests |
| Wallet/ledger reconciliation | 100%; zero unexplained Rupiah or credit difference |
| Duplicate income/cash-out | Zero across automated retry/concurrency cases |
| Parent liability | Never exceeds configured funded child/month limits |
| Supply charged without income | Zero |
| Representative child task success | At least 4 of 5 tasks without adult correction |
| Savings/Builder Credit comprehension | 100% of tested household children after explanation |
| Requested/Approved/Paid comprehension | 100% of tested child/parent pairs |
| Theme-cost/progress misconception | Zero in household usability pass |
| Critical accessibility/comprehension defects | Zero at release gate |
| Incorrect recommended/resume objective | Zero across persisted-state integration cases |
| Duplicate core building or Q002 starter supply | Zero |
| Invalid feature-mode readiness | 100% rejected before serving affected actions |
| Supply/income affected by move, road, or theme | Zero state/rate regressions |
| Outbound pressure/live-ops behavior | Zero push, streak, expiring offer, or unversioned content paths |

Do not optimize total screen time, daily return streaks, or pressure-based engagement.

## 21. Delivery stages

1. **Foundation:** characterization tests, Jakarta clock, backup/restore, connection safety, atomic
   legacy answer consumption.
2. **Experience and visual foundation:** information architecture, flows, responsive wireframes,
   tested prototype, component/token system, logical catalog, theme manifests, graybox grid, golden
   asset set, road autotile proof, and automated design/asset validation.
3. **First-house backend:** additive schema, validated Q001 content, world initialization,
   transactional answer/reward/placement/theme APIs.
4. **First-house frontend:** world grid, theme selector, quest/challenge/hint/build flow, refresh
   restoration.
5. **Pilot hardening:** concurrency, migration, accessibility, mobile performance, logs and rollback.
6. **Economy foundation:** immutable wallet/XP ledgers, 25/75 investment, known-item store,
   blueprint sources, adult gate, liability limits, externally fulfilled cash-out tracking, and
   reviewed child/parent economy flows behind flags.
7. **Minimum playable economy:** staged Q002–Q006 tutorials, roads, supplies, bounded productive
   buildings, inventory, movement, additional challenge types, and complete three-theme packs.
8. **Parent insights:** learning dashboard and per-skill adaptation behind flags.

The detailed execution order and file-level changes are maintained in
`docs/KidQuest_Implementation_Plan.md`.

## 22. Remaining decisions

These do not block the first-house implementation:

- Whether large layered source masters live in Git LFS or an access-controlled design workspace;
  runtime exports and their source/license metadata always live in the repository.
- Whether optional audio ships in the first pilot.
- Final KidQuest daily attempt limit after observed child testing.
- Conversion denomination, resource/store prices, supply price/duration, building income, Discovery
  Meter threshold/chance, XP levels, payback targets, and funded daily/monthly limits after the
  economy simulator and parent review.
- Savings goal/maturity rules and whether a separately funded Savings Bonus is enabled.
- Whether any historical `legacy_rp` is parent-approved for cash-out; default is conversion-only.
- Whether the full parent dashboard is required before a household-only pilot.
- Whether the legacy cross-child recap (`/stats`, `/api/stats`) moves behind the adult gate; it is
  unchanged for the first deliverable.
- Legal/privacy review requirements for any broader Indonesian public release.

## 23. Definition of done for the first deliverable

- Existing Math, General Knowledge, and statistics behavior has automated compatibility coverage.
- A backup and additive migration path is documented and tested.
- Both existing children receive independent persistent worlds.
- Q001 starts, retries, rewards, and completes through placement.
- Resource balance cannot duplicate or become negative.
- Duplicate and concurrent answer/placement tests pass.
- Theme changes persist without changing any logical world or learning state.
- The golden terrain, quest board, and all 16 road masks pass visual QA in all themes.
- All six buildings are generated as one fixed-layout sprite map per theme (identical slot order and
  slot resolution) and all 18 extracted building sprites pass cross-theme geometry QA.
- Every shipped asset is represented by the validated manifest and source/license metadata.
- Child/adult information architecture, Q001/theme/build responsive wireframes, reusable component
  states, content strings, and accessibility behavior are stored and traceable to implementation.
- The revised Q001/theme/build prototype passes the applicable AC-22, AC-23, and AC-25 household
  tasks before first-house UI sign-off.
- Refresh and application restart preserve state.
- Feature flag rollback leaves the legacy app operational.
- README links to the PRD, visual asset pipeline, implementation plan, launch steps, and verification
  commands.

### First-deliverable acceptance scope

Some acceptance criteria describe the complete six-quest MVP. For the first deliverable (M0–M6)
they apply as follows:

| Criteria | First-deliverable scope |
| --- | --- |
| AC-01 – AC-13 | Full. AC-09 as limited by its pilot-scope note. |
| AC-14 Theme completeness | The release manifest contains every asset the first house renders, in all three themes: the golden terrain set including every shore mask used by `pulau_tunas_v1`, `quest_board`, all 16 road masks, all six buildings, the `wood` icon, the theme thumbnail, and shared overlays. Missing assets, incompatible anchors, or mismatched footprints fail CI. Props, fences, plant variations, the `stone` icon, and the complete 16-mask shore set are verified in KQ-023. |
| AC-15 Road topology | All 16 masks render and join in a 3×3 gallery scene per theme; mask resolution from N/E/S/W adjacency is unit-tested; theme switching does not alter stored path rows. Road placement, removal, segment limit, entrance connectivity, and bridge connectivity are verified with road editing in KQ-019 and KQ-021. |
| AC-16 Visual and responsive quality | Full. All six building silhouettes are verified in the asset gallery at 38/48/64 px; in-world states are verified for the starter house, quest board, and placement overlays. |
| AC-17 – AC-21, AC-24, AC-26 – AC-28 | Not applicable; economy and six-quest milestones. |
| AC-22, AC-23, AC-25 | Applicable to first-house screens and tasks. |

The wallet, blueprint discovery, productive-building supply/income, and manual cash-out system are
not part of the first Q001 deliverable. They are done for the minimum playable economy only when
AC-17 through AC-28 applicable to that release pass, parent-funded limits are configured, and the
economy flags can be disabled without changing or losing existing ledger history.

## 24. Product-decision change control

- Every accepted change to product behavior, progression, economy, visual rules, safety, or scope is
  written into a versioned PRD before implementation begins.
- The implementation plan and visual pipeline are updated in the same documentation change whenever
  their milestones, contracts, assets, or tests are affected.
- Conversation-only agreements are not treated as the final source of truth; this PRD is.
- Unresolved proposals stay in Remaining Decisions and are not implemented as assumptions.

