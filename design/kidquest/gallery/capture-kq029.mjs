// Capture the KQ-029 review-only gallery with headless Chrome (CDP, Node >= 22).
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PAGE = pathToFileURL(join(HERE, 'kq029.html')).href;
const OUT = resolve(process.argv[2] || join(HERE, 'screenshots'));
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
const work = mkdtempSync(join(tmpdir(), 'kq029-gallery-'));
mkdirSync(OUT, { recursive: true });
const profile = join(work, 'chrome');
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
  '--allow-file-access-from-files', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
let ws; let id = 1; const pending = new Map(); const listeners = [];
function done(code) { try { ws && ws.close(); } catch {} try { chrome.kill('SIGKILL'); } catch {} rmSync(work, { recursive: true, force: true }); process.exit(code); }
process.on('uncaughtException', (error) => { console.error('FAILED:', error.message || error); done(1); });
const portFile = join(profile, 'DevToolsActivePort');
for (let attempt = 0; attempt < 150 && !ws; attempt++) {
  if (existsSync(portFile)) {
    try {
      const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
      const page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((item) => item.type === 'page');
      if (page) { ws = new WebSocket(page.webSocketDebuggerUrl); await new Promise((resolveOpen, reject) => { ws.onopen = resolveOpen; ws.onerror = reject; });
        ws.onmessage = (message) => { const value = JSON.parse(message.data); if (value.id && pending.has(value.id)) { pending.get(value.id)(value); pending.delete(value.id); } else if (value.method) listeners.forEach((listener) => listener(value)); }; }
    } catch { /* Chrome is still starting. */ }
  }
  if (!ws) await sleep(100);
}
if (!ws) throw new Error('Chrome did not start');
const send = (method, params = {}) => new Promise((resolveSend, reject) => { const requestId = id++; const timer = setTimeout(() => reject(new Error(`CDP timeout: ${method}`)), 30000);
  pending.set(requestId, (message) => { clearTimeout(timer); message.error ? reject(new Error(message.error.message)) : resolveSend(message.result); }); ws.send(JSON.stringify({ id: requestId, method, params })); });
const js = async (expression) => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value;
await send('Page.enable'); await send('Runtime.enable');
const errors = []; listeners.push((message) => { if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text); });
async function open(width) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 600 });
  const loaded = new Promise((resolveLoad) => { const listener = (message) => { if (message.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(listener), 1); resolveLoad(); } }; listeners.push(listener); });
  await send('Page.navigate', { url: PAGE }); await loaded;
  await js("Promise.all([...document.images].map((image) => image.complete ? 1 : new Promise((resolveImage) => { image.onload = image.onerror = resolveImage; })))"); await sleep(150);
}
async function section(selector, name) {
  const box = await js(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height}; })()`);
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x: Math.max(0, box.x - 8), y: Math.max(0, box.y - 8), width: box.w + 16, height: Math.min(box.h + 16, 12000), scale: 1 } });
  writeFileSync(join(OUT, `${name}.png`), Buffer.from(shot.data, 'base64')); console.log('wrote', `${name}.png`);
}
await open(1280); await section('#cross-theme', '1280-kq029-cross-theme'); await section('#states', '1280-kq029-states');
await open(360); await section('#cross-theme', '360-kq029-cross-theme'); await section('#states', '360-kq029-states');
const result = await js(`({broken:[...document.images].filter((image)=>image.complete&&image.naturalWidth===0).map((image)=>image.src),overflow:document.documentElement.scrollWidth>innerWidth})`);
console.log(JSON.stringify({ ...result, jsErrors: errors })); done(result.broken.length || result.overflow || errors.length ? 1 : 0);
