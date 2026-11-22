/*
 * KidQuest first-house prototype — child shell (KQ-005).
 *
 * Low-fidelity, graybox, no backend. A tiny in-browser "server" simulates the
 * authoritative behaviour from PRD §7.1, §9.1, §12, §14 so reviewers can walk
 * through success, retry, stale, offline, and idempotent-replay states.
 * Nothing here is production code; KQ-010 implements the real slice.
 */
(function () {
    'use strict';

    /* ------------------------------------------------------------------ */
    /* Static content (mirrors PRD §8.1, §11.3, pipeline §12.3)            */
    /* ------------------------------------------------------------------ */
    var STORE_KEY = 'kq-proto-first-house-v1';
    var SIM_KEY = 'kq-proto-sim-v1';

    // Existing app art and per-child accent (pipeline §8.2a). Read-only references into static/.
    var IMG = '../../../../static/images/';
    var PROFILES = {
        althafandra: { name: 'Althafandra', initial: 'A', avatar: 'althafandra-avatar.png', accent: 'profile-theme-blue' },
        alleia: { name: 'Alleia', initial: 'Al', avatar: 'alleia-avatar.png', accent: 'profile-theme-purple' }
    };
    function avatar(id) {
        return '<span class="learner-avatar" aria-hidden="true"><img src="' + IMG + PROFILES[id].avatar + '" alt=""></span>';
    }

    // Names and labels mirror content/kidquest/themes.json (themes[].name, labels.starter_house,
    // labels.quest_board). Indonesian in every theme; drafts pending household content review (pipeline §9.1).
    var THEMES = {
        perkampungan: { name: 'Kampung Ceria', house: 'Rumah Kampung', board: 'Papan Pengumuman', blurb: 'Kayu, bambu, kebun' },
        kingdom: { name: 'Kerajaan Ceria', house: 'Pondok Penjaga', board: 'Papan Berita Kerajaan', blurb: 'Batu, menara bulat' },
        city: { name: 'Kota Ceria', house: 'Rumah Warna-Warni', board: 'Kios Info Kota', blurb: 'Toko ceria, taman' }
    };
    var THEME_ORDER = ['perkampungan', 'kingdom', 'city'];

    // Mirrors content/kidquest/layouts/pulau_tunas_v1.json (KQ-004, content_version 1).
    // (0,0) is north-west, x grows east, y grows south; a position is the footprint's top-left cell.
    // Reconciled 2026-11-21 (decision log C3). Do not edit here without the content file changing.
    var GRID = 8;
    var ZONE = { x0: 1, y0: 1, x1: 4, y1: 2 };            // tutorial_zone x1, y1, 4x2
    var EXPANSION = { x0: 4, y0: 6, x1: 7, y1: 7 };       // expansion_zone, unlocked_by_quest Q005
    var FIXED = { '0,0': 'tree', '7,0': 'tree', '4,3': 'board', '0,7': 'rock', '7,7': 'tree' };
    var WATER = ['3,4', '4,4', '5,4', '6,4', '7,4', '3,5', '4,5', '5,5', '6,5', '7,5', '3,6', '3,7'];
    // bridge_zone (5,4)-(5,5) lies on water; it is not introduced in the first-house release.
    var HOUSE = { type: 'starter_house', w: 2, h: 2, cost: 4 };

    function terrainAt(x, y) {
        return WATER.indexOf(x + ',' + y) >= 0 ? 'water' : 'ground';
    }
    function inZone(x, y) {
        return x >= ZONE.x0 && x <= ZONE.x1 && y >= ZONE.y0 && y <= ZONE.y1;
    }
    function inExpansion(x, y) {
        return x >= EXPANSION.x0 && x <= EXPANSION.x1 && y >= EXPANSION.y0 && y <= EXPANSION.y1;
    }
    // Decision D11 (proposal, 2026-11-22): a tap inside the striped zone picks the footprint that
    // covers the tapped cell and fits the zone, so every striped cell works. The request still sends
    // the footprint's top-left cell (content convention). Outside the zone the tapped cell is the
    // top-left cell, so the child sees the concrete reason it cannot be built there.
    function fitOrigin(x, y) {
        if (!inZone(x, y)) { return { x: x, y: y }; }
        return {
            x: Math.min(Math.max(x, ZONE.x0), ZONE.x1 - HOUSE.w + 1),
            y: Math.min(Math.max(y, ZONE.y0), ZONE.y1 - HOUSE.h + 1)
        };
    }

    // Q001 strings, verbatim from content/kidquest/quests.json (copy_review_status: pending_product_review).
    var Q001 = {
        title: 'Rumah Pertama',
        story: 'Kita butuh 10 kayu untuk membangun rumah. Sudah ada 6 kayu.',
        prompt: 'Kita butuh 10 kayu. Sudah ada 6. Berapa lagi?',
        hints: [
            'Kita sudah punya 6 kayu. Hitung terus sampai 10. Berapa kali kamu menghitung?',
            'Bayangkan 10 tempat kayu. 6 tempat sudah terisi. Hitung tempat yang masih kosong.'
        ],
        rewardPreview: 'Hadiah: kayu yang kurang + Cetak biru Rumah',
        rewardMessage: 'Hebat! Kamu dapat 4 kayu dan cetak biru Rumah.'
    };

    /* ------------------------------------------------------------------ */
    /* Storage (wrapped: private windows may throw)                        */
    /* ------------------------------------------------------------------ */
    var memoryStore = {};
    function readJSON(key, fallback) {
        try {
            var raw = window.localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) {
            return memoryStore[key] || fallback;
        }
    }
    function writeJSON(key, value) {
        memoryStore[key] = value;
        try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* memory only */ }
    }

    function freshWorld() {
        return {
            theme: 'perkampungan',
            quest: 'AVAILABLE',
            attempts: 0,
            hints: 0,
            wood: 0,
            blueprints: [],
            buildings: [],
            worldVersion: 1,
            lastChange: null,
            themeIntroDone: false,
            placeTutorialDone: false,
            catalogTipDone: false,
            idem: {}
        };
    }

    var store = readJSON(STORE_KEY, null) || { active: null, worlds: {} };
    var sim = readJSON(SIM_KEY, null) || {};
    sim = Object.assign({
        offline: false, dropNext: false, themeFail: false, staleNext: false,
        dailyCap: false, slow: false, economy: false, reduceMotion: false, text200: false
    }, sim);

    function S() {
        if (!store.active) { return null; }
        if (!store.worlds[store.active]) { store.worlds[store.active] = freshWorld(); }
        return store.worlds[store.active];
    }
    function save() { writeJSON(STORE_KEY, store); }
    function saveSim() { writeJSON(SIM_KEY, sim); }

    /* ------------------------------------------------------------------ */
    /* Simulated server (authoritative)                                    */
    /* ------------------------------------------------------------------ */
    var keySeq = Date.now() % 100000;
    function newKey(kind) { keySeq += 1; return kind + '-' + keySeq; }

    function validatePlacement(st, ox, oy) {
        var x, y, k, obj, b;
        for (y = oy; y < oy + HOUSE.h; y++) {
            for (x = ox; x < ox + HOUSE.w; x++) {
                if (x < 0 || y < 0 || x >= GRID || y >= GRID) { return { ok: false, code: 'bounds' }; }
            }
        }
        for (y = oy; y < oy + HOUSE.h; y++) {
            for (x = ox; x < ox + HOUSE.w; x++) {
                k = x + ',' + y;
                obj = FIXED[k];
                if (obj) { return { ok: false, code: obj }; }
                for (b = 0; b < st.buildings.length; b++) {
                    var bl = st.buildings[b];
                    if (x >= bl.x && x < bl.x + HOUSE.w && y >= bl.y && y < bl.y + HOUSE.h) { return { ok: false, code: 'building' }; }
                }
                if (terrainAt(x, y) === 'water') { return { ok: false, code: 'water' }; }
                if (inExpansion(x, y)) { return { ok: false, code: 'expansion' }; }
            }
        }
        for (y = oy; y < oy + HOUSE.h; y++) {
            for (x = ox; x < ox + HOUSE.w; x++) {
                if (!inZone(x, y)) { return { ok: false, code: 'zone' }; }
            }
        }
        return { ok: true };
    }

    var INVALID_TEXT = {
        bounds: 'Tidak bisa di sini: rumah keluar dari pulau.',
        tree: 'Tidak bisa di sini: ada pohon.',
        rock: 'Tidak bisa di sini: ada batu.',
        board: 'Tidak bisa di sini: ada papan misi.',
        building: 'Tidak bisa di sini: sudah ada bangunan.',
        water: 'Tidak bisa di sini: ada air.',
        expansion: 'Tidak bisa di sini: area ini belum dibuka.',
        zone: 'Tidak bisa di sini: pilih di dalam zona bergaris.'
    };

    function applyMutation(kind, p, st) {
        if (kind === 'start') {
            if (st.quest === 'AVAILABLE') { st.quest = 'IN_PROGRESS'; }
            return { ok: true, quest: st.quest };
        }
        if (kind === 'answer') {
            if (sim.dailyCap) {
                return { ok: false, error: { code: 'DAILY_CAP_REACHED', message: 'Latihan hari ini sudah cukup. Tantangan bisa dilanjutkan besok.' } };
            }
            if (st.quest !== 'IN_PROGRESS') {
                return { ok: false, error: { code: 'QUEST_LOCKED', message: 'Tantangan ini sudah selesai.' } };
            }
            st.attempts += 1;
            if (String(p.answer).trim() === '4') {
                st.quest = 'READY_TO_BUILD';
                st.wood += 4;
                if (st.blueprints.indexOf('starter_house') < 0) { st.blueprints.push('starter_house'); }
                st.lastChange = 'Kamu menjawab benar dan mendapat 4 kayu dan cetak biru Rumah.';
                return { ok: true, correct: true, awarded: { wood: 4, blueprint: 'starter_house' }, quest: st.quest };
            }
            st.lastChange = 'Kamu sudah mencoba tantangan Rumah Pertama ' + st.attempts + ' kali.';
            return { ok: true, correct: false, hintLevel: st.attempts >= 2 ? 2 : 1, quest: st.quest };
        }
        if (kind === 'place') {
            if (sim.staleNext) {
                sim.staleNext = false; saveSim();
                st.worldVersion += 1; // something changed elsewhere (another tab/device)
                return { ok: false, error: { code: 'WORLD_VERSION_CONFLICT', message: 'Duniamu baru saja diperbarui.' }, noStore: true };
            }
            if (p.worldVersion !== st.worldVersion) {
                return { ok: false, error: { code: 'WORLD_VERSION_CONFLICT', message: 'Duniamu baru saja diperbarui.' }, noStore: true };
            }
            if (st.blueprints.indexOf('starter_house') < 0 || st.wood < HOUSE.cost) {
                return { ok: false, error: { code: 'INSUFFICIENT_RESOURCES', message: 'Kayu atau cetak biru belum cukup.' } };
            }
            var v = validatePlacement(st, p.x, p.y);
            if (!v.ok) { return { ok: false, error: { code: 'INVALID_PLACEMENT', message: INVALID_TEXT[v.code] } }; }
            st.wood -= HOUSE.cost;
            st.buildings.push({ id: 'bld_1', type: HOUSE.type, x: p.x, y: p.y, rotation: 0 });
            st.quest = 'COMPLETED';
            st.worldVersion += 1;
            st.lastChange = 'Kamu membangun rumah pertama. 4 kayu dipakai.';
            return { ok: true, building: st.buildings[st.buildings.length - 1], quest: st.quest };
        }
        if (kind === 'theme') {
            if (sim.themeFail) {
                return { ok: false, error: { code: 'NETWORK_FAILED', message: 'Tema belum tersimpan.' }, noStore: true };
            }
            if (THEME_ORDER.indexOf(p.theme) < 0) {
                return { ok: false, error: { code: 'INVALID_THEME', message: 'Tema tidak dikenal.' } };
            }
            if (st.theme !== p.theme) {
                st.theme = p.theme;
                st.worldVersion += 1;
                st.lastChange = 'Kamu mengganti tema dunia menjadi ' + THEMES[p.theme].name + '.';
            }
            return { ok: true, theme: st.theme, worldVersion: st.worldVersion };
        }
        return { ok: false, error: { code: 'UNKNOWN', message: 'Tidak dikenal.' } };
    }

    function server(kind, key, payload) {
        return new Promise(function (resolve) {
            window.setTimeout(function () {
                var st = S();
                if (st.idem[key]) {
                    resolve(Object.assign({ replayed: true }, st.idem[key]));
                    return;
                }
                var out = applyMutation(kind, payload || {}, st);
                if (!out.noStore) { st.idem[key] = out; }
                save();
                if (sim.dropNext && !out.noStore) {
                    // Committed on the server, but the response never reached the browser.
                    sim.dropNext = false; saveSim();
                    resolve({ uncertain: true });
                    return;
                }
                resolve(out);
            }, sim.slow ? 1500 : 350);
        });
    }

    /* ------------------------------------------------------------------ */
    /* Transient UI state                                                  */
    /* ------------------------------------------------------------------ */
    var ui = {
        view: 'entry',
        load: 'ready',          // ready | loading | error
        showResume: false,
        inspect: null,          // {x,y}
        cursor: { x: 4, y: 3 },
        place: null,            // {origin:{x,y}|null, wv, msg}
        previewTheme: null,
        themeMsg: null,         // {type, text}
        answer: '',
        feedback: null,         // {type:'wrong'|'cap'|'hint', level}
        busy: null,             // 'start'|'answer'|'place'|'theme'
        checking: null,         // {kind, key, payload}
        pendingKey: {},         // kind -> idempotency key for the current intent
        justBuilt: false,
        catalogTip: false,
        menuOpen: false,
        focus: null,
        popup: null,            // 'wrong' while the wrong-answer popup is open
        invariance: null
    };

    var VIEW_KIND = {
        entry: 'entry', choose: 'entry', 'quiz-stub': 'entry',
        world: 'world', place: 'world', checkpoint: 'world', theme: 'world',
        missions: 'task', quest: 'task', challenge: 'task', reward: 'task', catalog: 'task', help: 'task', q002: 'task'
    };
    var NAV_OF = {
        world: 'world', checkpoint: 'world', theme: 'world',
        missions: 'missions', quest: 'missions', challenge: 'missions', reward: 'missions', q002: 'missions',
        catalog: 'catalog', place: 'catalog'
    };

    /* ------------------------------------------------------------------ */
    /* Helpers                                                              */
    /* ------------------------------------------------------------------ */
    function $(sel, root) { return (root || document).querySelector(sel); }
    function announce(text) {
        var live = $('#live');
        live.textContent = '';
        window.setTimeout(function () { live.textContent = text; }, 40);
    }

    var ICONS = {
        world: '<path d="M3 18c3-2 6-2 9 0s6 2 9 0"/><path d="M12 15V6"/><path d="M12 6c-3 0-5 2-6 4 2-1 4-1 6 0 2-1 4-1 6 0-1-2-3-4-6-4z"/>',
        missions: '<path d="M5 21V4"/><path d="M5 4h12l-2.5 4L17 12H5"/>',
        build: '<path d="M3 21l9-9"/><path d="M11 5l6-2 4 4-2 6-4-4z"/>',
        menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
        check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
        cross: '<path d="M6 6l12 12M18 6L6 18"/>',
        lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
        bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.4 1 2.5h6c0-1.1.4-1.9 1-2.5A6 6 0 0 0 12 3z"/>',
        star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
        back: '<path d="M15 5l-7 7 7 7"/>',
        wood: '<rect x="3" y="8" width="18" height="8" rx="2"/><circle cx="17.5" cy="12" r="2"/>',
        blueprint: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 13l4-4 4 4M9.5 13v4h5v-4"/>',
        offline: '<path d="M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8.5 15.5a5 5 0 0 1 7 0"/><path d="M3 3l18 18"/>',
        refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
        info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
        palette: '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.7 1.5-1.5S13 18 13 17s.7-1.5 1.5-1.5H17a4 4 0 0 0 4-4C21 6.8 17 3 12 3z"/><circle cx="7.5" cy="11" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16.5" cy="11" r="1"/>',
        up: '<path d="M6 15l6-6 6 6"/>', down: '<path d="M6 9l6 6 6-6"/>',
        left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17v.5"/>',
        user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
        quiz: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
        motion: '<path d="M3 12h4l2.5-5 5 10 2.5-5h4"/>',
        shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
        close: '<path d="M6 6l12 12M18 6L6 18"/>'
    };
    function icon(name, cls) {
        return '<svg class="icon ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICONS[name] + '</svg>';
    }
    function houseArt() {
        return '<div class="house-art" aria-hidden="true"><div class="house-roof"></div><div class="house-body"></div><div class="house-door"></div></div>';
    }
    function pos(x, y, w, h) {
        return 'left:calc(var(--tile)*' + x + ');top:calc(var(--tile)*' + y + ');width:calc(var(--tile)*' + w + ');height:calc(var(--tile)*' + h + ')';
    }
    function themeName() { return THEMES[ui.previewTheme || S().theme].name; }
    function houseAt(st, x, y) {
        for (var i = 0; i < st.buildings.length; i++) {
            var b = st.buildings[i];
            if (x >= b.x && x < b.x + HOUSE.w && y >= b.y && y < b.y + HOUSE.h) { return b; }
        }
        return null;
    }
    function offlineReason() {
        return sim.offline ? '<p class="muted" data-reason="offline">' + icon('offline', 'icon-sm') + ' Butuh internet untuk menyimpan. Duniamu tetap aman.</p>' : '';
    }

    /* ------------------------------------------------------------------ */
    /* Render: entry views                                                 */
    /* ------------------------------------------------------------------ */
    // Entry mirrors home.html: .home-card with the star mascot and the two profile cards.
    function renderEntry() {
        var mascot = '<img class="star-mascot" src="' + IMG + 'star-mascot.png" alt="">';
        if (ui.view === 'entry') {
            return '<main id="main" class="entry" tabindex="-1">' +
                '<div class="entry-header">' + mascot +
                '<h1 id="entry-title" tabindex="-1">Pilih akun dulu</h1>' +
                '<p>Siapa yang main hari ini?</p></div>' +
                '<div class="entry-choices">' +
                Object.keys(PROFILES).map(function (id) {
                    return '<button class="profile-card ' + PROFILES[id].accent + '" data-act="pick-profile" data-id="' + id + '" data-fk="profile-' + id + '">' +
                        avatar(id) + '<span class="profile-name">' + PROFILES[id].name + '</span>' +
                        '<span class="continue-button">Lanjutkan ' + icon('right', 'icon-sm') + '</span></button>';
                }).join('') +
                '</div></main>';
        }
        if (ui.view === 'choose') {
            var p = PROFILES[store.active];
            return '<main id="main" class="entry ' + p.accent + '" tabindex="-1">' +
                '<div class="entry-header">' + mascot +
                '<h1 id="entry-title" tabindex="-1">Mau main apa, ' + p.name + '?</h1></div>' +
                '<div class="entry-body">' +
                '<button class="choice" data-act="enter-kidquest" data-fk="enter-kq"><span class="tab-icon">' + icon('world') + '</span>' +
                '<span><strong>KidQuest</strong><span class="muted">Belajar matematika sambil membangun pulaumu</span></span></button>' +
                '<button class="choice" data-act="go" data-view="quiz-stub" data-fk="enter-quiz"><span class="tab-icon">' + icon('quiz') + '</span>' +
                '<span><strong>Kuis</strong><span class="muted">Latihan soal seperti biasa</span></span></button>' +
                '</div>' +
                '<div class="entry-footer"><button class="btn btn-text" data-act="go" data-view="entry" data-fk="switch">Bukan ' + p.name + '? Ganti akun</button></div>' +
                '</main>';
        }
        // quiz-stub
        return '<main id="main" class="entry" tabindex="-1">' +
            '<div class="entry-header"><h1 id="entry-title" tabindex="-1">Kuis</h1></div>' +
            '<div class="entry-body">' +
            '<div class="alert alert-info">' + icon('info') + '<div><p>Di aplikasi asli, tombol ini membuka Kuis yang sudah ada (Matematika dan Pengetahuan Umum). Kuis tidak diubah oleh KidQuest.</p><p class="muted">Prototipe berhenti di sini.</p></div></div>' +
            '<button class="btn btn-primary" data-act="enter-kidquest" data-fk="back-kq">Kembali ke KidQuest</button>' +
            '</div></main>';
    }

    /* ------------------------------------------------------------------ */
    /* Render: shell pieces                                                */
    /* ------------------------------------------------------------------ */
    // Header card mirrors quiz.html .quiz-header: avatar, "Nama", name, a context line, the header
    // link (here: Menu), and a compact .today-card. No level/XP (decision C9): the context line names
    // the island instead of the quiz "Tingkat".
    function renderHeader() {
        var st = S();
        var p = PROFILES[store.active];
        // Progressive onboarding (AC-22): the resource card appears once the child owns something,
        // or where cost matters (catalog). Hidden in world-centric modes on phones (see CSS).
        var owns = st.wood > 0 || st.blueprints.length > 0;
        var showCard = (owns || ui.view === 'catalog') && ui.view !== 'place' && ui.view !== 'theme' && ui.view !== 'challenge';
        var hasBp = st.blueprints.indexOf('starter_house') >= 0;
        var card = showCard ? '<section class="today-card" aria-label="Bahanmu" data-testid="wood-chip">' +
            '<div class="today-title">' + icon('wood') + ' Bahanmu</div>' +
            '<div class="today-total"><strong>' + st.wood + '</strong> kayu</div>' +
            '<div class="today-divider" aria-hidden="true"></div>' +
            '<div class="today-detail"><span>' + icon('blueprint', 'icon-sm') + 'Cetak biru: <b>' + (hasBp ? 'Rumah' : 'belum ada') + '</b></span></div>' +
            '<img class="gift-icon" src="' + IMG + 'reward-gift.png" alt="">' +
            '<span class="gift-sparkle sparkle-one" aria-hidden="true">✦</span><span class="gift-sparkle sparkle-two" aria-hidden="true">✦</span><span class="gift-sparkle sparkle-three" aria-hidden="true">✦</span>' +
            '</section>' : '';
        return '<header class="kq-header">' +
            '<div class="learner-summary">' + avatar(store.active) +
            '<div class="learner-copy"><span>Nama</span><strong class="hud-name">' + p.name + '</strong><span>Pulau: <b>Pulau Tunas</b></span></div>' +
            '<button class="header-link" data-act="open-menu" data-fk="menu-btn" aria-haspopup="dialog">' + icon('menu') + '<span>Menu</span></button>' +
            '</div>' + card + '</header>';
    }

    // Tab row mirrors quiz.html .quiz-tabs (icon tile + label, highlighted active tab). No Dompet.
    function renderNav() {
        var current = NAV_OF[ui.view];
        var items = [['world', 'Dunia', 'world'], ['missions', 'Misi', 'missions'], ['catalog', 'Bangun', 'build']];
        return '<nav class="nav" aria-label="Navigasi utama">' + items.map(function (it) {
            return '<button class="nav-item" data-act="nav" data-view="' + it[0] + '" data-fk="nav-' + it[0] + '"' +
                (current === it[0] ? ' aria-current="page"' : '') + '><span class="tab-icon" aria-hidden="true">' + icon(it[2]) + '</span><span>' + it[1] + '</span></button>';
        }).join('') + '</nav>';
    }

    function renderBanners() {
        var out = '';
        if (sim.offline) {
            out += '<div class="alert alert-offline" role="status">' + icon('offline') +
                '<div><p><strong>Kamu sedang offline.</strong> Duniamu aman. Menjawab dan membangun bisa lagi saat internet tersambung.</p></div></div>';
        }
        if (ui.view === 'place') {
            out += '<div class="alert alert-mode">' + icon('build') +
                '<div><p><strong>Mode Bangun: Rumah.</strong> Belum ada yang berubah sebelum kamu menekan “Bangun di Sini”.</p></div>' +
                '<button class="btn btn-secondary" data-act="cancel-place" data-fk="cancel-place-top">Batal</button></div>';
        }
        if (ui.view === 'theme' && ui.previewTheme && ui.previewTheme !== S().theme) {
            out += '<div class="alert alert-info" role="status">' + icon('palette') +
                '<div><p><strong>Pratinjau: ' + THEMES[ui.previewTheme].name + '.</strong> Belum dipakai. Tekan “Gunakan Tema” atau “Batal”.</p></div></div>';
        }
        return out;
    }

    /* ------------------------------------------------------------------ */
    /* Render: objective / resume                                          */
    /* ------------------------------------------------------------------ */
    function objectiveModel(st) {
        if (st.quest === 'AVAILABLE') {
            return { eyebrow: 'Misi sekarang', title: 'Rumah Pertama', text: 'Bantu siapkan kayu untuk rumah pertamamu.', cta: 'Mulai Misi', act: 'open-quest' };
        }
        if (st.quest === 'IN_PROGRESS') {
            return { eyebrow: 'Misi sekarang', title: 'Rumah Pertama', text: 'Tantanganmu belum selesai. Jawaban yang sudah dikirim tetap tersimpan.', cta: 'Lanjutkan Tantangan', act: 'resume-challenge' };
        }
        if (st.quest === 'READY_TO_BUILD') {
            return { eyebrow: 'Misi sekarang', title: 'Bangun Rumah', text: 'Kayu dan cetak biru sudah siap. Ayo pilih tempat rumahmu.', cta: 'Bangun Rumah', act: 'start-place' };
        }
        if (sim.economy) {
            return { eyebrow: 'Misi berikutnya', title: 'Kebun Tunas', text: 'Rumah pertamamu sudah jadi! Misi berikutnya sudah terbuka.', cta: 'Lihat Misi', act: 'open-q002' };
        }
        if (!st.themeIntroDone) {
            return { eyebrow: 'Baru', title: 'Tema Dunia', text: 'Rumah pertamamu sudah jadi! Sekarang kamu bisa mengganti tampilan pulaumu. Gratis, dan rumahmu tetap di tempatnya.', cta: 'Coba Tema Dunia', act: 'open-theme', later: true };
        }
        return { eyebrow: 'Duniamu', title: 'Lengkap untuk sekarang', text: 'Bangunan berikutnya belum dibuka; orang tuamu yang bisa membukanya. Kamu boleh melihat-lihat pulaumu atau latihan di Kuis.', cta: 'Main Kuis', act: 'go', view: 'quiz-stub' };
    }

    function renderObjective(compact) {
        var st = S();
        if (ui.load === 'loading') {
            return '<section class="card" aria-busy="true" aria-label="Memuat"><div class="skeleton" style="height:18px;width:40%"></div><div class="skeleton" style="height:28px;width:70%"></div><div class="skeleton" style="height:44px"></div><p class="muted">Memuat duniamu…</p></section>';
        }
        if (ui.load === 'error') {
            return '<section class="card" aria-labelledby="load-err"><div class="alert alert-error" role="alert">' + icon('info') +
                '<div><h2 id="load-err" tabindex="-1" style="font-size:1.125rem">Duniamu belum bisa dibuka.</h2><p>Periksa internet, lalu coba lagi. Tidak ada yang hilang.</p>' +
                '<button class="btn btn-primary" data-act="retry-load" data-fk="retry-load">' + icon('refresh') + 'Coba Lagi</button></div></div></section>';
        }
        if (compact) {
            // Desktop left column on non-home views: orientation only, no competing primary action.
            var cm = objectiveModel(st);
            return '<section class="card" aria-labelledby="obj-title" data-testid="objective-compact">' +
                '<p class="eyebrow">' + cm.eyebrow + '</p><h2 id="obj-title" tabindex="-1" style="font-size:1.125rem">' + cm.title + '</h2>' +
                (st.quest !== 'COMPLETED' ? questStatus(st.quest) : '') + '</section>';
        }
        if (ui.showResume) {
            var r = resumeModel(st);
            return '<section class="card card-accent" aria-labelledby="resume-title" data-testid="resume">' +
                '<p class="eyebrow">Selamat datang lagi</p>' +
                '<h2 id="resume-title" tabindex="-1">Sejak Kunjungan Terakhir</h2>' +
                '<ul class="list-plain">' +
                '<li>' + icon('check', 'icon-sm') + '<span>' + st.lastChange + '</span></li>' +
                '<li>' + icon('info', 'icon-sm') + '<span>Sekarang: ' + r.current + '</span></li>' +
                '<li>' + icon('shield', 'icon-sm') + '<span>Semua sudah tersimpan otomatis.</span></li>' +
                '</ul>' +
                '<div class="btn-row">' +
                (r.cta ? '<button class="btn btn-primary" data-act="' + r.act + '" data-fk="resume-cta">' + r.cta + '</button>' : '') +
                '<button class="btn btn-secondary" data-act="dismiss-resume" data-fk="resume-close">Tutup</button></div></section>';
        }
        var m = objectiveModel(st);
        return '<section class="card card-accent" aria-labelledby="obj-title" data-testid="objective">' +
            '<p class="eyebrow">' + m.eyebrow + '</p>' +
            '<h2 id="obj-title" tabindex="-1">' + m.title + '</h2>' +
            '<p class="lead">' + m.text + '</p>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="' + m.act + '"' + (m.view ? ' data-view="' + m.view + '"' : '') + ' data-fk="obj-cta">' + m.cta + '</button>' +
            (m.later ? '<button class="btn btn-text" data-act="theme-later" data-fk="obj-later">Nanti saja</button>' : '') +
            '</div></section>';
    }

    function resumeModel(st) {
        if (st.quest === 'IN_PROGRESS') {
            return { current: 'tantangan Rumah Pertama belum selesai.', cta: 'Lanjutkan Tantangan', act: 'resume-challenge' };
        }
        if (st.quest === 'READY_TO_BUILD') {
            return { current: 'kayu dan cetak biru sudah siap. Rumah belum dibangun.', cta: 'Lanjutkan: Bangun Rumah', act: 'start-place' };
        }
        if (st.quest === 'COMPLETED') {
            return { current: 'rumahmu berdiri di tempat yang sama.', cta: null };
        }
        return { current: 'misi Rumah Pertama bisa dimulai.', cta: 'Mulai Misi', act: 'open-quest' };
    }

    /* ------------------------------------------------------------------ */
    /* Render: world grid                                                  */
    /* ------------------------------------------------------------------ */
    function cellLabel(st, x, y) {
        var t = THEMES[ui.previewTheme || st.theme];
        var where = ' di kolom ' + (x + 1) + ', baris ' + (y + 1);
        var b = houseAt(st, x, y);
        var what;
        if (b) { what = t.house + ', rumahmu. Pintu di sisi bawah'; }
        else if (FIXED[x + ',' + y] === 'tree') { what = 'pohon'; }
        else if (FIXED[x + ',' + y] === 'rock') { what = 'batu'; }
        else if (FIXED[x + ',' + y] === 'board') { what = t.board + (st.quest === 'AVAILABLE' || st.quest === 'IN_PROGRESS' ? ', ada misi' : ''); }
        else if (terrainAt(x, y) === 'water') { what = 'Air'; }
        else if (inExpansion(x, y)) { what = 'Area belum dibuka'; }
        else { what = 'Tanah kosong'; }
        what = what.charAt(0).toUpperCase() + what.slice(1);
        return what + where + (ui.view === 'place' && inZone(x, y) ? ', zona rumah' : '');
    }

    function renderWorld() {
        var st = S();
        if (ui.load === 'loading') {
            return '<div class="world-frame" aria-hidden="true"><div class="skeleton" style="width:calc(var(--tile)*8);height:calc(var(--tile)*8)"></div></div>';
        }
        if (ui.load === 'error') { return ''; }
        var cells = '';
        for (var y = 0; y < GRID; y++) {
            cells += '<div role="row" style="display:contents">';
            for (var x = 0; x < GRID; x++) {
                var isCursor = ui.cursor.x === x && ui.cursor.y === y;
                cells += '<button role="gridcell" class="cell' + (ui.view === 'place' && !st.placeTutorialDone && inZone(x, y) ? ' pulse' : '') + '"' +
                    ' data-act="cell" data-x="' + x + '" data-y="' + y + '" data-fk="cell-' + x + '-' + y + '"' +
                    ' data-terrain="' + terrainAt(x, y) + '"' + (inZone(x, y) ? ' data-zone="tutorial"' : (inExpansion(x, y) ? ' data-zone="expansion"' : '')) +
                    ' tabindex="' + (isCursor ? '0' : '-1') + '" aria-label="' + cellLabel(st, x, y) + '"></button>';
            }
            cells += '</div>';
        }
        var objs = '';
        Object.keys(FIXED).forEach(function (k) {
            var xy = k.split(',').map(Number);
            objs += '<div class="obj obj-' + FIXED[k] + '" style="' + pos(xy[0], xy[1], 1, 1) + '" aria-hidden="true"></div>';
            if (FIXED[k] === 'board' && (st.quest === 'AVAILABLE' || st.quest === 'IN_PROGRESS') && ui.view !== 'place') {
                objs += '<div class="obj" style="' + pos(xy[0], xy[1], 1, 1) + ';overflow:visible"><span class="badge">!<span>Misi</span></span></div>';
            }
        });
        st.buildings.forEach(function (b) {
            objs += '<div class="obj obj-house" data-testid="house" style="' + pos(b.x, b.y, HOUSE.w, HOUSE.h) + '" aria-hidden="true">' + houseArt() + '</div>';
            if (ui.justBuilt) {
                objs += '<div class="built-flash" style="' + pos(b.x, b.y, HOUSE.w, HOUSE.h) + '" aria-hidden="true">' + icon('star') + '</div>';
            }
        });
        if (ui.view === 'place') {
            var o = ui.place.origin;
            if (o) {
                var v = validatePlacement(st, o.x, o.y);
                var w = Math.min(HOUSE.w, GRID - o.x), h = Math.min(HOUSE.h, GRID - o.y);
                objs += '<div class="preview ' + (v.ok ? 'valid' : 'invalid') + '" data-testid="preview" style="' + pos(o.x, o.y, w, h) + '" aria-hidden="true">' +
                    '<span class="preview-mark">' + icon(v.ok ? 'check' : 'cross', 'icon-sm') + '</span>' +
                    (v.ok ? '<span class="preview-door">Pintu</span>' : '') + '</div>';
            }
            var fc = fitOrigin(ui.cursor.x, ui.cursor.y);
            if (!o || o.x !== fc.x || o.y !== fc.y) {
                var cw = Math.min(HOUSE.w, GRID - fc.x), ch = Math.min(HOUSE.h, GRID - fc.y);
                objs += '<div class="preview hover" style="' + pos(fc.x, fc.y, cw, ch) + '" aria-hidden="true"></div>';
            }
        }
        var caption = '<p class="world-caption">' +
            (ui.view === 'place' ? '<span><span class="legend-swatch" aria-hidden="true"></span>Bergaris = zona rumah</span>' : '') +
            '<span>Tema: ' + themeName() + '</span><span class="proto-tag">Graybox, bukan gambar final</span></p>';
        return '<section class="world-frame" aria-label="Pulau ' + PROFILES[store.active].name + '">' +
            '<div class="world-grid" role="grid" aria-label="Pulau 8 kali 8 kotak. Gunakan tombol panah untuk berpindah kotak." data-testid="grid">' + cells + objs + '</div>' +
            '</section>' + caption;
    }

    /* ------------------------------------------------------------------ */
    /* Render: panels                                                      */
    /* ------------------------------------------------------------------ */
    function backBtn(view, label) {
        return '<button class="btn btn-secondary" data-act="go" data-view="' + view + '" data-fk="back-' + ui.view + '" aria-label="' + (label || 'Kembali') + '">' + icon('back') + '<span>Kembali</span></button>';
    }

    function panelChecking() {
        return '<section class="card" aria-labelledby="chk-title" data-testid="checking">' +
            '<div class="alert alert-info" role="status">' + icon('refresh') +
            '<div><h2 id="chk-title" tabindex="-1" style="font-size:1.125rem">Memeriksa perubahan…</h2>' +
            '<p>Internet sempat terputus. Kami memastikan perubahanmu sudah tersimpan. Tidak akan dihitung dua kali.</p>' +
            '<button class="btn btn-primary" data-act="recheck" data-fk="recheck"' + (sim.offline ? ' disabled' : '') + '>' + icon('refresh') + 'Periksa Lagi</button>' +
            offlineReason() + '</div></div></section>';
    }

    function panelWorld() {
        var st = S();
        if (ui.load !== 'ready') { return ''; }
        if (!ui.inspect) {
            return '<section class="card" aria-labelledby="ctx-title"><h2 id="ctx-title" class="eyebrow" style="font-size:.875rem">Lihat pulau</h2>' +
                '<p>Ketuk benda di pulau untuk melihatnya.</p></section>';
        }
        var x = ui.inspect.x, y = ui.inspect.y;
        var t = THEMES[st.theme];
        var title, body, action = '';
        var b = houseAt(st, x, y);
        var f = FIXED[x + ',' + y];
        if (b) {
            title = t.house;
            body = 'Rumah pertamamu. Pintunya ada di sisi bawah. Rumah ini tidak menghasilkan uang; ia tanda kemajuanmu.';
        } else if (f === 'board') {
            title = t.board;
            body = 'Tempat melihat misi.';
            action = '<button class="btn btn-primary" data-act="nav" data-view="missions" data-fk="insp-missions">Lihat Misi</button>';
        } else if (f === 'tree') {
            title = 'Pohon'; body = 'Pohon tidak bisa dipindah. Tidak bisa membangun di sini.';
        } else if (f === 'rock') {
            title = 'Batu'; body = 'Batu tidak bisa dipindah. Tidak bisa membangun di sini.';
        } else if (terrainAt(x, y) === 'water') {
            title = 'Air'; body = 'Tidak bisa membangun di atas air.';
        } else if (inExpansion(x, y)) {
            title = 'Area belum dibuka';
            body = 'Area ini terbuka setelah misi Jembatan Kecil selesai. Sekarang belum bisa dipakai.';
        } else {
            title = 'Tanah kosong'; body = 'Tanah ini bisa dipakai untuk bangunan nanti.';
        }
        return '<section class="card" aria-labelledby="insp-title" data-testid="inspector">' +
            '<div class="panel-head"><h2 id="insp-title" tabindex="-1">' + title + '</h2>' +
            '<button class="btn btn-secondary" data-act="close-inspect" data-fk="insp-close">' + icon('close') + '<span>Tutup</span></button></div>' +
            '<p>' + body + '</p><p class="muted">Kolom ' + (x + 1) + ', baris ' + (y + 1) + '</p>' + action + '</section>';
    }

    function questStatus(state) {
        var map = {
            AVAILABLE: ['status-available', 'star', 'Bisa dimulai'],
            IN_PROGRESS: ['status-active', 'clock', 'Sedang dikerjakan'],
            READY_TO_BUILD: ['status-ready', 'build', 'Siap dibangun'],
            COMPLETED: ['status-done', 'check', 'Selesai']
        };
        var m = map[state];
        return '<span class="status ' + m[0] + '">' + icon(m[1], 'icon-sm') + m[2] + '</span>';
    }

    function panelMissions() {
        var st = S();
        var q2;
        if (st.quest !== 'COMPLETED') {
            q2 = '<span class="status status-locked">' + icon('lock', 'icon-sm') + 'Terkunci</span>' +
                '<p><strong>Kenapa?</strong> Selesaikan misi Rumah Pertama dulu.</p>' +
                '<button class="btn btn-secondary" data-act="open-quest" data-fk="q2-goto">Ke Misi Rumah Pertama</button>';
        } else if (!sim.economy) {
            q2 = '<span class="status status-notyet">' + icon('clock', 'icon-sm') + 'Belum dibuka</span>' +
                '<p>Bangunan berikutnya belum dibuka. Orang tuamu yang bisa membukanya nanti. Duniamu sudah lengkap untuk sekarang.</p>';
        } else {
            q2 = questStatus('AVAILABLE') + '<p>Tanam kebun dan hitung kelompok tanaman.</p>' +
                '<button class="btn btn-primary" data-act="open-q002" data-fk="q2-open">Lihat Misi</button>';
        }
        return '<section class="stack" aria-labelledby="missions-title">' +
            '<h2 id="missions-title" tabindex="-1" class="section-title">Misi</h2>' +
            '<article class="card' + (st.quest !== 'COMPLETED' ? ' card-accent' : '') + '" aria-labelledby="q1-title" data-testid="q001-card">' +
            '<h3 id="q1-title">Rumah Pertama</h3>' + questStatus(st.quest) +
            '<p>Siapkan kayu dan bangun rumah pertamamu.</p>' +
            '<button class="btn ' + (st.quest !== 'COMPLETED' ? 'btn-primary' : 'btn-secondary') + '" data-act="open-quest" data-fk="q1-open">Lihat Misi</button></article>' +
            '<article class="card" aria-labelledby="q2-title" data-testid="q002-card"><h3 id="q2-title">Kebun Tunas</h3>' + q2 + '</article>' +
            '</section>';
    }

    function panelQuest() {
        var st = S();
        var cta = '';
        if (st.quest === 'AVAILABLE') {
            cta = '<button class="btn btn-primary" data-act="start-challenge" data-fk="quest-cta"' + (sim.offline || ui.busy ? ' disabled' : '') + '>' +
                (ui.busy === 'start' ? 'Menyiapkan…' : 'Mulai Tantangan') + '</button>';
        } else if (st.quest === 'IN_PROGRESS') {
            cta = '<button class="btn btn-primary" data-act="resume-challenge" data-fk="quest-cta">Lanjutkan Tantangan</button>';
        } else if (st.quest === 'READY_TO_BUILD') {
            cta = '<button class="btn btn-primary" data-act="start-place" data-fk="quest-cta">Bangun Rumah</button>';
        } else {
            cta = '<button class="btn btn-primary" data-act="show-house" data-fk="quest-cta">Lihat di Dunia</button>';
        }
        return '<section class="card" aria-labelledby="quest-title" data-testid="quest-detail">' +
            '<div class="panel-head">' + backBtn('missions') + '</div>' +
            '<p class="eyebrow">Misi · Pengurangan</p>' +
            '<h2 id="quest-title" tabindex="-1">Rumah Pertama</h2>' + questStatus(st.quest) +
            '<p class="lead">' + Q001.story + '</p>' +
            '<p class="reward-preview">' + icon('blueprint', 'icon-sm') + '<strong>' + Q001.rewardPreview + '</strong></p>' +
            cta + (st.quest === 'AVAILABLE' ? offlineReason() : '') + '</section>';
    }

    function planks(level) {
        var out = '';
        for (var i = 1; i <= 10; i++) {
            if (i <= 6) {
                out += '<span class="plank" aria-hidden="true"></span>';
            } else if (level >= 2) {
                out += '<span class="plank empty counted" aria-hidden="true">' + i + '</span>';
            } else {
                out += '<span class="plank empty" aria-hidden="true"></span>';
            }
        }
        return out;
    }

    // Touch devices use the on-screen keypad, so focusing the field must not open the OS keyboard.
    var COARSE = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

    // Challenge mirrors quiz.html .quiz-question + .quiz-pad: progress strip, owl tutor with speech
    // bubble, prompt, answer box, the 💡 help line (which carries the hint), and the 3-column keypad.
    // KidQuest keeps an explicit Kirim key (no quiz-style auto-submit) because answers can have 2 digits.
    function panelChallenge() {
        if (ui.checking && ui.checking.kind === 'answer') { return panelChecking(); }
        var level = 0;
        var bubble = 'Ayo hitung kayunya!';
        var help = '<p class="quiz-help" id="submit-why"><span class="emoji" aria-hidden="true">💡</span><span>Tekan angka, lalu tekan Kirim.</span></p>';
        if (ui.feedback && (ui.feedback.type === 'wrong' || ui.feedback.type === 'hint')) {
            level = ui.feedback.level;
            bubble = ui.feedback.type === 'wrong' ? 'Belum tepat. Coba lagi, ya!' : 'Ini petunjuknya!';
            help = '<p class="quiz-help has-hint" data-testid="hint"><span class="emoji" aria-hidden="true">💡</span><span id="fb-text">' + Q001.hints[level >= 2 ? 1 : 0] + '</span></p>';
        }
        var capped = sim.dailyCap && ui.feedback && ui.feedback.type === 'cap';
        if (capped) {
            bubble = 'Latihan hari ini sudah cukup.';
            help = '<p class="quiz-help has-hint" data-testid="cap">' + icon('clock', 'icon-sm') + '<span id="fb-text">Tantangan ini bisa dilanjutkan besok. Kamu tetap bisa melihat duniamu.</span></p>';
        }
        var canSubmit = ui.answer.length > 0 && !sim.offline && !ui.busy && !capped;
        var dis = capped ? ' disabled' : '';
        var keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(function (d) {
            return '<button class="btn" data-act="key" data-key="' + d + '" data-fk="key-' + d + '"' + dis + '>' + d + '</button>';
        }).join('') +
            '<button class="btn key-del" data-act="key" data-key="del" data-fk="key-del" aria-label="Hapus angka terakhir"' + dis + '>Hapus</button>' +
            '<button class="btn" data-act="key" data-key="0" data-fk="key-0"' + dis + '>0</button>' +
            '<button class="btn btn-primary" data-act="submit" data-fk="submit" data-testid="submit"' + (canSubmit ? '' : ' disabled') + ' aria-describedby="' + (level || capped ? 'fb-text' : 'submit-why') + '">' +
            (ui.busy === 'answer' ? 'Memeriksa…' : icon('check', 'icon-sm') + 'Kirim') + '</button>';
        return '<section class="card challenge" aria-labelledby="ch-title" data-testid="challenge">' +
            '<div class="question-head">' +
            '<div class="question-progress"><span>Langkah 1 dari 2</span><span class="progress-track" aria-hidden="true"><span style="width:50%"></span></span>' +
            '<button class="btn btn-secondary" data-act="hint" data-fk="hint"' + dis + '>' + icon('bulb', 'icon-sm') + 'Petunjuk</button></div>' +
            '<div class="tutor-area"><p class="tutor-bubble" id="fb-title" aria-live="polite">' + bubble + '</p>' +
            '<img class="tutor-owl" src="' + IMG + 'owl-tutor.png" alt=""></div></div>' +
            '<h2 id="ch-title" tabindex="-1" class="challenge-q">' + Q001.prompt + '</h2>' +
            '<figure class="challenge-fig"><div class="planks" role="img" aria-label="Gambar: 10 tempat kayu. 6 tempat sudah berisi kayu.">' + planks(level) + '</div>' +
            '<figcaption class="plank-caption"><span>Butuh 10</span><span>Ada 6</span></figcaption></figure>' +
            '<div class="answer-row"><label for="answer">Jawabanmu</label>' +
            '<input id="answer" class="answer-input" data-fk="answer" data-testid="answer" placeholder="–" inputmode="' + (COARSE ? 'none' : 'numeric') + '" autocomplete="off" maxlength="2" value="' + ui.answer + '" aria-describedby="' + (level || capped ? 'fb-title fb-text' : 'submit-why') + '"' + (capped ? ' disabled' : '') + '></div>' +
            '<div aria-live="polite">' + help + '</div>' +
            '<div class="quiz-pad"><div class="keypad-grid" role="group" aria-label="Tombol angka">' + keys + '</div></div>' +
            offlineReason() + '</section>';
    }

    // Reward mirrors the quiz "correct" popup (popup-correct-background/-icon, mint reward pill).
    // The pills use wood and blueprint icons, never popup-reward-coin (an Rp coin; pipeline §8.4).
    function panelReward() {
        return '<div class="kq-popup" role="dialog" aria-modal="true" aria-labelledby="rw-title" data-testid="reward">' +
            '<div class="kq-popup-card is-correct">' +
            '<img class="kq-popup-bg" src="' + IMG + 'popup-correct-background.png" alt="">' +
            '<img class="kq-popup-icon" src="' + IMG + 'popup-correct-icon.png" alt="">' +
            '<h2 id="rw-title" class="kq-popup-title" tabindex="-1">Benar!</h2>' +
            '<p class="kq-popup-text">10 − 6 = 4. ' + Q001.rewardMessage + '</p>' +
            '<ul class="reward-pills" aria-label="Kamu dapat">' +
            '<li class="reward-pill"><span class="pill-icon">' + icon('wood') + '</span><span>4 kayu<small>Paket kayu awal untuk rumahmu</small></span></li>' +
            '<li class="reward-pill"><span class="pill-icon is-blueprint">' + icon('blueprint') + '</span><span>Cetak biru Rumah<small>Sekarang kamu bisa membangun rumah</small></span></li></ul>' +
            '<p class="kq-popup-sub">Hadiahmu sudah tersimpan.</p>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="reward-build" data-fk="rw-build">Bangun Rumah</button>' +
            '<button class="btn btn-secondary" data-act="go" data-view="world" data-fk="rw-later">Nanti saja</button></div>' +
            '</div></div>';
    }

    // Wrong answer mirrors the quiz "wrong" popup frame (pink attention line, popup-wrong-background),
    // but with the owl tutor instead of the red ✕ and neutral wording (PRD §10.2, decision D4).
    function renderWrongPopup() {
        var hint = Q001.hints[ui.feedback && ui.feedback.level >= 2 ? 1 : 0];
        return '<div class="kq-popup" role="dialog" aria-modal="true" aria-labelledby="wp-title" aria-describedby="wp-text" data-testid="wrong-popup">' +
            '<div class="kq-popup-card is-learn">' +
            '<img class="kq-popup-bg" src="' + IMG + 'popup-wrong-background.png" alt="">' +
            '<img class="kq-popup-icon" src="' + IMG + 'owl-tutor.png" alt="" data-testid="wrong-icon">' +
            '<h2 id="wp-title" class="kq-popup-title" tabindex="-1">Belum tepat. Coba lagi, ya!</h2>' +
            '<p id="wp-text" class="kq-popup-text"><span aria-hidden="true">💡 </span>' + hint + '</p>' +
            '<p class="kq-popup-sub">Petunjuk ini tetap ada di bawah soal.</p>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="wrong-ok" data-fk="wrong-ok">Coba Lagi</button></div>' +
            '</div></div>';
    }

    function panelCatalog() {
        var st = S();
        var owned = st.buildings.length > 0;
        var hasBp = st.blueprints.indexOf('starter_house') >= 0;
        var status, action;
        if (owned) {
            status = '<span class="status status-done">' + icon('check', 'icon-sm') + 'Sudah dibangun</span>';
            action = '<button class="btn btn-secondary" data-act="show-house" data-fk="cat-cta">Lihat di Dunia</button>';
        } else if (!hasBp) {
            status = '<span class="status status-locked">' + icon('lock', 'icon-sm') + 'Terkunci</span>';
            action = '<p><strong>Kenapa?</strong> Butuh cetak biru dari misi Rumah Pertama.</p>' +
                '<button class="btn btn-secondary" data-act="open-quest" data-fk="cat-cta">Ke Misi Rumah Pertama</button>';
        } else if (st.wood < HOUSE.cost) {
            status = '<span class="status status-locked">' + icon('wood', 'icon-sm') + 'Kayu kurang</span>';
            action = '<p>Butuh 4 kayu. Kamu punya ' + st.wood + '.</p>';
        } else {
            status = '<span class="status status-ready">' + icon('check', 'icon-sm') + 'Siap dibangun</span>';
            action = '<button class="btn btn-primary" data-act="start-place" data-fk="cat-cta">Pilih Tempat</button>';
        }
        var tip = ui.catalogTip ? '<div class="alert alert-info" role="status">' + icon('info') +
            '<div><p>Ini menu <strong>Bangun</strong>. Cetak biru Rumah sekarang ada di sini.</p>' +
            '<button class="btn btn-text" data-act="dismiss-tip" data-fk="tip-ok">Mengerti</button></div></div>' : '';
        return '<section class="stack" aria-labelledby="cat-title">' +
            '<h2 id="cat-title" tabindex="-1" class="section-title">Bangun</h2>' + tip +
            '<article class="card catalog-card" aria-labelledby="house-name" data-testid="house-card">' +
            '<div class="thumb' + (hasBp ? '' : ' locked') + '" aria-hidden="true">' + houseArt() + '</div>' +
            '<div class="stack"><h3 id="house-name">Rumah</h3>' + status +
            '<p>Tempat tinggal pertamamu di pulau.</p>' +
            '<dl class="facts"><dt>Ukuran</dt><dd>2 × 2 kotak</dd><dt>Biaya</dt><dd>4 kayu</dd><dt>Pintu</dt><dd>Sisi bawah</dd></dl>' +
            action + '</div></article>' +
            '<p class="muted">Bangunan lain muncul saat misinya terbuka.</p></section>';
    }

    function panelPlace() {
        var st = S();
        if (ui.checking && ui.checking.kind === 'place') { return panelChecking(); }
        var o = ui.place.origin;
        var status, valid = false;
        if (!o) {
            status = '<div class="place-status idle" data-testid="place-status">' + icon('info') + '<span>Belum memilih tempat.</span></div>';
        } else {
            var v = validatePlacement(st, o.x, o.y);
            valid = v.ok;
            status = v.ok
                ? '<div class="place-status valid" data-testid="place-status">' + icon('check') + '<span>Bisa dibangun di sini.</span></div>'
                : '<div class="place-status invalid" data-testid="place-status">' + icon('cross') + '<span>' + INVALID_TEXT[v.code] + ' Coba kotak bergaris yang kosong.</span></div>';
        }
        var tutorial = !st.placeTutorialDone ? '<div class="alert alert-info">' + icon('info') +
            '<div><p><strong>Petunjuk:</strong> kotak bergaris adalah zona rumah. Rumah memakai 2 × 2 kotak.</p>' +
            '<button class="btn btn-text" data-act="dismiss-place-tip" data-fk="place-tip-ok">Mengerti</button></div></div>' : '';
        var msg = ui.place.msg ? '<div class="alert alert-' + ui.place.msg.type + '" role="alert">' + icon('refresh') + '<div><p>' + ui.place.msg.text + '</p></div></div>' : '';
        var canConfirm = valid && !sim.offline && !ui.busy;
        // Decision controls come straight after the instruction so they stay above the fold on
        // desktop; on phones and tablets the same block is the fixed action bar.
        return '<section class="card" aria-labelledby="place-title" data-testid="place-panel">' +
            '<h2 id="place-title" tabindex="-1">Pilih tempat rumah</h2>' +
            '<p class="lead">Ketuk kotak di zona bergaris.</p>' +
            '<div class="action-bar" data-testid="place-actions">' + msg +
            '<div aria-live="polite">' + status + '</div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="confirm-place" data-fk="confirm-place" data-testid="confirm-place"' + (canConfirm ? '' : ' disabled') + '>' +
            (ui.busy === 'place' ? 'Membangun…' : 'Bangun di Sini · 4 kayu') + '</button>' +
            '<button class="btn btn-secondary" data-act="cancel-place" data-fk="cancel-place">Batal</button></div>' +
            offlineReason() + '</div>' +
            tutorial +
            '<div class="nudge" role="group" aria-label="Geser rumah">' +
            '<button class="btn btn-secondary up" data-act="nudge" data-dx="0" data-dy="-1" data-fk="n-up" aria-label="Geser ke atas">' + icon('up') + '</button>' +
            '<button class="btn btn-secondary left" data-act="nudge" data-dx="-1" data-dy="0" data-fk="n-left" aria-label="Geser ke kiri">' + icon('left') + '</button>' +
            '<button class="btn btn-secondary down" data-act="nudge" data-dx="0" data-dy="1" data-fk="n-down" aria-label="Geser ke bawah">' + icon('down') + '</button>' +
            '<button class="btn btn-secondary right" data-act="nudge" data-dx="1" data-dy="0" data-fk="n-right" aria-label="Geser ke kanan">' + icon('right') + '</button></div>' +
            '<p class="muted">' + (!valid ? 'Tombol Bangun menyala setelah kamu memilih tempat yang bisa dibangun.' : 'Rumah 2 × 2 kotak. Memakai 4 kayu.') + '</p>' +
            '<p class="muted">Rumah menutupi kotak yang kamu ketuk. Keyboard: panah untuk pindah, Enter untuk memilih, Esc untuk batal.</p>' +
            '</section>';
    }

    function panelCheckpoint() {
        var econ = sim.economy;
        return '<section class="card card-accent" aria-labelledby="cp-title" data-testid="checkpoint">' +
            '<div class="alert alert-success">' + icon('star') + '<div><h2 id="cp-title" tabindex="-1">Rumah Pertama selesai!</h2></div></div>' +
            '<h3>Yang berubah</h3><ul class="list-plain">' +
            '<li>' + icon('check', 'icon-sm') + '<span>Rumahmu berdiri di pulau.</span></li>' +
            '<li>' + icon('wood', 'icon-sm') + '<span>4 kayu dipakai.</span></li></ul>' +
            '<p>' + icon('shield', 'icon-sm') + ' Semua sudah tersimpan otomatis. Kamu boleh berhenti kapan saja.</p>' +
            '<h3>Berikutnya</h3>' +
            '<p>' + (econ ? 'Misi Kebun Tunas sudah terbuka.' : 'Bangunan berikutnya belum dibuka. Orang tuamu yang bisa membukanya. Duniamu sudah lengkap untuk sekarang.') + '</p>' +
            '<div class="alert alert-info">' + icon('palette') + '<div><p><strong>Baru: Tema Dunia.</strong> Kamu bisa mengganti tampilan pulaumu. Gratis, dan rumahmu tetap di tempatnya.</p></div></div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="checkpoint-done" data-fk="cp-done">Selesai</button>' +
            '<button class="btn btn-secondary" data-act="open-theme" data-fk="cp-theme">' + icon('palette', 'icon-sm') + 'Coba Tema Dunia</button></div>' +
            '<button class="btn btn-text" data-act="go" data-view="quiz-stub" data-fk="cp-quiz">Main Kuis</button></section>';
    }

    function panelTheme() {
        var st = S();
        if (ui.checking && ui.checking.kind === 'theme') { return panelChecking(); }
        var selected = ui.previewTheme || st.theme;
        var cards = THEME_ORDER.map(function (id) {
            var isAuth = id === st.theme;
            var isSel = id === selected;
            var mark = isAuth ? '<span class="theme-mark">' + icon('check', 'icon-sm') + 'Dipakai</span>'
                : (isSel ? '<span class="theme-mark">' + icon('palette', 'icon-sm') + 'Dilihat</span>' : '<span class="theme-mark small">Gratis</span>');
            return '<button class="theme-card" role="radio" aria-checked="' + isSel + '" tabindex="' + (isSel ? '0' : '-1') + '"' +
                ' data-act="preview-theme" data-id="' + id + '" data-fk="theme-' + id + '" data-testid="theme-' + id + '">' +
                '<span class="theme-thumb" data-theme="' + id + '" style="background:var(--t-ground)" aria-hidden="true">' + houseArt() + '</span>' +
                '<span>' + THEMES[id].name + '</span>' + mark + '</button>';
        }).join('');
        var msg = '';
        if (ui.themeMsg) {
            msg = '<div class="alert alert-' + ui.themeMsg.type + '" role="' + (ui.themeMsg.type === 'error' ? 'alert' : 'status') + '" data-testid="theme-msg">' +
                icon(ui.themeMsg.type === 'error' ? 'info' : 'check') + '<div><p>' + ui.themeMsg.text + '</p>' +
                (ui.themeMsg.retry ? '<button class="btn btn-primary" data-act="theme-retry" data-fk="theme-retry">' + icon('refresh') + 'Coba Lagi</button>' : '') +
                '</div></div>';
        }
        var changed = ui.previewTheme && ui.previewTheme !== st.theme;
        var canUse = changed && !sim.offline && !ui.busy;
        return '<section class="card" aria-labelledby="theme-title" data-testid="theme-panel">' +
            '<h2 id="theme-title" tabindex="-1">Tema Dunia</h2>' +
            '<p>Lihat pulaumu dengan gaya lain. Semua tema <strong>gratis</strong>. Rumah, kayu, dan misimu tidak berubah.</p>' +
            '<div class="action-bar" data-testid="theme-actions">' + msg +
            '<div class="theme-cards" role="radiogroup" aria-label="Pilih tema">' + cards + '</div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="confirm-theme" data-fk="confirm-theme" data-testid="confirm-theme"' + (canUse ? '' : ' disabled') + '>' +
            (ui.busy === 'theme' ? 'Menyimpan…' : 'Gunakan Tema') + '</button>' +
            '<button class="btn btn-secondary" data-act="cancel-theme" data-fk="cancel-theme">' + (changed ? 'Batal' : 'Kembali') + '</button></div>' +
            offlineReason() + '</div>' +
            (!changed && !ui.themeMsg ? '<p class="muted">Ketuk tema lain untuk melihat pratinjau.</p>' : '') +
            '</section>';
    }

    function panelHelp() {
        return '<section class="card" aria-labelledby="help-title">' +
            '<div class="panel-head">' + backBtn('world') + '</div>' +
            '<h2 id="help-title" tabindex="-1">Bantuan</h2>' +
            '<h3>Menjawab tantangan</h3><p>Tekan angka jawabanmu, lalu tekan Kirim. Kalau belum tepat, baca petunjuk dan coba lagi. Kayumu tidak akan hilang.</p>' +
            '<h3>Membangun</h3><p>Buka Bangun, pilih bangunan, ketuk kotak bergaris, lalu tekan Bangun di Sini. Batal tidak mengubah apa pun.</p>' +
            '<h3>Tema Dunia</h3><p>Tema hanya mengubah tampilan. Gratis. Bangunan tetap di tempatnya.</p>' +
            '<button class="btn btn-secondary" data-act="replay-tips" data-fk="help-replay">Tampilkan lagi petunjuk membangun</button></section>';
    }

    function panelQ002() {
        return '<section class="card" aria-labelledby="q2d-title">' +
            '<div class="panel-head">' + backBtn('missions') + '</div>' +
            '<h2 id="q2d-title" tabindex="-1">Kebun Tunas</h2>' +
            '<div class="alert alert-info">' + icon('info') + '<div><p>Prototipe berhenti di sini. Alur Kebun Tunas (Dompet, Kredit Bangun, kebun) dirancang di tugas KQ-016 dan KQ-018.</p></div></div></section>';
    }

    function renderPanel() {
        switch (ui.view) {
            case 'world': return panelWorld();
            case 'missions': return panelMissions();
            case 'quest': return panelQuest();
            case 'challenge': return panelChallenge();
            case 'reward': return panelReward();
            case 'catalog': return panelCatalog();
            case 'place': return panelPlace();
            case 'checkpoint': return panelCheckpoint();
            case 'theme': return panelTheme();
            case 'help': return panelHelp();
            case 'q002': return panelQ002();
            default: return '';
        }
    }

    /* ------------------------------------------------------------------ */
    /* Menu dialog                                                          */
    /* ------------------------------------------------------------------ */
    function renderMenu() {
        var root = $('#dialog-root');
        if (!ui.menuOpen) { root.innerHTML = ui.popup === 'wrong' && ui.view === 'challenge' ? renderWrongPopup() : ''; return; }
        root.innerHTML = '<div class="scrim" data-act="close-menu-scrim">' +
            '<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="menu-title" data-testid="menu">' +
            '<div class="panel-head"><h2 id="menu-title">Menu</h2>' +
            '<button class="btn btn-secondary" data-act="close-menu" data-fk="menu-close">' + icon('close') + '<span>Tutup</span></button></div>' +
            '<ul class="menu-list">' +
            '<li><button class="btn btn-secondary" data-act="menu-theme" data-fk="m-theme">' + icon('palette') + 'Tema Dunia</button></li>' +
            '<li><button class="btn btn-secondary" data-act="toggle-motion" data-fk="m-motion" aria-pressed="' + sim.reduceMotion + '">' + icon('motion') + 'Kurangi Gerakan<span class="switch-state">' + (sim.reduceMotion ? 'Nyala' : 'Mati') + '</span></button></li>' +
            '<li><button class="btn btn-secondary" data-act="menu-help" data-fk="m-help">' + icon('help') + 'Bantuan</button></li>' +
            '<li><button class="btn btn-secondary" data-act="menu-quiz" data-fk="m-quiz">' + icon('quiz') + 'Main Kuis</button></li>' +
            '<li><button class="btn btn-secondary" data-act="menu-switch" data-fk="m-switch">' + icon('user') + 'Ganti Akun</button></li>' +
            '</ul>' +
            '<div class="menu-divider"><p class="eyebrow">Untuk orang tua</p>' +
            '<a class="btn btn-secondary" href="parent.html" data-fk="m-parent">' + icon('shield') + 'Area Orang Tua <span class="muted" style="margin-left:auto;font-weight:600">Perlu PIN</span></a></div>' +
            '</div></div>';
    }

    /* ------------------------------------------------------------------ */
    /* Reviewer panel                                                       */
    /* ------------------------------------------------------------------ */
    function renderReviewer() {
        var body = $('#reviewer-body');
        var st = S();
        var auth = st ? JSON.stringify({
            profile: store.active, theme: st.theme, quest: st.quest, attempts: st.attempts, hints: st.hints,
            wood: st.wood, blueprints: st.blueprints, buildings: st.buildings, worldVersion: st.worldVersion
        }, null, 1) : '(belum memilih profil)';
        function tog(key, label) {
            return '<label class="toggle"><input type="checkbox" data-sim="' + key + '"' + (sim[key] ? ' checked' : '') + '> ' + label + '</label>';
        }
        body.innerHTML =
            '<p>Panel ini hanya untuk peninjau dan pengujian. Ia mensimulasikan server, jaringan, dan pengaturan orang tua. Anak tidak melihat panel ini.</p>' +
            '<fieldset><legend>Skenario</legend>' +
            '<button class="btn btn-secondary" data-rev="fresh">Mulai baru (dunia kosong)</button>' +
            '<button class="btn btn-secondary" data-rev="ret-progress">Kembali: di tengah tantangan</button>' +
            '<button class="btn btn-secondary" data-rev="ret-ready">Kembali: siap membangun</button>' +
            '<button class="btn btn-secondary" data-rev="ret-done">Kembali: rumah sudah jadi</button>' +
            '<button class="btn btn-secondary" data-rev="reload">Muat ulang halaman</button></fieldset>' +
            '<fieldset><legend>Server dan jaringan (simulasi)</legend>' +
            tog('offline', 'Offline') + tog('dropNext', 'Putus saat simpan berikutnya') + tog('themeFail', 'Simpan tema gagal') +
            tog('staleNext', 'Dunia berubah di perangkat lain (bangun berikutnya)') + tog('dailyCap', 'Batas harian tercapai') + tog('slow', 'Respons lambat (1,5 dtk)') +
            '<button class="btn btn-secondary" data-rev="loading">Tampilkan memuat</button>' +
            '<button class="btn btn-secondary" data-rev="load-error">Tampilkan gagal memuat</button></fieldset>' +
            '<fieldset><legend>Pengaturan orang tua (simulasi)</legend>' + tog('economy', 'Ekonomi diaktifkan (Q002 terbuka)') + '</fieldset>' +
            '<fieldset><legend>Aksesibilitas</legend>' + tog('text200', 'Teks 200%') + tog('reduceMotion', 'Kurangi gerakan') + '</fieldset>' +
            '<p><strong>PIN orang tua prototipe:</strong> 2468</p>' +
            (ui.invariance ? '<p data-testid="invariance"><strong>Invarian tema:</strong> ' + ui.invariance + '</p>' : '') +
            '<p><strong>Status otoritatif (server simulasi):</strong></p><pre data-testid="auth-state">' + auth + '</pre>';
    }

    /* ------------------------------------------------------------------ */
    /* Main render                                                          */
    /* ------------------------------------------------------------------ */
    function render() {
        var app = $('#app');
        var active = document.activeElement;
        var fk = active && active.dataset ? active.dataset.fk : null;
        document.documentElement.classList.toggle('reduce-motion', !!sim.reduceMotion);
        document.documentElement.classList.toggle('text-200', !!sim.text200);
        app.dataset.view = ui.view;
        app.dataset.viewKind = VIEW_KIND[ui.view];
        // The world theme only skins the world canvas; the shell takes the child's accent (pipeline §8.2a).
        app.className = 'kq-app' + (store.active && PROFILES[store.active] ? ' ' + PROFILES[store.active].accent : '');
        if (VIEW_KIND[ui.view] === 'entry' || !S()) {
            app.dataset.theme = 'perkampungan';
            app.innerHTML = renderEntry();
        } else {
            app.dataset.theme = ui.previewTheme || S().theme;
            app.innerHTML = renderHeader() +
                '<section class="kq-workspace">' + renderNav() +
                '<div class="banner-slot">' + renderBanners() + '</div>' +
                '<div class="obj-slot">' + (ui.view === 'world' || (window.innerWidth >= 960 && ['place', 'theme', 'reward'].indexOf(ui.view) < 0) ? renderObjective(ui.view !== 'world') : '') + '</div>' +
                '<div class="world-slot">' + renderWorld() + '</div>' +
                '<main id="main" class="panel-slot" tabindex="-1">' + renderPanel() + '</main>' +
                '</section>';
        }
        renderMenu();
        renderReviewer();
        var target = null;
        if (ui.focus) { target = $(ui.focus); }
        if (!target && fk) { target = $('[data-fk="' + fk + '"]'); }
        ui.focus = null;
        if (target && !target.disabled) { target.focus({ preventScroll: VIEW_KIND[ui.view] === 'task' }); }
        else if (target && target.disabled) { var m = $('#main'); if (m) { m.focus(); } }
    }

    /* ------------------------------------------------------------------ */
    /* Actions                                                              */
    /* ------------------------------------------------------------------ */
    function go(view, focusSel) {
        if (ui.view === 'place' && view !== 'place') {
            ui.place = null;
            announce('Membangun dibatalkan. Tidak ada yang berubah.');
        }
        if (ui.view === 'theme' && view !== 'theme' && ui.previewTheme) {
            ui.previewTheme = null;
            announce('Pratinjau tema dibatalkan. Tema tidak berubah.');
        }
        if (view !== 'theme') { ui.themeMsg = null; }
        if (view !== 'challenge') { ui.feedback = null; ui.popup = null; }
        ui.justBuilt = false;
        var changed = ui.view !== view;
        ui.view = view;
        ui.focus = focusSel || ({
            world: '#obj-title', missions: '#missions-title', quest: '#quest-title', challenge: '#ch-title', reward: '#rw-title',
            catalog: '#cat-title', place: '#place-title', checkpoint: '#cp-title', theme: '#theme-title', help: '#help-title',
            q002: '#q2d-title', entry: '#entry-title', choose: '#entry-title', 'quiz-stub': '#entry-title'
        })[view];
        render();
        if (changed && VIEW_KIND[view] === 'task') { window.scrollTo(0, 0); }
        if (view === 'challenge') { revealChallenge(); }
    }

    // Phone: bring the whole question card into view (question → hint → answer box → keypad → Kirim).
    // The challenge view has no fixed bars, so "in the viewport" means "not hidden" (lead finding 1).
    function revealChallenge() {
        var card = $('[data-testid="challenge"]');
        var submit = $('[data-testid="submit"]');
        if (!card || !submit) { return; }
        var top = card.getBoundingClientRect().top;
        var bottom = submit.getBoundingClientRect().bottom;
        var vh = window.innerHeight;
        if (top >= 0 && bottom <= vh) { return; }
        window.scrollBy(0, top - 6);
        // Text scaled up: if Kirim is still below, keep the answer box and Kirim in view instead.
        var input = $('#answer');
        bottom = submit.getBoundingClientRect().bottom;
        if (bottom > vh && input) { window.scrollBy(0, Math.min(bottom - vh + 8, input.getBoundingClientRect().top - 6)); }
    }


    function enterKidQuest() {
        ui.load = 'loading';
        ui.view = 'world';
        var st = S();
        ui.showResume = !!st.lastChange;
        render();
        window.setTimeout(function () {
            ui.load = 'ready';
            ui.focus = ui.showResume ? '#resume-title' : '#obj-title';
            render();
        }, sim.slow ? 1500 : 500);
    }

    function startPlace() {
        var st = S();
        if (st.quest !== 'READY_TO_BUILD') { go('catalog'); return; }
        ui.showResume = false;
        ui.place = { origin: null, wv: st.worldVersion, msg: null };
        ui.pendingKey.place = null;
        ui.cursor = { x: ZONE.x0, y: ZONE.y0 };
        go('place', '[data-fk="cell-' + ZONE.x0 + '-' + ZONE.y0 + '"]');
        announce('Mode Bangun. Pilih kotak di zona bergaris. Tidak ada yang berubah sampai kamu menekan Bangun di Sini.');
    }

    function selectOrigin(x, y) {
        ui.place.origin = { x: x, y: y };
        ui.place.msg = null;
        ui.pendingKey.place = null; // a new choice is a new intent
        var v = validatePlacement(S(), x, y);
        announce(v.ok ? 'Bisa dibangun di sini.' : INVALID_TEXT[v.code]);
    }

    function handleResult(kind, res) {
        var st = S();
        ui.busy = null;
        if (res.uncertain) {
            ui.checking = { kind: kind, key: ui.pendingKey[kind] };
            ui.focus = '#chk-title';
            announce('Memeriksa perubahan.');
            render();
            return;
        }
        ui.checking = null;
        if (kind === 'answer') {
            if (res.ok && res.correct) {
                ui.answer = '';
                ui.pendingKey.answer = null;
                announce('Benar! Kamu dapat 4 kayu dan cetak biru Rumah.');
                go('reward');
                return;
            }
            if (res.ok && !res.correct) {
                ui.answer = '';
                ui.pendingKey.answer = null;
                ui.feedback = { type: 'wrong', level: res.hintLevel };
                ui.popup = 'wrong';
                ui.focus = '[data-fk="wrong-ok"]';
                render();
                announce('Belum tepat. ' + $('#fb-text').textContent);
                return;
            }
            if (res.error && res.error.code === 'DAILY_CAP_REACHED') {
                ui.pendingKey.answer = null;
                ui.feedback = { type: 'cap' };
                ui.focus = '#ch-title';
                render();
                announce('Latihan hari ini sudah cukup. Tantangan bisa dilanjutkan besok.');
                return;
            }
            if (res.error && res.error.code === 'QUEST_LOCKED') {
                // Already answered (e.g. replay after reconnect) — follow authoritative state.
                go(st.quest === 'READY_TO_BUILD' ? 'reward' : 'world');
                return;
            }
        }
        if (kind === 'place') {
            if (res.ok) {
                ui.pendingKey.place = null;
                ui.place = null;
                ui.justBuilt = true;
                ui.view = 'checkpoint';
                var b = res.building;
                ui.cursor = { x: b.x, y: b.y };
                ui.focus = '[data-fk="cell-' + b.x + '-' + b.y + '"]';
                announce('Rumah sudah dibangun! Misi Rumah Pertama selesai.');
                render();
                window.setTimeout(function () { ui.justBuilt = false; }, 1000);
                return;
            }
            if (res.error.code === 'WORLD_VERSION_CONFLICT') {
                ui.pendingKey.place = null;
                ui.place.wv = st.worldVersion; // refreshed authoritative state
                ui.place.msg = { type: 'info', text: 'Duniamu baru saja diperbarui, jadi kami memuat versi terbaru. Tempat pilihanmu masih bisa dipakai. Tekan Bangun di Sini lagi.' };
                ui.focus = '#place-title';
                announce('Duniamu baru saja diperbarui. Cek tempatnya, lalu tekan Bangun di Sini lagi.');
                render();
                return;
            }
            ui.pendingKey.place = null;
            ui.place.msg = { type: 'error', text: res.error.message + ' Tidak ada yang berubah.' };
            render();
            return;
        }
        if (kind === 'theme') {
            if (res.ok) {
                var before = ui.invarianceBefore;
                var after = invariantSnapshot();
                ui.invariance = (before === after ? 'SAMA — bangunan, koordinat, kayu, cetak biru, misi, dan percobaan tidak berubah.' : 'BERBEDA (bug)') + ' worldVersion: ' + st.worldVersion;
                ui.pendingKey.theme = null;
                ui.previewTheme = null;
                ui.themeMsg = { type: 'success', text: 'Tema ' + THEMES[st.theme].name + ' dipakai. Rumahmu tetap di tempat yang sama.' };
                ui.focus = '#theme-title';
                announce(ui.themeMsg.text);
                render();
                return;
            }
            var tried = ui.previewTheme;
            ui.pendingKey.theme = null;
            ui.previewTheme = null; // restore authoritative look
            ui.retryTheme = tried;
            ui.themeMsg = { type: 'error', text: 'Tema belum tersimpan. Tampilan kembali ke ' + THEMES[st.theme].name + '. Duniamu tidak berubah.', retry: true };
            ui.focus = '[data-fk="theme-retry"]';
            announce(ui.themeMsg.text);
            render();
        }
    }

    function invariantSnapshot() {
        var st = S();
        return JSON.stringify([st.buildings, st.wood, st.blueprints, st.quest, st.attempts, st.hints]);
    }

    function mutate(kind, payload) {
        if (!ui.pendingKey[kind]) { ui.pendingKey[kind] = newKey(kind); }
        ui.busy = kind;
        render();
        server(kind, ui.pendingKey[kind], payload).then(function (res) { handleResult(kind, res); });
    }

    var actions = {
        'pick-profile': function (el) {
            store.active = el.dataset.id; S(); save();
            go('choose');
        },
        'enter-kidquest': function () { enterKidQuest(); },
        go: function (el) { go(el.dataset.view); },
        nav: function (el) { ui.inspect = null; go(el.dataset.view); },
        'open-quest': function () { ui.showResume = false; go('quest'); },
        'open-q002': function () { go('q002'); },
        'start-challenge': function () {
            ui.busy = 'start'; render();
            server('start', newKey('start'), {}).then(function () { ui.busy = null; go('challenge'); });
        },
        'resume-challenge': function () { ui.showResume = false; go('challenge'); },
        'start-place': function () { startPlace(); },
        'reward-build': function () {
            var st = S();
            if (!st.catalogTipDone) { ui.catalogTip = true; st.catalogTipDone = true; save(); }
            go('catalog');
        },
        'dismiss-tip': function () { ui.catalogTip = false; ui.focus = '#cat-title'; render(); },
        'dismiss-place-tip': function () { S().placeTutorialDone = true; save(); ui.focus = '#place-title'; render(); },
        'show-house': function () {
            var b = S().buildings[0];
            ui.inspect = b ? { x: b.x, y: b.y } : null;
            if (b) { ui.cursor = { x: b.x, y: b.y }; }
            go('world', b ? '#insp-title' : '#obj-title');
        },
        'dismiss-resume': function () { ui.showResume = false; ui.focus = '#obj-title'; render(); },
        'theme-later': function () { S().themeIntroDone = true; save(); ui.focus = '#obj-title'; render(); },
        'open-theme': function () { S().themeIntroDone = true; save(); go('theme'); },
        'checkpoint-done': function () { go('world'); },
        'retry-load': function () { enterKidQuest(); },
        'close-inspect': function () {
            var i = ui.inspect; ui.inspect = null;
            ui.focus = i ? '[data-fk="cell-' + i.x + '-' + i.y + '"]' : null;
            render();
        },
        cell: function (el) {
            var x = +el.dataset.x, y = +el.dataset.y;
            ui.cursor = { x: x, y: y };
            if (ui.view === 'place') {
                var fo = fitOrigin(x, y);
                selectOrigin(fo.x, fo.y);
                ui.focus = '[data-fk="cell-' + x + '-' + y + '"]';
                render();
                return;
            }
            if (ui.view === 'theme') {
                announce('Ini pratinjau tema. Tekan Gunakan Tema atau Batal.');
                return;
            }
            ui.inspect = { x: x, y: y };
            if (ui.view !== 'world') { go('world', '#insp-title'); return; }
            ui.focus = '#insp-title';
            render();
        },
        nudge: function (el) {
            var o = ui.place.origin || { x: ui.cursor.x, y: ui.cursor.y };
            var nx = Math.max(0, Math.min(GRID - 1, o.x + (+el.dataset.dx)));
            var ny = Math.max(0, Math.min(GRID - 1, o.y + (+el.dataset.dy)));
            ui.cursor = { x: nx, y: ny };
            selectOrigin(nx, ny);
            render();
        },
        'confirm-place': function () {
            var o = ui.place.origin;
            mutate('place', { building_type: HOUSE.type, x: o.x, y: o.y, rotation: 0, worldVersion: ui.place.wv });
        },
        'cancel-place': function () { go('catalog'); },
        key: function (el) {
            var k = el.dataset.key;
            if (k === 'del') { ui.answer = ui.answer.slice(0, -1); }
            else if (ui.answer.length < 2) { ui.answer += k; }
            render();
        },
        hint: function () {
            var st = S();
            st.hints += 1; save();
            var level = ui.feedback && ui.feedback.level ? Math.max(ui.feedback.level, 1) : 1;
            if (st.hints >= 2) { level = 2; }
            ui.feedback = { type: 'hint', level: level };
            ui.focus = '#answer';
            render();
            revealChallenge();
            announce('Petunjuk. ' + $('#fb-text').textContent);
        },
        'wrong-ok': function () {
            ui.popup = null;
            ui.focus = '#answer';
            render();
            revealChallenge();
        },
        submit: function () {
            if (!ui.answer) { return; }
            mutate('answer', { answer: ui.answer, hint_count: S().hints });
        },
        recheck: function () {
            var c = ui.checking;
            ui.busy = c.kind; render();
            server(c.kind, c.key, {}).then(function (res) { handleResult(c.kind, res); });
        },
        'preview-theme': function (el) {
            var id = el.dataset.id;
            ui.themeMsg = null;
            ui.previewTheme = id === S().theme ? null : id;
            ui.focus = '[data-fk="theme-' + id + '"]';
            announce(id === S().theme ? THEMES[id].name + ' sedang dipakai.' : 'Pratinjau ' + THEMES[id].name + '. Bangunan tetap di tempat yang sama. Belum dipakai.');
            render();
        },
        'confirm-theme': function () {
            ui.invarianceBefore = invariantSnapshot();
            mutate('theme', { theme: ui.previewTheme, world_version: S().worldVersion });
        },
        'theme-retry': function () {
            ui.previewTheme = ui.retryTheme;
            ui.themeMsg = null;
            ui.invarianceBefore = invariantSnapshot();
            mutate('theme', { theme: ui.previewTheme, world_version: S().worldVersion });
        },
        'cancel-theme': function () { go('world'); },
        'open-menu': function () { ui.menuOpen = true; renderMenu(); $('[data-fk="m-theme"]').focus(); },
        'close-menu': closeMenu,
        'close-menu-scrim': function (el, e) { if (e.target === el) { closeMenu(); } },
        'menu-theme': function () { closeMenu(true); S().themeIntroDone = true; save(); go('theme'); },
        'menu-help': function () { closeMenu(true); go('help'); },
        'menu-quiz': function () { closeMenu(true); go('quiz-stub'); },
        'menu-switch': function () { closeMenu(true); go('entry'); },
        'toggle-motion': function () {
            sim.reduceMotion = !sim.reduceMotion; saveSim();
            document.documentElement.classList.toggle('reduce-motion', sim.reduceMotion);
            renderMenu(); renderReviewer();
            $('[data-fk="m-motion"]').focus();
            announce(sim.reduceMotion ? 'Kurangi gerakan: nyala.' : 'Kurangi gerakan: mati.');
        },
        'replay-tips': function () {
            var st = S(); st.placeTutorialDone = false; st.catalogTipDone = false; save();
            announce('Petunjuk membangun akan muncul lagi.');
        }
    };

    function closeMenu(skipFocus) {
        ui.menuOpen = false;
        renderMenu();
        if (skipFocus !== true) { var b = $('[data-fk="menu-btn"]'); if (b) { b.focus(); } }
    }

    /* ------------------------------------------------------------------ */
    /* Events                                                               */
    /* ------------------------------------------------------------------ */
    document.addEventListener('click', function (e) {
        var t = e.target.closest('[data-act]');
        if (!t || t.disabled) { return; }
        var fn = actions[t.dataset.act];
        if (fn) { e.preventDefault(); fn(t, e); }
    });

    document.addEventListener('input', function (e) {
        if (e.target.id === 'answer') {
            var clean = e.target.value.replace(/[^0-9]/g, '').slice(0, 2);
            if (clean !== e.target.value) { e.target.value = clean; }
            ui.answer = clean;
            var btn = $('[data-fk="submit"]');
            if (btn) { btn.disabled = !(clean.length > 0 && !sim.offline && !ui.busy); }
        }
    });

    document.addEventListener('keydown', function (e) {
        // Modal dialogs (menu, wrong-answer popup, reward popup): Escape closes, Tab is trapped.
        var modal = ui.menuOpen ? '.sheet' : (ui.popup === 'wrong' && ui.view === 'challenge' ? '[data-testid="wrong-popup"]' : (ui.view === 'reward' ? '[data-testid="reward"]' : null));
        if (modal) {
            if (e.key === 'Escape') {
                e.preventDefault();
                if (ui.menuOpen) { closeMenu(); } else if (ui.view === 'reward') { go('world'); } else { actions['wrong-ok'](); }
                return;
            }
            if (e.key === 'Tab') {
                var f = Array.prototype.slice.call(document.querySelectorAll(modal + ' button:not(:disabled), ' + modal + ' a'));
                var first = f[0], last = f[f.length - 1];
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
            return;
        }
        var t = e.target;
        if (t.id === 'answer' && e.key === 'Enter') {
            e.preventDefault();
            if (ui.answer && !sim.offline && !ui.busy) { actions.submit(); }
            return;
        }
        if (t.classList && t.classList.contains('cell')) {
            var dx = { ArrowLeft: -1, ArrowRight: 1 }[e.key] || 0;
            var dy = { ArrowUp: -1, ArrowDown: 1 }[e.key] || 0;
            if (dx || dy) {
                e.preventDefault();
                ui.cursor = { x: Math.max(0, Math.min(GRID - 1, ui.cursor.x + dx)), y: Math.max(0, Math.min(GRID - 1, ui.cursor.y + dy)) };
                ui.focus = '[data-fk="cell-' + ui.cursor.x + '-' + ui.cursor.y + '"]';
                render();
                return;
            }
            if (e.key === 'Escape' && ui.view === 'place') { e.preventDefault(); go('catalog'); return; }
            if (e.key === 'Escape' && ui.inspect) { e.preventDefault(); actions['close-inspect'](); return; }
        }
        if (e.key === 'Escape' && ui.view === 'place') { e.preventDefault(); go('catalog'); return; }
        if (t.getAttribute && t.getAttribute('role') === 'radio') {
            var step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
            if (step) {
                e.preventDefault();
                var i = THEME_ORDER.indexOf(t.dataset.id);
                var next = THEME_ORDER[(i + step + THEME_ORDER.length) % THEME_ORDER.length];
                actions['preview-theme']({ dataset: { id: next } });
            }
        }
    });

    // Reviewer panel controls
    document.addEventListener('change', function (e) {
        var k = e.target.dataset && e.target.dataset.sim;
        if (!k) { return; }
        sim[k] = e.target.checked;
        saveSim();
        render();
    });

    function setScenario(kind) {
        var w = freshWorld();
        if (!store.active) { store.active = 'althafandra'; }
        if (kind === 'ret-progress') {
            w.quest = 'IN_PROGRESS'; w.attempts = 1;
            w.lastChange = 'Kamu sudah mencoba tantangan Rumah Pertama 1 kali.';
        } else if (kind === 'ret-ready') {
            w.quest = 'READY_TO_BUILD'; w.attempts = 2; w.wood = 4; w.blueprints = ['starter_house'];
            w.catalogTipDone = true;
            w.lastChange = 'Kamu menjawab benar dan mendapat 4 kayu dan cetak biru Rumah.';
        } else if (kind === 'ret-done') {
            w.quest = 'COMPLETED'; w.attempts = 2; w.wood = 0; w.blueprints = ['starter_house'];
            w.buildings = [{ id: 'bld_1', type: 'starter_house', x: 2, y: 1, rotation: 0 }];
            w.worldVersion = 2; w.placeTutorialDone = true; w.catalogTipDone = true;
            w.lastChange = 'Kamu membangun rumah pertama. 4 kayu dipakai.';
        }
        store.worlds[store.active] = w;
        save();
    }

    $('#reviewer').addEventListener('click', function (e) {
        var b = e.target.closest('[data-rev]');
        if (!b) { return; }
        var r = b.dataset.rev;
        Object.assign(ui, { inspect: null, place: null, previewTheme: null, themeMsg: null, answer: '', feedback: null, busy: null, checking: null, pendingKey: {}, invariance: null, catalogTip: false, popup: null });
        if (r === 'fresh') { setScenario('fresh'); ui.view = 'world'; enterKidQuest(); return; }
        if (r.indexOf('ret-') === 0) { setScenario(r); enterKidQuest(); return; }
        if (r === 'reload') { window.location.reload(); return; }
        if (r === 'loading') { ui.view = 'world'; ui.load = 'loading'; render(); window.setTimeout(function () { ui.load = 'ready'; render(); }, 2000); return; }
        if (r === 'load-error') { ui.view = 'world'; ui.load = 'error'; ui.focus = '#load-err'; render(); }
    });

    /* ------------------------------------------------------------------ */
    /* Boot: a returning child resumes from authoritative state             */
    /* ------------------------------------------------------------------ */
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches && !readJSON(SIM_KEY, null)) {
        sim.reduceMotion = true;
    }
    var params = new URLSearchParams(window.location.search);
    if (params.get('scenario')) { setScenario(params.get('scenario')); }
    if (store.active && params.get('entry') !== '1') {
        enterKidQuest();
    } else {
        render();
    }

    // Exposed for the automated walkthrough check only.
    window.__kq = { ui: ui, sim: sim, state: S, render: render, validate: function (x, y) { return validatePlacement(S(), x, y); } };
}());
