---
name: demo
description: Generate demo artifacts for a feature, enhancement, or fix. Creates a polished HTML demo script with screenshots/captions and an MP4 video with talk track, subtitles, and transitions. Use whenever creating or updating a significant feature. Also invoked by help-docs skill.
---

# Demo Generator

Creates two artifacts per demo: a static HTML script and an MP4 video.

## Usage

```
/demo [feature-name] [--scope whole|feature] [--title "Demo Title"]
```

- `/demo` — generate demo for most recently changed feature
- `/demo whole` — generate full end-to-end product walkthrough
- `/demo units` — generate demo for the units feature

## What to produce

### Artifact 1: HTML Demo Script

Output path: `help-docs/demos/features/<name>.html` or `help-docs/demos/whole-project.html`

Structure:
1. **Title page** — product name, tagline, demo title, date
2. **Executive summary** — 2–3 sentences: what this feature does and why it matters to the user
3. **Step-by-step walkthrough** — for each step:
   - `<h2>` step heading (action verb + outcome)
   - `<img>` pointing to the real screenshot (`../screenshots/<name>.png` or `screenshots/<name>.png`)
   - Caption div: 1–2 sentences active-voice describing the action and its benefit
4. **Key takeaways** — bulleted list of 3–5 "what you just saw" highlights
5. **Call to action** — link or next step for the reader
6. **`<video>` player** — embedded MP4 at the top of the main content area

Visual style:
- Clean white cards on `#fbf0ee` (blush) background
- Brand header: `linear-gradient(135deg, #2D3192 0%, #1a1040 100%)` (navy gradient — NEVER use old `#1e3a5f` or `#2563eb`)
- Step numbers in pink circles: `linear-gradient(135deg, #ff0080, #d4006a)`
- Screenshot: `width: 100%; border-radius: 10px; border: 1px solid #f0e0e6; box-shadow: 0 4px 20px rgba(45,49,146,0.12)`
- Caption: left border accent `#ff0080`, `background: #fff8fb`, navy text `#2D3192`
- Overall feel: polished, almost ready for a public marketing campaign

### Artifact 2: MP4 Video

Output path: `help-docs/demos/features/<name>.mp4` or `help-docs/demos/whole-project.mp4`

Generate using **Pillow** (for text rendering) + **ffmpeg** (for video encoding):

- **Title card** (3 s): brand gradient background, product name + demo title + tagline via Pillow `ImageDraw`
- **Step slides** (5 s each): screenshot scaled to fill canvas minus caption bar; navy caption bar at bottom with wrapped text via Pillow
- **Closing card** (3 s): brand gradient, product name + tagline via Pillow
- **No SFX** — do not add sound effects at any polish level
- **Subtitles**: SRT burned via ffmpeg `subtitles=` filter at `standard` and `production` polish — but **only when `has_libass()` returns True**. At `draft` polish or when libass is absent, omit subtitles and log a warning.
- **Concatenate** via ffmpeg concat demuxer: `-c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -movflags +faststart`

**Do NOT use ffmpeg `drawtext` filter.** Stock Homebrew ffmpeg is built without `libfreetype`. Use Pillow for all text rendering onto PNG frames; use ffmpeg only for encoding PNGs into video clips and for concatenation. The `subtitles=` filter may also be absent; always check `has_libass()` before using it.

ffmpeg binary: prefer `/opt/homebrew/bin/ffmpeg` on macOS, fall back to `shutil.which("ffmpeg")`.

## Capturing real screenshots

Screenshots are required for quality demos. Capture them from the live app before building the MP4.

### CDP screenshot approach (Node.js, recommended)

```javascript
// Requires Node 22+ (built-in WebSocket)
import { spawn } from 'child_process';
import { writeFileSync, mkdirSync } from 'fs';
import http from 'http';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9222;

const chrome = spawn(CHROME, [
  `--remote-debugging-port=${PORT}`, '--headless=new',
  '--no-first-run', '--disable-extensions', '--window-size=1280,800',
  '--force-device-scale-factor=1', `--user-data-dir=/tmp/demo-${Date.now()}`, 'about:blank',
], { stdio: 'ignore' });

// Wait 2.5 s for Chrome to start, then:
//   GET http://localhost:PORT/json → find page target → open WebSocket
//   CDP.send('Page.navigate', { url }) → sleep → CDP.send('Page.captureScreenshot')
```

