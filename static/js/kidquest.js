/*
 * KidQuest first-house page (KQ-010): the child's world, the first quest, building, and world themes.
 *
 * Behaviour follows the approved KQ-005 prototype (design/kidquest/prototypes/first-house/child.js)
 * and decision log, adapted to the real API (app/api/kidquest_routes.py). Rules this file keeps:
 *   - The server is the only source of game state. Nothing is updated optimistically: the page
 *     renders `GET /api/kidquest/state` and the bodies the API returns, and buttons are disabled
 *     only while their request is in flight (or offline, with the reason shown).
 *   - Every mutation sends an Idempotency-Key made once per logical action and kept across retries
 *     of that action. A lost response (offline, 5xx) shows "Memeriksa perubahan" and re-sends the
 *     same request with the same key, so nothing is counted twice.
 *   - All child-facing copy comes from content: ui_strings.json (boot JSON), quest/hint/reward
 *     wording from the API, building and quest-board names from the theme labels.
 *   - Every world visual comes from the displayed theme's `assets` map (state.theme.assets). If an
 *     image is missing the neutral placeholder is drawn; if there is no placeholder either, a visible
 *     development error is drawn in development (PRD 11.3). No code branches on a theme or building ID.
 *   - Local storage holds only per-device UI conveniences (tips seen, theme intro seen, reduced
 *     motion), never game state.
 */
