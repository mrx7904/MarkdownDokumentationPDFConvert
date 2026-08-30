# markdown-pdf-convert

## Purpose

Standalone Markdown → PDF converter for technical documentation. A single ReportLab-based
Python script (`md_to_pdf.py`) renders `.md` files into styled A4 PDFs with cover page,
table of contents, syntax-highlighted code blocks, tables and admonition boxes.
This is the vault's reference tool for turning documentation into shareable PDFs — see
the `markdown-to-pdf` skill and `knowledge/documentation-format.md` in the vault root.

## Status

active (branch `main`) · single-file tool, no framework churn expected.

## Tech & conventions

- Stack: Python 3, single dependency `reportlab` (see `requirements.txt`).
- Setup: `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
- Run (single file): `python md_to_pdf.py input.md [output.pdf] [options]`
- Run (batch): `python md_to_pdf.py ./docs/` — converts every `*.md` in the directory.
- No test suite; verify by converting a sample `.md` and inspecting the PDF.

## Supported Markdown features

- Headings, inline formatting (bold/italic/`code`/links)
- Fenced code blocks with language badge + syntax highlighting
  (python, sql, bash, yaml, json, js/ts, html, css, dockerfile, toml, xml, …)
- Tables (including wide SQL result tables)
- Admonitions: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!IMPORTANT]` (also INFO/WARN/DANGER)
- Blockquotes, horizontal rules
- Manual page break marker: `<!--pagebreak-->`
- Auto TOC (`--toc`), cover page with metadata (`--no-cover` to disable)
- Header/footer with page numbers (`--header-left`, `--company`)

## CLI options

`--title --author --subject --date --version --toc --no-cover --header-left --company`

## Rules for agents

1. Read this file before making any changes in this project.
2. Record significant decisions, learnings and post-mortems in `knowledge/` (one file per topic).
3. Keep it a single-file tool with a single dependency unless there's a strong reason to add more.
4. When a documentation feature can't be rendered, prefer extending the converter over
   telling authors to avoid the Markdown syntax — all docs in the vault are `.md` and should
   round-trip through this tool (see vault `knowledge/documentation-format.md`).

## Key paths

| Path | What it is |
|---|---|
| `md_to_pdf.py` | the entire converter (CLI + rendering) |
| `requirements.txt` | single dependency: `reportlab` |
| `data_engineering_pipeline.md` | sample/reference input document |
| `knowledge/` | decisions, learnings, post-mortems for this project |

> Note: the GitHub remote still points at the original repo name
> `MarkdownDokumentationPDFConvert`; only the local folder was renamed to `markdown-pdf-convert`.
