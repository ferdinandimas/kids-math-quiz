// KQ-010 browser end-to-end check for the KidQuest first-house slice (real app, real API).
//
// Drives local headless Chrome through the DevTools Protocol. No npm dependencies (Node >= 22 for
// global WebSocket/fetch). Modelled on design/kidquest/prototypes/first-house/walkthrough-check.mjs.
//
//   node tests/browser/kidquest/first_house_e2e.mjs --base http://127.0.0.1:PORT [--shots DIR]
//
// The server must run with a FRESH database, KIDQUEST_ENABLED=true,
// KIDQUEST_PROFILE_ALLOWLIST=alleia,althafandra and KIDQUEST_DAILY_ATTEMPT_LIMIT=3
// (tests/browser/kidquest/test_first_house_browser.py starts one).
//
// Rules: every step waits on DOM/app state (waitFor), never on a fixed sleep, except a short settle
// after a viewport change before a screenshot. Exit codes: 0 all passed, 1 failures, 77 skipped
// (no Chrome). The last line is always "N/M checks passed." (or "SKIP: ...").
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const BASE = (arg('--base') || '').replace(/\/$/, '');
const SHOTS = arg('--shots') ? resolve(arg('--shots')) : null;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const WIDTHS = [[360, 780], [768, 1024], [1280, 800]];
const WAIT_MS = 15000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

if (!BASE) { console.error('usage: first_house_e2e.mjs --base http://127.0.0.1:PORT [--shots DIR]'); process.exit(2); }
if (!existsSync(CHROME)) { console.log(`SKIP: Chrome not found at ${CHROME} (set CHROME=/path/to/chrome).`); process.exit(77); }

/* ---------------- results ---------------- */
const results = [];
let step = 'start';
function check(name, ok, detail = '') {
    results.push({ name, ok: !!ok, detail });
    console.log(`${ok ? 'PASS' : 'FAIL'} [${step}] ${name}${detail ? ' — ' + detail : ''}`);
}

/* ---------------- Chrome lifecycle ---------------- */
const profileDir = mkdtempSync(join(tmpdir(), 'kq010-chrome-'));
let chrome = null, ws = null, nextId = 1;
const pending = new Map();
const listeners = [];
let cleanedUp = false;
function cleanup() {
    if (cleanedUp) { return; }
    cleanedUp = true;
    try { ws && ws.close(); } catch { /* ignore */ }
    try { chrome && chrome.kill('SIGKILL'); } catch { /* ignore */ }
    try { rmSync(profileDir, { recursive: true, force: true }); } catch { /* ignore */ }
}
function finish(code) {
    const failed = results.filter((r) => !r.ok);
    console.log(`\n${results.length - failed.length}/${results.length} checks passed.`);
    cleanup();
    process.exit(code ?? (failed.length ? 1 : 0));
}
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) { process.on(sig, () => { check(`interrupted by ${sig}`, false); finish(130); }); }
process.on('uncaughtException', (e) => { check('uncaught exception', false, String(e && e.message || e)); finish(1); });
process.on('unhandledRejection', (e) => { check('unhandled rejection', false, String(e && e.message || e)); finish(1); });

