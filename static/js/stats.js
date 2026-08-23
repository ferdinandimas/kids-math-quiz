function tdRight(value) {
    return `<td class="right">${value}</td>`;
}

function renderChild(prefix, recap) {
    const totals = recap.totals || {};
    document.getElementById(`${prefix}_total_answered`).textContent = totals.answered_count ?? 0;
    document.getElementById(`${prefix}_total_correct`).textContent = totals.correct_count ?? 0;
    document.getElementById(`${prefix}_total_acc`).textContent = `${totals.accuracy_pct ?? 0}%`;
    document.getElementById(`${prefix}_total_earned`).textContent = `Rp ${totals.earned ?? 0}`;

    const rows = document.getElementById(`${prefix}_rows`);
    rows.innerHTML = "";

    (recap.days || []).forEach((day) => {
        const row = document.createElement("tr");
        row.innerHTML = `<td>${day.day}</td>${tdRight(day.answered_count ?? 0)}${tdRight(day.correct_count ?? 0)}${tdRight(`${day.accuracy_pct ?? 0}%`)}${tdRight(`Rp ${day.earned ?? 0}`)}`;
        rows.appendChild(row);
    });
}

async function load() {
    const response = await fetch("/api/stats");
    const data = await response.json();

    if (!data.ok) {
        document.getElementById("rangeText").textContent = data.message || "Gagal memuat.";
        return;
    }

    const range = data.recap7?.range;
    document.getElementById("rangeText").textContent = range
        ? `Rentan: ${range.start} sampai ${range.end}`
        : "7 hari terakhir";

    const children = data.recap7?.children || {};
    if (children.althafandra) renderChild("a", children.althafandra);
    if (children.alleia) renderChild("b", children.alleia);

    const timestamp = data.recap7?.generated_at || "";
    document.getElementById("updated_a").textContent = timestamp ? `Updated: ${timestamp}` : "";
    document.getElementById("updated_b").textContent = timestamp ? `Updated: ${timestamp}` : "";
}

document.getElementById("clearBtn").addEventListener("click", async () => {
    const password = prompt("Masukkan password untuk clear database:");
    if (!password || !confirm("Yakin mau hapus SEMUA data quiz dan statistik?")) return;

    const response = await fetch("/api/admin/clear", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({password}),
    });
    const data = await response.json();
    alert(data.message || (data.ok ? "OK" : "Gagal"));

    if (data.ok) load();
});

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js");
}

load();
