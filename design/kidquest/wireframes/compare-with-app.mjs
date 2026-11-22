// KQ-005 consistency check against the EXISTING Kids Math Quiz (pipeline §8.2a).
//
// Captures the real app (/home, /quiz/math for both children, the quiz correct/wrong popups) and the
// KidQuest prototype at the same phone size, then composes labelled side-by-side sheets.
// The app is only visited; the popups are opened with the page's own showPopup() and their
// auto-continue timer is cleared, so no extra answers are submitted.
//
//   DB_PATH=$(mktemp -d)/app.sqlite3 .venv/bin/python -m uvicorn app.main:app --port 8765 &
//   node design/kidquest/wireframes/compare-with-app.mjs http://127.0.0.1:8765 design/kidquest/wireframes/renders
//
// Writes compare-360-*.png into the output directory. No npm dependencies (Node >= 22).
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROTO = pathToFileURL(join(HERE, '..', 'prototypes', 'first-house', 'index.html')).href;
const BASE = process.argv[2] || 'http://127.0.0.1:8765';
const OUT = resolve(process.argv[3] || join(HERE, 'renders'));
const W = 360, H = 780;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const work = mkdtempSync(join(tmpdir(), 'kq-compare-'));

const profile = join(work, 'chrome');
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
let ws; let id = 1; const pending = new Map(); const listeners = [];
function done(code) { try { ws && ws.close(); } catch {} try { chrome.kill('SIGKILL'); } catch {} rmSync(work, { recursive: true, force: true }); process.exit(code); }
process.on('uncaughtException', (e) => { console.error('FAILED:', e.message || e); done(1); });

const portFile = join(profile, 'DevToolsActivePort');
for (let i = 0; i < 150 && !ws; i++) {
    if (existsSync(portFile)) {
        try {
            const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
            const page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === 'page');
            if (page) {
                ws = new WebSocket(page.webSocketDebuggerUrl);
                await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
                ws.onmessage = (m) => { const msg = JSON.parse(m.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } else if (msg.method) { listeners.forEach((l) => l(msg)); } };
            }
        } catch { /* not ready */ }
    }
    if (!ws) { await sleep(100); }
}
if (!ws) { throw new Error('Chrome did not start'); }
const send = (method, params = {}) => new Promise((r, j) => {
    const i = id++;
    const t = setTimeout(() => { pending.delete(i); j(new Error('CDP timeout: ' + method)); }, 20000);
    pending.set(i, (m) => { clearTimeout(t); return m.error ? j(new Error(m.error.message)) : r(m.result); });
    ws.send(JSON.stringify({ id: i, method, params }));
});
async function js(expression) {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) { throw new Error('JS: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); }
    return r.result.value;
}
async function waitFor(expr, desc) {
    const end = Date.now() + 8000;
    while (Date.now() < end) { try { if (await js(`!!(${expr})`)) { return; } } catch { /* navigating */ } await sleep(50); }
    throw new Error('timed out waiting for ' + desc);
}
async function settle() {
    await js("Promise.all([...document.images].map((i) => i.complete ? 1 : new Promise((r) => { i.onload = i.onerror = r; })))");
    await js("(() => { const s = document.createElement('style'); s.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}'; document.head.appendChild(s); return true; })()");
}
async function go(url) {
    const loaded = new Promise((r) => { const l = (m) => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(l), 1); r(); } }; listeners.push(l); });
    await send('Page.navigate', { url }); await loaded; await settle();
}
async function shot(name) {
    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    const file = join(work, name + '.png');
    writeFileSync(file, Buffer.from(data, 'base64'));
    return file;
}
const click = (sel) => waitFor(`document.querySelector(${JSON.stringify(sel)}) && !document.querySelector(${JSON.stringify(sel)}).disabled`, sel).then(() => js(`document.querySelector(${JSON.stringify(sel)}).click(), true`));
const idle = () => waitFor("window.__kq && window.__kq.ui.load === 'ready' && !window.__kq.ui.busy", 'prototype idle');

await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: true });
const S = {};

/* ---- existing app ---- */
await go(BASE + '/home'); S.appHome = await shot('app-home');
for (const child of ['althafandra', 'alleia']) {
    await go(`${BASE}/home/${child}`);
    await go(`${BASE}/quiz/math`);
    await waitFor("document.getElementById('prompt') && !/Memuat/.test(document.getElementById('prompt').textContent)", 'quiz question');
    await settle();
    S['appQuiz_' + child] = await shot('app-quiz-' + child);
}
await js("showPopup({ correct: false, correctAnswer: 4 }); clearTimeout(popupTimer); true"); await settle(); S.appWrong = await shot('app-wrong');
await js("showPopup({ correct: true }); clearTimeout(popupTimer); true"); await settle(); S.appCorrect = await shot('app-correct');
await js("clearTimeout(popupTimer); document.getElementById('popup').style.display = 'none'; true");

