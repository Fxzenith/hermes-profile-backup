# ASS Karaoke Active-Word Highlight

Per-word (1–3 words/cue) timing is assumed. Highlight the FIRST word of each cue so
the viewer's eye tracks the active word as speech advances.

## Colour format
ASS primary colour override is `&HBBGGRR` (BGR byte order, not RGB).
- neon yellow `#FFE600` → `&H00E6FF`
- neon green `#39FF14` → `&H14FF39`
Helper:
```python
def hex_to_ass(hex_color):
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFE600"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}"
```

## Inline override (wrap the active word)
```
{\c&H00E6FF}active word{\c&HFFFFFF}
```
The trailing `{\c&HFFFFFF}` reverts the rest of the cue to white so only the active
word is tinted.

## Python f-string PITFALL
`f"{\c{hc}}"` is a SyntaxError (backslash not allowed in f-string expression part).
Concatenate string literals instead:
```python
styled = "{\\c" + hc + "}" + word + "{\\c&HFFFFFF}"
```
This is exactly how the `projects/autoclipping` `subtitles_oneline.py::style_chunk`
applies `highlight_active` to `words[0]`.

## Wiring in that pipeline
- `style_chunk(words, keyword_emphasis, keyword_emoji, highlight_active, highlight_color)`
  tints `words[0]`.
- CLI: `--no-highlight` disables, `--highlight-color #RRGGBB` overrides (default `#FFE600`).
- `build_ass(...)` and `main()` both forward `highlight_active` / `highlight_color`.
