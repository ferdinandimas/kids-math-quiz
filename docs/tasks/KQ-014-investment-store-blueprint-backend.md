---
id: KQ-014
title: Build investment, store, and blueprint backend
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-013]
milestone: M7
updated: 2026-11-21
---

# KQ-014 — Build investment, store, and blueprint backend

## Outcome

Quiz earnings (`available_rp`) can be invested into the world, splitting exactly 25% into Savings (`savings_rp`) and 75% into Builder Credits (`builder_credit`), and children can obtain known blueprints through governed progression paths.

## Scope

1. Grant answer earnings and XP through idempotent ledger events.
2. Implement child-initiated world investment with a server quote: one `available_rp` debit, one 25% `savings_rp` credit, and one 75% `builder_credit` credit, using the approved denomination, rounding, and limits. "Investment" names the action only; the 25% bucket is always called Savings and is never described as interest or a fee.
3. Implement a fixed-price store that reveals only known/eligible resources and blueprints.
4. Implement blueprint acquisition through quest, level, discovery/chance, and store sources with duplicate-safe behavior.
5. Keep optional discovery paths unavailable until after Q006 unless the PRD explicitly marks them as tutorial rewards.

## Deliverables

- Earnings, investment, store, XP/level, and blueprint services/APIs.
- Server-owned catalog/price configuration tied to the approved economy version.
- Idempotency, concurrency, eligibility, and ledger tests.

## Acceptance criteria

- [ ] One answer grants earnings/XP at most once.
- [ ] Each investment's `available_rp` debit equals its `savings_rp` credit plus its `builder_credit` credit, committed atomically and reconciled exactly (AC-17).
- [ ] Children cannot buy unknown, locked, duplicate-forbidden, or server-hidden items.
- [ ] Prices cannot be manipulated by request payloads.
- [ ] Blueprint sources are attributable and duplicates follow the documented rule.

## Verification

- Run full tests plus concurrent duplicate investment/purchase scenarios.
- Reconcile ledgers across answer → investment → purchase → blueprint acquisition flows.

## Out of scope

- Frontend Wallet, cash-out lifecycle, and productive-building income.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** Uses Migration 9
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

