# KidQuest flows (Stage B)

| File | Covers |
|---|---|
| [information-architecture.md](information-architecture.md) | Child and parent IA, navigation ownership, objective priority, mode separation |
| [first-house-flow.md](first-house-flow.md) | Q001 → reward → catalog → placement → checkpoint, with wrong/cap/stale/offline recovery, safe points, and the canonical `pulau_tunas_v1` geometry |
| [theme-switch-flow.md](theme-switch-flow.md) | Theme picker preview, cancel, confirm, failure, and copy |
| [calm-resume-flow.md](calm-resume-flow.md) | Loading/error on entry, "Sejak Kunjungan Terakhir", and the "Memeriksa perubahan" idempotent recheck |
| [adult-gate-flow.md](adult-gate-flow.md) | Gate, adult shell, session expiry, scoped reset |

Diagrams are Mermaid and render on GitHub. Every flow has a matching clickable path in [`../prototypes/first-house/`](../prototypes/README.md).

Stage B gate self-check (pipeline §15): every task traces from entry to completion with no dead end. Each placeholder end (Q002, Legacy Quiz) is labelled as out of scope and has a way back. No action depends on a hidden gesture, and no adult action is reachable from child mode without the gate. Product, engineering, learning, and parent-representative sign-off is still pending.
