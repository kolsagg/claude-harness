---
name: motion-film
description: Kodla motion/tanıtım videosu üretir (canvas + headless Chrome + ffmpeg, ses de koddan). Hem 16:9 hem 9:16 (sosyal medya) çıkarır, süre hikâyeye göre (kullanıcı sınır verirse ona uyar). Marka profilleri (profiles/<id>: görsel kimlik + ton) ve referans filmlerle çalışır; markasız `_template` profili hazır, kendi marka profilini `profiles/<id>` altına eklersin. Tetik: '/motion-film', 'video yap', 'tanıtım videosu', 'ürün videosu', 'motion video', 'reels/tiktok videosu', 'mobil video', 'profil ekle' (video markası). Use for any request to produce a promo/explainer/product motion video.
---

# motion-film

Everything is code: a canvas page draws any frame on demand (`renderFrame(t)`), headless Chrome
screenshots every frame, ffmpeg encodes them with a code-synthesized soundtrack. No video editor,
no stock media. Owner decisions (2026-09-26): name motion-film; films live in `~/dev/video-studio/`;
profiles hold visual identity + tone; do NOT stop for approvals mid-production, deliver the finished
video and iterate on feedback; default both formats; synth audio plus the owner's music if given;
one agent per film when several films are requested; 1080p 60 fps; outputs stay in the studio folder.

## Layout
```
~/.claude/skills/motion-film/
  SKILL.md            this file
  lessons.md          hard-won rules from past films. READ FIRST, every time.
  engine/             core.js start.js render.js synth.js new-film.js (+ node_modules: playwright-core)
  profiles/<id>/      profile.js (PROFILE), theme.js (THEME), film-template.html, audio-bed.js,
                      audio-template.js, profile.md (identity + tone), assets/ (fonts, shapes, images)
  profiles/_template/ neutral starting point for a new brand
  templates/storyboard.md
  references/<id>/    approved films of that profile + INDEX.md (what to borrow from each)
~/dev/video-studio/<profile>/<film>/   film.html, audio.js, storyboard.md, [music.mp3], stills/, out/
```

## Workflow
1. **Read** `lessons.md`, the profile's `profile.md` and `references/<id>/INDEX.md`. If the brand has no
   profile, create one (see "New profile") before the film.
2. **Brief**: from the user's message collect: profile, what the film must explain, source text
   (product copy, site, brief), length limit if any (none = what the story needs), formats (default
   16:9 + 9:16; "sadece mobil/yatay" = one), music file if any (copy it to the film folder as music.*).
   Ask only if the subject itself is unclear; otherwise decide and proceed.
3. **Storyboard** (`storyboard.md`, from templates/): beats with concrete on-screen objects showing the
   mechanic (input -> processing -> action -> result), one big caption per beat in the profile's tone,
   hard rules (privacy, the brand's own terms), portrait layout notes. Length follows the beats.
4. **Scaffold**: `node ~/.claude/skills/motion-film/engine/new-film.js <profile> <film> --duration <s>`.
5. **Build** `film.html` (FILM: duration, drawScene, init; one timing table `E`) and `audio.js`
   (profile bed + cues at the E times). Branch layout on `PORTRAIT` for 9:16: re-layout, never crop.
   Several films: spawn one Opus agent per film (prompt below); the lead owns engine/, theme and profile.
6. **Review** (no user stop, but never skip): `node render.js <filmDir> sheet --both`, read both sheets,
   then full-size `stills` at every beat. At least 3 fix rounds. Checklist below.
7. **Render**: `node render.js <filmDir> video` (both formats; runs audio.js first; mixes music.* if
   present). Long jobs in the background; wait for "ffmpeg exit 0". Verify with ffprobe (size, duration,
   audio stream).
8. **Deliver**: paths in `<film>/out/` (`<film>.mp4`, `<film>-9x16.mp4`), what each beat shows, known
   weaknesses. When the owner corrects something, fix it and append the lesson to `lessons.md` (what
   happened -> rule) and any brand term to `profile.md`.

## Review checklist
- Every beat shows the mechanic with a concrete object; nothing is decorative filler.
- Captions: one big at a time, landscape <= ~45 chars, profile tone, no banned words; diacritics correct.
- UI text >= 20 px; nothing clipped; margins >= 60 px; objects gone before the end card.
- Portrait: nothing important in top 250 / bottom 330 px; stacked layout, readable at phone size.
- Brand names uppercase with `upper(name, true)`; words with `upper(word)` (profile locale).
- Audio cue at each E event; no page errors (render.js exits non-zero on them).

## Engine API (globals available in the film script)
- Frame: `W H CX CY PORTRAIT L` (layout slots: bigY smallY capMax navX navY safeTop safeBottom margin,
  plus theme slots), `x` (2D context), `C` (profile colors), `F` (font stack), `PROFILE`, `DUR` (after load).
- Math: `clamp seg lerp mix rgba rng hash3 rotYP`, easings `eOutExpo eInExpo eInOut eInOutQ eOutCubic eOutBack`.
- UI: `text caption bigCaption smallCaption drawLetters panel pill glow circle beam flow absorb check
  drawCursor drawAvatar drawLock upper loadImage`.
- FILM contract: `duration` (s, required), `drawScene(t)`, optional async `init()`, plus theme fields.
- THEME contract (profile): `init()`, `background(t)`, `foreground(t)`; documents its own timeline and
  FILM fields in its header (a rich theme may add fields such as shape, tagline, end-card timing).
- Audio (`audio.js`, run by render.js with MOTION_ENGINE / MOTION_PROFILE / FILM_DUR):
  `S.create()` -> `ping whoosh thud click tone pad write`; profile `audio-bed.js(s)` adds the brand bed.
- Commands (`engine/render.js <filmDir> ...`): `sheet [--portrait|--both]`, `stills 3.2,7.5 [--portrait]`,
  `video [--landscape|--portrait] [--fps 30] [--music-vol 0.5]`, `serve` (live preview URL).

## New profile
Copy `profiles/_template/` to `profiles/<id>/`. Ask the owner for: brand name, CTA text, url, language,
colors, fonts (files), logo/visual language, voice and words to avoid, the brand's own product terms,
reference material (site, deck, earlier videos). Fill profile.js, write theme.js for the visual language
(start from _template), write profile.md. Make one short test film and a sheet before real work.

## Agent prompt (one per film)
"Build the <film> film for profile <id> in <filmDir>. Read ~/.claude/skills/motion-film/SKILL.md,
lessons.md, profiles/<id>/profile.md + theme.js, references/<id>/INDEX.md and the closest reference film,
and storyboard.md. Edit only files in <filmDir>. Write film.html and audio.js, branch the layout on
PORTRAIT for 9:16. Iterate with `node <engine>/render.js <filmDir> sheet --both` and full-size stills
(read the PNGs), at least 3 rounds against the checklist, then run `... video` and wait for
'ffmpeg exit 0'. Report beats with times, deviations from the storyboard, weaknesses, output paths."
