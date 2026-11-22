// KQ-005 automated prototype walkthrough (proxy verification, NOT user testing).
//
// Drives the prototype in local headless Chrome through the DevTools Protocol.
// No npm dependencies (Node >= 22 for global WebSocket/fetch).
//
//   node design/kidquest/prototypes/first-house/walkthrough-check.mjs [--shots <dir>]
//
// Determinism rules:
//   - Every step waits on a DOM selector or app state (waitFor), never on a fixed sleep.
//   - A step that cannot complete fails loudly with the step name; the run continues with the next width.
//   - The final "N/M checks passed" line is always printed; exit code is non-zero on any failure.
//   - Only one instance may run at a time (lock file in the OS temp directory).
//   - Chrome picks a free debugging port (--remote-debugging-port=0) and is killed on exit or signal.
//
// Env CHROME=/path/to/chrome overrides the default macOS Chrome location.
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync, openSync, closeSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const INDEX = pathToFileURL(join(HERE, 'index.html')).href;
const PARENT = pathToFileURL(join(HERE, 'parent.html')).href;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const shotsArg = process.argv.indexOf('--shots');
const SHOTS = shotsArg > 0 ? resolve(process.argv[shotsArg + 1]) : null;
const WAIT_MS = 8000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------------- single-instance lock ---------------- */
const LOCK = join(tmpdir(), 'kq-walkthrough-check.lock');
function acquireLock() {
    if (existsSync(LOCK)) {
        const pid = Number(readFileSync(LOCK, 'utf8'));
        let alive = false;
        try { process.kill(pid, 0); alive = true; } catch { alive = false; }
        if (alive) {
            console.error(`Another walkthrough-check is running (pid ${pid}). Run only one instance at a time.`);
            console.log('\n0/1 checks passed. (not run: another instance holds the lock)');
            process.exit(2);
        }
        unlinkSync(LOCK); // stale lock from a crashed run
    }
    const fd = openSync(LOCK, 'wx');
    writeFileSync(fd, String(process.pid));
    closeSync(fd);
}
acquireLock();

/* ---------------- results ---------------- */
const results = [];
let step = 'start';
function check(width, name, ok, detail = '') {
    results.push({ width, name, ok: !!ok, detail });
    console.log(`${ok ? 'PASS' : 'FAIL'} [${width}] ${name}${detail ? ' — ' + detail : ''}`);
}

/* ---------------- Chrome lifecycle ---------------- */
const profileDir = mkdtempSync(join(tmpdir(), 'kq-chrome-'));
let chrome = null;
let cleanedUp = false;
function cleanup() {
    if (cleanedUp) { return; }
    cleanedUp = true;
    try { ws && ws.close(); } catch { /* ignore */ }
    try { chrome && chrome.kill('SIGKILL'); } catch { /* ignore */ }
    try { rmSync(profileDir, { recursive: true, force: true }); } catch { /* ignore */ }
    try { unlinkSync(LOCK); } catch { /* ignore */ }
}
function summaryAndExit(code) {
    const failed = results.filter((r) => !r.ok);
    console.log(`\n${results.length - failed.length}/${results.length} checks passed.`);
    cleanup();
    process.exit(code ?? (failed.length ? 1 : 0));
}
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(sig, () => { results.push({ width: '-', name: `interrupted by ${sig}`, ok: false }); summaryAndExit(130); });
}
process.on('uncaughtException', (e) => { console.error(e); results.push({ width: '-', name: 'uncaught exception', ok: false, detail: String(e.message || e) }); summaryAndExit(1); });

let ws, nextId = 1;
const pending = new Map();
const listeners = [];

async function connect() {
    chrome = spawn(CHROME, [
        '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profileDir}`,
        '--no-first-run', '--no-default-browser-check', '--allow-file-access-from-files', 'about:blank'
    ], { stdio: 'ignore' });
    const portFile = join(profileDir, 'DevToolsActivePort');
    const deadline = Date.now() + 15000;
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
            } catch { /* endpoint not ready yet */ }
        }
        await sleep(100);
    }
    throw new Error('Chrome DevTools endpoint did not start within 15 s');
}

function send(method, params = {}) {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((r, j) => {
        const t = setTimeout(() => { pending.delete(id); j(new Error(`CDP timeout: ${method}`)); }, 20000);
        pending.set(id, (m) => { clearTimeout(t); r(m); });
    }).then((m) => {
        if (m.error) { throw new Error(method + ': ' + m.error.message); }
        return m.result;
    });
}

async function js(expr) {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) { throw new Error(`[step: ${step}] JS error: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`); }
    return r.result.value;
}

async function waitFor(expr, desc, timeout = WAIT_MS) {
    const deadline = Date.now() + timeout;
    let last;
    while (Date.now() < deadline) {
        try { last = await js(`(() => { try { return !!(${expr}); } catch (e) { return false; } })()`); } catch { last = false; }
        if (last) { return true; }
        await sleep(40);
    }
    throw new Error(`[step: ${step}] timed out after ${timeout} ms waiting for: ${desc}`);
}

