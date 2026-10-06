// Scaffold a film: node new-film.js <profile> <film> [--duration 15] [--studio ~/dev/video-studio]
// Creates <studio>/<profile>/<film>/ with film.html (from the profile's film-template.html),
// audio.js (profile audio-template.js, or a plain synth stub) and storyboard.md.
const fs = require('fs');
const path = require('path');
const os = require('os');
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const [profile, film] = argv.filter((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--')));
if (!profile || !film) { console.error('usage: node new-film.js <profile> <film> [--duration 15] [--studio dir]'); process.exit(2); }
const P = path.join(__dirname, '..', 'profiles', profile);
if (!fs.existsSync(path.join(P, 'profile.js'))) { console.error('unknown profile: ' + profile); process.exit(2); }
const studio = path.resolve(opt('--studio', path.join(os.homedir(), 'dev', 'video-studio')));
const D = path.join(studio, profile, film);
if (fs.existsSync(path.join(D, 'film.html'))) { console.error('already exists: ' + D); process.exit(2); }
fs.mkdirSync(D, { recursive: true });
const dur = opt('--duration', '15');
const tpl = fs.readFileSync(path.join(P, 'film-template.html'), 'utf8')
  .replace(/{{TITLE}}/g, film).replace(/{{DURATION}}/g, dur);
fs.writeFileSync(path.join(D, 'film.html'), tpl);
const at = path.join(P, 'audio-template.js');
fs.writeFileSync(path.join(D, 'audio.js'), fs.existsSync(at) ? fs.readFileSync(at, 'utf8')
  : "const path = require('path');\nconst s = require(path.join(process.env.MOTION_ENGINE, 'synth.js')).create();\n// cues at the same times as E in film.html\ns.write();\n");
fs.writeFileSync(path.join(D, 'storyboard.md'), fs.readFileSync(path.join(__dirname, '..', 'templates', 'storyboard.md'), 'utf8').replace(/{{FILM}}/g, film).replace(/{{DURATION}}/g, dur));
console.log(D);
