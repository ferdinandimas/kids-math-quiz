const SVG_NS = "http://www.w3.org/2000/svg";

function svgNode(name, attrs = {}, text = "") {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
}

function formatUpdate(value) {
    return value ? `Updated: ${value.replace("T", " ").replace(/\.\d+$/, "")}` : "";
}

function renderChart(prefix, days) {
    const target = document.getElementById(`${prefix}_chart`);
    target.replaceChildren();
    const values = days.map((day) => Number(day.accuracy_pct || 0));
    const labels = days.map((day) => String(day.day || "").slice(5).split("-").reverse().join("/"));
    const svg = svgNode("svg", { viewBox: "0 0 860 130", role: "img", "aria-label": "Grafik akurasi tujuh hari" });
    const left = 58, right = 16, top = 10, bottom = 31, width = 860 - left - right, height = 130 - top - bottom;
    const y = (value) => top + height - (Math.max(0, Math.min(100, value)) / 100 * height);
    const x = (index) => left + (values.length <= 1 ? width / 2 : index * width / (values.length - 1));
    [100, 50, 0].forEach((value) => {
        const lineY = y(value);
        svg.append(svgNode("line", { x1: left, y1: lineY, x2: 860 - right, y2: lineY, class: value === 0 ? "chart-axis" : "chart-grid" }));
        svg.append(svgNode("text", { x: left - 12, y: lineY + 5, "text-anchor": "end", class: "chart-label" }, `${value}%`));
    });
    svg.append(svgNode("line", { x1: left, y1: top, x2: left, y2: y(0), class: "chart-axis" }));
    if (values.length) {
        const path = values.map((value, index) => `${index ? "L" : "M"}${x(index)} ${y(value)}`).join(" ");
        svg.append(svgNode("path", { d: path, class: "chart-line" }));
        values.forEach((value, index) => {
            svg.append(svgNode("circle", { cx: x(index), cy: y(value), r: index === values.length - 1 ? 5 : 4, class: "chart-dot" }));
            svg.append(svgNode("text", { x: x(index), y: 123, "text-anchor": "middle", class: "chart-label" }, labels[index]));
        });
        const last = values.length - 1;
        svg.append(svgNode("text", { x: x(last) - 4, y: Math.max(15, y(values[last]) - 13), "text-anchor": "end", class: "chart-value" }, `${values[last]}%`));
    }
    target.append(svg);
}

function renderChild(prefix, recap) {
    const totals = recap.totals || {};
    document.getElementById(`${prefix}_total_answered`).textContent = totals.answered_count ?? 0;
    document.getElementById(`${prefix}_total_correct`).textContent = totals.correct_count ?? 0;
    document.getElementById(`${prefix}_total_acc`).textContent = `${totals.accuracy_pct ?? 0}%`;
    document.getElementById(`${prefix}_total_earned`).textContent = `Rp ${totals.earned ?? 0}`;
    const days = recap.days || [];
    renderChart(prefix, days);
    const rows = document.getElementById(`${prefix}_rows`);
    rows.replaceChildren();
    days.forEach((day) => {
        const row = document.createElement("tr");
        [day.day, day.answered_count ?? 0, day.correct_count ?? 0, `${day.accuracy_pct ?? 0}%`, `Rp ${day.earned ?? 0}`].forEach((value) => {
            const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
        });
        rows.append(row);
    });
}

async function load() {
    const response = await fetch("/api/stats");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Gagal memuat statistik");
    const range = data.recap7.range;
    document.getElementById("rangeText").innerHTML = `Rentan: <span class="range-date">${range.start}</span> sampai <span class="range-date">${range.end}</span>`;
    renderChild("a", data.recap7.children.althafandra);
    renderChild("b", data.recap7.children.alleia);
    const updated = formatUpdate(data.recap7.generated_at);
    document.getElementById("updated_a").textContent = updated;
    document.getElementById("updated_b").textContent = updated;
}

document.getElementById("clearBtn").addEventListener("click", async () => {
    const typed = prompt("Ketik RESET untuk menghapus semua riwayat statistik.");
    if (typed !== "RESET") return;
    const response = await fetch("/api/admin/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) });
    const data = await response.json();
    if (!data.ok) return alert(data.error || "Gagal menghapus data");
    await load();
});

load().catch((error) => { document.getElementById("rangeText").textContent = error.message; });
