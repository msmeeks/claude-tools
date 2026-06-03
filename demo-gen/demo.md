# Demo Rules & Specification

Extracted from `~/.claude/skills/demo/SKILL.md` and global CLAUDE.md. This file defines how `demo-gen` produces its artifacts and how the `/demo` skill should behave when delegating to the CLI.

## Artifacts produced per demo

1. **HTML demo script** — `help-docs/demos/features/<name>.html` or `help-docs/demos/whole-project.html`
2. **MP4 video** — matching path with `.mp4` extension
3. **SRT subtitles** — `help-docs/demos/<name>.srt` (only when ffmpeg has libass; otherwise omitted)

## HTML structure (canonical Variant B)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="description" content="[product] — [feature] demo">
  <title>[Feature] | [Product]</title>
  <style>/* all CSS inline — no external deps */</style>
</head>
<body>
  <header><!-- brand gradient, product name, tagline, demo title --></header>
  <div class="page-body">
    <aside class="sidebar-nav"><!-- sticky white card, step links, IntersectionObserver target --></aside>
    <main class="main-content">
      <!-- per step: -->
      <section class="card" id="step{n}">
        <div class="step-header">
          <span class="step-num">{n}</span>
          <p class="step-title">{action verb + outcome}</p>
        </div>
        <!-- real screenshot: -->
        <div class="screenshot-wrap highlight">
          <img src="..." alt="[screen name]: [what is shown]">
          <!-- production polish only: -->
          <div class="callout-label">{label}</div>
        </div>
        <!-- placeholder mock (draft/standard if no screenshot): -->
        <div class="app-shell" role="img" aria-label="...">...</div>
        <div class="caption">{1-2 sentences, active voice, benefit-first}</div>
      </section>
      <section class="takeaways" id="takeaways">
        <h2>Key Takeaways</h2>
        <ul><!-- 3-5 bullets --></ul>
      </section>
    </main>
  </div>
  <footer>[Product] — [Tagline]</footer>
  <script>/* IntersectionObserver for sidebar active state (production polish) */</script>
</body>
</html>
```

## Polish levels

| Element | draft | standard | production |
|---|---|---|---|
| Screenshots | placeholder div mock | real `<img>` | real `<img>` + highlight ring + callout label |
| Captions | plain text | styled `.caption` block | styled + 4px accent border |
| Takeaways | absent | plain `<ul>` | gradient card + checkmark bullets |
| IntersectionObserver | absent | absent | present |
| Footer | absent | product name | product name + tagline + year |
| TTS backend | Piper (fast) | Kokoro standard | Kokoro best voice |
| Video SFX | none | none | none |
| Video subtitles | none | SRT if libass available | SRT if libass available |
| Video transitions | cut | fade 0.5s | fade 0.5s |

## Video spec

- Resolution: 1280×720 (default), 1920×1080 (optional)
- Slide structure: title card (3s) → step slides (audio-duration-matched) → closing card (3s)
- **Text rendering**: all text (titles, captions, closing card) rendered onto PNG frames via **Pillow** `ImageDraw`. Do NOT use ffmpeg `drawtext` — stock Homebrew ffmpeg lacks libfreetype.
- **Caption bar layout**: screenshot slides scale the image to fill (w × h-barHeight) with light letterbox padding (`#f8f9fc`), then paint a navy bar at the bottom containing wrapped caption text.
- Subtitles: SRT, burned via ffmpeg `subtitles=` filter **only when `has_libass()` returns True**; otherwise omitted with a logged warning
- Audio: per-step WAV from TTS, faded in/out 0.1s, concatenated
- SFX: **none** — do not insert sound effects at any polish level
- All ffmpeg calls: explicit arg lists, `shell=False`
- ffmpeg binary: prefer `/opt/homebrew/bin/ffmpeg` (macOS Homebrew); fall back to `shutil.which("ffmpeg")`

## Brand compliance

Before writing any script content:
1. Read `BRAND_VOICE.md` at project root
2. Match voice attributes, tone, terminology, and writing rules
3. Use the project's design tokens (from `design_tokens.json` or `--tokens` flag)

## Privacy requirements

- **Local by default**: scripting runs via Ollama (`--local`), no data leaves the machine
- **Cloud mode** (`--cloud`): requires explicit pre-flight consent listing files to be sent
- Only files in `--include-docs` list are sent to API; never sweep entire `docs/` trees
- All temp files in `TemporaryDirectory` context — cleaned up on exit/exception

## Terminology guard

Never use these terms in customer-facing demo copy:

| Avoid | Use instead |
|---|---|
| entity, record, object | the domain noun (e.g. "unit", "task") |
| CRUD, endpoint, payload | describe the action in plain English |
| template, schema, category | domain term (e.g. "task type") |
| staff member, employee | "worker" (for hospitality demos) |
| ticket, job | "task" (for hospitality demos) |
| state, phase, stage | "status" |

## `/demo` skill CLI delegation

If `demo-gen` is available in PATH, the skill should delegate:

```bash
demo-gen generate \
  --feature <name> \
  --brand-voice ./BRAND_VOICE.md \
  --polish standard \
  --format both \
  --output-dir help-docs/demos/
```

Fall back to the Pillow+ffmpeg approach described in the `/demo` skill if `demo-gen` is not installed. Never fall back to ffmpeg drawtext.
