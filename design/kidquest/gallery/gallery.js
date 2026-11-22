// KQ-006 development gallery. Reads window.KQ_GALLERY (gallery-data.js, generated) and the committed
// runtime files under static/images/kidquest/ through relative paths. No network, no build step.
(() => {
    const D = window.KQ_GALLERY;
    const ROOT = '../../../';
    const BITS = { N: 1, E: 2, S: 4, W: 8 };
    const SIDES = ['N', 'E', 'S', 'W'];
    const STEP = { N: [0, -1], E: [1, 0], S: [0, 1], W: [-1, 0] };
    const SIDE_ID = { N: 'utara', E: 'timur', S: 'selatan', W: 'barat' };
    const params = new URLSearchParams(location.search);
    const state = {
        theme: params.get('theme') || D.themes[0].id,
        cell: Number(params.get('cell')) || 64,
    };
    const $ = (id) => document.getElementById(id);
    const el = (tag, attrs = {}, ...kids) => {
        const n = document.createElement(tag);
        for (const [k, v] of Object.entries(attrs)) {
            if (k === 'style') { for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith('--')) { n.style.setProperty(sk, sv); } else { n.style[sk] = sv; } } } else if (k === 'class') { n.className = v; } else { n.setAttribute(k, v); }
        }
        kids.flat().forEach((k) => n.append(k instanceof Node ? k : document.createTextNode(String(k))));
        return n;
    };
    const entry = (theme, id) => D.manifests[theme].assets.find((a) => a.asset_id === id);
    const src = (theme, id) => { const e = entry(theme, id); return e ? ROOT + e.runtime_path : null; };
    const sidesOf = (m) => SIDES.filter((s) => m & BITS[s]);
    const pad = (m) => String(m).padStart(2, '0');

    // An <img> that turns into a loud placeholder if the file is missing (never an invisible control).
    function art(theme, id, box) {
        const url = src(theme, id);
        const style = { left: box.x + 'px', top: box.y + 'px', width: box.w + 'px', height: box.h + 'px' };
        const miss = () => el('div', { class: 'missing-img', style, title: `${theme}/${id} missing` }, 'MISSING');
        if (!url) { return miss(); }
        const img = el('img', { src: url, alt: '', style, 'data-asset': `${theme}/${id}` });
        img.addEventListener('error', () => img.replaceWith(miss()));
        return img;
    }

    // Stage: a positioned world fragment. items: {id | gb, x, y (cells), w, h (cells), fh (footprint rows)}
    function stage(theme, cols, rows, items, opts = {}) {
        const c = opts.cell || state.cell;
        const topCells = opts.top || 0;
        const s = el('div', { class: 'stage' + (opts.grid ? ' grid' : ''), style: { '--w': cols * c + 'px', '--h': (rows + topCells) * c + 'px', '--cell': c + 'px', '--top': topCells * c + 'px' } });
        for (const it of items) {
            const e = it.id ? entry(theme, it.id) : null;
            const wpx = e ? e.pixel_size.width / 128 * c : it.w * c;
            const hpx = e ? e.pixel_size.height / 128 * c : it.h * c;
            const fh = it.fh || 1;
            const box = { x: it.x * c, y: (topCells + it.y + fh) * c - hpx, w: wpx, h: hpx };
            if (it.gb) {
                s.append(it.img ? el('img', { src: it.img, alt: '', style: { left: box.x + 'px', top: box.y + 'px', width: box.w + 'px', height: box.h + 'px' } })
                    : el('div', { class: 'gb ' + it.gb, title: 'graybox ' + it.gb, style: { left: box.x + c * 0.2 + 'px', top: box.y + box.h - c * 0.8 + 'px', width: c * 0.6 + 'px', height: c * 0.6 + 'px' } }));
            } else {
                s.append(art(theme, it.id, box));
            }
            if (opts.marks && (it.anchor || (e && e.anchor))) {
                s.append(el('div', { class: 'bounds', style: { left: box.x + 'px', top: box.y + 'px', width: box.w + 'px', height: box.h + 'px' } }));
                const fw = e && e.footprint ? e.footprint.width : it.w;
                s.append(el('div', { class: 'foot', style: { left: it.x * c + 'px', top: (topCells + it.y) * c + 'px', width: fw * c + 'px', height: fh * c + 'px' } }));
                s.append(el('div', { class: 'anchor', style: { left: (it.x + fw / 2) * c + 'px', top: (topCells + it.y + fh) * c + 'px' } }));
            }
        }
        return s;
    }

    function terrainItems(cols, rows, water) {
        const items = [];
        const isWater = (x, y) => water.has(x + ',' + y);
        for (let y = 0; y < rows; y++) {
            for (let x = 0; x < cols; x++) {
                if (!isWater(x, y)) { items.push({ id: 'ground_buildable--base', x, y }); continue; }
                let m = 0;
                for (const s of SIDES) {
                    const nx = x + STEP[s][0], ny = y + STEP[s][1];
                    if (nx >= 0 && ny >= 0 && nx < cols && ny < rows && !isWater(nx, ny)) { m |= BITS[s]; }
                }
                items.push({ id: m ? `shore--mask_${pad(m)}` : 'water--base', x, y });
            }
        }
        return items;
    }
    function roadItems(roads) {
        const set = new Set(roads.map(([x, y]) => x + ',' + y));
        return roads.map(([x, y]) => {
            const m = SIDES.reduce((acc, s) => acc | (set.has((x + STEP[s][0]) + ',' + (y + STEP[s][1])) ? BITS[s] : 0), 0);
            return { id: `road_basic--mask_${pad(m)}`, x, y };
        });
    }

    function card(caption, idText, ...content) {
        return el('div', { class: 'tile-card' }, ...content, el('span', { class: 'id' }, idText), caption ? el('span', { class: 'cap' }, caption) : '');
    }

    // --------------------------------------------------------------- sections
    function renderValidator() {
        const v = D.validator;
        $('validator-out').replaceChildren(
            el('p', { class: 'status ' + (v.ok ? 'ok' : 'bad') }, v.ok ? `✓ scripts/validate_kidquest_assets.py passed (decoder: ${v.decoder})` : `✗ ${v.problems.length} problem(s)`),
            el('pre', {}, [...v.summary, ...v.problems].join('\n')),
            el('p', { class: 'help' }, 'Geometry parity in this page: ' + geometryDiffs() + '. This page only shows; the validator decides.'));
    }
    function geometryDiffs() {
        const keys = ['category', 'pixel_size', 'css_cell_size', 'footprint', 'anchor', 'overhang', 'collision_ref', 'entrances', 'layer', 'alpha_required'];
        const [base, ...rest] = D.themes.map((t) => t.id);
        let n = 0;
        for (const a of D.manifests[base].assets) {
            for (const t of rest) {
                const o = entry(t, a.asset_id);
                if (!o) { n++; continue; }
                for (const k of keys) { if (JSON.stringify(a[k] ?? null) !== JSON.stringify(o[k] ?? null)) { n++; } }
            }
        }
        return n === 0 ? '0 differences across themes' : `${n} difference(s) across themes`;
    }

    function renderCompleteness() {
        const themes = D.themes.map((t) => t.id);
        const ids = D.catalog[themes[0]];
        const head = el('tr', {}, el('th', {}, 'asset'), el('th', {}, 'group'), ...themes.map((t) => el('th', {}, t)));
        const rows = ids.map((a) => el('tr', {}, el('td', {}, a.asset_id), el('td', {}, a.group || ''),
            ...themes.map((t) => {
                const td = el('td', { class: a.golden ? 'ok' : 'na' }, a.golden ? '…' : (a.group === 'buildings' ? 'KQ-029' : 'KQ-023'));
                if (a.golden) {
                    const url = src(t, a.asset_id);
                    if (!url) { td.className = 'miss'; td.textContent = 'MISSING (no entry)'; } else {
                        const probe = new Image();
                        probe.onload = () => { td.textContent = `✓ ${probe.naturalWidth}×${probe.naturalHeight}`; };
                        probe.onerror = () => { td.className = 'miss'; td.textContent = 'MISSING'; };
                        probe.src = url;
                    }
                }
                return td;
            })));
        const golden = ids.filter((a) => a.golden).length;
        $('complete-out').replaceChildren(el('p', { class: 'help' }, `${golden} of ${ids.length} per theme are in the KQ-006 golden set.`), el('table', {}, head, ...rows));
    }

    function renderTerrain() {
        const t = state.theme, c = state.cell;
        const out = [card('tanah bisa dibangun', 'ground_buildable--base', stage(t, 1, 1, [{ id: 'ground_buildable--base', x: 0, y: 0 }])),
            card('air', 'water--base', stage(t, 1, 1, [{ id: 'water--base', x: 0, y: 0 }]))];
        for (let m = 0; m < 16; m++) {
            const land = sidesOf(m);
            out.push(card(land.length ? 'darat di ' + land.map((s) => SIDE_ID[s]).join(' + ') : 'air di semua sisi', `shore--mask_${pad(m)}`,
                stage(t, 1, 1, [{ id: `shore--mask_${pad(m)}`, x: 0, y: 0 }], { cell: c })));
        }
        $('terrain-out').replaceChildren(...out);
    }

    function renderRoads() {
        const t = state.theme;
        const tiles = [], scenes = [];
        for (let m = 0; m < 16; m++) {
            tiles.push(card(sidesOf(m).join('+') || 'isolated', `road_basic--mask_${pad(m)}`,
                stage(t, 1, 1, [{ id: 'ground_buildable--base', x: 0, y: 0 }, { id: `road_basic--mask_${pad(m)}`, x: 0, y: 0 }])));
            const roads = [[1, 1], ...sidesOf(m).map((s) => [1 + STEP[s][0], 1 + STEP[s][1]])];
            scenes.push(card(`mask ${pad(m)} · ${sidesOf(m).join('+') || 'none'}`, '3×3',
                stage(t, 3, 3, [...terrainItems(3, 3, new Set()), ...roadItems(roads)], { grid: document.body.classList.contains('show-grid') })));
        }
        $('roads-out').replaceChildren(...tiles);
        $('roads3-out').replaceChildren(...scenes);
    }

    function renderFeatures() {
        const t = state.theme;
        const theme = D.themes.find((x) => x.id === t);
        const board = card(`${theme.labels.quest_board} · 1×1, anchor (0.5, 1), overhang top 0.5`, 'quest_board--base',
            stage(t, 1, 1, [{ id: 'ground_buildable--base', x: 0, y: 0 }, { id: 'quest_board--base', x: 0, y: 0, anchor: true }], { top: 0.5, marks: true }));
        const icons = card('Kayu · 24 / 32 / 48 CSS px', 'wood--icon', el('div', { style: { display: 'flex', gap: '12px', alignItems: 'end' } },
            ...[24, 32, 48].map((s) => el('img', { src: src(t, 'wood--icon'), alt: 'Kayu', width: s, height: s }))));
        const thumbs = D.themes.map((th) => card(th.name, `${th.id}/theme_thumbnail--base`,
            el('img', { src: src(th.id, 'theme_thumbnail--base'), alt: '', width: 128, height: 128 })));
        $('features-out').replaceChildren(board, icons, ...thumbs);
    }

    function renderOverlays() {
        const t = state.theme;
        const captions = {
            'overlay_focus--base': 'Fokus di sel ini', 'overlay_selection--base': 'Dipilih',
            'overlay_valid--base': 'Bisa dibangun di sini', 'overlay_invalid--base': 'Tidak bisa dibangun di sini: ada air',
            'overlay_connectivity--connected': 'Tersambung ke Papan Pengumuman', 'overlay_connectivity--disconnected': 'Belum tersambung ke jalan',
        };
        $('overlays-out').replaceChildren(...D.shared.assets.map((o) => card(`${captions[o.asset_id] || o.meaning} · cue: ${o.non_color_cue}`, o.asset_id,
            el('div', { style: { display: 'flex', gap: '10px', alignItems: 'end' } }, ...[38, 48, 64].map((c) => {
                const s = stage(t, 1, 1, [{ id: 'ground_buildable--base', x: 0, y: 0 }, { id: 'road_basic--mask_05', x: 0, y: 0 }], { cell: c });
                s.append(el('img', { src: ROOT + o.runtime_path, alt: '', style: { left: 0, top: 0, width: c + 'px', height: c + 'px' } }));
                return s;
            })))));
    }

    function renderProof() {
        const t = state.theme;
        $('proof-out').replaceChildren(...D.manifests[t].assets.filter((a) => !['wood--icon', 'theme_thumbnail--base'].includes(a.asset_id)).map((a) =>
            card('', a.asset_id, el('div', { style: { display: 'flex', gap: '8px', alignItems: 'end' } }, ...[38, 48, 64].map((c) => {
                const items = [{ id: 'ground_buildable--base', x: 0, y: 0 }];
                if (!['ground_buildable--base'].includes(a.asset_id)) { items.push({ id: a.asset_id, x: 0, y: 0 }); }
                return stage(t, 1, 1, items, { cell: c, top: a.overhang ? a.overhang.top : 0 });
            })))));
    }

    function islandStage(theme) {
        const L = D.layout;
        const water = new Set(L.water.map((w) => w.x + ',' + w.y));
        const items = [...terrainItems(L.width, L.height, water), ...roadItems(L.sample_roads)];
        const objs = L.fixed_objects.map((o) => o.kind === 'quest_board' ? { id: 'quest_board--base', x: o.x, y: o.y } : { gb: o.kind === 'blocked_rock' ? 'rock' : 'tree', x: o.x, y: o.y, w: 1, h: 1 });
        objs.push({ gb: 'building', img: '../templates/graybox-buildings/graybox_2x2--plain.png', x: 1, y: 1, w: 2, h: 3, fh: 2, anchor: true });
        objs.push({ gb: 'bridge', img: '../templates/graybox-buildings/graybox_1x2--plain.png', x: 5, y: 4, w: 1, h: 2.25, fh: 2, anchor: true });
        objs.sort((a, b) => (a.y + (a.fh || 1)) - (b.y + (b.fh || 1)) || a.x - b.x);
        return stage(theme, L.width, L.height, [...items, ...objs], { top: 1, grid: true, marks: true });
    }
    function renderDrift() {
        const out = $('drift-out');
        out.classList.toggle('onion', $('opt-onion').checked);
        out.replaceChildren(...D.themes.map((t) => el('div', { class: 'island-card' }, el('div', { class: 'coords' }, `${t.id} · ${t.name} · cell ${state.cell}px · origin (0,0) top-left`), islandStage(t.id))));
        const rows = D.themes.map((t) => el('tr', {}, el('td', {}, t.id), el('td', {}, JSON.stringify(D.drift[t.id].quest_board_bbox)),
            el('td', {}, String(D.drift[t.id].road_layer_max_alpha_diff)), el('td', {}, JSON.stringify(entry(t.id, 'quest_board--base').anchor))));
        $('drift-table').replaceChildren(el('table', {}, el('tr', {}, el('th', {}, 'theme'), el('th', {}, 'quest board alpha bbox (px)'), el('th', {}, 'road layer drift (max α diff)'), el('th', {}, 'board anchor')), ...rows));
    }

    function renderStrings() {
        const longest = [
            ['ok', 'Rumah Kampung sudah tersambung ke Papan Pengumuman lewat jalan di sisi selatan.'],
            ['bad', 'Belum bisa dibangun di sini: tempat ini air. Pilih tanah hijau di Pulau Tunas.'],
            ['info', 'Jembatan Kayu-Bambu menghubungkan jalan di utara dan selatan sungai.'],
        ];
        $('strings-out').replaceChildren(...D.themes.map((t) => el('div', { class: 'string-card', lang: 'id' },
            el('div', { class: 'thumb-row' }, el('img', { src: src(t.id, 'theme_thumbnail--base'), alt: '' }), el('div', {}, el('strong', {}, t.name), el('br'), el('span', { class: 'cap' }, Object.values(t.labels).join(' · ')))),
            ...longest.map(([k, s]) => el('div', { class: 'status ' + k }, s.replace('Papan Pengumuman', t.labels.quest_board).replace('Rumah Kampung', t.labels.starter_house).replace('Jembatan Kayu-Bambu', t.labels.bridge))))));
    }

    function renderGraybox() {
        $('graybox-out').replaceChildren(...['2x2', '1x2', '1x1'].map((n) => el('figure', {},
            el('img', { src: `../templates/graybox-buildings/graybox_${n}--study.png`, alt: `Graybox ${n} geometry study, non-production` }),
            el('figcaption', {}, `graybox_${n} — NON-PRODUCTION geometry study (footprint, anchor, entrances, overhang)`))));
    }
    function renderRenders() {
        const files = ['theme-switch-matrix.png', ...D.themes.flatMap((t) => [`golden-${t.id}-38-48-64.png`, `roads-3x3-${t.id}-64.png`, `roads-3x3-${t.id}-38.png`, `island-${t.id}-64.png`, `island-${t.id}-38.png`]),
            '../templates/cell-128-template.png', '../templates/quest-board-1x1-template.png'];
        $('renders-out').replaceChildren(...files.map((f) => {
            const path = f.startsWith('..') ? f : '../proofs/' + f;
            return el('a', { href: path }, el('img', { src: path, alt: '' }), f.replace('../', ''));
        }));
    }

    function controls() {
        $('theme-switch').replaceChildren(...D.themes.map((t) => {
            const b = el('button', { type: 'button', 'aria-pressed': String(t.id === state.theme) }, t.name);
            b.addEventListener('click', () => { state.theme = t.id; render(); });
            return b;
        }));
        $('size-switch').replaceChildren(...[38, 48, 64].map((c) => {
            const b = el('button', { type: 'button', 'aria-pressed': String(c === state.cell) }, c + ' px');
            b.addEventListener('click', () => { state.cell = c; render(); });
            return b;
        }));
    }
    function render() {
        document.body.classList.toggle('show-bounds', $('opt-bounds').checked);
        document.body.classList.toggle('show-anchor', $('opt-anchor').checked);
        document.body.classList.toggle('show-grid', $('opt-grid').checked);
        document.documentElement.style.setProperty('--cell', state.cell + 'px');
        controls(); renderValidator(); renderTerrain(); renderRoads(); renderFeatures(); renderOverlays(); renderProof(); renderDrift(); renderStrings();
    }
    ['opt-bounds', 'opt-anchor', 'opt-grid', 'opt-onion'].forEach((id) => $(id).addEventListener('change', render));
    if (params.get('onion') === '1') { $('opt-onion').checked = true; }
    if (params.get('grid') === '1') { $('opt-grid').checked = true; }
    renderCompleteness(); renderGraybox(); renderRenders(); render();
    window.__gallery = { state, render, ready: true };
})();