Key patterns:
- Use `Page.addScriptToEvaluateOnNewDocument` to inject localStorage **before** page JS runs
- Use `Runtime.evaluate` to simulate clicks and fill forms
- Use `Emulation.setDeviceMetricsOverride` to pin viewport to 1280×800
- Screenshots go in `help-docs/demos/screenshots/<slug>.png`

### Onboarding tour suppression

Many apps show a welcome tour on first load. Suppress it by injecting localStorage before page load:

```javascript
await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
  source: `localStorage.setItem('YOUR_TOUR_KEY', JSON.stringify(['seen']))`
});
```

Check the app's source for the localStorage key the tour checks. If the tour fires via a `setTimeout` after React mounts, also set it after page load and click any visible close button.

### Authentication

Find the correct login endpoint from the API source (not from memory). Common patterns:
- `POST /api/v1/auth/login` with JSON body `{"email":"...","password":"..."}`
- Fill form fields and click submit via `Runtime.evaluate`

### Screenshot directory

Screenshots live in `help-docs/demos/screenshots/`. HTML files in `features/` reference them as `../screenshots/<name>.png`. `whole-project.html` references them as `screenshots/<name>.png`.

## Brand compliance

Always read `meta/BRAND_VOICE.md` before writing any script content. Match voice, tone, and terminology defined there.

## CLI delegation

If `demo-gen` is available in PATH, delegate to it instead of generating inline:

```bash
demo-gen generate \
  --product "<Product Name>" \
  --feature "<feature>" \
  --brand-voice ./meta/BRAND_VOICE.md \
  --polish standard \
  --format both \
  --screenshot help-docs/demos/screenshots/<slug1>.png \
  --screenshot help-docs/demos/screenshots/<slug2>.png \
  --output-dir help-docs/demos/features/
```

Pass `--polish production` for public-facing releases. Pass `--tone casual` for internal demos.
Pass `--cloud` only if the user has explicitly opted in; default is `--local`.

**Voice selection:** Default voice is `af_sky` (warm American female — matches BRAND_VOICE.md recommendation). Other options: `af_kore`, `af_heart`, `am_puck` (male), `am_michael`, `am_echo`, `am_santa`. Always use `--voice af_sky` for Hospitality Scheduler demos unless the user requests otherwise. Kokoro requires Python 3.11+ and the `kokoro` extra (`pip install demo-gen[kokoro]`). Models are cached at `~/.demo-gen/models/kokoro/` after first use. demo-gen binary is at `~/Code/claude-tools/demo-gen/.venv/bin/demo-gen`.

**Python requirement:** demo-gen requires Python 3.11+. The project venv must be created with `python3.11 -m venv .venv`.

After running, update `help-docs/demos/index.html` to link the new demo card.

## Fallback implementation steps (when demo-gen is not installed)

1. Read `meta/BRAND_VOICE.md` and `docs/llms.md`
2. Read the relevant feature doc(s) in `docs/features/`
3. Capture real screenshots using the CDP approach above (or reuse existing ones from `help-docs/demos/screenshots/`)
4. Write the HTML artifact using real `<img>` tags (not inline CSS mock-ups)
5. Build the MP4 using Pillow + ffmpeg (see Artifact 2 spec above)
6. Update `help-docs/demos/index.html` to link the new demo card

## Polish levels

| Element | draft | standard | production |
|---|---|---|---|
| Screenshots | placeholder div | real `<img>` | real `<img>` |
| Captions | plain text | styled `.caption` block | styled + accent border |
| Takeaways | absent | plain `<ul>` | gradient card + checkmark bullets |
| IntersectionObserver sidebar | absent | absent | present |
| Footer | absent | product name | product name + tagline + year |
| TTS backend | Piper (fast) | Kokoro `af_sky` (default) | Kokoro `am_puck` or `af_sky` |
| Video SFX | none | none | none |
| Video subtitles | none | SRT if libass available | SRT if libass available |
| Video transitions | cut | fade 0.5s | fade 0.5s |