async function navigate(url) {
    const loaded = new Promise((r) => {
        const l = (m) => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(l), 1); r(); } };
        listeners.push(l);
    });
    await send('Page.navigate', { url });
    await loaded;
}

// The child app is "ready" when the simulated load finished and no request is in flight.
const READY = "window.__kq && window.__kq.ui.load === 'ready' && !window.__kq.ui.busy";
async function openChild(query) {
    await navigate(INDEX + query);
    await waitFor(`${READY} && document.querySelector('#app').children.length > 0 && (window.__kq.ui.view !== 'world' || document.querySelector('[data-testid=objective],[data-testid=resume]'))`, `child app ready (${query})`);
}
const idle = (desc) => waitFor(READY, desc || 'no request in flight');

async function key(k, code, keyCode) {
    const base = { key: k, code, windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode };
    if (k === 'Enter') { await send('Input.dispatchKeyEvent', { type: 'keyDown', text: '\r', ...base }); }
    else { await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...base }); }
    await send('Input.dispatchKeyEvent', { type: 'keyUp', ...base });
}

async function shot(name) {
    if (!SHOTS) { return; }
    mkdirSync(SHOTS, { recursive: true });
    await js('new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))');
    const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    writeFileSync(join(SHOTS, name + '.png'), Buffer.from(data, 'base64'));
}

const q = (s) => JSON.stringify(s);
async function click(sel) {
    await waitFor(`document.querySelector(${q(sel)}) && !document.querySelector(${q(sel)}).disabled`, `enabled ${sel}`);
    await js(`document.querySelector(${q(sel)}).click(), true`);
}
const exists = (sel) => js(`!!document.querySelector(${q(sel)})`);
const text = (sel) => js(`(document.querySelector(${q(sel)}) || {}).innerText || ''`);
const state = () => js('JSON.parse(JSON.stringify(window.__kq.state()))');
// Mobile emulation widens the layout viewport when content overflows, so compare with the device width.
let DEVICE_W = 0, DEVICE_H = 0;
const noOverflow = () => js(`document.documentElement.scrollWidth <= ${DEVICE_W} && window.innerWidth === ${DEVICE_W}`);
const setSim = (k, v) => js(`(() => { window.__kq.sim[${q(k)}] = ${v}; localStorage.setItem('kq-proto-sim-v1', JSON.stringify(window.__kq.sim)); window.__kq.render(); return true; })()`);
async function setView(v) {
    await js(`window.__kq.ui.view = ${q(v)}; window.__kq.render(); true`);
    await waitFor(`document.getElementById('app').dataset.view === ${q(v)}`, `view ${v}`);
}

// Is every listed element fully inside the viewport AND not covered by anything (fixed bars,
// sticky headers, popups)? Occlusion is tested with elementFromPoint at the centre and the four
// inset corners, so any fixed or sticky element that overlaps the control is caught.
const fullyVisible = (sels) => js(`(() => {
  if (window.innerWidth !== ${DEVICE_W} || window.innerHeight !== ${DEVICE_H}) return ['layout viewport grew to ' + window.innerWidth + 'x' + window.innerHeight + ' (content overflow)'];
  return ${q(sels)}.map((s) => { const e = document.querySelector(s); if (!e) return s + ': missing';
    const r = e.getBoundingClientRect();
    if (!(r.height > 0 && r.top >= -0.5 && r.bottom <= ${DEVICE_H} + 0.5 && r.left >= -0.5 && r.right <= ${DEVICE_W} + 0.5)) return s + ': ' + Math.round(r.top) + '–' + Math.round(r.bottom) + ' outside 0–${DEVICE_H}';
    const pts = [[0.5, 0.5], [0.08, 0.15], [0.92, 0.15], [0.08, 0.85], [0.92, 0.85]];
    for (const [fx, fy] of pts) { const x = r.left + r.width * fx, y = r.top + r.height * fy; const hit = document.elementFromPoint(x, y);
      if (!hit || !(e === hit || e.contains(hit))) return s + ': covered at (' + Math.round(x) + ',' + Math.round(y) + ') by ' + (hit ? (hit.className || hit.tagName) : 'nothing'); }
    return ''; }).filter(Boolean);
})()`);

const smallTargets = () => js(`(() => {
  const out = [];
  document.querySelectorAll('#app button, #app a, #app input, #app select, #dialog-root button, #dialog-root a, #adult-app button, #adult-app a, #adult-app input, #adult-app select').forEach((e) => {
    if (e.classList.contains('cell') || e.type === 'radio') return;
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (getComputedStyle(e).visibility === 'hidden') return;
    if (r.width < 44 || r.height < 44) out.push((e.innerText || e.getAttribute('aria-label') || e.id || e.tagName).trim().slice(0, 30) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  return out;
})()`);

