# Calm resume flow

Sources: PRD §7.1–7.3, §11.11, AC-22, AC-28; pipeline §5.4.

## 1. Decision on entry

```mermaid
flowchart TD
    E[Enter KidQuest or reload] --> L[Loading skeleton: 'Memuat duniamu…']
    L -->|load error| ER["Duniamu belum bisa dibuka. Periksa internet, lalu coba lagi. Tidak ada yang hilang." + Coba Lagi]
    ER --> L
    L --> S{Authoritative last completed change exists?}
    S -->|no| H[World Home with objective card]
    S -->|yes| R{Is something incomplete?}
    R -->|IN_PROGRESS| R1["Sejak Kunjungan Terakhir · Resume: Lanjutkan Tantangan"]
    R -->|READY_TO_BUILD| R2["Sejak Kunjungan Terakhir · Resume: Lanjutkan: Bangun Rumah"]
    R -->|COMPLETED| R3["Sejak Kunjungan Terakhir · no Resume button · Tutup"]
    R1 -->|Tutup| H
    R2 -->|Tutup| H
    R3 -->|Tutup| H
    R1 -->|Resume| C[Same challenge, attempts preserved]
    R2 -->|Resume| P[Placement mode]
```

## 2. Content contract

The summary card replaces the objective card while shown, so the screen keeps exactly one primary action. Dismissing it reveals the objective card with the same recommendation.

| Line | Source | Example |
|---|---|---|
| Last completed change | Server's last committed mutation | Kamu menjawab benar dan mendapat 4 kayu dan cetak biru Rumah. |
| Current authoritative state | Quest state | Sekarang: kayu dan cetak biru sudah siap. Rumah belum dibangun. |
| Safety | Constant | Semua sudah tersimpan otomatis. |
| Resume | Only if a challenge, placement, or tutorial is incomplete | Lanjutkan: Bangun Rumah |

Never shown: days away, missed days, streaks, "kami rindu", countdowns, red badges, or replayed tutorials. Completed tips (the catalog tip and the placement tip) are not replayed. They can be shown again from Bantuan → "Tampilkan lagi petunjuk membangun".

The walkthrough check asserts that the resume card has exactly one primary button, contains no absence or streak vocabulary, and does not replay the completed catalog tip.

## 3. Interrupted mutation ("Memeriksa perubahan")

```mermaid
sequenceDiagram
    participant Child
    participant UI
    participant Server
    Child->>UI: Kirim / Bangun di Sini / Gunakan Tema
    UI->>Server: request + idempotency key K
    Server-->>Server: commits once, stores response for K
    Server--xUI: response lost
    UI->>Child: "Memeriksa perubahan… Tidak akan dihitung dua kali." [Periksa Lagi]
    Child->>UI: Periksa Lagi
    UI->>Server: same request key K
    Server->>UI: stored original response (no second reward or cost)
    UI->>Child: normal success screen
```

The walkthrough check proves this in the simulation: after a lost answer response and a recheck, the wood stays at 4 and the attempts at 2. It is not double-credited.