(function () {
    'use strict';

    var boot = JSON.parse(document.getElementById('kq-boot').textContent);
    var STRINGS = boot.strings;
    var DEV = !!boot.dev;
    var LINKS = boot.links;
    var API = '/api/kidquest';
    var IMG = '/static/images/';
    // Neutral placeholders exist for these layout kinds (PRD 11.3 fallback 2); see kidquest.css.
    var PLACEHOLDER_KINDS = { blocked_tree: 1, blocked_rock: 1, quest_board: 1 };

    /* ------------------------------------------------------------------ */
    /* Copy                                                                 */
    /* ------------------------------------------------------------------ */
    var missingStrings = [];
    function t(key, params) {
        var parts = key.split('.');
        var value = STRINGS[parts[0]] && STRINGS[parts[0]][parts[1]];
        if (typeof value !== 'string') {
            if (missingStrings.indexOf(key) < 0) { missingStrings.push(key); }
            if (window.console) { window.console.error('KidQuest: missing UI string ' + key); }
            return DEV ? '[' + key + ']' : '';
        }
        if (!params) { return value; }
        return value.replace(/\{(\w+)\}/g, function (m, name) {
            return Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : m;
        });
    }
    function h(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function tt(key, params) { return h(t(key, params)); }

    /* ------------------------------------------------------------------ */
    /* Per-device UI preferences (never game state)                         */
    /* ------------------------------------------------------------------ */
    var PREF_KEY = 'kq-ui-v1:' + boot.child;
    var prefs = (function () {
        try { return JSON.parse(window.localStorage.getItem(PREF_KEY)) || {}; } catch (e) { return {}; }
    }());
    function savePrefs() {
        try { window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch (e) { /* private mode: keep in memory */ }
    }

    /* ------------------------------------------------------------------ */
    /* Authoritative data and transient UI state                            */
    /* ------------------------------------------------------------------ */
    var data = {
        state: null,     // GET /api/kidquest/state
        themes: null,    // GET /api/kidquest/themes
        quests: {},      // quest_id -> quest payload with story/reward_preview (start/challenge responses)
        buildings: {}    // building type -> {type, w, h, cost, zone} from the preview endpoint
    };
    var ui = {
        view: 'world',
        load: 'loading',        // loading | ready | error
        loadError: null,        // {kind: 'profile' | 'closed' | 'error', message}
        showResume: false,
        inspect: null,          // {x, y}
        cursor: { x: 0, y: 0 },
        place: null,            // {type, info, origin, preview, seq, msg}
        previewTheme: null,
        retryTheme: null,
        themeMsg: null,         // {type, text, retry}
        questId: null,          // quest shown in the quest view
        challenge: null,        // challenge payload being answered
        answer: '',
        hint: null,             // latest hint from the server
        popup: null,            // 'wrong'
        reward: null,           // correct-answer response
        checkpoint: null,       // placement response
        notice: null,           // {type, text} banner after a refusal or refresh
        busy: null,             // kind of the request in flight
        checking: null,         // the mutation whose response was lost
        keys: {},               // kind -> Idempotency-Key of the current logical action
        justBuilt: false,
        catalogTip: false,
        menuOpen: false,
        focus: null,
        offline: navigator.onLine === false
    };

    var VIEW_KIND = {
        world: 'world', place: 'world', checkpoint: 'world', theme: 'world',
        missions: 'task', quest: 'task', challenge: 'task', reward: 'task', catalog: 'task', help: 'task'
    };
    var NAV_OF = {
        world: 'world', checkpoint: 'world', theme: 'world', help: 'world',
        missions: 'missions', quest: 'missions', challenge: 'missions', reward: 'missions',
        catalog: 'catalog', place: 'catalog'
    };
    var FOCUS_OF = {
        world: '#obj-title', missions: '#missions-title', quest: '#quest-title', challenge: '#ch-title',
        reward: '#rw-title', catalog: '#cat-title', place: '#place-title', checkpoint: '#cp-title',
        theme: '#theme-title', help: '#help-title'
    };

    /* ------------------------------------------------------------------ */
    /* API                                                                  */
    /* ------------------------------------------------------------------ */
    function newKey(kind) {
        var id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID()
            : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
        return 'kq-' + kind + '-' + id;
    }

    function request(method, path, body, key) {
        var opts = { method: method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
        if (body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        if (key) { opts.headers['Idempotency-Key'] = key; }
        return window.fetch(API + path, opts).then(function (res) {
            return res.text().then(function (text) {
                var json = null;
                try { json = JSON.parse(text); } catch (e) { json = null; }
                return { status: res.status, body: json, ok: res.ok && !!json && json.ok === true };
            });
        }, function () {
            return { status: 0, body: null, ok: false, network: true };
        });
    }
    function errorOf(res) { return (res.body && res.body.error) || {}; }
    // A lost or failed-on-the-server response: the outcome is unknown, so re-check with the same key.
    function isUncertain(res) { return res.network || res.status >= 500 || !res.body; }

    function query(params) {
        return Object.keys(params).map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); }).join('&');
    }

    function refresh() {
        return request('GET', '/state').then(function (res) {
            if (res.ok) { data.state = res.body; return true; }
            if (!isUncertain(res)) { gateFailure(res); }
            return false;
        });
    }

    function loadThemes() {
        return request('GET', '/themes').then(function (res) {
            if (res.ok) { data.themes = res.body; }
            return res.ok;
        });
    }

    // 401 / 403 / 404 KIDQUEST_DISABLED: the page cannot continue for this browser.
    function gateFailure(res) {
        var code = errorOf(res).code;
        if (res.status === 401) {
            ui.load = 'error'; ui.loadError = { kind: 'profile' };
            return true;
        }
        if (code === 'KIDQUEST_DISABLED') {
            ui.load = 'error'; ui.loadError = { kind: 'closed', message: errorOf(res).message };
            return true;
        }
        return false;
    }

    /* Mutations: one key per logical action, kept until the server answers. */
    function mutate(op) {
        if (!ui.keys[op.kind]) { ui.keys[op.kind] = newKey(op.kind); }
        op.key = ui.keys[op.kind];
        ui.busy = op.kind;
        render();
        send(op);
    }

    function send(op) {
        request(op.method, op.path, op.body, op.key).then(function (res) {
            ui.busy = null;
            if (isUncertain(res)) {
                ui.checking = op;
                ui.focus = '#chk-title';
                announce(t('checking.announce'));
                render();
                return;
            }
            ui.checking = null;
            ui.keys[op.kind] = null;   // answered: the next action is a new intent
            if (res.ok) { op.done(res.body); return; }
            if (gateFailure(res)) { render(); return; }
            if (op.fail && op.fail(res, errorOf(res).code)) { return; }
            refusedGeneric(res);
        });
    }

    function recheck() {
        var op = ui.checking;
        if (!op) { return; }
        ui.busy = op.kind;
        render();
        send(op);
    }

    // Any other refusal: reload the authoritative state and say what happened. Nothing changed.
    function refusedGeneric(res) {
        var err = errorOf(res);
        var text = err.message || t('errors.generic');
        if (err.code === 'WORLD_VERSION_CONFLICT' || err.code === 'IDEMPOTENCY_CONFLICT') { text = t('errors.conflict'); }
        refresh().then(function () {
            ui.notice = { type: 'error', text: text };
            followNextAction();
        });
    }

    /* ------------------------------------------------------------------ */
    /* Derived views of the authoritative state                             */
    /* ------------------------------------------------------------------ */
    function st() { return data.state; }
    function questById(id) {
        var qs = st().quests;
        for (var i = 0; i < qs.length; i++) { if (qs[i].id === id) { return qs[i]; } }
        return null;
    }
    function questForBuilding(type) {
        var qs = st().quests;
        for (var i = 0; i < qs.length; i++) { if (qs[i].building_id === type) { return qs[i]; } }
        return null;
    }
    function nextAction() { return st().next_action || { type: 'none' }; }
    // The quest the child is on, or the last playable one once everything is done.
    function currentQuest() {
        var na = nextAction();
        if (na.quest_id) { return questById(na.quest_id); }
        var playable = st().quests.filter(function (q) { return q.playable; });
        return playable[playable.length - 1] || st().quests[0];
    }
    function capped() { var d = st().daily_attempts; return !!d && d.remaining <= 0; }
    function displayThemeId() { return ui.previewTheme || st().theme.id; }
    function themeEntry(id) {
        if (!data.themes) { return null; }
        for (var i = 0; i < data.themes.themes.length; i++) { if (data.themes.themes[i].id === id) { return data.themes.themes[i]; } }
        return null;
    }
    function labels() {
        if (ui.previewTheme) { var e = themeEntry(ui.previewTheme); if (e) { return e.labels; } }
        return st().theme.labels;
    }
    function themeName(id) {
        if (id === st().theme.id) { return st().theme.name; }
        var e = themeEntry(id);
        return e ? e.name : id;
    }
    function buildingName(type) { return labels()[type] || type; }
    // The displayed theme's asset map. A previewed theme has one only if /themes provides it.
    function displayAssets() {
        if (!ui.previewTheme) { return st().theme.assets; }
        var e = themeEntry(ui.previewTheme);
        return e && e.assets ? e.assets : null;
    }
    function resourceName(resource) { return t('resources.' + resource); }
    function costText(cost) {
        return Object.keys(cost || {}).map(function (r) { return cost[r] + ' ' + resourceName(r); }).join(', ');
    }
    function buildingAt(x, y) {
        var bs = st().buildings;
        for (var i = 0; i < bs.length; i++) {
            var b = bs[i];
            if (x >= b.x && x < b.x + b.width && y >= b.y && y < b.y + b.height) { return b; }
        }
        return null;
    }
    function fixedAt(x, y) {
        var fo = st().world.terrain.fixed_objects;
        for (var i = 0; i < fo.length; i++) { if (fo[i].x === x && fo[i].y === y) { return fo[i]; } }
        return null;
    }
    function waterAt(x, y) {
        var w = st().world.terrain.water;
        for (var i = 0; i < w.length; i++) { if (w[i].x === x && w[i].y === y) { return w[i]; } }
        return null;
    }
    function inRect(z, x, y) { return z && x >= z.x && x < z.x + z.width && y >= z.y && y < z.y + z.height; }
    // A zone that opens with a quest stays locked until that quest is completed.
    function lockedZoneAt(x, y) {
        var zones = st().world.terrain.zones;
        for (var i = 0; i < zones.length; i++) {
            var z = zones[i];
            if (z.unlocked_by_quest && inRect(z, x, y)) {
                var q = questById(z.unlocked_by_quest);
                if (!q || q.status !== 'COMPLETED') { return z; }
            }
        }
        return null;
    }
    function placeZone() { return ui.place && ui.place.info ? ui.place.info.zone : null; }
    // Decision D11: a tap inside the build zone picks the footprint that covers the tapped cell and
    // fits the zone; the request still sends the footprint's top-left cell. Outside the zone the
    // tapped cell is the top-left cell, so the child hears the concrete reason it cannot be built.
    function fitOrigin(x, y) {
        var z = placeZone(), info = ui.place && ui.place.info;
        if (!z || !info || !inRect(z, x, y)) { return { x: x, y: y }; }
        return {
            x: Math.min(Math.max(x, z.x), z.x + z.width - info.w),
            y: Math.min(Math.max(y, z.y), z.y + z.height - info.h)
        };
    }

    /* ------------------------------------------------------------------ */
    /* Theme art (PRD 11.3): selected-theme asset -> neutral placeholder -> dev error  */
    /* ------------------------------------------------------------------ */
    var assetState = {};     // url -> pending | ok | missing
    var devProblems = [];    // asset IDs with neither art nor placeholder
    var renderQueued = false;
    function scheduleRender() {
        if (renderQueued) { return; }
        renderQueued = true;
        window.requestAnimationFrame(function () { renderQueued = false; if (ui.load === 'ready') { renderArt(); } });
    }
    // An image arrived: redraw only the art (world and theme thumbnails), so a tap on a panel button
    // that is in progress is never lost to a re-render.
    function renderArt() {
        var slot = $('.world-slot');
        var active = document.activeElement;
        var fk = active && active.dataset && slot && slot.contains(active) ? active.dataset.fk : null;
        if (slot) { slot.innerHTML = renderWorld(); }
        document.querySelectorAll('.theme-card').forEach(function (card) {
            var e = themeEntry(card.dataset.id), thumb = card.querySelector('.theme-thumb');
            if (e && thumb) { thumb.outerHTML = themeThumb(e); }
        });
        if (fk) { var el = $('[data-fk="' + fk + '"]'); if (el) { el.focus({ preventScroll: true }); } }
    }
    function probe(url) {
        if (assetState[url]) { return assetState[url]; }
        assetState[url] = 'pending';
        var img = new Image();
        img.onload = function () { assetState[url] = 'ok'; scheduleRender(); };
        img.onerror = function () { assetState[url] = 'missing'; if (DEV) { scheduleRender(); } };
        img.src = url;
        return 'pending';
    }
    function devError(assetId) {
        if (devProblems.indexOf(assetId) < 0) { devProblems.push(assetId); }
        return DEV ? '<span class="dev-asset-error" data-testid="dev-asset-error">' + h(assetId) + '</span>' : '';
    }
    // Returns {html, art}: the theme image when it has loaded, else '' (the caller draws the placeholder).
    function art(assetId) {
        var map = displayAssets();
        if (!map) { return { html: '', art: false }; }             // previewed theme without an asset map
        var url = map[assetId];
        if (!url) { return { html: devError(assetId), art: false, error: true }; }
        if (probe(url) !== 'ok') { return { html: '', art: false }; }
        return { html: '<img class="art" src="' + h(url) + '" alt="" data-asset="' + h(assetId) + '">', art: true };
    }
    function assetSummary() {
        var map = displayAssets();
        var used = usedAssetIds();
        var counts = { ok: 0, missing: 0, pending: 0 };
        used.forEach(function (id) {
            var url = map && map[id];
            counts[url ? (assetState[url] || 'pending') : 'missing'] += 1;
        });
        counts.total = used.length;
        return counts;
    }
    function usedAssetIds() {
        var w = st().world, ids = [w.terrain.ground_asset_id];
        w.terrain.water.forEach(function (c) { ids.push(c.asset_id); });
        w.terrain.fixed_objects.forEach(function (o) { ids.push(o.asset_id); });
        st().buildings.forEach(function (b) { ids.push(b.asset_id); });
        st().paths.forEach(function (p) { ids.push(p.asset_id); });
        return ids.filter(function (id, i) { return ids.indexOf(id) === i; });
    }

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
        stats: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
        motion: '<path d="M3 12h4l2.5-5 5 10 2.5-5h4"/>',
        shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>'
    };
    function icon(name, cls) {
        return '<svg class="icon ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICONS[name] + '</svg>';
    }
    function houseArt() {
        return '<div class="house-art" aria-hidden="true"><div class="house-roof"></div><div class="house-body"></div><div class="house-door"></div></div>';
    }
    function pos(x, y, w, h2) {
        return 'left:calc(var(--tile)*' + x + ');top:calc(var(--tile)*' + y + ');width:calc(var(--tile)*' + w + ');height:calc(var(--tile)*' + h2 + ')';
    }
    function cellSel(c) { return '[data-fk="cell-' + c.x + '-' + c.y + '"]'; }
    function offlineReason() {
        return ui.offline ? '<p class="muted" data-reason="offline">' + icon('offline', 'icon-sm') + ' ' + tt('offline.reason') + '</p>' : '';
    }
    function blocked() { return ui.offline || !!ui.busy; }

    /* ------------------------------------------------------------------ */
    /* Render: shell                                                        */
    /* ------------------------------------------------------------------ */
    function avatar() {
        return '<span class="learner-avatar" aria-hidden="true"><img src="' + IMG + h(boot.child) + '-avatar.png" alt=""></span>';
    }

    // Header card mirrors quiz.html .quiz-header. No level/XP (decision C9): the context line names the island.
    function renderHeader() {
        var inv = st() ? st().inventory : null;
        var owns = inv && (inv.blueprints.length > 0 || Object.keys(inv.resources).some(function (r) { return inv.resources[r] > 0; }));
        var showCard = ui.load === 'ready' && (owns || ui.view === 'catalog') && ['place', 'theme', 'challenge'].indexOf(ui.view) < 0;
        var card = '';
        if (showCard) {
            var res = Object.keys(inv.resources).filter(function (r) { return inv.resources[r] > 0; });
            if (!res.length) { res = Object.keys(inv.resources).slice(0, 1); }
            var bps = inv.blueprints.map(buildingName).join(', ') || t('shell.blueprint_none');
            card = '<section class="today-card" aria-label="' + tt('shell.resources_title') + '" data-testid="resources">' +
                '<div class="today-title">' + icon('wood') + ' ' + tt('shell.resources_title') + '</div>' +
                '<div class="today-total">' + res.map(function (r) {
                    return '<span data-resource="' + h(r) + '"><strong>' + h(inv.resources[r]) + '</strong> ' + h(resourceName(r)) + '</span>';
                }).join(' · ') + '</div>' +
                '<div class="today-divider" aria-hidden="true"></div>' +
                '<div class="today-detail"><span>' + icon('blueprint', 'icon-sm') + tt('shell.blueprint_label') + ' <b>' + h(bps) + '</b></span></div>' +
                '<img class="gift-icon" src="' + IMG + 'reward-gift.png" alt="">' +
                '<span class="gift-sparkle sparkle-one" aria-hidden="true">✦</span><span class="gift-sparkle sparkle-two" aria-hidden="true">✦</span><span class="gift-sparkle sparkle-three" aria-hidden="true">✦</span>' +
                '</section>';
        }
        return '<header class="kq-header">' +
            '<div class="learner-summary">' + avatar() +
            '<div class="learner-copy"><span>' + tt('shell.name_label') + '</span><strong class="hud-name">' + h(boot.name) + '</strong>' +
            '<span>' + tt('shell.island_label') + ' <b>' + tt('shell.island_name') + '</b></span></div>' +
            '<button class="header-link" data-act="open-menu" data-fk="menu-btn" aria-haspopup="dialog">' + icon('menu') + '<span>' + tt('shell.menu') + '</span></button>' +
            '</div>' + card + '</header>';
    }

    // Tab row mirrors quiz.html .quiz-tabs. No Dompet in the first-house release.
    function renderNav() {
        var current = NAV_OF[ui.view];
        var items = [['world', 'shell.nav_world', 'world'], ['missions', 'shell.nav_missions', 'missions'], ['catalog', 'shell.nav_build', 'build']];
        return '<nav class="nav" aria-label="' + tt('shell.nav_label') + '">' + items.map(function (it) {
            return '<button class="nav-item" data-act="nav" data-view="' + it[0] + '" data-fk="nav-' + it[0] + '"' +
                (current === it[0] ? ' aria-current="page"' : '') + '><span class="tab-icon" aria-hidden="true">' + icon(it[2]) + '</span><span>' + tt(it[1]) + '</span></button>';
        }).join('') + '</nav>';
    }

    function renderBanners() {
        var out = '';
        if (ui.offline) {
            out += '<div class="alert alert-offline" role="status" data-testid="offline-banner">' + icon('offline') +
                '<div><p><strong>' + tt('offline.banner_title') + '</strong> ' + tt('offline.banner_text') + '</p></div></div>';
        }
        if (ui.notice) {
            out += '<div class="alert alert-' + (ui.notice.type === 'error' ? 'error' : 'info') + '" role="' + (ui.notice.type === 'error' ? 'alert' : 'status') + '" data-testid="notice">' +
                icon('info') + '<div><p>' + h(ui.notice.text) + '</p></div>' +
                '<button class="btn btn-secondary" data-act="dismiss-notice" data-fk="notice-close">' + tt('shell.close') + '</button></div>';
        }
        if (ui.view === 'place' && ui.place) {
            out += '<div class="alert alert-mode">' + icon('build') +
                '<div><p><strong>' + tt('place.mode_banner', { name: buildingName(ui.place.type) }) + '</strong> ' + tt('place.mode_banner_text') + '</p></div>' +
                '<button class="btn btn-secondary" data-act="cancel-place" data-fk="cancel-place-top">' + tt('place.cancel') + '</button></div>';
        }
        if (ui.view === 'theme' && ui.previewTheme) {
            out += '<div class="alert alert-info" role="status" data-testid="theme-preview-banner">' + icon('palette') +
                '<div><p><strong>' + tt('theme.preview_banner', { name: themeName(ui.previewTheme) }) + '</strong> ' + tt('theme.preview_banner_text') + '</p></div></div>';
        }
        return out;
    }

    /* ------------------------------------------------------------------ */
    /* Render: objective and calm resume (PRD 7.1, 11.11), from next_action  */
    /* ------------------------------------------------------------------ */
    function objectiveModel() {
        var na = nextAction(), q = currentQuest();
        if (na.type === 'start_quest') {
            return { eyebrow: t('objective.eyebrow_now'), title: q.title, text: t('objective.start_text'), cta: t('objective.start_cta'), act: 'open-quest', id: q.id };
        }
        if (na.type === 'answer_challenge') {
            if (capped()) {
                return { eyebrow: t('objective.eyebrow_rest'), title: t('objective.cap_title'), text: t('objective.cap_text'), link: true };
            }
            return { eyebrow: t('objective.eyebrow_now'), title: q.title, text: t('objective.resume_text'), cta: t('objective.resume_cta'), act: 'open-challenge', id: q.id };
        }
        if (na.type === 'place_building') {
            var name = buildingName(na.building_id);
            return { eyebrow: t('objective.eyebrow_now'), title: t('objective.build_title', { name: name }), text: t('objective.build_text'), cta: t('objective.build_cta', { name: name }), act: 'start-place', id: na.building_id };
        }
        if (!prefs.themeIntroDone) {
            return { eyebrow: t('objective.eyebrow_new'), title: t('objective.theme_title'), text: t('objective.theme_text'), cta: t('objective.theme_cta'), act: 'open-theme', later: true };
        }
        return { eyebrow: t('objective.eyebrow_world'), title: t('objective.done_title'), text: t('objective.done_text'), link: true };
    }

    function resumeModel() {
        var na = nextAction(), q = currentQuest();
        var built = st().buildings[st().buildings.length - 1];
        if (na.type === 'answer_challenge') {
            return {
                last: t('resume.last_answered', { title: q.title }),
                now: capped() ? t('resume.now_cap') : t('resume.now_challenge', { title: q.title }),
                cta: capped() ? null : t('objective.resume_cta'), act: 'open-challenge', id: q.id
            };
        }
        if (na.type === 'place_building') {
            var name = buildingName(na.building_id);
            return { last: t('resume.last_reward', { title: q.title }), now: t('resume.now_build', { name: name }), cta: t('resume.build_cta', { name: name }), act: 'start-place', id: na.building_id };
        }
        return { last: built ? t('resume.last_built', { name: buildingName(built.type) }) : t('resume.saved'), now: t('resume.now_done'), cta: null };
    }
    // Resume appears on entry once there is progress to come back to (never for a brand-new child).
    function hasProgress() {
        var na = nextAction();
        if (na.type === 'start_quest') { return false; }
        if (na.type === 'answer_challenge') { return !!(st().active_challenge && st().active_challenge.attempt_count > 0); }
        return true;
    }

    function renderObjective(compact) {
        if (ui.load === 'loading') {
            return '<section class="card" aria-busy="true" aria-label="' + tt('load.loading_label') + '" data-testid="loading"><div class="skeleton" style="height:18px;width:40%"></div><div class="skeleton" style="height:28px;width:70%"></div><div class="skeleton" style="height:44px"></div><p class="muted">' + tt('load.loading') + '</p></section>';
        }
        if (compact) {
            var cm = objectiveModel();
            var cq = currentQuest();
            return '<section class="card" aria-labelledby="obj-title" data-testid="objective-compact">' +
                '<p class="eyebrow">' + h(cm.eyebrow) + '</p><h2 id="obj-title" tabindex="-1" style="font-size:1.125rem">' + h(cm.title) + '</h2>' +
                (cq && cq.status !== 'COMPLETED' ? questStatus(cq.status) : '') + '</section>';
        }
        if (ui.showResume) {
            var r = resumeModel();
            return '<section class="card card-accent" aria-labelledby="resume-title" data-testid="resume">' +
                '<p class="eyebrow">' + tt('resume.eyebrow') + '</p>' +
                '<h2 id="resume-title" tabindex="-1">' + tt('resume.title') + '</h2>' +
                '<ul class="list-plain">' +
                '<li>' + icon('check', 'icon-sm') + '<span>' + h(r.last) + '</span></li>' +
                '<li>' + icon('info', 'icon-sm') + '<span>' + tt('resume.now', { text: r.now }) + '</span></li>' +
                '<li>' + icon('shield', 'icon-sm') + '<span>' + tt('resume.saved') + '</span></li>' +
                '</ul>' +
                '<div class="btn-row">' +
                (r.cta ? '<button class="btn btn-primary" data-act="' + r.act + '" data-id="' + h(r.id) + '" data-fk="resume-cta"' + (ui.busy ? ' disabled' : '') + '>' + h(r.cta) + '</button>' : '') +
                '<button class="btn btn-secondary" data-act="dismiss-resume" data-fk="resume-close">' + tt('shell.close') + '</button></div></section>';
        }
        var m = objectiveModel();
        var action = m.link
            ? '<a class="btn btn-primary" href="' + h(LINKS.quiz) + '" data-fk="obj-cta">' + tt('objective.done_cta') + '</a>'
            : '<button class="btn btn-primary" data-act="' + m.act + '"' + (m.id ? ' data-id="' + h(m.id) + '"' : '') + ' data-fk="obj-cta"' + (ui.busy ? ' disabled' : '') + '>' + h(m.cta) + '</button>';
        return '<section class="card card-accent" aria-labelledby="obj-title" data-testid="objective">' +
            '<p class="eyebrow">' + h(m.eyebrow) + '</p>' +
            '<h2 id="obj-title" tabindex="-1">' + h(m.title) + '</h2>' +
            '<p class="lead">' + h(m.text) + '</p>' +
            '<div class="btn-row">' + action +
            (m.later ? '<button class="btn btn-text" data-act="theme-later" data-fk="obj-later">' + tt('shell.later') + '</button>' : '') +
            '</div></section>';
    }

    function renderLoadError() {
        var e = ui.loadError || { kind: 'error' };
        if (e.kind === 'profile') {
            return '<section class="card" aria-labelledby="load-err" data-testid="load-profile"><h2 id="load-err" tabindex="-1">' + tt('load.profile_title') + '</h2>' +
                '<p>' + tt('load.profile_text') + '</p><a class="btn btn-primary" href="' + h(LINKS.home) + '" data-fk="load-cta">' + tt('load.profile_cta') + '</a></section>';
        }
        if (e.kind === 'closed') {
            return '<section class="card" aria-labelledby="load-err" data-testid="load-closed"><h2 id="load-err" tabindex="-1">' + tt('load.closed_title') + '</h2>' +
                '<p>' + h(e.message || '') + '</p><p>' + tt('load.closed_text') + '</p>' +
                '<div class="btn-row"><a class="btn btn-primary" href="' + h(LINKS.quiz) + '" data-fk="load-cta">' + tt('menu.quiz') + '</a>' +
                '<a class="btn btn-secondary" href="' + h(LINKS.stats) + '">' + tt('menu.stats') + '</a></div></section>';
        }
        return '<section class="card" aria-labelledby="load-err" data-testid="load-error"><div class="alert alert-error" role="alert">' + icon('info') +
            '<div><h2 id="load-err" tabindex="-1" style="font-size:1.125rem">' + tt('load.error_title') + '</h2><p>' + tt('load.error_text') + '</p>' +
            '<button class="btn btn-primary" data-act="retry-load" data-fk="retry-load">' + icon('refresh') + tt('shell.retry') + '</button>' + offlineReason() + '</div></div></section>';
    }

    /* ------------------------------------------------------------------ */
    /* Render: world grid (8x8 CSS grid, layered, row-ordered)              */
    /* ------------------------------------------------------------------ */
    function cellLabel(x, y) {
        var what;
        var b = buildingAt(x, y), f = fixedAt(x, y), na = nextAction();
        if (b) { what = t('world.cell_house', { name: buildingName(b.type) }); }
        else if (f) {
            var name = labels()[f.kind] || t('world.kind_' + f.kind);
            what = f.kind === 'quest_board' && (na.type === 'start_quest' || na.type === 'answer_challenge') ? t('world.cell_quest', { name: name }) : name;
        }
        else if (waterAt(x, y)) { what = t('world.kind_water'); }
        else if (lockedZoneAt(x, y)) { what = t('world.kind_locked'); }
        else { what = t('world.kind_ground'); }
        if (ui.view === 'place' && inRect(placeZone(), x, y)) { what = t('world.cell_zone', { label: what }); }
        return t('world.cell_where', { what: what, x: x + 1, y: y + 1 });
    }

    function renderWorld() {
        if (ui.load === 'loading') {
            return '<div class="world-frame" aria-hidden="true"><div class="skeleton" style="width:calc(var(--tile)*8);height:calc(var(--tile)*8)"></div></div>';
        }
        if (ui.load !== 'ready') { return ''; }
        var w = st().world, na = nextAction(), zone = ui.view === 'place' ? placeZone() : null;
        var cells = '';
        for (var y = 0; y < w.height; y++) {
            cells += '<div role="row" style="display:contents">';
            for (var x = 0; x < w.width; x++) {
                var water = waterAt(x, y);
                var terrain = art(water ? water.asset_id : w.terrain.ground_asset_id);
                var zoneAttr = inRect(zone, x, y) ? ' data-zone="target"' : (lockedZoneAt(x, y) ? ' data-zone="locked"' : '');
                cells += '<button role="gridcell" class="cell' + (zone && !prefs.placeTipDone && inRect(zone, x, y) ? ' pulse' : '') + '"' +
                    ' data-act="cell" data-x="' + x + '" data-y="' + y + '" data-fk="cell-' + x + '-' + y + '"' +
                    ' data-terrain="' + (water ? 'water' : 'ground') + '"' + zoneAttr +
                    ' tabindex="' + (ui.cursor.x === x && ui.cursor.y === y ? '0' : '-1') + '" aria-label="' + h(cellLabel(x, y)) + '">' + terrain.html + '</button>';
            }
            cells += '</div>';
        }
        var objs = '';
        st().paths.forEach(function (p) {
            var a = art(p.asset_id);
            objs += '<div class="obj obj-road" style="' + pos(p.x, p.y, 1, 1) + '" aria-hidden="true">' + (a.art ? a.html : '<span class="ph-road"></span>' + a.html) + '</div>';
        });
        w.terrain.fixed_objects.forEach(function (o) {
            var a = art(o.asset_id);
            var ph = a.art ? '' : (PLACEHOLDER_KINDS[o.kind] ? ' ph-' + o.kind : (DEV ? '' : ' ph-generic'));
            var missing = !a.art && !PLACEHOLDER_KINDS[o.kind] ? devError(o.kind) : '';
            objs += '<div class="obj obj-shadow" style="' + pos(o.x, o.y, 1, 1) + '" aria-hidden="true"></div>' +
                '<div class="obj obj-prop' + ph + '" data-kind="' + h(o.kind) + '" style="' + pos(o.x, o.y, 1, 1) + ';--row:' + o.y + '" aria-hidden="true">' + a.html + missing + '</div>';
            if (o.kind === 'quest_board' && (na.type === 'start_quest' || na.type === 'answer_challenge') && ui.view !== 'place') {
                objs += '<div class="obj obj-badge" style="' + pos(o.x, o.y, 1, 1) + ';overflow:visible" aria-hidden="true"><span class="badge">!<span>' + tt('world.badge_quest') + '</span></span></div>';
            }
        });
        st().buildings.forEach(function (b) {
            var a = art(b.asset_id);
            objs += '<div class="obj obj-shadow" style="' + pos(b.x, b.y, b.width, b.height) + '" aria-hidden="true"></div>' +
                '<div class="obj obj-building" data-testid="building" data-type="' + h(b.type) + '" data-art="' + (a.art ? 'theme' : 'placeholder') + '" style="' + pos(b.x, b.y, b.width, b.height) + ';--row:' + (b.y + b.height - 1) + '" aria-hidden="true">' +
                (a.art ? a.html : houseArt() + a.html) + '</div>';
            if (ui.justBuilt) {
                objs += '<div class="built-flash" style="' + pos(b.x, b.y, b.width, b.height) + '" aria-hidden="true">' + icon('star') + '</div>';
            }
        });
        if (ui.view === 'place' && ui.place && ui.place.info) {
            var info = ui.place.info, o2 = ui.place.origin, pv = ui.place.preview;
            if (o2) {
                var cls = !pv ? 'hover' : (pv.valid ? 'valid' : 'invalid');
                var pw = Math.max(1, Math.min(info.w, w.width - o2.x)), ph2 = Math.max(1, Math.min(info.h, w.height - o2.y));
                objs += '<div class="preview ' + cls + '" data-testid="preview" data-x="' + o2.x + '" data-y="' + o2.y + '" style="' + pos(o2.x, o2.y, pw, ph2) + '" aria-hidden="true">' +
                    (pv ? '<span class="preview-mark">' + icon(pv.valid ? 'check' : 'cross', 'icon-sm') + '</span>' : '') + '</div>';
            }
            var fc = fitOrigin(ui.cursor.x, ui.cursor.y);
            if (!o2 || o2.x !== fc.x || o2.y !== fc.y) {
                objs += '<div class="preview hover" style="' + pos(fc.x, fc.y, Math.min(info.w, w.width - fc.x), Math.min(info.h, w.height - fc.y)) + '" aria-hidden="true"></div>';
            }
        }
        var caption = '<p class="world-caption">' +
            (ui.view === 'place' ? '<span><span class="legend-swatch" aria-hidden="true"></span>' + tt('world.legend_zone') + '</span>' : '') +
            '<span data-testid="theme-caption">' + tt('world.caption_theme', { name: themeName(displayThemeId()) }) + '</span></p>';
        return '<section class="world-frame" aria-label="' + tt('world.frame_label', { name: boot.name }) + '" data-theme-id="' + h(displayThemeId()) + '">' +
            '<div class="world-grid" role="grid" aria-label="' + tt('world.grid_label') + '" data-testid="grid">' + cells + objs + '</div>' +
            '</section>' + caption + devNote();
    }

    // Development only: how much of the theme pack is real art. Not child copy, so not in ui_strings.
    function devNote() {
        if (!DEV) { return ''; }
        var s = assetSummary();
        var problems = devProblems.length ? ' Errors: ' + devProblems.join(', ') + '.' : '';
        return '<p class="dev-note' + (devProblems.length || missingStrings.length ? ' is-error' : '') + '" data-testid="dev-note">DEV · theme ' + h(displayThemeId()) +
            (displayAssets() ? ' · art ' + s.ok + '/' + s.total + ' loaded, ' + s.missing + ' missing, ' + s.pending + ' pending -> neutral placeholder'
                : ' · no asset map for this preview -> neutral placeholder') +
            h(problems) + (missingStrings.length ? ' Missing strings: ' + h(missingStrings.join(', ')) + '.' : '') + '</p>';
    }

    /* ------------------------------------------------------------------ */
    /* Render: panels                                                       */
    /* ------------------------------------------------------------------ */
    function backBtn(view) {
        return '<button class="btn btn-secondary" data-act="go" data-view="' + view + '" data-fk="back-' + ui.view + '">' + icon('back') + '<span>' + tt('shell.back') + '</span></button>';
    }

    function questStatus(status) {
        var map = {
            AVAILABLE: ['status-available', 'star', 'status.available'],
            IN_PROGRESS: ['status-active', 'clock', 'status.in_progress'],
            READY_TO_BUILD: ['status-ready', 'build', 'status.ready_to_build'],
            COMPLETED: ['status-done', 'check', 'status.completed'],
            LOCKED: ['status-locked', 'lock', 'status.locked']
        };
        var m = map[status] || map.LOCKED;
        return '<span class="status ' + m[0] + '" data-status="' + h(status) + '">' + icon(m[1], 'icon-sm') + tt(m[2]) + '</span>';
    }

    function panelChecking() {
        return '<section class="card" aria-labelledby="chk-title" data-testid="checking">' +
            '<div class="alert alert-info" role="status">' + icon('refresh') +
            '<div><h2 id="chk-title" tabindex="-1" style="font-size:1.125rem">' + tt('checking.title') + '</h2>' +
            '<p>' + tt('checking.text') + '</p>' +
            '<button class="btn btn-primary" data-act="recheck" data-fk="recheck" data-testid="recheck"' + (blocked() ? ' disabled' : '') + '>' + icon('refresh') +
            (ui.busy ? tt('challenge.checking') : tt('checking.cta')) + '</button>' +
            offlineReason() + '</div></div></section>';
    }

    function panelWorld() {
        if (!ui.inspect) {
            return '<section class="card" aria-labelledby="ctx-title"><h2 id="ctx-title" class="eyebrow" style="font-size:.875rem">' + tt('world.inspect_hint_title') + '</h2>' +
                '<p>' + tt('world.inspect_hint') + '</p></section>';
        }
        var x = ui.inspect.x, y = ui.inspect.y;
        var b = buildingAt(x, y), f = fixedAt(x, y), locked = lockedZoneAt(x, y);
        var title, body, action = '';
        if (b) {
            title = buildingName(b.type); body = t('world.inspect_house');
        } else if (f && f.kind === 'quest_board') {
            title = labels().quest_board || t('world.kind_object'); body = t('world.inspect_quest_board');
            action = '<button class="btn btn-primary" data-act="nav" data-view="missions" data-fk="insp-missions">' + tt('world.inspect_missions_cta') + '</button>';
        } else if (f) {
            title = labels()[f.kind] || t('world.kind_' + f.kind); body = t('world.inspect_blocked');
        } else if (waterAt(x, y)) {
            title = t('world.kind_water'); body = t('world.inspect_water');
        } else if (locked) {
            var lq = questById(locked.unlocked_by_quest);
            title = t('world.kind_locked'); body = t('world.inspect_locked', { title: lq ? lq.title : locked.unlocked_by_quest });
        } else {
            title = t('world.kind_ground'); body = t('world.inspect_ground');
        }
        return '<section class="card" aria-labelledby="insp-title" data-testid="inspector">' +
            '<div class="panel-head"><h2 id="insp-title" tabindex="-1">' + h(title) + '</h2>' +
            '<button class="btn btn-secondary" data-act="close-inspect" data-fk="insp-close"><span>' + tt('shell.close') + '</span></button></div>' +
            '<p>' + h(body) + '</p><p class="muted">' + tt('world.inspect_where', { x: x + 1, y: y + 1 }) + '</p>' + action + '</section>';
    }

    function panelMissions() {
        var qs = st().quests, out = '';
        var nextLocked = null;
        qs.forEach(function (q) {
            if (q.playable) {
                var open = q.status !== 'COMPLETED';
                out += '<article class="card' + (open ? ' card-accent' : '') + '" aria-labelledby="q-' + h(q.id) + '" data-testid="quest-card" data-quest="' + h(q.id) + '">' +
                    '<h3 id="q-' + h(q.id) + '">' + h(q.title) + '</h3>' + questStatus(q.status) +
                    '<button class="btn ' + (open ? 'btn-primary' : 'btn-secondary') + '" data-act="open-quest" data-id="' + h(q.id) + '" data-fk="open-' + h(q.id) + '"' + (ui.busy ? ' disabled' : '') + '>' + tt('missions.open') + '</button></article>';
            } else if (!nextLocked) {
                nextLocked = q;
            }
        });
        if (nextLocked) {
            var prevDone = qs.filter(function (q) { return q.playable; }).every(function (q) { return q.status === 'COMPLETED'; });
            out += '<article class="card" aria-labelledby="q-' + h(nextLocked.id) + '" data-testid="quest-card" data-quest="' + h(nextLocked.id) + '"><h3 id="q-' + h(nextLocked.id) + '">' + h(nextLocked.title) + '</h3>' +
                (prevDone ? '<span class="status status-notyet">' + icon('clock', 'icon-sm') + tt('status.not_yet') + '</span><p>' + tt('missions.not_yet') + '</p>'
                    : '<span class="status status-locked">' + icon('lock', 'icon-sm') + tt('status.locked') + '</span><p>' + tt('missions.locked_why') + '</p>') +
                '</article>';
        }
        return '<section class="stack" aria-labelledby="missions-title">' +
            '<h2 id="missions-title" tabindex="-1" class="section-title">' + tt('missions.title') + '</h2>' + out + '</section>';
    }

    function panelQuest() {
        var q = data.quests[ui.questId] || questById(ui.questId);
        var status = (questById(ui.questId) || q).status;
        var cta;
        if (status === 'AVAILABLE' || status === 'IN_PROGRESS') {
            cta = '<button class="btn btn-primary" data-act="open-challenge" data-id="' + h(q.id) + '" data-fk="quest-cta"' + (blocked() ? ' disabled' : '') + '>' +
                (ui.busy === 'challenge' ? tt('quest.preparing') : tt(status === 'AVAILABLE' ? 'quest.start_challenge' : 'quest.resume_challenge')) + '</button>';
        } else if (status === 'READY_TO_BUILD') {
            cta = '<button class="btn btn-primary" data-act="start-place" data-id="' + h(q.building_id) + '" data-fk="quest-cta">' + tt('quest.build', { name: buildingName(q.building_id) }) + '</button>';
        } else {
            cta = '<button class="btn btn-primary" data-act="show-building" data-id="' + h(q.building_id) + '" data-fk="quest-cta">' + tt('quest.show_in_world') + '</button>';
        }
        // Before a correct answer only the content's reward_preview is shown, never an amount (PRD 8.4).
        var preview = q.reward_preview && (status === 'AVAILABLE' || status === 'IN_PROGRESS')
            ? '<p class="reward-preview" data-testid="reward-preview">' + icon('blueprint', 'icon-sm') + '<strong>' + h(q.reward_preview) + '</strong></p>' : '';
        return '<section class="card" aria-labelledby="quest-title" data-testid="quest-detail">' +
            '<div class="panel-head">' + backBtn('missions') + '</div>' +
            '<p class="eyebrow">' + tt('missions.skill_eyebrow') + '</p>' +
            '<h2 id="quest-title" tabindex="-1">' + h(q.title) + '</h2>' + questStatus(status) +
            (q.story ? '<p class="lead">' + h(q.story) + '</p>' : '') + preview +
            cta + (status === 'AVAILABLE' || status === 'IN_PROGRESS' ? offlineReason() : '') + '</section>';
    }

    // Slots of the challenge picture, from the server's visual_context; the worked hint numbers the gaps.
    function planks(visual, worked) {
        var out = '';
        for (var i = 1; i <= visual.required; i++) {
            if (i <= visual.available) { out += '<span class="plank" aria-hidden="true"></span>'; }
            else if (worked) { out += '<span class="plank empty counted" aria-hidden="true">' + i + '</span>'; }
            else { out += '<span class="plank empty" aria-hidden="true"></span>'; }
        }
        return out;
    }

    var COARSE = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

    // Challenge mirrors quiz.html .quiz-question + .quiz-pad: progress strip, owl tutor bubble, prompt,
    // answer box, the 💡 line (which carries the server hint), and the keypad (Hapus · 0 · Kirim).
    function panelChallenge() {
        var c = ui.challenge;
        var isCapped = capped();
        var bubble = t('challenge.bubble_start');
        var help = '<p class="quiz-help" id="submit-why"><span class="emoji" aria-hidden="true">💡</span><span>' + tt('challenge.help') + '</span></p>';
        if (ui.hint) {
            bubble = ui.popup === 'wrong' ? t('challenge.bubble_wrong') : t('challenge.bubble_hint');
            help = '<p class="quiz-help has-hint" data-testid="hint" data-level="' + h(ui.hint.level) + '"><span class="emoji" aria-hidden="true">💡</span><span id="fb-text">' + h(ui.hint.text) + '</span></p>';
        }
        if (isCapped) {
            bubble = t('challenge.bubble_cap');
            help = '<p class="quiz-help has-hint" data-testid="cap">' + icon('clock', 'icon-sm') + '<span id="fb-text">' + tt('challenge.cap_text') + '</span></p>';
        }
        var canSubmit = ui.answer.length > 0 && !blocked() && !isCapped;
        var dis = isCapped || ui.busy ? ' disabled' : '';
        var keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(function (d) {
            return '<button class="btn" data-act="key" data-key="' + d + '" data-fk="key-' + d + '"' + dis + '>' + d + '</button>';
        }).join('') +
            '<button class="btn key-del" data-act="key" data-key="del" data-fk="key-del" aria-label="' + tt('challenge.delete_label') + '"' + dis + '>' + tt('challenge.delete') + '</button>' +
            '<button class="btn" data-act="key" data-key="0" data-fk="key-0"' + dis + '>0</button>' +
            '<button class="btn btn-primary" data-act="submit" data-fk="submit" data-testid="submit"' + (canSubmit ? '' : ' disabled') + ' aria-describedby="' + (ui.hint || isCapped ? 'fb-text' : 'submit-why') + '">' +
            (ui.busy === 'answer' ? tt('challenge.checking') : icon('check', 'icon-sm') + tt('challenge.submit')) + '</button>';
        var visual = (ui.hint && ui.hint.visual) || c.visual_context;
        var figure = visual && visual.required ? '<figure class="challenge-fig"><div class="planks" style="--slots:' + h(visual.required) + '" role="img" aria-label="' +
            tt('challenge.figure_label', { required: visual.required, available: visual.available, item: resourceName(visual.item) }) + '">' +
            planks(visual, ui.hint && ui.hint.kind === 'worked_example') + '</div>' +
            '<figcaption class="plank-caption"><span>' + tt('challenge.figure_needed', { required: visual.required }) + '</span><span>' + tt('challenge.figure_have', { available: visual.available }) + '</span></figcaption></figure>' : '';
        return '<section class="card challenge" aria-labelledby="ch-title" data-testid="challenge">' +
            '<div class="question-head">' +
            '<div class="question-progress"><span>' + tt('challenge.step', { step: 1, total: 2 }) + '</span><span class="progress-track" aria-hidden="true"><span style="width:50%"></span></span></div>' +
            '<div class="tutor-area"><p class="tutor-bubble" id="fb-title" aria-live="polite">' + h(bubble) + '</p>' +
            '<img class="tutor-owl" src="' + IMG + 'owl-tutor.png" alt=""></div></div>' +
            '<h2 id="ch-title" tabindex="-1" class="challenge-q">' + h(c.prompt) + '</h2>' + figure +
            '<div class="answer-row"><label for="answer">' + tt('challenge.answer_label') + '</label>' +
            '<input id="answer" class="answer-input" data-fk="answer" data-testid="answer" placeholder="–" inputmode="' + (COARSE ? 'none' : 'numeric') + '" autocomplete="off" maxlength="4" value="' + h(ui.answer) + '" aria-describedby="' + (ui.hint || isCapped ? 'fb-title fb-text' : 'submit-why') + '"' + (isCapped ? ' disabled' : '') + '></div>' +
            '<div aria-live="polite">' + help + '</div>' +
            '<div class="quiz-pad"><div class="keypad-grid" role="group" aria-label="' + tt('challenge.keypad_label') + '">' + keys + '</div></div>' +
            offlineReason() + '</section>';
    }

    // Reward mirrors the quiz "correct" popup; pills use wood and blueprint icons, never a coin (C13).
    // Amounts come only from this correct-answer response.
    function panelReward() {
        var r = ui.reward, reward = r.reward || { resources: {}, blueprints: [] };
        var pills = Object.keys(reward.resources || {}).map(function (res) {
            return '<li class="reward-pill"><span class="pill-icon">' + icon('wood') + '</span><span>' + tt('reward.resource_pill', { amount: reward.resources[res], name: resourceName(res) }) +
                '<small>' + tt('reward.resource_sub') + '</small></span></li>';
        }).join('') + (reward.blueprints || []).map(function (bp) {
            return '<li class="reward-pill"><span class="pill-icon is-blueprint">' + icon('blueprint') + '</span><span>' + tt('reward.blueprint_pill', { name: buildingName(bp) }) +
                '<small>' + tt('reward.blueprint_sub', { name: buildingName(bp) }) + '</small></span></li>';
        }).join('');
        var na = r.next_action || {};
        var build = na.type === 'place_building'
            ? '<button class="btn btn-primary" data-act="reward-build" data-id="' + h(na.building_id) + '" data-fk="rw-build">' + tt('reward.build_cta', { name: buildingName(na.building_id) }) + '</button>' : '';
        return '<div class="kq-popup" role="dialog" aria-modal="true" aria-labelledby="rw-title" data-testid="reward">' +
            '<div class="kq-popup-card is-correct">' +
            '<img class="kq-popup-bg" src="' + IMG + 'popup-correct-background.png" alt="">' +
            '<img class="kq-popup-icon" src="' + IMG + 'popup-correct-icon.png" alt="">' +
            '<h2 id="rw-title" class="kq-popup-title" tabindex="-1">' + tt('reward.title') + '</h2>' +
            '<p class="kq-popup-text">' + h(r.reward_message || '') + '</p>' +
            '<ul class="reward-pills" aria-label="' + tt('reward.list_label') + '">' + pills + '</ul>' +
            '<p class="kq-popup-sub">' + tt('reward.saved') + '</p>' +
            '<div class="btn-row">' + build +
            '<button class="btn btn-secondary" data-act="go" data-view="world" data-fk="rw-later">' + tt('shell.later') + '</button></div>' +
            '</div></div>';
    }

    // Wrong answer: the quiz "wrong" popup frame with the owl, neutral wording, and the server's hint (D4, C11).
    function renderWrongPopup() {
        return '<div class="kq-popup" role="dialog" aria-modal="true" aria-labelledby="wp-title" aria-describedby="wp-text" data-testid="wrong-popup">' +
            '<div class="kq-popup-card is-learn">' +
            '<img class="kq-popup-bg" src="' + IMG + 'popup-wrong-background.png" alt="">' +
            '<img class="kq-popup-icon" src="' + IMG + 'owl-tutor.png" alt="" data-testid="wrong-icon">' +
            '<h2 id="wp-title" class="kq-popup-title" tabindex="-1">' + tt('challenge.wrong_title') + '</h2>' +
            '<p id="wp-text" class="kq-popup-text"><span aria-hidden="true">💡 </span>' + h(ui.hint ? ui.hint.text : '') + '</p>' +
            '<p class="kq-popup-sub">' + tt('challenge.wrong_sub') + '</p>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="wrong-ok" data-fk="wrong-ok">' + tt('challenge.wrong_cta') + '</button></div>' +
            '</div></div>';
    }

    function catalogTypes() {
        return st().quests.filter(function (q) { return q.playable; }).map(function (q) { return q.building_id; });
    }

    function panelCatalog() {
        var tip = ui.catalogTip ? '<div class="alert alert-info" role="status">' + icon('info') +
            '<div><p>' + tt('catalog.tip') + '</p>' +
            '<button class="btn btn-text" data-act="dismiss-tip" data-fk="tip-ok">' + tt('shell.got_it') + '</button></div></div>' : '';
        var cards = catalogTypes().map(function (type) {
            var info = data.buildings[type];
            var q = questForBuilding(type);
            var inv = st().inventory;
            var built = st().buildings.some(function (b) { return b.type === type; });
            var hasBp = inv.blueprints.indexOf(type) >= 0;
            var enough = info && Object.keys(info.cost).every(function (r) { return (inv.resources[r] || 0) >= info.cost[r]; });
            var status, action;
            if (built) {
                status = '<span class="status status-done">' + icon('check', 'icon-sm') + tt('catalog.built') + '</span>';
                action = '<button class="btn btn-secondary" data-act="show-building" data-id="' + h(type) + '" data-fk="cat-cta">' + tt('quest.show_in_world') + '</button>';
            } else if (!hasBp) {
                status = '<span class="status status-locked">' + icon('lock', 'icon-sm') + tt('catalog.locked') + '</span>';
                action = '<p>' + tt('catalog.locked_why', { title: q ? q.title : '' }) + '</p>' +
                    (q ? '<button class="btn btn-secondary" data-act="open-quest" data-id="' + h(q.id) + '" data-fk="cat-cta"' + (ui.busy ? ' disabled' : '') + '>' + tt('catalog.to_quest', { title: q.title }) + '</button>' : '');
            } else if (info && !enough) {
                status = '<span class="status status-locked">' + icon('wood', 'icon-sm') + tt('catalog.short') + '</span>';
                action = '<p>' + tt('catalog.short_text') + '</p>';
            } else {
                status = '<span class="status status-ready">' + icon('check', 'icon-sm') + tt('catalog.ready') + '</span>';
                action = '<button class="btn btn-primary" data-act="start-place" data-id="' + h(type) + '" data-fk="cat-cta"' + (info ? '' : ' disabled') + '>' + tt('catalog.choose_place') + '</button>';
            }
            var facts = info ? '<dl class="facts"><dt>' + tt('catalog.size') + '</dt><dd>' + tt('catalog.size_value', { w: info.w, h: info.h }) + '</dd>' +
                '<dt>' + tt('catalog.cost') + '</dt><dd>' + h(costText(info.cost)) + '</dd></dl>' : '<p class="muted">' + tt('catalog.loading') + '</p>';
            return '<article class="card catalog-card" aria-labelledby="b-' + h(type) + '" data-testid="building-card" data-type="' + h(type) + '">' +
                '<div class="thumb' + (hasBp ? '' : ' locked') + '" aria-hidden="true">' + houseArt() + '</div>' +
                '<div class="stack"><h3 id="b-' + h(type) + '">' + h(buildingName(type)) + '</h3>' + status + facts + action + '</div></article>';
        }).join('');
        return '<section class="stack" aria-labelledby="cat-title">' +
            '<h2 id="cat-title" tabindex="-1" class="section-title">' + tt('catalog.title') + '</h2>' + tip + cards +
            '<p class="muted">' + tt('catalog.more_later') + '</p></section>';
    }

    function panelPlace() {
        var p = ui.place, info = p.info;
        var status, valid = false;
        if (!p.origin) {
            status = '<div class="place-status idle" data-testid="place-status">' + icon('info') + '<span>' + tt('place.idle') + '</span></div>';
        } else if (!p.preview) {
            status = '<div class="place-status idle" data-testid="place-status">' + icon('clock') + '<span>' + tt('place.checking') + '</span></div>';
        } else if (p.preview.valid) {
            valid = true;
            status = '<div class="place-status valid" data-testid="place-status" data-valid="true">' + icon('check') + '<span>' + tt('place.valid') + '</span></div>';
        } else {
            // The server's own words for the first broken rule (PRD 9.13), never a client-side rule.
            status = '<div class="place-status invalid" data-testid="place-status" data-valid="false" data-rule="' + h(p.preview.problems[0].rule) + '">' + icon('cross') +
                '<span>' + h(p.preview.problems[0].message) + '</span></div>';
        }
        var tip = !prefs.placeTipDone ? '<div class="alert alert-info">' + icon('info') +
            '<div><p>' + tt('place.tip', { w: info.w, h: info.h }) + '</p>' +
            '<button class="btn btn-text" data-act="dismiss-place-tip" data-fk="place-tip-ok">' + tt('shell.got_it') + '</button></div></div>' : '';
        var msg = p.msg ? '<div class="alert alert-' + p.msg.type + '" role="alert" data-testid="place-msg">' + icon('refresh') + '<div><p>' + h(p.msg.text) + '</p></div></div>' : '';
        var canConfirm = valid && !blocked();
        return '<section class="card" aria-labelledby="place-title" data-testid="place-panel">' +
            '<h2 id="place-title" tabindex="-1">' + tt('place.title') + '</h2>' +
            '<p class="lead">' + tt('place.lead') + '</p>' +
            '<div class="action-bar" data-testid="place-actions">' + msg +
            '<div aria-live="polite">' + status + '</div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="confirm-place" data-fk="confirm-place" data-testid="confirm-place"' + (canConfirm ? '' : ' disabled') + '>' +
            (ui.busy === 'place' ? tt('place.building') : tt('place.confirm', { cost: costText(info.cost) })) + '</button>' +
            '<button class="btn btn-secondary" data-act="cancel-place" data-fk="cancel-place">' + tt('place.cancel') + '</button></div>' +
            offlineReason() + '</div>' + tip +
            '<div class="nudge" role="group" aria-label="' + tt('place.nudge_label') + '">' +
            '<button class="btn btn-secondary up" data-act="nudge" data-dx="0" data-dy="-1" data-fk="n-up" aria-label="' + tt('place.nudge_up') + '">' + icon('up') + '</button>' +
            '<button class="btn btn-secondary left" data-act="nudge" data-dx="-1" data-dy="0" data-fk="n-left" aria-label="' + tt('place.nudge_left') + '">' + icon('left') + '</button>' +
            '<button class="btn btn-secondary down" data-act="nudge" data-dx="0" data-dy="1" data-fk="n-down" aria-label="' + tt('place.nudge_down') + '">' + icon('down') + '</button>' +
            '<button class="btn btn-secondary right" data-act="nudge" data-dx="1" data-dy="0" data-fk="n-right" aria-label="' + tt('place.nudge_right') + '">' + icon('right') + '</button></div>' +
            '<p class="muted">' + (valid ? tt('place.size_note', { w: info.w, h: info.h, cost: costText(info.cost) }) : tt('place.disabled_why')) + '</p>' +
            '<p class="muted">' + tt('place.keyboard_note') + '</p>' +
            '</section>';
    }

    function panelCheckpoint() {
        var cp = ui.checkpoint || {};
        var b = cp.building, q = cp.quest;
        var spent = Object.keys(cp.spent || {}).map(function (r) {
            return '<li>' + icon('wood', 'icon-sm') + '<span>' + tt('checkpoint.spent', { amount: cp.spent[r], resource: resourceName(r) }) + '</span></li>';
        }).join('');
        return '<section class="card card-accent" aria-labelledby="cp-title" data-testid="checkpoint">' +
            '<div class="alert alert-success">' + icon('star') + '<div><h2 id="cp-title" tabindex="-1">' + tt('checkpoint.title', { title: q ? q.title : '' }) + '</h2></div></div>' +
            '<h3>' + tt('checkpoint.changed') + '</h3><ul class="list-plain">' +
            (b ? '<li>' + icon('check', 'icon-sm') + '<span>' + tt('checkpoint.built', { name: buildingName(b.type) }) + '</span></li>' : '') + spent + '</ul>' +
            '<p>' + icon('shield', 'icon-sm') + ' ' + tt('checkpoint.saved') + '</p>' +
            '<h3>' + tt('checkpoint.next') + '</h3><p>' + tt('checkpoint.next_text') + '</p>' +
            '<div class="alert alert-info">' + icon('palette') + '<div><p><strong>' + tt('checkpoint.theme_new') + '</strong> ' + tt('checkpoint.theme_text') + '</p></div></div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="checkpoint-done" data-fk="cp-done">' + tt('checkpoint.done') + '</button>' +
            '<button class="btn btn-secondary" data-act="open-theme" data-fk="cp-theme">' + icon('palette', 'icon-sm') + tt('checkpoint.theme_cta') + '</button></div>' +
            '<a class="btn btn-text" href="' + h(LINKS.quiz) + '" data-fk="cp-quiz">' + tt('checkpoint.quiz_cta') + '</a></section>';
    }

    function themeThumb(entry) {
        var url = entry.thumbnail, img = '';
        if (url && probe(url) === 'ok') { img = '<img class="art" src="' + h(url) + '" alt="">'; }
        return '<span class="theme-thumb" aria-hidden="true">' + (img || houseArt()) + '</span>';
    }

    function panelTheme() {
        if (!data.themes) {
            return '<section class="card" aria-labelledby="theme-title" data-testid="theme-panel" aria-busy="true"><h2 id="theme-title" tabindex="-1">' + tt('theme.title') + '</h2><p class="muted">' + tt('theme.loading') + '</p></section>';
        }
        var current = st().theme.id;
        var selected = ui.previewTheme || current;
        var cards = data.themes.themes.map(function (e) {
            var isAuth = e.id === current, isSel = e.id === selected;
            var mark = isAuth ? '<span class="theme-mark">' + icon('check', 'icon-sm') + tt('theme.in_use') + '</span>'
                : (isSel ? '<span class="theme-mark">' + icon('palette', 'icon-sm') + tt('theme.viewing') + '</span>' : '<span class="theme-mark small">' + tt('theme.free') + '</span>');
            return '<button class="theme-card" role="radio" aria-checked="' + isSel + '" tabindex="' + (isSel ? '0' : '-1') + '"' +
                ' data-act="preview-theme" data-id="' + h(e.id) + '" data-fk="theme-' + h(e.id) + '" data-testid="theme-' + h(e.id) + '">' +
                themeThumb(e) + '<span>' + h(e.name) + '</span>' + mark + '</button>';
        }).join('');
        var msg = '';
        if (ui.themeMsg) {
            msg = '<div class="alert alert-' + ui.themeMsg.type + '" role="' + (ui.themeMsg.type === 'error' ? 'alert' : 'status') + '" data-testid="theme-msg">' +
                icon(ui.themeMsg.type === 'error' ? 'info' : 'check') + '<div><p>' + h(ui.themeMsg.text) + '</p>' +
                (ui.themeMsg.retry ? '<button class="btn btn-primary" data-act="theme-retry" data-fk="theme-retry"' + (blocked() ? ' disabled' : '') + '>' + icon('refresh') + tt('shell.retry') + '</button>' : '') +
                '</div></div>';
        }
        var changed = !!ui.previewTheme;
        return '<section class="card" aria-labelledby="theme-title" data-testid="theme-panel">' +
            '<h2 id="theme-title" tabindex="-1">' + tt('theme.title') + '</h2>' +
            '<p>' + tt('theme.text') + '</p>' +
            '<div class="action-bar" data-testid="theme-actions">' + msg +
            '<div class="theme-cards" role="radiogroup" aria-label="' + tt('theme.group_label') + '">' + cards + '</div>' +
            '<div class="btn-row"><button class="btn btn-primary" data-act="confirm-theme" data-fk="confirm-theme" data-testid="confirm-theme"' + (changed && !blocked() ? '' : ' disabled') + '>' +
            (ui.busy === 'theme' ? tt('theme.saving') : tt('theme.use')) + '</button>' +
            '<button class="btn btn-secondary" data-act="cancel-theme" data-fk="cancel-theme">' + (changed ? tt('theme.cancel') : tt('theme.back')) + '</button></div>' +
            offlineReason() + '</div>' +
            (!changed && !ui.themeMsg ? '<p class="muted">' + tt('theme.hint') + '</p>' : '') +
            '</section>';
    }

    function panelHelp() {
        return '<section class="card" aria-labelledby="help-title" data-testid="help">' +
            '<div class="panel-head">' + backBtn('world') + '</div>' +
            '<h2 id="help-title" tabindex="-1">' + tt('help.title') + '</h2>' +
            '<h3>' + tt('help.answer_title') + '</h3><p>' + tt('help.answer_text') + '</p>' +
            '<h3>' + tt('help.build_title') + '</h3><p>' + tt('help.build_text') + '</p>' +
            '<h3>' + tt('help.theme_title') + '</h3><p>' + tt('help.theme_text') + '</p>' +
            '<button class="btn btn-secondary" data-act="replay-tips" data-fk="help-replay">' + tt('help.replay') + '</button></section>';
    }

    function renderPanel() {
        if (ui.load === 'loading') { return ''; }
        if (ui.checking) { return panelChecking(); }   // a lost response is resolved before anything else
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
            default: return '';
        }
    }

    /* ------------------------------------------------------------------ */
    /* Dialogs                                                              */
    /* ------------------------------------------------------------------ */
    function renderDialogs() {
        var root = $('#dialog-root');
        if (!ui.menuOpen) { root.innerHTML = ui.popup === 'wrong' && ui.view === 'challenge' ? renderWrongPopup() : ''; return; }
        root.innerHTML = '<div class="scrim" data-act="close-menu-scrim">' +
            '<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="menu-title" data-testid="menu">' +
            '<div class="panel-head"><h2 id="menu-title">' + tt('menu.title') + '</h2>' +
            '<button class="btn btn-secondary" data-act="close-menu" data-fk="menu-close"><span>' + tt('shell.close') + '</span></button></div>' +
            '<ul class="menu-list">' +
            (ui.load === 'ready' ? '<li><button class="btn btn-secondary" data-act="menu-theme" data-fk="m-theme">' + icon('palette') + tt('menu.theme') + '</button></li>' : '') +
            '<li><button class="btn btn-secondary" data-act="toggle-motion" data-fk="m-motion" aria-pressed="' + !!prefs.reduceMotion + '">' + icon('motion') + tt('menu.motion') +
            '<span class="switch-state">' + (prefs.reduceMotion ? tt('menu.motion_on') : tt('menu.motion_off')) + '</span></button></li>' +
            (ui.load === 'ready' ? '<li><button class="btn btn-secondary" data-act="menu-help" data-fk="m-help">' + icon('help') + tt('menu.help') + '</button></li>' : '') +
            '<li><a class="btn btn-secondary" href="' + h(LINKS.quiz) + '" data-fk="m-quiz" data-testid="menu-quiz">' + icon('quiz') + tt('menu.quiz') + '</a></li>' +
            '<li><a class="btn btn-secondary" href="' + h(LINKS.stats) + '" data-fk="m-stats" data-testid="menu-stats">' + icon('stats') + tt('menu.stats') + '</a></li>' +
            '<li><a class="btn btn-secondary" href="' + h(LINKS.home) + '" data-fk="m-switch">' + icon('user') + tt('menu.switch') + '</a></li>' +
            '</ul></div></div>';
    }

    /* ------------------------------------------------------------------ */
    /* Main render                                                          */
    /* ------------------------------------------------------------------ */
    function render() {
        var app = $('#app');
        var active = document.activeElement;
        var fk = active && active.dataset ? active.dataset.fk : null;
        var root = document.documentElement;
        root.classList.toggle('reduce-motion', !!prefs.reduceMotion);
        // Large text (200% browser text size): let rows wrap (kidquest.css html.text-200 rules).
        root.classList.toggle('text-200', parseFloat(window.getComputedStyle(root).fontSize) >= 24);
        app.dataset.view = ui.view;
        app.dataset.viewKind = VIEW_KIND[ui.view] || 'world';
        app.dataset.load = ui.load;
        var mainContent;
        if (ui.load === 'error') {
            app.innerHTML = renderHeader() + '<section class="kq-workspace"><div class="banner-slot">' + renderBanners() + '</div>' +
                '<main id="main" class="panel-slot" tabindex="-1">' + renderLoadError() + '</main></section>';
        } else {
            var wide = window.innerWidth >= 960;
            var showObj = ui.load === 'loading' || ui.view === 'world' || (wide && ['place', 'theme', 'reward', 'checkpoint'].indexOf(ui.view) < 0);
            mainContent = renderPanel();
            app.innerHTML = renderHeader() +
                '<section class="kq-workspace">' + renderNav() +
                '<div class="banner-slot">' + renderBanners() + '</div>' +
                '<div class="obj-slot">' + (showObj ? renderObjective(ui.view !== 'world') : '') + '</div>' +
                '<div class="world-slot">' + renderWorld() + '</div>' +
                '<main id="main" class="panel-slot" tabindex="-1">' + mainContent + '</main>' +
                '</section>';
        }
        renderDialogs();
        var target = null;
        if (ui.focus) { target = $(ui.focus); }
        if (!target && fk) { target = $('[data-fk="' + fk + '"]'); }
        ui.focus = null;
        if (target && !target.disabled) { target.focus({ preventScroll: VIEW_KIND[ui.view] === 'task' }); }
        else if (target && target.disabled) { var m = $('#main'); if (m) { m.focus(); } }
    }

    /* ------------------------------------------------------------------ */
    /* Navigation and flows                                                 */
    /* ------------------------------------------------------------------ */
    function go(view, focusSel) {
        if (ui.view === 'place' && view !== 'place') {
            ui.place = null;
            ui.keys.place = null;
            announce(t('place.announce_cancel'));
        }
        if (ui.view === 'theme' && view !== 'theme' && ui.previewTheme) {
            ui.previewTheme = null;
            announce(t('theme.announce_cancel'));
        }
        if (view !== 'theme') { ui.themeMsg = null; }
        if (view !== 'challenge') { ui.popup = null; }
        if (view !== 'world') { ui.showResume = false; }
        ui.justBuilt = view === 'checkpoint' ? ui.justBuilt : false;
        var changed = ui.view !== view;
        ui.view = view;
        ui.focus = focusSel || FOCUS_OF[view];
        render();
        if (changed && VIEW_KIND[view] === 'task') { window.scrollTo(0, 0); }
        if (view === 'challenge') { revealChallenge(); }
    }

    // Phone: bring the whole question card into view (question -> hint -> answer -> keypad -> Kirim).
    function revealChallenge() {
        var card = $('[data-testid="challenge"]');
        var submit = $('[data-testid="submit"]');
        if (!card || !submit) { return; }
        var top = card.getBoundingClientRect().top;
        var bottom = submit.getBoundingClientRect().bottom;
        var vh = window.innerHeight;
        if (top >= 0 && bottom <= vh) { return; }
        window.scrollBy(0, top - 6);
        var input = $('#answer');
        bottom = submit.getBoundingClientRect().bottom;
        if (bottom > vh && input) { window.scrollBy(0, Math.min(bottom - vh + 8, input.getBoundingClientRect().top - 6)); }
    }

    // Where the server says the child is (next_action), used after refusals and on resume.
    function followNextAction() {
        var na = nextAction();
        ui.challenge = null; ui.hint = null; ui.popup = null; ui.answer = '';
        if (na.type === 'place_building' && ['catalog', 'place', 'reward'].indexOf(ui.view) >= 0) { openCatalog(); return; }
        go('world');
    }

    function enter() {
        ui.load = 'loading';
        ui.loadError = null;
        render();
        refresh().then(function (ok) {
            if (!ok) {
                if (ui.load !== 'error') { ui.load = 'error'; ui.loadError = { kind: 'error' }; }
                ui.focus = '#load-err';
                render();
                return;
            }
            ui.load = 'ready';
            var b = st().buildings[0];
            ui.cursor = b ? { x: b.x, y: b.y } : { x: 0, y: 0 };
            var fo = st().world.terrain.fixed_objects.filter(function (o) { return o.kind === 'quest_board'; })[0];
            if (!b && fo) { ui.cursor = { x: fo.x, y: fo.y }; }
            ui.showResume = hasProgress();
            ui.view = 'world';
            ui.focus = ui.showResume ? '#resume-title' : '#obj-title';
            render();
        });
    }

    function openQuest(id) {
        ui.questId = id;
        mutate({
            kind: 'start', method: 'POST', path: '/quests/' + encodeURIComponent(id) + '/start',
            done: function (body) {
                data.quests[id] = body.quest;
                refresh().then(function () { ui.questId = id; go('quest'); });
            },
            fail: questRefused
        });
    }

    function openChallenge(id) {
        ui.questId = id;
        mutate({
            kind: 'challenge', method: 'POST', path: '/quests/' + encodeURIComponent(id) + '/challenge',
            done: function (body) {
                data.quests[id] = body.quest;
                if (data.state) { data.state.daily_attempts = body.daily_attempts; }
                if (!body.challenge) { refresh().then(function () { followNextAction(); }); return; }
                if (!ui.challenge || ui.challenge.id !== body.challenge.id) { ui.answer = ''; }
                ui.challenge = body.challenge;
                ui.hint = body.challenge.hint || null;
                ui.popup = null;
                refresh().then(function () { go('challenge'); });
            },
            fail: questRefused
        });
    }

    // 404 NOT_FOUND / 409 QUEST_LOCKED / CHALLENGE_EXPIRED: follow the authoritative state.
    function questRefused(res, code) {
        if (code === 'NOT_FOUND' || code === 'QUEST_LOCKED' || code === 'CHALLENGE_EXPIRED') {
            refresh().then(function () {
                ui.notice = { type: 'info', text: code === 'CHALLENGE_EXPIRED' ? t('challenge.expired') : errorOf(res).message };
                followNextAction();
            });
            return true;
        }
        return false;
    }

    function submitAnswer() {
        var c = ui.challenge;
        if (!ui.answer || !c) { return; }
        mutate({
            kind: 'answer', method: 'POST', path: '/challenges/' + encodeURIComponent(c.id) + '/answers',
            body: { answer: ui.answer, hint_count: ui.hint ? ui.hint.level : 0 },
            done: function (body) {
                if (data.state) { data.state.daily_attempts = body.daily_attempts; }
                ui.answer = '';
                if (body.correct) {
                    ui.reward = body;
                    ui.challenge = null;
                    ui.hint = null;
                    announce((body.reward_message || t('reward.title')));
                    refresh().then(function () { go('reward'); });
                    return;
                }
                ui.challenge.attempt_count = body.challenge.attempt_count;
                ui.hint = body.hint;
                ui.popup = 'wrong';
                ui.focus = '[data-fk="wrong-ok"]';
                render();
                announce(t('challenge.wrong_title') + ' ' + (body.hint ? body.hint.text : ''));
            },
            fail: function (res, code) {
                if (code === 'DAILY_CAP_REACHED') {
                    if (data.state && errorOf(res).daily_attempts) { data.state.daily_attempts = errorOf(res).daily_attempts; }
                    ui.focus = '#ch-title';
                    render();
                    announce(t('challenge.bubble_cap') + ' ' + t('challenge.cap_text'));
                    return true;
                }
                return questRefused(res, code);
            }
        });
    }

    // Building facts come from the preview endpoint (footprint cells and cost); the zone is the one
    // whose top-left preview does not report `outside_zone`. No building or zone ID is hard-coded.
    function buildingInfo(type) {
        if (data.buildings[type]) { return Promise.resolve(data.buildings[type]); }
        var zones = st().world.terrain.zones;
        return Promise.all(zones.map(function (z) {
            return request('GET', '/buildings/preview?' + query({ building_type: type, x: z.x, y: z.y, rotation: 0 }));
        })).then(function (results) {
            var first = results.filter(function (r) { return r.ok; })[0];
            if (!first) { return null; }
            var xs = first.body.cells.map(function (c) { return c[0]; }), ys = first.body.cells.map(function (c) { return c[1]; });
            var zone = null;
            results.forEach(function (r, i) {
                if (!zone && r.ok && !r.body.problems.some(function (p) { return p.rule === 'outside_zone' || p.rule === 'out_of_bounds'; })) { zone = zones[i]; }
            });
            data.buildings[type] = {
                type: type, cost: first.body.cost, zone: zone,
                w: Math.max.apply(null, xs) - Math.min.apply(null, xs) + 1,
                h: Math.max.apply(null, ys) - Math.min.apply(null, ys) + 1
            };
            return data.buildings[type];
        });
    }

    function openCatalog(focusSel) {
        go('catalog', focusSel);
        var missing = catalogTypes().filter(function (type) { return !data.buildings[type]; });
        if (!missing.length) { return; }
        Promise.all(missing.map(buildingInfo)).then(function () { if (ui.view === 'catalog') { ui.focus = null; render(); } });
    }

    function startPlace(type) {
        buildingInfo(type).then(function (info) {
            if (!info) { ui.notice = { type: 'error', text: t('errors.generic') }; render(); return; }
            ui.place = { type: type, info: info, origin: null, preview: null, seq: 0, msg: null };
            ui.keys.place = null;
            ui.cursor = info.zone ? { x: info.zone.x, y: info.zone.y } : { x: 0, y: 0 };
            go('place', cellSel(ui.cursor));
            announce(t('place.announce_mode'));
        });
    }

    function selectOrigin(x, y) {
        var p = ui.place;
        p.origin = { x: x, y: y };
        p.preview = null;
        p.msg = null;
        ui.keys.place = null;   // a new spot is a new intent
        var seq = p.seq += 1;
        request('GET', '/buildings/preview?' + query({ building_type: p.type, x: x, y: y, rotation: 0 })).then(function (res) {
            if (ui.place !== p || p.seq !== seq) { return; }
            if (res.ok) {
                p.preview = res.body;
                announce(res.body.valid ? t('place.valid') : res.body.problems[0].message);
            } else if (!gateFailure(res)) {
                p.msg = { type: 'error', text: isUncertain(res) ? t('offline.reason') : (errorOf(res).message || t('errors.generic')) };
            }
            render();
        });
        render();
    }

    function confirmPlace() {
        var p = ui.place;
        if (!p || !p.preview || !p.preview.valid) { return; }
        mutate({
            kind: 'place', method: 'POST', path: '/buildings',
            body: { building_type: p.type, x: p.origin.x, y: p.origin.y, rotation: 0, world_version: p.preview.world_version },
            done: function (body) {
                ui.checkpoint = body;
                ui.place = null;
                ui.justBuilt = true;
                ui.cursor = { x: body.building.x, y: body.building.y };
                refresh().then(function () {
                    go('checkpoint', '#cp-title');
                    announce(t('place.announce_built', { name: buildingName(body.building.type), title: body.quest.title }));
                    window.setTimeout(function () { ui.justBuilt = false; }, 1000);
                });
            },
            fail: function (res, code) {
                var err = errorOf(res);
                refresh().then(function () {
                    if (ui.place !== p) { return; }
                    if (nextAction().type !== 'place_building') { followNextAction(); return; }
                    var text = code === 'WORLD_VERSION_CONFLICT' ? t('place.conflict')
                        : (err.message || t('errors.generic')) + ' ' + t('place.refused');
                    selectOrigin(p.origin.x, p.origin.y);   // re-check the same spot against the new state
                    p.msg = { type: code === 'WORLD_VERSION_CONFLICT' ? 'info' : 'error', text: text };
                    ui.focus = '#place-title';
                    render();
                    announce(text);
                });
                return true;
            }
        });
    }

    function openTheme() {
        prefs.themeIntroDone = true;
        savePrefs();
        ui.previewTheme = null;
        go('theme');
        if (!data.themes) {
            loadThemes().then(function () { if (ui.view === 'theme') { ui.focus = null; render(); } });
        }
    }

    function previewTheme(id) {
        ui.themeMsg = null;
        ui.previewTheme = id === st().theme.id ? null : id;
        ui.focus = '[data-fk="theme-' + id + '"]';
        announce(id === st().theme.id ? t('theme.announce_current', { name: themeName(id) }) : t('theme.announce_preview', { name: themeName(id) }));
        render();
    }

    function confirmTheme() {
        var id = ui.previewTheme, e = themeEntry(id);
        if (!id || !e) { return; }
        mutate({
            kind: 'theme', method: 'PATCH', path: '/theme',
            body: { theme_id: id, world_version: st().world.version, manifest_version: e.manifest_version },
            done: function (body) {
                // The response carries the full, unchanged state with the new theme (KQ-007).
                data.state = body;
                if (data.themes) { data.themes.current_theme_id = body.theme_id; data.themes.world_version = body.world_version; }
                ui.previewTheme = null;
                ui.retryTheme = null;
                ui.themeMsg = { type: 'success', text: t('theme.saved', { name: themeName(body.theme_id) }) };
                ui.focus = '#theme-title';
                render();
                announce(ui.themeMsg.text);
            },
            fail: function () {
                // Restore the authoritative look, then offer a retry of the same choice.
                ui.retryTheme = id;
                ui.previewTheme = null;
                Promise.all([refresh(), loadThemes()]).then(function () {
                    ui.themeMsg = { type: 'error', text: t('theme.failed', { name: themeName(st().theme.id) }), retry: true };
                    ui.focus = '[data-fk="theme-retry"]';
                    render();
                    announce(ui.themeMsg.text);
                });
                return true;
            }
        });
    }

    function closeMenu(skipFocus) {
        ui.menuOpen = false;
        renderDialogs();
        if (skipFocus !== true) { var b = $('[data-fk="menu-btn"]'); if (b) { b.focus(); } }
    }

    var actions = {
        go: function (el) { go(el.dataset.view); },
        nav: function (el) {
            if (ui.load !== 'ready') { return; }
            ui.inspect = null;
            if (el.dataset.view === 'catalog') { openCatalog(); } else { go(el.dataset.view); }
        },
        'open-quest': function (el) { ui.showResume = false; openQuest(el.dataset.id); },
        'open-challenge': function (el) { ui.showResume = false; openChallenge(el.dataset.id); },
        'start-place': function (el) { ui.showResume = false; startPlace(el.dataset.id); },
        'reward-build': function () {
            if (!prefs.catalogTipDone) { ui.catalogTip = true; prefs.catalogTipDone = true; savePrefs(); }
            ui.reward = null;
            openCatalog();
        },
        'dismiss-tip': function () { ui.catalogTip = false; ui.focus = '#cat-title'; render(); },
        'dismiss-place-tip': function () { prefs.placeTipDone = true; savePrefs(); ui.focus = '#place-title'; render(); },
        'dismiss-notice': function () { ui.notice = null; ui.focus = '#main'; render(); },
        'show-building': function (el) {
            var b = st().buildings.filter(function (x) { return x.type === el.dataset.id; })[0];
            ui.inspect = b ? { x: b.x, y: b.y } : null;
            if (b) { ui.cursor = { x: b.x, y: b.y }; }
            go('world', b ? '#insp-title' : '#obj-title');
        },
        'dismiss-resume': function () { ui.showResume = false; ui.focus = '#obj-title'; render(); },
        'theme-later': function () { prefs.themeIntroDone = true; savePrefs(); ui.focus = '#obj-title'; render(); },
        'open-theme': function () { openTheme(); },
        'checkpoint-done': function () { go('world'); },
        'retry-load': function () { enter(); },
        'close-inspect': function () {
            var i = ui.inspect; ui.inspect = null;
            ui.focus = i ? cellSel(i) : null;
            render();
        },
        cell: function (el) {
            var x = +el.dataset.x, y = +el.dataset.y;
            ui.cursor = { x: x, y: y };
            if (ui.view === 'place') {
                var fo = fitOrigin(x, y);
                ui.focus = cellSel({ x: x, y: y });
                selectOrigin(fo.x, fo.y);
                return;
            }
            if (ui.view === 'theme') { announce(t('world.theme_preview_only')); return; }
            ui.inspect = { x: x, y: y };
            if (ui.view !== 'world') { go('world', '#insp-title'); return; }
            ui.showResume = false;
            ui.focus = '#insp-title';
            render();
        },
        nudge: function (el) {
            var o = ui.place.origin || fitOrigin(ui.cursor.x, ui.cursor.y);
            var w = st().world;
            var nx = Math.max(0, Math.min(w.width - 1, o.x + (+el.dataset.dx)));
            var ny = Math.max(0, Math.min(w.height - 1, o.y + (+el.dataset.dy)));
            ui.cursor = { x: nx, y: ny };
            ui.focus = '[data-fk="' + el.dataset.fk + '"]';
            selectOrigin(nx, ny);
        },
        'confirm-place': function () { confirmPlace(); },
        'cancel-place': function () { openCatalog(); },
        key: function (el) {
            var k = el.dataset.key;
            if (k === 'del') { ui.answer = ui.answer.slice(0, -1); }
            else if (ui.answer.length < 4) { ui.answer += k; }
            render();
        },
        'wrong-ok': function () {
            ui.popup = null;
            ui.focus = '#answer';
            render();
            revealChallenge();
        },
        submit: function () { submitAnswer(); },
        recheck: function () { recheck(); },
        'preview-theme': function (el) { previewTheme(el.dataset.id); },
        'confirm-theme': function () { confirmTheme(); },
        'theme-retry': function () {
            ui.previewTheme = ui.retryTheme;
            ui.themeMsg = null;
            confirmTheme();
        },
        'cancel-theme': function () { go('world'); },
        'open-menu': function () { ui.menuOpen = true; renderDialogs(); var f = $('.sheet button, .sheet a'); if (f) { f.focus(); } },
        'close-menu': function () { closeMenu(); },
        'close-menu-scrim': function (el, e) { if (e.target === el) { closeMenu(); } },
        'menu-theme': function () { closeMenu(true); openTheme(); },
        'menu-help': function () { closeMenu(true); go('help'); },
        'toggle-motion': function () {
            prefs.reduceMotion = !prefs.reduceMotion;
            savePrefs();
            document.documentElement.classList.toggle('reduce-motion', !!prefs.reduceMotion);
            renderDialogs();
            $('[data-fk="m-motion"]').focus();
            announce(prefs.reduceMotion ? t('menu.announce_motion_on') : t('menu.announce_motion_off'));
        },
        'replay-tips': function () {
            prefs.placeTipDone = false; prefs.catalogTipDone = false; savePrefs();
            announce(t('help.announce_replay'));
        }
    };

    /* ------------------------------------------------------------------ */
    /* Events                                                               */
    /* ------------------------------------------------------------------ */
    document.addEventListener('click', function (e) {
        var el = e.target.closest('[data-act]');
        if (!el || el.disabled) { return; }
        var fn = actions[el.dataset.act];
        if (fn) { e.preventDefault(); fn(el, e); }
    });

    document.addEventListener('input', function (e) {
        if (e.target.id === 'answer') {
            var clean = e.target.value.replace(/[^0-9]/g, '').slice(0, 4);
            if (clean !== e.target.value) { e.target.value = clean; }
            ui.answer = clean;
            var btn = $('[data-fk="submit"]');
            if (btn) { btn.disabled = !(clean.length > 0 && !blocked() && !capped()); }
        }
    });

    function modalSelector() {
        if (ui.menuOpen) { return '.sheet'; }
        if (ui.popup === 'wrong' && ui.view === 'challenge') { return '[data-testid="wrong-popup"]'; }
        if (ui.view === 'reward' && ui.reward) { return '[data-testid="reward"]'; }
        return null;
    }

    document.addEventListener('keydown', function (e) {
        // Modal dialogs: Escape closes, Tab stays inside.
        var modal = modalSelector();
        if (modal) {
            if (e.key === 'Escape') {
                e.preventDefault();
                if (ui.menuOpen) { closeMenu(); } else if (ui.view === 'reward') { go('world'); } else { actions['wrong-ok'](); }
                return;
            }
            if (e.key === 'Tab') {
                var f = Array.prototype.slice.call(document.querySelectorAll(modal + ' button:not(:disabled), ' + modal + ' a'));
                var first = f[0], last = f[f.length - 1];
                if (!f.length) { return; }
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
                else if (!e.target.closest(modal)) { e.preventDefault(); first.focus(); }
            }
            return;
        }
        var el = e.target;
        if (el.id === 'answer' && e.key === 'Enter') {
            e.preventDefault();
            if (ui.answer && !blocked() && !capped()) { submitAnswer(); }
            return;
        }
        if (el.classList && el.classList.contains('cell')) {
            var dx = { ArrowLeft: -1, ArrowRight: 1 }[e.key] || 0;
            var dy = { ArrowUp: -1, ArrowDown: 1 }[e.key] || 0;
            if (dx || dy) {
                e.preventDefault();
                var w = st().world;
                ui.cursor = { x: Math.max(0, Math.min(w.width - 1, ui.cursor.x + dx)), y: Math.max(0, Math.min(w.height - 1, ui.cursor.y + dy)) };
                ui.focus = cellSel(ui.cursor);
                render();
                return;
            }
            if (e.key === 'Escape' && ui.inspect) { e.preventDefault(); actions['close-inspect'](); return; }
        }
        if (e.key === 'Escape' && ui.view === 'place') { e.preventDefault(); openCatalog(); return; }
        if (e.key === 'Escape' && ui.view === 'theme' && !ui.busy) { e.preventDefault(); go('world'); return; }
        if (el.getAttribute && el.getAttribute('role') === 'radio' && data.themes) {
            var step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
            if (step) {
                e.preventDefault();
                var ids = data.themes.themes.map(function (x) { return x.id; });
                var i = ids.indexOf(el.dataset.id);
                previewTheme(ids[(i + step + ids.length) % ids.length]);
            }
        }
    });

    window.addEventListener('offline', function () { ui.offline = true; if (ui.load !== 'loading') { render(); } });
    window.addEventListener('online', function () {
        ui.offline = false;
        if (ui.checking && !ui.busy) { recheck(); return; }   // same key: replays or applies once
        if (ui.load === 'error' && ui.loadError && ui.loadError.kind === 'error') { enter(); return; }
        render();
    });
    var resizeTimer = null;
    window.addEventListener('resize', function () {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(function () { if (ui.load === 'ready') { render(); } }, 120);
    });

    // Test hook (read-only snapshot for the browser e2e suite; never used by the page itself).
    window.__kidquest = {
        snapshot: function () {
            return JSON.parse(JSON.stringify({ view: ui.view, load: ui.load, busy: ui.busy, checking: ui.checking ? ui.checking.kind : null, key: ui.checking ? ui.checking.key : null, keys: ui.keys, previewTheme: ui.previewTheme, state: data.state, missingStrings: missingStrings, devProblems: devProblems }));
        }
    };

    enter();
}());