async function connect() {
    chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profileDir}`,
        '--no-first-run', '--no-default-browser-check', '--allow-file-access-from-files', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
    const portFile = join(profileDir, 'DevToolsActivePort');
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
        if (existsSync(portFile)) {
            const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
            try {
                const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
                const page = list.find((t) => t.type === 'page');
                if (page) {
                    ws = new WebSocket(page.webSocketDebuggerUrl);
                    await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
                    ws.onmessage = (m) => {
                        const msg = JSON.parse(m.data);
                        if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
                        else if (msg.method) { listeners.forEach((l) => l(msg)); }
                    };
                    return;
                }
            } catch { /* not ready yet */ }
        }
        await sleep(100);
    }
    throw new Error('Chrome DevTools endpoint did not start within 45 s');
}
function send(method, params = {}) {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((r, j) => {
        const t = setTimeout(() => { pending.delete(id); j(new Error(`CDP timeout: ${method}`)); }, 20000);
        pending.set(id, (m) => { clearTimeout(t); r(m); });
    }).then((m) => { if (m.error) { throw new Error(method + ': ' + m.error.message); } return m.result; });
}
async function js(expr) {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) { throw new Error(`[${step}] JS error: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`); }
    return r.result.value;
}
async function waitFor(expr, desc, timeout = WAIT_MS) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
        let ok = false;
        try { ok = await js(`(() => { try { return !!(${expr}); } catch (e) { return false; } })()`); } catch { ok = false; }
        if (ok) { return true; }
        await sleep(40);
    }
    check(`wait: ${desc}`, false, `timed out after ${timeout} ms`);
    return false;
}
const q = (sel) => JSON.stringify(sel);
async function navigate(url, readyExpr) {
    await send('Page.navigate', { url });
    if (readyExpr) { return waitFor(readyExpr, `load ${url}`); }
    return waitFor('document.readyState === "complete"', `load ${url}`);
}
let viewport = WIDTHS[0];
async function setViewport([width, height]) {
    viewport = [width, height];
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 768 });
    if ((await js('location.href')) === 'about:blank') { return; }
    await waitFor(`window.innerWidth === ${width}`, `viewport ${width}`);
    await js('window.dispatchEvent(new Event("resize"))');
    await sleep(250);   // the page re-renders 120 ms after a resize
}
// A real tap at the element's centre when nothing covers it; otherwise a DOM click (and say so).
async function tap(sel, desc) {
    const box = await js(`(() => { const el = document.querySelector(${q(sel)}); if (!el) { return null; }
        el.scrollIntoView({ block: 'center', inline: 'center' });
        const r = el.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2;
        const hit = document.elementFromPoint(x, y);
        return { x, y, hit: !!hit && (hit === el || el.contains(hit)), disabled: !!el.disabled }; })()`);
    if (!box) { check(`tap ${desc || sel}`, false, 'element not found'); return false; }
    if (box.disabled) { check(`tap ${desc || sel}`, false, 'element is disabled'); return false; }
    if (box.hit) {
        for (const type of ['mousePressed', 'mouseReleased']) {
            await send('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 });
        }
    } else {
        await js(`document.querySelector(${q(sel)}).click()`);
    }
    return true;
}
async function key(keyName, code) {
    const keyCode = { ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40, Enter: 13, Escape: 27, Tab: 9 }[keyName] || 0;
    for (const type of ['keyDown', 'keyUp']) {
        await send('Input.dispatchKeyEvent', { type, key: keyName, code: code || keyName, windowsVirtualKeyCode: keyCode });
    }
}
const snap = () => js('window.__kidquest.snapshot()');
const api = (path) => js(`fetch(${q('/api/kidquest' + path)}, {credentials: 'same-origin'}).then(r => r.json())`);
const text = (sel) => js(`(document.querySelector(${q(sel)}) || {}).textContent || ''`);
const exists = (sel) => js(`!!document.querySelector(${q(sel)})`);

let shotIndex = 0;
const shotList = [];
async function shots(name) {
    if (!SHOTS) { return; }
    const back = viewport;
    shotIndex += 1;
    const label = `${String(shotIndex).padStart(2, '0')}-${name}`;
    for (const vp of WIDTHS) {
        await setViewport(vp);
        const file = `${label}-${vp[0]}.jpg`;
        const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 72 });
        writeFileSync(join(SHOTS, file), Buffer.from(r.data, 'base64'));
        shotList.push(file);
    }
    await setViewport(back);
}
async function shotOnce(file) {
    if (!SHOTS) { return; }
    const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 72 });
    writeFileSync(join(SHOTS, file), Buffer.from(r.data, 'base64'));
    shotList.push(file);
}

/* ---------------- shared checks ---------------- */
async function noHorizontalOverflow(desc) {
    const r = await js('({ sw: document.documentElement.scrollWidth, w: window.innerWidth })');
    check(`no horizontal overflow (${desc})`, r.sw <= r.w, `scrollWidth ${r.sw}, viewport ${r.w}`);
}
// Every visible control is at least 44x44 CSS px, except the world's grid cells (PRD 11.13).
async function targetsAtLeast44(desc) {
    const small = await js(`[...document.querySelectorAll('button, a[href], input')].filter((el) => {
        if (el.classList.contains('cell') || el.classList.contains('skip-link')) { return false; }
        const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
        if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none') { return false; }
        return r.width < 43.5 || r.height < 43.5;
    }).map((el) => (el.dataset.fk || el.textContent.trim().slice(0, 20)) + ' ' + Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height))`);
    check(`touch targets >= 44 px (${desc})`, small.length === 0, small.join(', '));
}
let interceptor = null;
listeners.push(async (msg) => {
    if (msg.method !== 'Fetch.requestPaused') { return; }
    const p = msg.params;
    try {
        if (interceptor) { await interceptor(p); } else { await send('Fetch.continueRequest', { requestId: p.requestId }); }
    } catch { /* request already gone */ }
});
async function intercept(patterns, handler) {
    interceptor = handler;
    await send('Fetch.enable', { patterns });
}
async function stopIntercept() { interceptor = null; await send('Fetch.disable'); }

/* ---------------- the walkthrough ---------------- */
async function run() {
    if (SHOTS) { mkdirSync(SHOTS, { recursive: true }); }
    await connect();
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Network.enable');
    await setViewport(WIDTHS[0]);

    step = 'entry';
    await navigate(BASE + '/home');
    check('home without a selected child has no KidQuest entry', !(await exists('[data-testid="kidquest-entry"]')));
    await navigate(BASE + '/home/alleia', 'location.pathname === "/quiz/math" && document.readyState === "complete"');
    check('quiz header shows the KidQuest entry for an allowlisted child', await exists('[data-testid="kidquest-entry"]'));
    await waitFor('document.querySelector("#prompt") && !/Memuat/.test(document.querySelector("#prompt").textContent)', 'quiz question loaded');
    for (const vp of WIDTHS) { await setViewport(vp); await shotOnce(`compare-quiz-math-${vp[0]}.jpg`); }
    await setViewport(WIDTHS[0]);
    await navigate(BASE + '/home');
    check('home shows the KidQuest entry once the child is chosen', /Alleia/.test(await text('[data-testid="kidquest-entry"]')));
    await shotOnce('compare-home-360.jpg');
    await navigate(BASE + '/quiz/math');
    await tap('[data-testid="kidquest-entry"]', 'KidQuest entry');
    const ready = await waitFor('location.pathname === "/kidquest" && document.querySelector("#app").dataset.load === "ready"', 'world loaded');
    if (!ready) { return; }

    step = 'world';
    let s = await snap();
    check('server state drives the page (Q001 available)', s.state.next_action.type === 'start_quest' && s.state.buildings.length === 0);
    check('8x8 grid of cells', (await js('document.querySelectorAll(".cell").length')) === 64);
    check('tile size follows clamp(38px, 10vw, 64px)', await js('Math.abs(document.querySelector(".cell").getBoundingClientRect().width - Math.min(64, Math.max(38, innerWidth * 0.1))) < 0.6'));
    check('objective names the first quest', (await text('#obj-title')) === 'Rumah Pertama');
    check('no resume card for a brand-new child', !(await exists('[data-testid="resume"]')));
    check('quest board badge (icon + text)', /Misi/.test(await text('.badge')));
    check('world visuals come from the theme manifest or the neutral placeholder',
        await js(`[...document.querySelectorAll('.world-grid img.art')].every((img) => img.src.includes('/static/images/kidquest/themes/' + window.__kidquest.snapshot().state.theme.id + '/'))`));
    check('no development asset errors', (await snap()).devProblems.length === 0, JSON.stringify((await snap()).devProblems));
    check('no missing UI strings', (await snap()).missingStrings.length === 0);
    check('grid has one tab stop', (await js('document.querySelectorAll(".cell[tabindex=\\"0\\"]").length')) === 1);
    await noHorizontalOverflow('world 360');
    await targetsAtLeast44('world 360');
    await js('document.querySelector(".cell[tabindex=\\"0\\"]").focus()');
    const before = await js('document.activeElement.dataset.fk');
    await key('ArrowRight');
    const after = await js('document.activeElement.dataset.fk');
    check('arrow keys move focus across the grid', before !== after && /^cell-/.test(after), `${before} -> ${after}`);
    check('grid focus ring is the navy world focus', await js('getComputedStyle(document.activeElement).outlineColor === "rgb(10, 42, 102)"'));
    await shots('world-home');

    step = 'quest';
    await tap('[data-fk="obj-cta"]', 'Mulai Misi');
    await waitFor('document.querySelector("[data-testid=quest-detail]")', 'quest view');
    check('quest view shows the story from the API', /10 kayu/.test(await text('[data-testid="quest-detail"] .lead')));
    check('reward preview has no amount before a correct answer', !/\d/.test(await text('[data-testid="reward-preview"]')));
    check('focus moves to the quest heading', (await js('document.activeElement.id')) === 'quest-title');
    await shots('quest');

    step = 'challenge';
    await tap('[data-fk="quest-cta"]', 'Mulai Tantangan');
    await waitFor('document.querySelector("[data-testid=challenge]")', 'challenge view');
    check('challenge prompt from the API', /Berapa lagi/.test(await text('#ch-title')));
    check('no reward amount on the challenge screen', !/\b4 kayu\b/.test(await text('#main')));
    check('step text from content', (await text('.question-progress')) === 'Langkah 1 dari 2');
    check('keypad last row is Hapus · 0 · Kirim', (await js('[...document.querySelectorAll(".keypad-grid .btn")].slice(-3).map(b => b.textContent.trim()).join("|")')) === 'Hapus|0|Kirim');
    check('Kirim is disabled until a digit is entered', await js('document.querySelector("[data-testid=submit]").disabled'));
    await noHorizontalOverflow('challenge 360');
    await targetsAtLeast44('challenge 360');
    await shots('challenge');

    step = 'wrong answer';
    await tap('[data-key="5"]');
    await tap('[data-testid="submit"]', 'Kirim');
    await waitFor('document.querySelector("[data-testid=wrong-popup]")', 'wrong popup');
    check('wrong popup uses the server hint (level 1)', /Hitung terus sampai 10/.test(await text('#wp-text')));
    check('focus moves into the popup', (await js('document.activeElement.dataset.fk')) === 'wrong-ok');
    check('no red cross icon on the wrong popup', !(await js('!!document.querySelector("[data-testid=wrong-popup] img[src*=popup-wrong-icon]")')));
    await shots('wrong-answer-popup');
    await key('Tab');
    check('Tab stays inside the popup', await js('!!document.activeElement.closest("[data-testid=wrong-popup]")'));
    await tap('[data-fk="wrong-ok"]', 'Coba Lagi');
    await waitFor('!document.querySelector("[data-testid=wrong-popup]")', 'popup closed');
    check('focus returns to the answer box', (await js('document.activeElement.id')) === 'answer');
    check('hint stays under the question', /Hitung terus/.test(await text('[data-testid="hint"]')));
    await shots('hint-under-question');
    await tap('[data-key="6"]');
    await tap('[data-testid="submit"]', 'Kirim');
    await waitFor('document.querySelector("[data-testid=wrong-popup]")', 'second wrong popup');
    await tap('[data-fk="wrong-ok"]');
    await waitFor('document.querySelector("[data-testid=hint][data-level=\\"2\\"]")', 'worked example hint');
    check('worked example numbers the empty slots', (await js('document.querySelectorAll(".plank.counted").length')) === 4);

    step = 'reward';
    await tap('[data-key="4"]');
    await tap('[data-testid="submit"]', 'Kirim');
    await waitFor('document.querySelector("[data-testid=reward]")', 'reward popup');
    check('reward message from the API', /Hebat! Kamu dapat 4 kayu/.test(await text('[data-testid="reward"] .kq-popup-text')));
    check('reward pills: 4 kayu and the blueprint, no coin', /4 kayu/.test(await text('.reward-pills')) && !(await exists('img[src*="coin"]')));
    s = await snap();
    check('server moved Q001 to READY_TO_BUILD with 4 wood', s.state.quests[0].status === 'READY_TO_BUILD' && s.state.inventory.resources.wood === 4);
    await shots('reward');

    step = 'resume after refresh';
    await navigate(BASE + '/kidquest', 'document.querySelector("#app").dataset.load === "ready"');
    await waitFor('document.querySelector("[data-testid=resume]")', 'resume card');
    check('resume card: Sejak Kunjungan Terakhir', /Sejak Kunjungan Terakhir/.test(await text('#resume-title')));
    check('resume offers the safe next step (build)', /Bangun/.test(await text('[data-fk="resume-cta"]')));
    s = await snap();
    check('refresh did not duplicate the reward', s.state.inventory.resources.wood === 4 && s.state.inventory.blueprints.length === 1);
    await shots('calm-resume');

    step = 'placement';
    await tap('[data-fk="resume-cta"]', 'Lanjutkan: Bangun');
    await waitFor('document.querySelector("[data-testid=place-panel]")', 'place view');
    check('build mode banner says nothing changes yet', /Belum ada yang berubah/.test(await text('.alert-mode')));
    await tap('[data-fk="cell-4-4"]', 'water cell');
    await waitFor('document.querySelector("[data-testid=place-status][data-valid=false]")', 'invalid preview');
    check('invalid placement shows the server message', /Tidak bisa membangun di atas air/.test(await text('[data-testid="place-status"]')) || /zona/.test(await text('[data-testid="place-status"]')),
        await text('[data-testid="place-status"]'));
    check('confirm stays disabled on an invalid spot', await js('document.querySelector("[data-testid=confirm-place]").disabled'));
    await shots('placement-invalid');
    await tap('[data-fk="cell-4-2"]', 'zone cell (4,2)');
    await waitFor('document.querySelector("[data-testid=place-status][data-valid=true]")', 'valid preview');
    check('D11: a tap on any striped cell picks the covering footprint (top-left 3,1)',
        (await js('[document.querySelector("[data-testid=preview]").dataset.x, document.querySelector("[data-testid=preview]").dataset.y].join(",")')) === '3,1');
    await tap('[data-fk="n-left"]', 'nudge left');
    await waitFor('document.querySelector("[data-testid=preview][data-x=\\"2\\"]") && document.querySelector("[data-testid=place-status][data-valid=true]")', 'nudged preview');
    check('nudge buttons move the footprint', true);
    check('state unchanged before confirm', (await snap()).state.buildings.length === 0);
    await targetsAtLeast44('placement 360');
    await shots('placement-valid');

    step = 'build';
    await tap('[data-testid="confirm-place"]', 'Bangun di Sini');
    await waitFor('document.querySelector("[data-testid=checkpoint]")', 'checkpoint');
    s = await snap();
    check('house built where chosen; Q001 completed; wood spent', s.state.buildings.length === 1 && s.state.buildings[0].x === 2 && s.state.buildings[0].y === 1
        && s.state.quests[0].status === 'COMPLETED' && s.state.inventory.resources.wood === 0);
    check('building drawn on the map', await exists('[data-testid="building"]'));
    await shots('checkpoint');

    step = 'theme';
    await tap('[data-fk="cp-theme"]', 'Coba Tema Dunia');
    await waitFor('document.querySelector("[data-testid=theme-kingdom]")', 'theme cards');
    const versionBefore = (await snap()).state.world.version;
    const logicBefore = await js('JSON.stringify((s => [s.buildings, s.inventory, s.quests, s.daily_attempts])(window.__kidquest.snapshot().state))');
    await shots('theme-perkampungan-current');
    await tap('[data-testid="theme-kingdom"]', 'Kerajaan Ceria');
    await waitFor('document.querySelector("[data-testid=theme-preview-banner]")', 'preview banner');
    check('preview is local (no request, state unchanged)', (await snap()).state.world.theme_id === 'perkampungan' && /Kerajaan Ceria/.test(await text('[data-testid="theme-caption"]')));
    await shots('theme-preview-kingdom');
    await key('ArrowRight');
    await waitFor('/Kota Ceria/.test(document.querySelector("[data-testid=theme-caption]").textContent)', 'arrow key previews the next theme');
    await shots('theme-preview-city');
    await tap('[data-testid="confirm-theme"]', 'Gunakan Tema');
    await waitFor('document.querySelector("[data-testid=theme-msg].alert-success")', 'theme saved');
    s = await snap();
    check('theme saved; buildings, inventory, quests, attempts unchanged',
        s.state.world.theme_id === 'city' && s.state.world.version === versionBefore + 1
        && (await js('JSON.stringify((s => [s.buildings, s.inventory, s.quests, s.daily_attempts])(window.__kidquest.snapshot().state))')) === logicBefore);
    check('world art now resolves from the city pack', await js(`[...document.querySelectorAll('.world-grid img.art')].every((img) => img.src.includes('/themes/city/'))`));
    await shots('theme-city-saved');

    step = 'theme failure';
    await tap('[data-testid="theme-kingdom"]');
    await intercept([{ urlPattern: '*/api/kidquest/theme', requestStage: 'Request' }], async (p) => {
        const body = JSON.stringify({ ok: false, error: { code: 'INVALID_THEME', message: 'Tema ini tidak tersedia.' } });
        await send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 422, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }], body: Buffer.from(body).toString('base64') });
    });
    await tap('[data-testid="confirm-theme"]');
    await waitFor('document.querySelector("[data-testid=theme-msg].alert-error")', 'theme failure message');
    await stopIntercept();
    check('failure restores the authoritative theme', (await snap()).previewTheme === null && /Kota Ceria/.test(await text('[data-testid="theme-caption"]')));
    check('retry offered and focused', (await js('document.activeElement.dataset.fk')) === 'theme-retry');
    await shots('theme-failed-retry');
    await tap('[data-fk="theme-retry"]', 'Coba Lagi');
    await waitFor('document.querySelector("[data-testid=theme-msg].alert-success")', 'retry saved');
    check('retry applies the same choice', (await snap()).state.world.theme_id === 'kingdom');

    step = 'menu';
    await tap('[data-fk="cancel-theme"]');
    await waitFor('document.querySelector("#app").dataset.view === "world"', 'back to world');
    check('completed world: theme intro done, quiz offered', /Lengkap untuk sekarang/.test(await text('#obj-title')));
    await tap('[data-fk="menu-btn"]', 'Menu');
    await waitFor('document.querySelector("[data-testid=menu]")', 'menu');
    check('menu keeps Quiz and Statistics reachable', (await js('document.querySelector("[data-testid=menu-quiz]").getAttribute("href")')) === '/quiz/math'
        && (await js('document.querySelector("[data-testid=menu-stats]").getAttribute("href")')) === '/stats');
    await targetsAtLeast44('menu 360');
    await key('Escape');
    await waitFor('!document.querySelector("[data-testid=menu]")', 'menu closed');
    check('focus returns to the menu button', (await js('document.activeElement.dataset.fk')) === 'menu-btn');

    step = 'reduced motion';
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    check('reduced motion removes transitions', await js('getComputedStyle(document.querySelector(".btn")).transitionDuration === "0s"'));
    await send('Emulation.setEmulatedMedia', { features: [] });

    /* ---- Second child: lost response, daily cap, offline, load error, 200% text ---- */
    step = 'lost response';
    await navigate(BASE + '/home/althafandra', 'location.pathname === "/quiz/math" && document.readyState === "complete"');
    await navigate(BASE + '/kidquest', 'document.querySelector("#app").dataset.load === "ready"');
    check('blue accent for the second child', await js('document.querySelector("#app").classList.contains("profile-theme-blue")'));
    await tap('[data-fk="obj-cta"]');
    await waitFor('document.querySelector("[data-fk=quest-cta]")', 'quest view');
    await tap('[data-fk="quest-cta"]');
    await waitFor('document.querySelector("[data-testid=challenge]")', 'challenge');
    // The server applies the answer, then the response is lost on the way back.
    await intercept([{ urlPattern: '*/answers', requestStage: 'Response' }], async (p) => {
        await send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'ConnectionReset' });
    });
    await tap('[data-key="7"]');
    await tap('[data-testid="submit"]');
    await waitFor('document.querySelector("[data-testid=checking]")', 'checking panel');
    await stopIntercept();
    const lost = await snap();
    check('lost response shows "Memeriksa perubahan" and keeps the key', lost.checking === 'answer' && /^kq-answer-/.test(lost.key || ''));
    await shots('offline-retry-checking');
    await tap('[data-testid="recheck"]', 'Periksa Lagi');
    await waitFor('document.querySelector("[data-testid=wrong-popup]")', 'replayed wrong answer');
    const usage = await api('/state');
    check('the answer was counted once (same key replayed)', usage.daily_attempts.used === 1, JSON.stringify(usage.daily_attempts));
    await tap('[data-fk="wrong-ok"]');

    step = 'daily cap';
    for (const digit of ['8', '9']) {
        await tap(`[data-key="${digit}"]`);
        await tap('[data-testid="submit"]');
        await waitFor('document.querySelector("[data-testid=wrong-popup]")', `wrong ${digit}`);
        await tap('[data-fk="wrong-ok"]');
        await waitFor('!document.querySelector("[data-testid=wrong-popup]")', 'popup closed');
    }
    // The 3rd attempt used the last one; the page shows the calm cap state without another request.
    await waitFor('document.querySelector("[data-testid=cap]")', 'cap state');
    check('daily cap: calm message, keypad disabled', /besok/.test(await text('[data-testid="cap"]')) && await js('document.querySelector("[data-key=\\"1\\"]").disabled'));
    check('no urgency or streak wording', !/(streak|cepat|segera|jangan sampai)/i.test(await text('#main')));
    await shots('daily-cap');
    await navigate(BASE + '/kidquest', 'document.querySelector("#app").dataset.load === "ready"');
    check('cap persists after refresh as a calm objective', /latihan hari ini sudah cukup/i.test(await text('#resume-title, #obj-title') + await text('[data-testid="resume"]')));

    step = 'offline';
    await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
    await waitFor('document.querySelector("[data-testid=offline-banner]")', 'offline banner');
    check('offline banner says the world is safe', /Duniamu aman/.test(await text('[data-testid="offline-banner"]')));
    await shots('offline');
    await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
    await waitFor('!document.querySelector("[data-testid=offline-banner]")', 'back online');

    step = 'load error';
    await intercept([{ urlPattern: '*/api/kidquest/state', requestStage: 'Request' }], async (p) => {
        await send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'InternetDisconnected' });
    });
    await navigate(BASE + '/kidquest', 'document.querySelector("[data-testid=load-error]")');
    check('load error offers a retry and says nothing is lost', /Tidak ada yang hilang/.test(await text('[data-testid="load-error"]')));
    await shots('load-error');
    await stopIntercept();
    await tap('[data-fk="retry-load"]', 'Coba Lagi');
    await waitFor('document.querySelector("#app").dataset.load === "ready"', 'retry loads the world');

    step = '200% text';
    await setViewport(WIDTHS[0]);
    await js('document.documentElement.style.fontSize = "32px"; window.dispatchEvent(new Event("resize"))');
    await waitFor('document.documentElement.classList.contains("text-200")', 'large-text layout');
    await noHorizontalOverflow('world at 200% text, 360');
    await tap('[data-fk="nav-missions"]');
    await waitFor('document.querySelector("#missions-title")', 'missions');
    await noHorizontalOverflow('missions at 200% text, 360');
    await shotOnce('text-200-missions-360.jpg');
    await js('document.documentElement.style.fontSize = ""; window.dispatchEvent(new Event("resize"))');

    if (SHOTS) { writeComparison(); }
}

// Side-by-side sheet: the quiz page and KidQuest at the same widths (open it in a browser).
function writeComparison() {
    const rows = WIDTHS.map(([w]) => `<h2>${w} px</h2><div class="row"><figure><img src="compare-quiz-math-${w}.jpg"><figcaption>/quiz/math</figcaption></figure>` +
        `<figure><img src="01-world-home-${w}.jpg"><figcaption>/kidquest world</figcaption></figure>` +
        `<figure><img src="03-challenge-${w}.jpg"><figcaption>/kidquest challenge</figcaption></figure></div>`).join('');
    writeFileSync(join(SHOTS, 'comparison.html'), `<!doctype html><meta charset="utf-8"><title>KQ-010 quiz vs KidQuest</title>
<style>body{background:#111;color:#eee;font:14px system-ui;margin:16px}.row{display:flex;gap:12px;align-items:flex-start;overflow-x:auto}
figure{margin:0}img{max-width:420px;border:1px solid #444}</style><h1>KQ-010: existing quiz vs KidQuest (same widths)</h1>${rows}
<h2>All screenshots</h2><ul>${shotList.map((f) => `<li><a href="${f}">${f}</a></li>`).join('')}</ul>`);
}

run().then(() => finish(), (e) => { check('run', false, String(e && e.stack || e)); finish(1); });
