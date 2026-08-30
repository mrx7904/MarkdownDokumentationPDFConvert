# Fix: black boxes for non-WinAnsi characters (2026-07-10)

## Symptom

Some characters rendered as black boxes (`.notdef` glyphs) in the PDF — notably the
box-drawing characters used in pipeline tree diagrams (`─ │ ├ └`) and the arrow `→`.
Umlauts, en-dash, `×`, `·`, `•` were fine.

## Root cause

Every style used the built-in ReportLab **Type1 fonts** (`Helvetica`, `Helvetica-Bold`,
`Helvetica-Oblique`, `Courier`). Those only cover the **WinAnsi** character set; any
codepoint outside it (box drawing U+2500–257F, arrows U+2192, checkmarks, …) has no glyph
and renders as `.notdef`. The Markdown was read correctly as UTF-8 — the problem was purely
the output font, not the input encoding.

## Fix

`_register_fonts()` registers Unicode-capable **TrueType** fonts *under the existing standard
names* (`Helvetica*` → DejaVuSans/Arial, `Courier` → DejaVuSansMono/Consolas), so no other
code had to change. It searches Windows and common Linux/macOS font dirs and falls back
silently to the Type1 fonts if none are found. Verified: after the fix the PDF embeds
`ArialMT`/`Consolas` subsets and all box-drawing + arrow glyphs are present.

Also fixed: `main()` now reconfigures `stdout`/`stderr` to UTF-8, because the success/error
messages use `✓`/`✗` and crashed on Windows' cp1252 console (`UnicodeEncodeError`).

## If black boxes reappear

A document may use a glyph missing from Arial/Consolas (e.g. `✓ ✗`, emoji). Options:
add a broader-coverage font to the search list in `_register_fonts()` (Windows `seguisym.ttf`
covers checkmarks), or bundle DejaVu fonts with the repo for consistent cross-platform output.
