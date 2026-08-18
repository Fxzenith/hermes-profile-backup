---
name: mermaid-render
description: Render Mermaid diagrams to PNG/SVG on a root Linux box.
---

# Mermaid → Image (headless, as root)

Render Mermaid `.mmd` files (or fenced ```mermaid blocks inside Markdown) to PNG/SVG with `mmdc` (mermaid-cli). The one real gotcha on this VPS: it runs as **root**, and puppeteer's bundled Chromium refuses to launch unless the sandbox is disabled.

## Hard rule (root)
`mmdc` drives headless Chromium via puppeteer. As root it fails with:
`Running as root without --no-sandbox is not supported.`
Fix: hand `mmdc` a puppeteer config via `-p` that disables the sandbox.

## Workflow
1. Ensure `mmdc` is present: `which mmdc` (installed globally at `/usr/local/bin/mmdc`). If missing: `npm i -g @mermaid-js/mermaid-cli`.
2. Write the puppeteer config (copy `templates/puppeteer-config.json`):
   `{"args":["--no-sandbox","--disable-setuid-sandbox"]}`
3. Render:
   `mmdc -i diagram.mmd -o diagram.png -b transparent -w 1400 -p /tmp/mmd-pptr.json`
   - `-w` width in px, `-b transparent` for overlay-friendly background, `-p` puppeteer config path.
4. Verify: the output PNG exists and is non-trivial in size (a real flowchart rendered ~76KB in testing).

## Notes
- The `--no-sandbox` requirement is **general** to any headless-Chromium tool on this box (puppeteer/playwright screenshotters, browser-use). Apply the same flag wherever Chromium won't start as root.
- Prefer the `diagram` skill (diagram-design) when you want an editorial, brand-aware diagram — it emits self-contained HTML/SVG and needs no browser at all. Use this skill only when a raster PNG/SVG of a Mermaid source is specifically required (e.g. delivering a single image, or the user asked "did you make a diagram?" and wants a picture file).
