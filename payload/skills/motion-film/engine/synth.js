// motion-film soundtrack synth: deterministic, code-generated sound effects synced to film events.
// A film's audio.js (run by render.js with MOTION_ENGINE, MOTION_PROFILE and FILM_DUR set) does:
//   const S = require(require('path').join(process.env.MOTION_ENGINE, 'synth.js'));
//   const s = S.create();                       // duration from FILM_DUR
//   require(require('path').join(process.env.MOTION_PROFILE, 'audio-bed.js'))(s);   // optional profile bed
//   s.ping(...); s.whoosh(...)                  // film cues at the same times as drawScene events
//   s.write();                                  // -> audio.wav in the film folder
// Voices: ping (bell), whoosh (filtered noise swell), thud (low hit), click (UI tick), tone (sustained,
// ring/hum), pad (chord bed). Keep one timing table in the film and mirror it here.
const fs = require('fs');
const path = require('path');

const SR = 48000;
const PENTA = [880, 987.77, 1108.73, 1318.51, 1479.98, 1760];

function create(opts = {}) {
  const DUR = opts.duration || Number(process.env.FILM_DUR) || 15, N = Math.round(SR * DUR);
  const dry = [new Float32Array(N), new Float32Array(N)];
  const wet = new Float32Array(N);
  const rnd = (() => { let s = 12345; return () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296) * 2 - 1; })();
  const add = (i, l, r, send = 0) => {
    if (i < 0 || i >= N) return;
    dry[0][i] += l; dry[1][i] += r; wet[i] += (l + r) * 0.5 * send;
  };

  // soft bell: sine + octave partial, exponential decay
  function ping(t0, f, amp, decay = 0.9, pan = 0, send = 0.6) {
    const s0 = Math.floor(t0 * SR), len = Math.floor(decay * 5 * SR);
    for (let k = 0; k < len; k++) {
      const t = k / SR;
      const env = Math.min(1, t / 0.004) * Math.exp(-t / decay);
      const v = amp * env * (Math.sin(2 * Math.PI * f * t) + 0.25 * Math.sin(2 * Math.PI * f * 2.01 * t) * Math.exp(-t * 6));
      add(s0 + k, v * (1 - pan) * 0.7, v * (1 + pan) * 0.7, send);
    }
  }
  // filtered-noise swell; rise then fall, cutoff follows the envelope
  function whoosh(t0, dur, amp, peakAt = 0.6, send = 0.4) {
    const s0 = Math.floor(t0 * SR), len = Math.floor(dur * SR);
    let lp = 0, lp2 = 0;
    for (let k = 0; k < len; k++) {
      const p = k / len;
      const env = p < peakAt ? Math.pow(p / peakAt, 2) : Math.pow(1 - (p - peakAt) / (1 - peakAt), 1.5);
      const cut = 0.02 + 0.18 * env;
      lp += cut * (rnd() - lp); lp2 += cut * (lp - lp2);
      const v = lp2 * amp * env * 3;
      const pan = Math.sin(p * Math.PI * 1.5) * 0.5;
      add(s0 + k, v * (1 - pan), v * (1 + pan), send);
    }
  }
  function thud(t0, f, amp, decay) {
    const s0 = Math.floor(t0 * SR), len = Math.floor(decay * 5 * SR);
    for (let k = 0; k < len; k++) {
      const t = k / SR;
      const fr = f * (1 + 1.5 * Math.exp(-t * 30));
      const v = amp * Math.exp(-t / decay) * Math.sin(2 * Math.PI * fr * t) * Math.min(1, t / 0.002);
      add(s0 + k, v, v, 0.15);
    }
  }
  function click(t0, amp) {
    const s0 = Math.floor(t0 * SR);
    for (let k = 0; k < SR * 0.03; k++) {
      const t = k / SR;
      const v = amp * Math.exp(-t * 180) * (rnd() * 0.6 + Math.sin(2 * Math.PI * 2400 * t));
      add(s0 + k, v, v, 0.3);
    }
  }
  // soft sustained tone with attack/release (ring tone, voice hum); vib = vibrato depth in Hz
  function tone(t0, dur, f, amp, pan = 0, send = 0.4, vib = 0) {
    const s0 = Math.floor(t0 * SR), len = Math.floor(dur * SR);
    for (let k = 0; k < len; k++) {
      const t = k / SR, p = k / len;
      const env = Math.min(1, t / 0.02) * Math.min(1, (1 - p) * len / (SR * 0.06));
      const v = amp * env * Math.sin(2 * Math.PI * f * t + (vib / 5) * Math.sin(2 * Math.PI * 5 * t));
      add(s0 + k, v * (1 - pan) * 0.7, v * (1 + pan) * 0.7, send);
    }
  }

  // Sustained chord pad. freqs: Hz list; env(t) -> 0..1 gain over time (fade in/out, swells).
  function pad(freqs, level, env) {
    for (let k = 0; k < N; k++) {
      const t = k / SR, e = level * env(t);
      if (e <= 0) continue;
      let l = 0, r = 0;
      freqs.forEach((f, j) => {
        const lfo = 0.75 + 0.25 * Math.sin(2 * Math.PI * (0.11 + j * 0.03) * t + j);
        l += Math.sin(2 * Math.PI * (f - 0.35) * t) * lfo / (1 + j * 0.35);
        r += Math.sin(2 * Math.PI * (f + 0.35) * t + 0.5) * lfo / (1 + j * 0.35);
      });
      add(k, l * e, r * e, 0.3);
    }
  }

  function write(file = 'audio.wav') {
    // reverb: parallel feedback combs + allpass, lightly low-passed
    const combs = [1687, 1601, 2053, 2251].map(d => ({ d, buf: new Float32Array(d), i: 0, lp: 0 }));
    const aps = [556, 441].map(d => ({ d, buf: new Float32Array(d), i: 0 }));
    const out = [Float32Array.from(dry[0]), Float32Array.from(dry[1])];
    for (let k = 0; k < N; k++) {
      let s = 0;
      for (const c of combs) {
        const y = c.buf[c.i];
        c.lp = c.lp + 0.3 * (y - c.lp);
        c.buf[c.i] = wet[k] + c.lp * 0.86;
        c.i = (c.i + 1) % c.d; s += y;
      }
      s *= 0.25;
      for (const a of aps) { const b = a.buf[a.i]; const y = -s + b; a.buf[a.i] = s + b * 0.5; a.i = (a.i + 1) % a.d; s = y; }
      out[0][k] += s * 0.55; out[1][k] += s * 0.5;
    }
    // master: soft clip, normalize to -1 dBFS, 20 ms edge fades
    let peak = 0;
    for (let ch = 0; ch < 2; ch++) for (let k = 0; k < N; k++) { out[ch][k] = Math.tanh(out[ch][k] * 1.4); peak = Math.max(peak, Math.abs(out[ch][k])); }
    const g = 0.89 / peak;
    const pcm = Buffer.alloc(44 + N * 4);
    pcm.write('RIFF', 0); pcm.writeUInt32LE(36 + N * 4, 4); pcm.write('WAVE', 8); pcm.write('fmt ', 12);
    pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(2, 22); pcm.writeUInt32LE(SR, 24);
    pcm.writeUInt32LE(SR * 4, 28); pcm.writeUInt16LE(4, 32); pcm.writeUInt16LE(16, 34); pcm.write('data', 36); pcm.writeUInt32LE(N * 4, 40);
    const edge = SR * 0.02;
    for (let k = 0; k < N; k++) {
      const e = Math.min(1, k / edge, (N - 1 - k) / edge);
      for (let ch = 0; ch < 2; ch++) pcm.writeInt16LE(Math.round(Math.max(-1, Math.min(1, out[ch][k] * g * e)) * 32767), 44 + k * 4 + ch * 2);
    }
    fs.writeFileSync(path.resolve(process.cwd(), file), pcm);
    console.log(file + ' written, peak before gain', peak.toFixed(3));
  }

  return { ping, whoosh, thud, click, tone, pad, write, DUR, SR };
}

module.exports = { create, PENTA, SR };
