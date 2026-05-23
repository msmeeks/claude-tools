---
name: help-docs
description: Generate or update customer-facing help documentation for a project. Creates separate UI and API docs plus a demo gallery. Uses the demo skill to create companion video/HTML demo artifacts. Run after any significant feature addition or change.
---

# Help-Docs Generator

Generates the full `help-docs/` directory with UI guide, API reference, and demo gallery.

## Usage

```
/help-docs           — full regeneration of all help docs
/help-docs ui        — UI guide only
/help-docs api       — API reference only
/help-docs demos     — demo gallery and artifacts only
```

## Directory structure to produce

```
help-docs/
  index.html            — landing page with links to all docs and demos
  ui/
    index.html          — complete UI user guide (non-technical, for admins & workers)
  api/
    index.html          — complete API reference (technical, for developers)
  demos/
    index.html          — demo gallery index
    whole-project.html  — full end-to-end demo HTML
    whole-project.mp4   — full end-to-end demo video
    features/
      <name>.html       — per-feature demo HTML
      <name>.mp4        — per-feature demo video
    assets/
      *.png / *.srt     — imagery and subtitle files
```

## Generation rules

### Before writing anything
1. Read `meta/BRAND_VOICE.md`
2. Read `docs/llms.md` to orient
3. Read `docs/overview.md` for product context
4. Read relevant feature docs for each section

### UI Guide (`help-docs/ui/index.html`)
- Audience: non-technical admins and workers
- Avoid API jargon, HTTP methods, JSON
- Use numbered steps, clear screenshots or mock-ups, plain English
- Cover every major workflow a user would do (not just feature descriptions)
- Include a "Getting Started" section and a "FAQ" section
- Structure: sidebar nav, hero header with brand gradient, white cards

### API Reference (`help-docs/api/index.html`)
- Audience: developers integrating with the API
- Include full request/response examples in JSON code blocks
- Document every endpoint: method, path, auth required, request body, response, error codes
- Include authentication section: how to obtain and refresh tokens
- Structure: left sidebar with endpoint list, main content panel, code blocks with syntax highlighting (Prism.js or highlight.js)

### Demo Gallery (`help-docs/demos/index.html`)
- Cards linking to every demo artifact
- Thumbnail image or mock-up per demo
- Brief description of what the demo shows

### Companion demos
After generating UI docs, invoke the demo skill for:
- `whole` — full walkthrough
- Each feature that has a docs section

## Brand compliance

All user-facing copy must match `meta/BRAND_VOICE.md`. Technical API docs may be more formal but must use canonical product terminology.

## Update hook

After any `/sdlc docs` run, check whether `help-docs/` exists. If yes, update only the sections affected by the change. If no, run full generation.
