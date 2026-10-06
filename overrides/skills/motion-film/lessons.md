# Lessons (product films, 2026-09)

Each item: what happened, the rule that follows. Read before every film.

## Story
1. **Show the mechanic, not the brochure.** A first cut that animated the site's copy and visuals was
   rejected ("siteyi videoya dökmüşsün, ürünü anlatmıyor"). The approved cut walked through
   input -> processing -> user/system action -> result with concrete objects (notes, AI tag, one-click
   approve, notes flying into spaces, locks). Every beat needs a visible object doing something.
2. **Storyboard from the source text before any code.** Beats, captions and hard rules come from the
   brand's own product copy. Name concrete objects per beat; vague beats become pretty filler.
3. **Use the owner's words.** A voice product's record landed in "CRM"; the owner wanted "PANEL". Put the brand's own
   terms in the profile and prefer them over generic industry terms.
4. **Pick the angle the owner cares about.** A retail-analytics product first showed queue + safety alerts; the owner wanted
   the store heatmap and what it teaches (which spot draws interest, dead corners, routes). When a
   product has many capabilities, pick the one that sells; do not cram all of them.
5. **Privacy-sensitive products**: no faces, no identities; people as anonymous dots, an "ANONİM" badge.
6. **Realism on request means real rendering**: flat line-art rooms read as clip-art. Generate SVG with
   perspective, gradients, soft shadows (feGaussianBlur), textures, light shafts; preload with
   `await loadImage()` in async `init()`. Photoreal needs a real photo or an image model.
7. **Payoff numbers make it land** ("%8 -> %34", "142 kaynak tarandı", "Bütçe içinde"). Invented data is
   fine but plausible, no real company names.

## Craft
8. One big caption at a time, <= ~45 chars landscape; small line under it. Portrait wraps to 2 lines.
9. UI text >= 20 px (phones). Everything on screen fades/collapses before the end card.
10. Keep every event time in one table (`E`) and mirror it in `audio.js`; sound on the exact event.
11. tr-TR locale: `toLocaleUpperCase('tr-TR')` for words, but brand/product names with `upper(name, true)`
    (Limit became "LİMİT" with the tr-TR locale).
12. Deterministic frames: `renderFrame(t)` is a pure function of t. No Date/Math.random in drawScene.
13. Imported 3D point sets (site shapes) are y-up; canvas is y-down. Flip once, verify with one still.

## Portrait (9:16)
14. Re-layout, never crop: stack side-by-side panels vertically, product shape up top, panels below.
15. Safe areas: nothing important in the top 250 px or bottom 330 px (platform UI), 60 px side margins.
16. Scripts that need PORTRAIT must run after core.js (the old base.js loaded last and every film had to
    re-parse the URL). The engine now loads core and theme before the film script.
17. When adding a portrait branch, byte-compare landscape stills before/after: landscape must not move.

## Process
18. Contact sheet (12 frames) before any full render; full-size stills at every beat. 3 review rounds.
19. Freeze and prove the shared engine before fanning out (one test film, pixel diff vs reference).
20. One agent per film in parallel works well (7 films in ~15 min + renders). Agents edit only their
    own film files; shared engine/theme changes are made by the lead.
21. Renders: ~6-8 min per 15 s at 60 fps per format; 6-7 in parallel is fine on this PC.
    Watch for "ffmpeg exit 0".
22. Tool pitfalls: writing JS through python-in-heredoc turned `\b` into a backspace byte and silently
    broke a regex. Write code files with the Write/Edit tools; grep for control bytes if a regex fails.
23. Chrome asks for /favicon.ico; the render server answers 204 so it does not fail the page-error check.
