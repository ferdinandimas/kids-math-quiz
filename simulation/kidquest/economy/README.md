# KidQuest economy simulation inputs

This directory contains draft-only inputs for the isolated KQ-030 simulator. Nothing here is
production configuration, and application runtime code must not import it.

Run the complete scenario matrix from the repository root:

```bash
PYTHONPATH=. python scripts/simulate_kidquest_economy.py --format markdown
```

Generate deterministic JSON for machine comparison:

```bash
PYTHONPATH=. python scripts/simulate_kidquest_economy.py --format json --output /tmp/kidquest-economy.json
```

`draft_v1.json` intentionally uses `approval_status: draft_not_approved`. KQ-012 may copy and vary
these parameters for sensitivity analysis after M6/Q001 observation. Production economy work must
not begin until KQ-012 records the approved version and parent-funded liability decision.

Compare the explicit draft axes in `sensitivity_v1.json`:

```bash
PYTHONPATH=. python scripts/analyze_kidquest_economy.py --format markdown
PYTHONPATH=. python scripts/analyze_kidquest_economy.py --format csv --output /tmp/kidquest-ranking.csv
```

The ranking exposes every penalty and uses stable candidate IDs and tie-breaking. It is decision
support only and cannot promote any candidate to production.

Simulation order within each Jakarta day is fixed: answer earnings, investment when required,
at most one construction, supply loading, then bounded income. Every amount uses integer Rupiah.
Building income is cash-out exposure only and is never an investment or supply-purchase source.

