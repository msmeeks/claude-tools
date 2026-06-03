# Design Brief — demo-gen

## Color palette (default tokens)

| Token | Hex | Use |
|---|---|---|
| `brand_gradient_start` | `#1e3a5f` | Header/title gradient start |
| `brand_gradient_end` | `#2563eb` | Header/title gradient end |
| `brand_primary` | `#2563eb` | Step circles, links, active nav |
| `brand_primary_light` | `#dbeafe` | Active nav bg, caption bg |
| `brand_primary_dark` | `#1e40af` | Caption text, dark accents |
| `highlight_color` | `#ef4444` | Screenshot annotation border |
| `highlight_shadow` | `rgba(239,68,68,0.12)` | Annotation glow |
| `page_bg` | `#f8f9fc` | Page background |
| `card_bg` | `#ffffff` | Card/step background |
| `body_text` | `#111827` | Primary text |
| `secondary_text` | `#374151` | Captions, secondary content |
| `app_shell_sidebar_bg` | `#111827` | App mockup sidebar (dark) |

## Typography

System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
Base size: 15px. No custom web fonts — demos must be fully self-contained.

## HTML component patterns

- **Step card**: white bg, `border-radius: 16px`, `box-shadow: 0 2px 12px rgba(0,0,0,0.08)`
- **Step circle**: 44px, `brand_primary` bg, 22px/700 white numeral
- **Caption block**: `border-left: 4px solid brand_primary`, `bg: brand_primary_light`, 13px, `color: brand_primary_dark`
- **Highlight ring**: `outline: 3px solid highlight_color; outline-offset: 3px`
- **Callout label**: absolute positioned chip above highlight target; red bg, white text
- **Takeaways**: gradient `brand_gradient_start → brand_gradient_end`, white text, checkmark bullets

## Canonical HTML structure (Variant B)

```
<aside class="sidebar-nav"> (sticky, white card)
<main class="main-content">
  <section class="card" id="step{n}">
    <div class="step-header">
      <span class="step-num">{n}</span>
      <p class="step-title">{heading}</p>
    </div>
    <div class="screenshot-wrap highlight">  ← wrapper for real screenshots
      <img ...>
      <div class="callout-label">{label}</div>  ← production polish only
    </div>
    <div class="caption">{caption}</div>
  </section>
```

## Video design tokens (at 1280×720)

| Element | Size/Position |
|---|---|
| Title h1 | 52px/700, white, centered |
| Step heading | 36px/700, `body_text`, left-aligned with 40px margin |
| Caption | 18px/400, `secondary_text` |
| Subtitle | 32px/600, white, drop-shadow 2px 2px 4px rgba(0,0,0,0.8), y=650px |
| Step circle | 48px diameter, 24px/700 white numeral |

## Layout

- Page max-width: 1200px, centered
- Sidebar width: 220px
- Content padding: 32px
- Card gap: 24px
- Responsive: sidebar stacks at 768px

## Motion

- Step transitions: fade 0.5s (standard), fade + slide (production)
- SFX: none (bell/ding removed; transitions are silent at all polish levels)
- No animation in HTML output (static screenshots only)

## Video canvas

| Token | Value | Use |
|---|---|---|
| `video_canvas_bg` | `#0f172a` | Letterbox fill behind screenshots/stills |