/* ---- KidQuest prototype ---- */
await go(PROTO + '?entry=1'); await js('localStorage.clear(), true'); await go(PROTO + '?entry=1');
S.kqProfiles = await shot('kq-profiles');
for (const child of ['althafandra', 'alleia']) {
    await js(`localStorage.setItem('kq-proto-first-house-v1', JSON.stringify({ active: '${child}', worlds: {} })); true`);
    await go(PROTO + '?scenario=fresh'); await idle(); await settle();
    S['kqWorld_' + child] = await shot('kq-world-' + child);
}
await js("localStorage.setItem('kq-proto-first-house-v1', JSON.stringify({ active: 'althafandra', worlds: {} })); true");
await go(PROTO + '?scenario=ret-progress'); await idle();
await click('[data-fk="resume-cta"]'); await idle();
await click('[data-key="5"]'); await click('[data-testid="submit"]'); await idle();
await waitFor("document.querySelector('[data-testid=wrong-popup]')", 'wrong popup'); await settle();
S.kqWrong = await shot('kq-wrong');
await click('[data-fk="wrong-ok"]'); await settle();
S.kqChallenge = await shot('kq-challenge');
await click('[data-key="4"]'); await click('[data-testid="submit"]'); await idle();
await waitFor("document.querySelector('[data-testid=reward]')", 'reward popup'); await settle();
S.kqReward = await shot('kq-reward');

/* ---- side-by-side sheets ---- */
const src = (f) => 'data:image/png;base64,' + readFileSync(f).toString('base64');
async function sheet(name, title, cols) {
    const html = `<!doctype html><meta charset="utf-8"><body style="margin:0;padding:20px;background:#ffffff;font:15px system-ui,sans-serif;color:#1d2420">
<h1 style="margin:0 0 4px;font-size:20px">${title}</h1>
<p style="margin:0 0 14px;color:#47504b">360 × 780 viewport, same device settings. Left: existing Kids Math Quiz (real app, temp DB). Right: KidQuest prototype (graybox world).</p>
<div style="display:flex;gap:18px;align-items:flex-start">${cols.map(([cap, f]) => `<figure style="margin:0;width:${W}px"><figcaption style="font-weight:800;margin:0 0 6px">${cap}</figcaption><img src="${src(f)}" width="${W}" height="${H}" style="display:block;border:1px solid #8a918c"></figure>`).join('')}</div></body>`;
    const file = join(work, name + '.html');
    writeFileSync(file, html);
    const width = 40 + cols.length * W + (cols.length - 1) * 18;
    await send('Emulation.setDeviceMetricsOverride', { width, height: H + 110, deviceScaleFactor: 1, mobile: false });
    await go(pathToFileURL(file).href);
    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(OUT, name + '.png'), Buffer.from(data, 'base64'));
    console.log('wrote', join(OUT, name + '.png'));
}
mkdirSync(OUT, { recursive: true });
await sheet('compare-360-home-vs-entry', 'Account choice: app /home vs KidQuest entry', [['App /home', S.appHome], ['KidQuest entry', S.kqProfiles]]);
await sheet('compare-360-quiz-vs-challenge', 'Quiz screen vs Q001 challenge (after a wrong answer)', [['App /quiz/math (Althafandra)', S.appQuiz_althafandra], ['KidQuest challenge + hint (Althafandra)', S.kqChallenge]]);
await sheet('compare-360-quiz-vs-world', 'Header card, tabs and accent: quiz vs World Home', [['App /quiz/math (Althafandra)', S.appQuiz_althafandra], ['KidQuest World Home (Althafandra)', S.kqWorld_althafandra], ['App /quiz/math (Alleia)', S.appQuiz_alleia], ['KidQuest World Home (Alleia)', S.kqWorld_alleia]]);
await sheet('compare-360-popups', 'Feedback popups: quiz vs KidQuest', [['App wrong popup', S.appWrong], ['KidQuest wrong answer (neutral)', S.kqWrong], ['App correct popup', S.appCorrect], ['KidQuest reward (wood, not Rp)', S.kqReward]]);
done(0);