const contrastAudit = () => js(`(() => {
  function rgb(s) { const m = s.match(/[\\d.]+/g); return m ? m.map(Number) : null; }
  function lum(c) { const a = c.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]; }
  function bg(el) { while (el && el.nodeType === 1) { const cs = getComputedStyle(el); const c = rgb(cs.backgroundColor); if (cs.backgroundImage !== 'none' && !(c && c[3] !== 0 && c.length === 3)) return null; if (c && (c.length === 3 || c[3] === 1)) return c; el = el.parentElement; } return [255, 255, 255]; }
  const fails = []; let min = 99; let n = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (el.closest('.reviewer, .visually-hidden, .skip-link')) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0) continue;
    const cs = getComputedStyle(el); const fg = rgb(cs.color); const b = bg(el); if (!b) continue;
    const L1 = lum(fg), L2 = lum(b); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5; n++;
    min = Math.min(min, ratio);
    if (ratio < need) fails.push(t.textContent.trim().slice(0, 24) + ' ' + ratio.toFixed(2));
  }
  return { n, min: Number(min.toFixed(2)), fails: [...new Set(fails)].slice(0, 8) };
})()`);

// Starter house at (2,1) in pulau_tunas_v1: cells (2,1) (3,1) (2,2) (3,2).
// Focus ring (outline colour) against the nearest opaque background behind the control: WCAG 2.4.13/1.4.11 >= 3:1.
const focusRingAudit = (sels) => js(`(() => {
  function rgb(s) { const m = s.match(/[\\d.]+/g); return m ? m.map(Number) : null; }
  function lum(c) { const a = c.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]; }
  function bg(el) { el = el.parentElement; while (el && el.nodeType === 1) { const c = rgb(getComputedStyle(el).backgroundColor); if (c && (c.length === 3 || c[3] === 1)) return c; el = el.parentElement; } return rgb(getComputedStyle(document.body).backgroundColor); }
  const out = [];
  for (const s of ${q(sels)}) { const e = document.querySelector(s); if (!e) { out.push(s + ': missing'); continue; }
    e.focus(); const cs = getComputedStyle(e); const ring = rgb(cs.outlineColor); const b = bg(e);
    const r = (Math.max(lum(ring), lum(b)) + 0.05) / (Math.min(lum(ring), lum(b)) + 0.05);
    out.push({ s, ratio: Number(r.toFixed(2)), width: parseFloat(cs.outlineWidth), style: cs.outlineStyle }); }
  return out;
})()`);

const houseRects = "JSON.stringify((() => { const g = document.querySelector('.world-grid').getBoundingClientRect(); return ['2-1','3-1','2-2','3-2'].map(k => { const r = document.querySelector('[data-fk=cell-' + k + ']').getBoundingClientRect(); return [r.x - g.x, r.y - g.y, r.width, r.height].map(Math.round); }); })())";
const roof = "(() => { const r = getComputedStyle(document.querySelector('.obj-house .house-roof')); return r.clipPath + '|' + r.borderRadius + '|' + r.height; })()";

async function answer(digits) {
    for (const d of digits) { await click(`[data-key="${d}"]`); }
    await click('[data-testid="submit"]');
    await idle('answer response');
}
// The wrong-answer popup must be acknowledged before the child continues.
async function closeWrongPopup() {
    await waitFor("document.querySelector('[data-testid=wrong-popup]') && document.activeElement && document.activeElement.dataset.fk === 'wrong-ok'", 'wrong-answer popup with focus on Coba Lagi');
    await click('[data-fk="wrong-ok"]');
    await waitFor("!document.querySelector('[data-testid=wrong-popup]') && document.activeElement && document.activeElement.id === 'answer'", 'popup closed, focus back on the answer box');
}

