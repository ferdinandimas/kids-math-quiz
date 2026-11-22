// Capture the KQ-006 development gallery with headless Chrome (CDP, no npm dependencies, Node >= 22).
//
//   node design/kidquest/gallery/capture-gallery.mjs [outDir]
//
// Writes one PNG per gallery section, per theme and per width into design/kidquest/gallery/screenshots/.
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PAGE = pathToFileURL(join(HERE, 'index.html')).href;
const OUT = resolve(process.argv[2] || join(HERE, 'screenshots'));
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const work = mkdtempSync(join(tmpdir(), 'kq-gallery-'));
mkdirSync(OUT, { recursive: true });

const profile = join(work, 'chrome');
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--allow-file-access-from-files', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
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
    const t = setTimeout(() => { pending.delete(i); j(new Error('CDP timeout: ' + method)); }, 30000);
    pending.set(i, (m) => { clearTimeout(t); return m.error ? j(new Error(m.error.message)) : r(m.result); });
    ws.send(JSON.stringify({ id: i, method, params }));
});
async function js(expression) {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) { throw new Error('JS: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); }
    return r.result.value;
}
await send('Page.enable');
await send('Runtime.enable');
const errors = [];
listeners.push((m) => { if (m.method === 'Runtime.exceptionThrown') { errors.push(m.params.exceptionDetails.text); } });

async function open(query, width) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 600 });
    const loaded = new Promise((r) => { const l = (m) => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(l), 1); r(); } }; listeners.push(l); });
    await send('Page.navigate', { url: PAGE + query });
    await loaded;
    await js("Promise.all([...document.images].map((i) => i.complete ? 1 : new Promise((r) => { i.onload = i.onerror = r; })))");
    await sleep(150);
}
async function section(sel, name) {
    const box = await js(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; })()`);
    const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
        clip: { x: Math.max(0, box.x - 8), y: Math.max(0, box.y - 8), width: box.w + 16, height: Math.min(box.h + 16, 6000), scale: 1 } });
    writeFileSync(join(OUT, name + '.png'), Buffer.from(data, 'base64'));
    console.log('wrote', name + '.png');
}

const shots = [];
await open('?theme=perkampungan&cell=64', 1280);
const stats = await js(`({ missing: document.querySelectorAll('.missing-img, td.miss').length, imgs: document.images.length,
    broken: [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute('src')) })`);
for (const [sel, name] of [['header', 'header'], ['#validator', 'validator'], ['#complete', 'completeness'], ['#overlays', 'overlays'],
    ['#graybox', 'graybox-study'], ['#strings', 'long-strings-1280']]) { await section(sel, `1280-${name}`); }
for (const theme of ['perkampungan', 'kingdom', 'city']) {
    await open(`?theme=${theme}&cell=64`, 1280);
    for (const [sel, name] of [['#terrain', 'terrain-shore'], ['#roads', 'roads'], ['#features', 'board-icon-thumbs'], ['#proof', 'proof-38-48-64']]) {
        await section(sel, `1280-${theme}-${name}`);
    }
}
await open('?theme=perkampungan&cell=48', 1280); await section('#drift', '1280-theme-switch-48');
await open('?theme=perkampungan&cell=48&onion=1', 1280); await section('#drift', '1280-theme-switch-onion-48');
await open('?theme=kingdom&cell=38', 360);
for (const [sel, name] of [['header', 'header'], ['#terrain', 'kingdom-terrain-shore-38'], ['#overlays', 'overlays'], ['#strings', 'long-strings'], ['#drift', 'theme-switch-38']]) {
    await section(sel, `360-${name}`);
}
const overflow = await js('document.documentElement.scrollWidth > innerWidth');
console.log(JSON.stringify({ ...stats, overflow360: overflow, jsErrors: errors }));
done(stats.missing || stats.broken.length || errors.length ? 1 : 0);
