// motion-film renderer. Serves the film over a local http server (/engine -> this folder,
// /profile -> profiles/<profile>, everything else -> the film folder), drives headless Chrome,
// and pipes frames into ffmpeg.
//
// Usage:
//   node render.js <filmDir> sheet   [--portrait|--both]   -> stills/<film>[-9x16]-sheet.png (12 frames spread over the film)
//   node render.js <filmDir> stills 3.2,7.5 [--portrait]   -> stills/<film>[-9x16]-t3.20.png ...
//   node render.js <filmDir> video   [--landscape|--portrait] [--fps 30]
//                                     -> out/<film>.mp4 and out/<film>-9x16.mp4 (both by default)
//   node render.js <filmDir> serve                          -> prints a URL to watch the film live in a browser
// Options: --profile <name> (default: the film folder's parent folder name), --music-vol 0.5
// Audio: if <filmDir>/audio.js exists it is run before a video render (writes audio.wav, synced to the
// film's events). If <filmDir>/music.(mp3|wav|m4a|aac|ogg) exists it is mixed under audio.wav.
const { chromium } = require('playwright-core');
const { spawn, spawnSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const flag = n => argv.includes(n);
const opt = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const pos = argv.filter((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--') && ['--fps', '--profile', '--music-vol'].includes(argv[i - 1])));
const [filmArg, mode = 'sheet', timesArg] = pos;
if (!filmArg) { console.error('usage: node render.js <filmDir> sheet|stills|video|serve [times] [--portrait|--landscape|--both] [--fps N]'); process.exit(2); }

const FILM_DIR = path.resolve(filmArg);
const FILM = path.basename(FILM_DIR);
const PROFILE = opt('--profile', path.basename(path.dirname(FILM_DIR)));
const ENGINE_DIR = __dirname;
const PROFILE_DIR = path.join(__dirname, '..', 'profiles', PROFILE);
const FPS = Number(opt('--fps', 60));
if (!fs.existsSync(path.join(FILM_DIR, 'film.html'))) { console.error('no film.html in ' + FILM_DIR); process.exit(2); }
if (!fs.existsSync(PROFILE_DIR)) { console.error('no profile folder ' + PROFILE_DIR + ' (use --profile)'); process.exit(2); }

const orients = flag('--both') ? [false, true]
  : flag('--portrait') ? [true]
  : flag('--landscape') ? [false]
  : mode === 'video' ? [false, true] : [false];

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.ttf': 'font/ttf', '.otf': 'font/otf', '.json': 'application/json', '.bin': 'application/octet-stream', '.mp4': 'video/mp4' };
function serve() {
  const srv = http.createServer((req, res) => {
    const u = decodeURIComponent(req.url.split('?')[0]);
    if (u === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    const [root, rel] = u.startsWith('/engine/') ? [ENGINE_DIR, u.slice(8)] : u.startsWith('/profile/') ? [PROFILE_DIR, u.slice(9)] : [FILM_DIR, u.slice(1) || 'film.html'];
    const f = path.resolve(root, rel);
    if (!f.startsWith(path.resolve(root)) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { console.error('404 ' + u); res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise(r => srv.listen(0, '127.0.0.1', () => r(srv)));
}

async function openPage(browser, port, portrait) {
  const page = await browser.newPage({ viewport: { width: portrait ? 1080 : 1920, height: portrait ? 1920 : 1080 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(`http://127.0.0.1:${port}/film.html?render=1${portrait ? '&portrait' : ''}`);
  const fontOk = await page.evaluate(() => window.ready);
  const meta = await page.evaluate(() => window.FILM_META);
  if (!fontOk) console.warn('warning: profile font not confirmed loaded');
  if (errors.length) { console.error('page errors:\n' + errors.join('\n')); process.exit(1); }
  return { page, meta, errors };
}

function prepareAudio(dur) {
  const script = path.join(FILM_DIR, 'audio.js');
  if (fs.existsSync(script)) {
    const r = spawnSync(process.execPath, [script], { cwd: FILM_DIR, stdio: 'inherit',
      env: { ...process.env, MOTION_ENGINE: ENGINE_DIR, MOTION_PROFILE: PROFILE_DIR, FILM_DUR: String(dur) } });
    if (r.status !== 0) { console.error('audio.js failed'); process.exit(1); }
  }
  const wav = path.join(FILM_DIR, 'audio.wav');
  const music = ['mp3', 'wav', 'm4a', 'aac', 'ogg'].map(e => path.join(FILM_DIR, 'music.' + e)).find(f => fs.existsSync(f));
  return { wav: fs.existsSync(wav) ? wav : null, music };
}

(async () => {
  const srv = await serve();
  const port = srv.address().port;
  if (mode === 'serve') { console.log(`live: http://127.0.0.1:${port}/film.html   (add ?portrait for 9:16)  ctrl+c to stop`); return; }
  const browser = await chromium.launch({ channel: 'chrome' });
  const stillsDir = path.join(FILM_DIR, 'stills'), outDir = path.join(FILM_DIR, 'out');
  let audio = null;
  for (const portrait of orients) {
    const sfx = portrait ? '-9x16' : '';
    const { page, meta, errors } = await openPage(browser, port, portrait);
    const dur = meta.duration;
    if (mode === 'sheet' || mode === 'stills') {
      fs.mkdirSync(stillsDir, { recursive: true });
      const times = mode === 'sheet' ? Array.from({ length: 12 }, (_, i) => +(dur * (i + 0.5) / 12).toFixed(2))
        : (timesArg || '').split(',').filter(Boolean).map(Number);
      const files = [];
      for (const t of times) {
        await page.evaluate(tt => window.renderFrame(tt), t);
        const f = path.join(stillsDir, `${FILM}${sfx}-t${t.toFixed(2)}.png`);
        await page.screenshot({ path: f }); files.push(f);
      }
      if (errors.length) { console.error('page errors:\n' + errors.join('\n')); process.exit(1); }
      if (mode === 'sheet') {
        const [tw, th, cols] = portrait ? [360, 640, 6] : [640, 360, 4];
        const labels = files.map((_, i) => `[${i}:v]scale=${tw}:${th}[v${i}]`).join(';');
        const stack = files.map((_, i) => `[v${i}]`).join('') + `xstack=inputs=${files.length}:layout=` +
          files.map((_, i) => `${(i % cols) * tw}_${Math.floor(i / cols) * th}`).join('|');
        const out = path.join(stillsDir, `${FILM}${sfx}-sheet.png`);
        const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...files.flatMap(f => ['-i', f]), '-filter_complex', labels + ';' + stack, out], { stdio: 'inherit' });
        console.log(r.status === 0 ? `sheet: ${out}  (times ${times.join(', ')})` : 'ffmpeg sheet failed');
      } else console.log('stills:', files.join('\n'));
    } else if (mode === 'video') {
      fs.mkdirSync(outDir, { recursive: true });
      if (!audio) audio = prepareAudio(dur);
      const out = path.join(outDir, `${FILM}${sfx}.mp4`);
      const args = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-'];
      if (audio.wav) args.push('-i', audio.wav);
      if (audio.music) args.push('-i', audio.music);
      args.push('-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', String(FPS));
      if (audio.wav && audio.music) {
        const mv = Number(opt('--music-vol', 0.5));
        args.push('-filter_complex', `[2:a]volume=${mv},afade=t=out:st=${Math.max(0, dur - 1.5)}:d=1.5[m];[1:a][m]amix=inputs=2:normalize=0:duration=first[a]`, '-map', '0:v', '-map', '[a]');
      } else if (audio.music) {
        args.push('-af', `afade=t=out:st=${Math.max(0, dur - 1.5)}:d=1.5`);
      }
      if (audio.wav || audio.music) args.push('-c:a', 'aac', '-b:a', '192k', '-shortest');
      else console.warn('no audio.js / audio.wav / music.*: rendering silent');
      args.push('-t', String(dur), '-movflags', '+faststart', out);
      const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'inherit'] });
      const N = Math.round(dur * FPS);
      for (let i = 0; i < N; i++) {
        await page.evaluate(tt => window.renderFrame(tt), i / FPS);
        const buf = await page.screenshot({ type: 'png' });
        if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
        if (i % (FPS * 2) === 0) console.log(`${sfx || 'landscape'} frame ${i}/${N}`);
      }
      ff.stdin.end();
      const code = await new Promise(r => ff.on('close', r));
      if (errors.length) { console.error('page errors during render:\n' + errors.join('\n')); process.exit(1); }
      console.log('ffmpeg exit', code, out);
      if (code !== 0) process.exit(1);
    } else { console.error('unknown mode ' + mode); process.exit(2); }
    await page.close();
  }
  await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