async function runChild(width, height, label) {
    const W = label;
    let st;
    DEVICE_W = width; DEVICE_H = height;
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 });
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });

    step = 'entry';
    await navigate(INDEX + '?entry=1');
    await js('localStorage.clear(), true');
    await navigate(INDEX + '?entry=1');
    await waitFor("document.querySelector('[data-act=pick-profile]')", 'profile buttons');
    check(W, 'Entry offers KidQuest and Quiz separately', true);
    await shot(`${label}-00-profiles`);
    await click('[data-id="althafandra"]');
    await waitFor("document.querySelector('[data-fk=enter-kq]')", 'Quiz/KidQuest choice');
    check(W, 'Profile choice shows KidQuest + Kuis', (await exists('[data-fk="enter-kq"]')) && (await exists('[data-fk="enter-quiz"]')));
    const entryContrast = await contrastAudit();
    check(W, 'Entry text contrast meets WCAG AA', entryContrast.fails.length === 0, `min ${entryContrast.min}:1 ${entryContrast.fails.join('; ')}`);
    await shot(`${label}-01-entry`);
    await click('[data-fk="enter-kq"]');
    await waitFor("document.querySelector('[aria-busy=true]')", 'loading skeleton');
    check(W, 'Loading skeleton shown while world loads', true);

    step = 'world home';
    await waitFor(`${READY} && document.querySelector('[data-testid=objective]')`, 'world home objective');
    const navLabels = await js("[...document.querySelectorAll('.nav-item')].map(n => n.innerText.trim())");
    check(W, 'Child nav is exactly Dunia/Misi/Bangun (no Dompet)', JSON.stringify(navLabels) === '["Dunia","Misi","Bangun"]', navLabels.join(','));
    const primaries = await js("[...document.querySelectorAll('#app .btn-primary')].filter(b => b.offsetParent).map(b => b.innerText.trim())");
    check(W, 'World Home has exactly one primary action', primaries.length === 1, primaries.join(' | '));
    check(W, 'World Home recommends Q001', (await text('[data-testid="objective"]')).includes('Rumah Pertama'));
    check(W, 'No horizontal overflow: World Home', await noOverflow());
    const tile = await js("document.querySelector('.cell').getBoundingClientRect().width");
    check(W, 'Tile size follows clamp(38px,10vw,64px)', Math.abs(tile - Math.min(64, Math.max(38, width * 0.1))) < 0.6, `${tile}px`);
    await shot(`${label}-02-world-home`);

    step = 'missions and quest';
    await click('[data-fk="nav-missions"]');
    await waitFor("document.querySelector('[data-testid=q002-card]')", 'missions list');
    check(W, 'Locked Q002 states concrete reason', (await text('[data-testid="q002-card"]')).includes('Selesaikan misi Rumah Pertama dulu'));
    await click('[data-fk="q1-open"]');
    await waitFor("document.querySelector('[data-testid=quest-detail]')", 'quest detail');
    check(W, 'Quest detail does not leak the answer (no "4 kayu")', !/4 kayu/.test(await text('[data-testid="quest-detail"]')));
    await shot(`${label}-03-quest-detail`);

    step = 'challenge';
    await click('[data-fk="quest-cta"]');
    await waitFor(`${READY} && document.querySelector('[data-testid=challenge]')`, 'challenge');
    check(W, 'Challenge shows Q001 prompt', (await text('[data-testid="challenge"]')).includes('Kita butuh 10 kayu. Sudah ada 6. Berapa lagi?'));
    check(W, 'Submit disabled until an answer is entered', await js("document.querySelector('[data-testid=submit]').disabled"));
    check(W, 'No horizontal overflow: challenge', await noOverflow());
    await answer('5');
    await waitFor("document.querySelector('[data-testid=wrong-popup]')", 'wrong-answer popup');
    st = await state();
    check(W, 'Wrong answer: neutral hint, 1 attempt, no reward', st.attempts === 1 && st.wood === 0 && st.quest === 'IN_PROGRESS' && (await text('[data-testid="wrong-popup"]')).includes('Hitung terus sampai 10'));
    const wrongLook = await js("(() => { const t = getComputedStyle(document.querySelector('#wp-title')).color; const i = document.querySelector('[data-testid=wrong-icon]').getAttribute('src'); return { t, i }; })()");
    check(W, 'Wrong-answer popup uses the owl, not the red ✕, and no red title', /owl-tutor/.test(wrongLook.i) && wrongLook.t !== 'rgb(255, 85, 93)', JSON.stringify(wrongLook));
    await shot(`${label}-04a-wrong-popup`);
    await closeWrongPopup();
    const hidden = await fullyVisible(['#ch-title', '[data-testid="hint"]', '[data-testid="answer"]', '[data-testid="submit"]']);
    check(W, 'After a wrong answer: question, hint, input, Submit fully visible (not behind HUD/nav)', hidden.length === 0, hidden.join('; '));
    const control = await js(`(() => { const d = document.createElement('div'); d.id = 'kq-probe'; d.style.cssText = 'position:fixed;left:0;top:${DEVICE_H + 40}px;width:10px;height:10px'; document.body.appendChild(d); return true; })()`);
    const probe = await fullyVisible(['#kq-probe']);
    await js("document.getElementById('kq-probe').remove(), true");
    check(W, 'Control: visibility probe flags an off-screen element', control && probe.length === 1, probe.join(''));
    check(W, 'After a wrong answer: focus is on the answer input', await js("document.activeElement && document.activeElement.id === 'answer'"));
    await shot(`${label}-04-challenge-hint`);
    await answer('7');
    await closeWrongPopup();
    await waitFor("document.querySelectorAll('.plank.counted').length === 4", 'worked decomposition');
    check(W, 'Second mistake shows worked visual decomposition', true);
    const hidden2 = await fullyVisible(['#ch-title', '[data-testid="hint"]', '[data-testid="answer"]', '[data-testid="submit"]']);
    check(W, 'After a second mistake: question, hint, input, Submit fully visible', hidden2.length === 0, hidden2.join('; '));
    await answer('4');
    await waitFor("document.querySelector('[data-testid=reward]')", 'reward');
    st = await state();
    check(W, 'Correct answer: reward 4 wood + starter_house, READY_TO_BUILD', st.wood === 4 && st.blueprints.includes('starter_house') && st.quest === 'READY_TO_BUILD');
    await shot(`${label}-05-reward`);

    step = 'catalog and placement';
    await click('[data-fk="rw-build"]');
    await waitFor("document.querySelector('[data-testid=house-card]')", 'catalog');
    const card = await text('[data-testid="house-card"]');
    check(W, 'Catalog: house card ready with cost and footprint', /4 kayu/.test(card) && /2 × 2/.test(card));
    await shot(`${label}-06-catalog`);
    await click('[data-fk="cat-cta"]');
    await waitFor("document.querySelector('[data-testid=place-panel]')", 'placement mode');
    check(W, 'Placement: confirm disabled before choosing', await js("document.querySelector('[data-testid=confirm-place]').disabled"));
    // pulau_tunas_v1: tree at (0,0); tutorial_zone x1-4, y1-2; valid origins (1,1) (2,1) (3,1).
    await click('[data-fk="cell-0-0"]');
    await waitFor("document.querySelector('.preview.invalid') && document.querySelector('[data-testid=place-status]').innerText.includes('ada pohon')", 'invalid preview on the tree');
    check(W, 'Placement invalid on tree (0,0): icon+text, confirm disabled', await js("document.querySelector('[data-testid=confirm-place]').disabled && getComputedStyle(document.querySelector('.preview.invalid')).borderStyle === 'dashed' && !!document.querySelector('.place-status.invalid svg')"));
    await shot(`${label}-07-place-invalid`);
    await click('[data-fk="cell-0-6"]');
    await waitFor("document.querySelector('[data-testid=place-status]').innerText.includes('ada batu')", 'rock reason');
    check(W, 'Placement invalid over the rock (0,7)', true);
    await click('[data-fk="cell-6-1"]');
    await waitFor("document.querySelector('[data-testid=place-status]').innerText.includes('zona bergaris')", 'outside-zone reason');
    check(W, 'Placement invalid outside tutorial zone', true);
    await click('[data-fk="cell-4-2"]');
    await waitFor("document.querySelector('.preview.valid')", 'fit preview from a lower-right striped cell');
    const fit = await js('window.__kq.ui.place.origin');
    check(W, 'Tap on any striped cell fits the house in the zone ((4,2) -> origin (3,1))', fit.x === 3 && fit.y === 1, JSON.stringify(fit));
    await click('[data-fk="cell-2-1"]');
    await waitFor("document.querySelector('.preview.valid') && window.__kq.ui.place.origin.x === 2 && window.__kq.ui.place.origin.y === 1", 'valid preview at (2,1)');
    check(W, 'Placement valid in zone: confirm enabled', (await text('[data-testid="place-status"]')).includes('Bisa dibangun') && !(await js("document.querySelector('[data-testid=confirm-place]').disabled")));
    check(W, 'No horizontal overflow: placement', await noOverflow());
    const placeHidden = await fullyVisible(['[data-testid="place-status"]', '[data-testid="confirm-place"]', '[data-fk="cancel-place"]']);
    check(W, 'Placement status, confirm and cancel fully visible', placeHidden.length === 0, placeHidden.join('; '));
    await shot(`${label}-08-place-valid`);
    await click('[data-fk="cancel-place"]');
    await waitFor("window.__kq.ui.view === 'catalog'", 'catalog after cancel');
    st = await state();
    check(W, 'Cancel placement commits nothing', st.wood === 4 && st.buildings.length === 0 && st.quest === 'READY_TO_BUILD');

    step = 'keyboard placement';
    await click('[data-fk="cat-cta"]');
    await waitFor("document.activeElement && document.activeElement.dataset.fk === 'cell-1-1'", 'focus starts on the first zone cell (1,1)');
    await key('ArrowRight', 'ArrowRight', 39);
    await waitFor("document.activeElement.dataset.fk === 'cell-2-1'", 'focus moved right');
    await key('ArrowDown', 'ArrowDown', 40);
    await waitFor("document.activeElement.dataset.fk === 'cell-2-2'", 'focus moved down');
    await key('Enter', 'Enter', 13);
    await waitFor('window.__kq.ui.place && window.__kq.ui.place.origin', 'origin selected by Enter');
    const origin = await js('window.__kq.ui.place.origin');
    check(W, 'Keyboard: arrows + Enter on (2,2) select origin (2,1)', origin.x === 2 && origin.y === 1, JSON.stringify(origin));
    check(W, 'Focus is visible on the focused cell', await js("(() => { const e = document.activeElement; const cs = getComputedStyle(e); return e.classList.contains('cell') && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2; })()"));
    await key('Escape', 'Escape', 27);
    await waitFor("window.__kq.ui.view === 'catalog'", 'Escape cancels placement');
    check(W, 'Keyboard: Escape cancels placement', true);

    step = 'build';
    await click('[data-fk="cat-cta"]');
    await click('[data-fk="cell-2-1"]');
    await click('[data-testid="confirm-place"]');
    await idle('placement response');
    await waitFor("document.querySelector('[data-testid=checkpoint]')", 'checkpoint');
    st = await state();
    check(W, 'Confirm builds house, spends 4 wood, completes Q001', st.buildings.length === 1 && st.wood === 0 && st.quest === 'COMPLETED');
    check(W, 'Success moves focus to the constructed house', await js("document.activeElement.dataset.fk === 'cell-2-1'"));
    check(W, 'House checkpoint shown with theme introduction', (await text('[data-testid="checkpoint"]')).includes('Tema Dunia'));
    check(W, 'Economy off: checkpoint says a parent opens the next building', (await text('[data-testid="checkpoint"]')).includes('Orang tuamu'));
    await waitFor("!document.querySelector('.built-flash') || window.__kq.ui.justBuilt === false", 'build flash settled');
    await shot(`${label}-09-checkpoint`);

    step = 'theme';
    const rectsBefore = await js(houseRects);
    const roofBefore = await js(roof);
    await click('[data-fk="cp-theme"]');
    await click('[data-testid="theme-kingdom"]');
    await waitFor("document.getElementById('app').dataset.theme === 'kingdom'", 'kingdom preview applied');
    const roofPreview = await js(roof);
    const rectsPreview = await js(houseRects);
    st = await state();
    check(W, 'Theme preview is local (authoritative theme unchanged)', st.theme === 'perkampungan');
    check(W, 'Theme preview visibly changes building silhouette', roofBefore !== roofPreview, `${roofBefore} -> ${roofPreview}`);
    check(W, 'Theme preview keeps identical hit areas', rectsBefore === rectsPreview);
    check(W, 'No horizontal overflow: theme picker', await noOverflow());
    const themeHidden = await fullyVisible(['[data-testid="theme-kingdom"]', '[data-testid="confirm-theme"]', '[data-fk="cancel-theme"]']);
    check(W, 'Theme cards, Gunakan Tema and Batal fully visible', themeHidden.length === 0, themeHidden.join('; '));
    await shot(`${label}-10-theme-preview`);
    await click('[data-fk="cancel-theme"]');
    await waitFor("document.getElementById('app').dataset.theme === 'perkampungan'", 'theme restored');
    st = await state();
    check(W, 'Cancel theme restores authoritative theme', st.theme === 'perkampungan');
    const before = JSON.stringify([st.buildings, st.wood, st.blueprints, st.quest, st.attempts]);
    const wv = st.worldVersion;
    await setView('world');
    await click('[data-fk="menu-btn"]');
    await waitFor("document.activeElement && document.activeElement.closest('[role=dialog]')", 'menu dialog focus');
    check(W, 'Menu opens as dialog with focus inside', true);
    await click('[data-fk="m-theme"]');
    await click('[data-testid="theme-city"]');
    await click('[data-testid="confirm-theme"]');
    await idle('theme response');
    await waitFor("document.querySelector('[data-testid=theme-msg]')", 'theme saved message');
    st = await state();
    check(W, 'Confirmed theme persists; state unchanged; version +1', st.theme === 'city' && JSON.stringify([st.buildings, st.wood, st.blueprints, st.quest, st.attempts]) === before && st.worldVersion === wv + 1);
    await setSim('themeFail', true);
    await click('[data-testid="theme-kingdom"]');
    await click('[data-testid="confirm-theme"]');
    await idle('theme failure response');
    await waitFor("document.querySelector('[data-fk=theme-retry]')", 'theme retry');
    st = await state();
    check(W, 'Failed theme save restores prior theme and offers retry', st.theme === 'city' && (await js("document.getElementById('app').dataset.theme")) === 'city');
    await shot(`${label}-11-theme-failed`);
    await setSim('themeFail', false);

    step = 'calm resume';
    await openChild('?scenario=ret-ready');
    await waitFor("document.querySelector('[data-testid=resume]')", 'resume summary');
    const rp = await js("[...document.querySelectorAll('#app .btn-primary')].filter(b => b.offsetParent).map(b => b.innerText.trim())");
    const resumeText = await text('[data-testid="resume"]');
    check(W, 'Calm resume: summary + exactly one Resume action', resumeText.includes('Sejak Kunjungan Terakhir') && rp.length === 1 && rp[0] === 'Lanjutkan: Bangun Rumah', rp.join(' | '));
    check(W, 'Calm resume avoids streak/absence language', !/(hari terlewat|streak|beruntun|kamu pergi|rindu)/i.test(resumeText));
    check(W, 'Calm resume does not replay completed catalog tip', !(await exists('[data-fk="tip-ok"]')));
    await shot(`${label}-12-resume`);

    step = 'lost response recheck';
    await openChild('?scenario=ret-progress');
    await click('[data-fk="resume-cta"]');
    await waitFor("document.querySelector('[data-testid=challenge]')", 'challenge after resume');
    await setSim('dropNext', true);
    await answer('4');
    await waitFor("document.querySelector('[data-testid=checking]')", 'checking card');
    check(W, 'Lost response shows "Memeriksa perubahan"', true);
    await shot(`${label}-13-checking`);
    await click('[data-fk="recheck"]');
    await idle('recheck response');
    await waitFor("document.querySelector('[data-testid=reward]')", 'reward after recheck');
    st = await state();
    check(W, 'Recheck replays same key: reward once (4 wood)', st.wood === 4 && st.attempts === 2);

    step = 'daily cap';
    await openChild('?scenario=ret-progress');
    await setSim('dailyCap', true);
    await click('[data-fk="resume-cta"]');
    await answer('4');
    await waitFor("document.querySelector('[data-testid=cap]')", 'cap message');
    st = await state();
    check(W, 'Daily cap: calm message, attempt not counted, inputs disabled', st.attempts === 1 && st.quest === 'IN_PROGRESS' && await js("document.querySelector('[data-key=\"1\"]').disabled && document.querySelector('[data-testid=submit]').disabled"));
    await setSim('dailyCap', false);

    step = 'stale world';
    await openChild('?scenario=ret-ready');
    await setSim('staleNext', true);
    await click('[data-fk="resume-cta"]');
    await click('[data-fk="cell-2-1"]');
    await click('[data-testid="confirm-place"]');
    await idle('stale placement response');
    await waitFor("document.querySelector('[data-testid=place-panel]') && document.querySelector('[data-testid=place-panel]').innerText.includes('diperbarui')", 'stale explanation');
    st = await state();
    check(W, 'Stale world: explains, refreshes, nothing built', st.buildings.length === 0);
    await click('[data-testid="confirm-place"]');
    await idle('second placement response');
    await waitFor("document.querySelector('[data-testid=checkpoint]')", 'checkpoint after stale retry');
    st = await state();
    check(W, 'Stale world: second confirm succeeds once', st.buildings.length === 1);

    step = 'offline';
    await setSim('offline', true);
    await setView('world');
    check(W, 'Offline banner explains safety', (await text('.banner-slot')).includes('offline'));
    await shot(`${label}-14-offline`);
    await setSim('offline', false);

    step = 'reduced motion and text scaling';
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await openChild('?scenario=ret-ready');
    await click('[data-fk="resume-cta"]');
    await js('(() => { window.__kq.state().placeTutorialDone = false; window.__kq.render(); return true; })()');
    await waitFor("document.querySelector('.cell.pulse')", 'pulse cells');
    const anim = await js("getComputedStyle(document.querySelector('.cell.pulse'), '::before').animationName");
    check(W, 'Reduced motion removes tutorial pulse', anim === 'none', anim);
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await setSim('text200', true);
    const overflowAt200 = [];
    for (const v of ['place', 'world', 'missions', 'catalog', 'theme', 'challenge']) {
        await js(`window.__kq.ui.place = ${q(v)} === 'place' ? (window.__kq.ui.place || {origin:null, wv: window.__kq.state().worldVersion}) : null; true`);
        await setView(v);
        if (!(await noOverflow())) { overflowAt200.push(v); }
    }
    check(W, 'Text at 200%: no horizontal overflow (place/world/missions/catalog/theme/challenge)', overflowAt200.length === 0, overflowAt200.join(','));
    await setSim('text200', false);

    step = 'targets and contrast';
    const small = new Set();
    const contrast = [];
    for (const v of ['world', 'missions', 'quest', 'catalog', 'theme', 'help']) {
        await setView(v);
        (await smallTargets()).forEach((s) => small.add(v + ': ' + s));
        contrast.push(await contrastAudit());
    }
    await openChild('?scenario=ret-progress');
    await click('[data-fk="resume-cta"]');
    await waitFor("document.querySelector('[data-testid=challenge]')", 'challenge for audit');
    (await smallTargets()).forEach((s) => small.add('challenge: ' + s));
    contrast.push(await contrastAudit());
    await answer('5');
    await waitFor("document.querySelector('[data-testid=wrong-popup]')", 'wrong popup for audit');
    (await smallTargets()).forEach((s) => small.add('wrong popup: ' + s));
    contrast.push(await contrastAudit());
    await closeWrongPopup();
    await answer('4');
    await waitFor("document.querySelector('[data-testid=reward]')", 'reward popup for audit');
    (await smallTargets()).forEach((s) => small.add('reward: ' + s));
    contrast.push(await contrastAudit());
    await click('[data-fk="rw-build"]');
    await waitFor("document.querySelector('[data-testid=house-card]') && document.querySelector('.today-card')", 'catalog with resource card');
    contrast.push(await contrastAudit());
    // Keyboard modality so programmatic focus shows :focus-visible. (A lone synthetic Shift press
    // stalls frame production in headless Chrome, which hung every later screenshot; Tab does not.)
    await key('Tab', 'Tab', 9);
    const rings = await focusRingAudit(['[data-fk="menu-btn"]', '[data-fk="nav-world"]', '[data-fk="cat-cta"]', '[data-fk="tip-ok"]']);
    const badRings = rings.filter((r) => typeof r === 'string' || r.ratio < 3 || r.width < 2 || r.style === 'none');
    check(W, 'Focus ring >= 3:1 against its background and >= 2px (header link, tab, primary, text button)', badRings.length === 0, rings.map((r) => typeof r === 'string' ? r : r.s + ' ' + r.ratio + ':1').join('; '));
    check(W, 'All non-grid controls are at least 44x44', small.size === 0, [...small].slice(0, 6).join('; '));
    const cfails = contrast.flatMap((c) => c.fails);
    check(W, 'Text contrast meets WCAG AA (auto audit)', cfails.length === 0, `min ${Math.min(...contrast.map((c) => c.min))}:1 over ${contrast.reduce((a, c) => a + c.n, 0)} text nodes ${cfails.slice(0, 4).join('; ')}`);
    check(W, 'Grid cell size recorded (approved C1 exception at 38 px)', true, `${tile}px cell`);

    step = 'adult gate';
    await navigate(PARENT);
    await waitFor("document.querySelector('#pin')", 'adult gate');
    check(W, 'Adult gate: separate shell, no child nav', !(await exists('.nav')) && (await text('.adult-bar')).includes('Area Orang Tua'));
    const gateContrast = await contrastAudit();
    check(W, 'Adult gate text contrast meets WCAG AA', gateContrast.fails.length === 0, `min ${gateContrast.min}:1 ${gateContrast.fails.join('; ')}`);
    await shot(`${label}-15-adult-gate`);
    await js("document.getElementById('pin').value = '1111'; document.querySelector('#gate-form button').click(); true");
    await waitFor("document.querySelector('#pin-err')", 'wrong-PIN error');
    check(W, 'Adult gate: wrong PIN shows error, stays locked, no lockout', (await text('#pin-err')).includes('PIN tidak cocok') && !(await exists('.adult-nav')) && !/(terkunci|tunggu|coba lagi dalam)/i.test(await text('main')));
    await js("document.getElementById('pin').value = '2468'; document.querySelector('#gate-form button').click(); true");
    await waitFor("document.querySelector('.adult-nav')", 'adult shell');
    let adultNav = await js("[...document.querySelectorAll('.adult-nav .btn')].map(b => b.innerText.trim())");
    check(W, 'Adult shell, economy off: Ringkasan/Belajar/Pengaturan only (no Ekonomi/Pencairan)', JSON.stringify(adultNav) === '["Ringkasan","Belajar","Pengaturan"]' && (await text('.adult-bar')).includes('Mode Orang Tua aktif'), adultNav.join(','));
    check(W, 'No horizontal overflow: adult shell', await noOverflow());
    await shot(`${label}-16-adult-shell`);
    await click('[data-id="pengaturan"]');
    await js("document.querySelector('input[value=kidquest]').click(); true");
    await click('[data-act="reset-review"]');
    await waitFor("document.querySelector('[data-act=reset-do]')", 'reset review');
    check(W, 'Scoped reset needs scope-specific confirmation value', await js("document.querySelector('[data-act=reset-do]').disabled") && (await text('main')).includes('HAPUS-DUNIA'));
    const adultSmall = await smallTargets();
    check(W, 'Adult controls at least 44x44', adultSmall.length === 0, adultSmall.join('; '));
    const adultContrast = await contrastAudit();
    check(W, 'Adult shell text contrast meets WCAG AA', adultContrast.fails.length === 0, `min ${adultContrast.min}:1 ${adultContrast.fails.join('; ')}`);
    await click('[data-rev="economy"]');
    await waitFor("document.querySelectorAll('.adult-nav .btn').length === 5", 'economy sections appear');
    adultNav = await js("[...document.querySelectorAll('.adult-nav .btn')].map(b => b.innerText.trim())");
    check(W, 'Adult shell, economy on: all five sections', JSON.stringify(adultNav) === '["Ringkasan","Belajar","Ekonomi","Pencairan","Pengaturan"]', adultNav.join(','));
}

try {
    await connect();
    await send('Page.enable');
    await send('Runtime.enable');
    for (const [w, h, label] of [[360, 780, 'phone-360'], [768, 1024, 'tablet-768'], [1280, 820, 'desktop-1280']]) {
        try {
            await runChild(w, h, label);
        } catch (e) {
            check(label, `step "${step}" could not complete`, false, String(e.message || e));
        }
    }
} catch (e) {
    check('-', 'runner setup', false, String(e.message || e));
}
summaryAndExit();
