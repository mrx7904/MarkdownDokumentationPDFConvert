"""
md_to_pdf.py – Markdown → PDF Konverter für technische Dokumentation
=====================================================================
Optimiert für Data Engineering Dokumentationen:
  • Python, SQL, Bash, YAML, JSON Code-Blöcke mit Sprachbadge
  • Tabellen (auch breite SQL-Ergebnisse)
  • Admonition-Boxen: NOTE, WARNING, TIP, IMPORTANT
  • Automatisches Inhaltsverzeichnis (TOC)
  • Deckblatt mit Metadaten
  • Kopf- und Fußzeile mit Seitenzahl

Verwendung:
    python md_to_pdf.py eingabe.md
    python md_to_pdf.py eingabe.md ausgabe.pdf \\
        --author "Marc Schubert" \\
        --subject "Data Engineering" \\
        --date "14. April 2026" \\
        --version "v1.0" \\
        --toc

Abhängigkeiten:
    pip install reportlab
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import date as dt_date

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable, KeepTogether, BaseDocTemplate,
        Frame, PageTemplate
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import Flowable
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib.sequencer import getSequencer
except ImportError:
    print("Fehler: reportlab ist nicht installiert.")
    print("Installieren mit:  pip install reportlab")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# PALETTE
# ─────────────────────────────────────────────────────────────────
C_INK       = colors.HexColor("#2d2d2d")
C_HEADING   = colors.HexColor("#3a3a3a")
C_SUBHEAD   = colors.HexColor("#555555")
C_MUTED     = colors.HexColor("#888888")
C_RULE      = colors.HexColor("#cccccc")
C_TH_BG     = colors.HexColor("#efefef")
C_TH_FG     = colors.HexColor("#333333")
C_ROW_ALT   = colors.HexColor("#f9f9f9")
C_BORDER    = colors.HexColor("#e0e0e0")
C_WHITE     = colors.white
C_PAGE_BG   = colors.HexColor("#fafafa")
C_LINK      = colors.HexColor("#2563ab")
C_CODE_BG   = colors.HexColor("#f4f4f4")
C_CODE_FG   = colors.HexColor("#333333")

# Language badge colors
LANG_COLORS = {
    "python":     ("#3572a5", "#ffffff"),
    "py":         ("#3572a5", "#ffffff"),
    "sql":        ("#e38c00", "#ffffff"),
    "bash":       ("#2d2d2d", "#ffffff"),
    "sh":         ("#2d2d2d", "#ffffff"),
    "shell":      ("#2d2d2d", "#ffffff"),
    "yaml":       ("#cb171e", "#ffffff"),
    "yml":        ("#cb171e", "#ffffff"),
    "json":       ("#000000", "#ffffff"),
    "javascript": ("#f1e05a", "#000000"),
    "js":         ("#f1e05a", "#000000"),
    "typescript": ("#2b7489", "#ffffff"),
    "ts":         ("#2b7489", "#ffffff"),
    "html":       ("#e34c26", "#ffffff"),
    "css":        ("#563d7c", "#ffffff"),
    "dockerfile": ("#384d54", "#ffffff"),
    "toml":       ("#9c4221", "#ffffff"),
    "xml":        ("#0060ac", "#ffffff"),
    "default":    ("#666666", "#ffffff"),
}

# ─────────────────────────────────────────────────────────────────
# SYNTAX HIGHLIGHTING
# ─────────────────────────────────────────────────────────────────
SH_DEFAULT   = colors.HexColor("#333333")
SH_KEYWORD   = colors.HexColor("#0000bb")
SH_STRING    = colors.HexColor("#a31515")
SH_COMMENT   = colors.HexColor("#5c8a5c")
SH_NUMBER    = colors.HexColor("#098658")
SH_BUILTIN   = colors.HexColor("#7c3aed")
SH_DECORATOR = colors.HexColor("#795e26")
SH_KEY       = colors.HexColor("#0451a5")
SH_VAR       = colors.HexColor("#1a1aaa")


def _tokenize(line, patterns):
    """Tokenize one line using ordered (compiled_regex, color) pairs."""
    result = []
    pos    = 0
    n      = len(line)
    while pos < n:
        best_m, best_col, best_start = None, SH_DEFAULT, n
        for pat, col in patterns:
            m = pat.search(line, pos)
            if m and m.start() < best_start:
                best_m, best_col, best_start = m, col, m.start()
        if best_m is None:
            result.append((line[pos:], SH_DEFAULT))
            break
        if best_start > pos:
            result.append((line[pos:best_start], SH_DEFAULT))
        result.append((best_m.group(), best_col))
        pos = best_m.end()
    return result or [(line, SH_DEFAULT)]


_PY_KW = {'False','None','True','and','as','assert','async','await','break',
           'class','continue','def','del','elif','else','except','finally',
           'for','from','global','if','import','in','is','lambda','nonlocal',
           'not','or','pass','raise','return','try','while','with','yield'}
_PY_BI = {'print','len','range','int','str','float','list','dict','set',
          'tuple','bool','type','isinstance','hasattr','getattr','setattr',
          'open','zip','map','filter','enumerate','sorted','reversed','sum',
          'min','max','abs','round','super','property','staticmethod',
          'classmethod','object','Exception','ValueError','KeyError',
          'DataFrame','Series','Path','datetime'}

_SQL_KW = {'SELECT','FROM','WHERE','JOIN','LEFT','RIGHT','INNER','OUTER',
           'CROSS','ON','GROUP','BY','ORDER','HAVING','INSERT','INTO','VALUES',
           'UPDATE','SET','DELETE','CREATE','DROP','ALTER','TABLE','VIEW',
           'INDEX','SCHEMA','DATABASE','WITH','AS','AND','OR','NOT','IN','IS',
           'NULL','DISTINCT','LIMIT','OFFSET','UNION','ALL','CASE','WHEN',
           'THEN','ELSE','END','COUNT','SUM','AVG','MAX','MIN','COALESCE',
           'CAST','CONVERT','OVER','PARTITION','ROW_NUMBER','RANK','DENSE_RANK',
           'NTILE','LAG','LEAD','PRIMARY','KEY','FOREIGN','REFERENCES',
           'CONSTRAINT','DEFAULT','EXISTS','BETWEEN','LIKE','ILIKE','TRUE',
           'FALSE','BOOLEAN','INTEGER','VARCHAR','TEXT','NUMERIC','FLOAT',
           'DATE','TIMESTAMP','INTERVAL','TRUNCATE','EXPLAIN','ANALYZE'}

_BASH_KW = {'if','then','else','elif','fi','for','while','do','done','case',
            'esac','function','return','exit','in','export','local','declare',
            'readonly','shift','source','echo','cd','ls','grep','awk','sed',
            'cat','rm','cp','mv','mkdir','chmod','chown','curl','wget','pip',
            'python','python3','set','unset'}

_JS_KW = {'const','let','var','function','return','if','else','for','while',
          'do','break','continue','class','extends','import','export','from',
          'default','new','this','super','typeof','instanceof','in','of',
          'try','catch','finally','throw','async','await','yield','switch',
          'case','null','undefined','true','false','interface','type','enum'}

_PY_PATS = [
    (re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL), SH_STRING),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),      SH_STRING),
    (re.compile(r'#.*'),                                           SH_COMMENT),
    (re.compile(r'@\w+'),                                          SH_DECORATOR),
    (re.compile(r'\b(' + '|'.join(_PY_KW) + r')\b'),             SH_KEYWORD),
    (re.compile(r'\b(' + '|'.join(_PY_BI) + r')\b'),             SH_BUILTIN),
    (re.compile(r'\b\d+\.?\d*\b'),                                 SH_NUMBER),
]
_SQL_PATS = [
    (re.compile(r"'(?:[^'\\]|\\.)*'"),                             SH_STRING),
    (re.compile(r'--.*'),                                          SH_COMMENT),
    (re.compile(r'/\*.*?\*/', re.DOTALL),                         SH_COMMENT),
    (re.compile(r'\b(' + '|'.join(_SQL_KW) + r')\b', re.I),      SH_KEYWORD),
    (re.compile(r'\b\d+\.?\d*\b'),                                 SH_NUMBER),
]
_BASH_PATS = [
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                             SH_STRING),
    (re.compile(r"'[^']*'"),                                       SH_STRING),
    (re.compile(r'#.*'),                                           SH_COMMENT),
    (re.compile(r'\$\{?\w+\}?'),                                  SH_VAR),
    (re.compile(r'\b(' + '|'.join(_BASH_KW) + r')\b'),           SH_KEYWORD),
    (re.compile(r'\b\d+\.?\d*\b'),                                 SH_NUMBER),
]
_YAML_PATS = [
    (re.compile(r'#.*'),                                           SH_COMMENT),
    (re.compile(r'\b([\w\-]+)(?=\s*:(?:\s|$))'),                  SH_KEY),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\''),                 SH_STRING),
    (re.compile(r'\b(true|false|null|yes|no|on|off)\b', re.I),   SH_KEYWORD),
    (re.compile(r'\b\d+\.?\d*\b'),                                 SH_NUMBER),
]
_JSON_PATS = [
    (re.compile(r'"(?:[^"\\]|\\.)*"(?=\s*:)'),                    SH_KEY),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                            SH_STRING),
    (re.compile(r'\b(true|false|null)\b'),                        SH_KEYWORD),
    (re.compile(r'-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b'),            SH_NUMBER),
]
_JS_PATS = [
    (re.compile(r'`(?:[^`\\]|\\.)*`'),                            SH_STRING),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),      SH_STRING),
    (re.compile(r'//.*'),                                          SH_COMMENT),
    (re.compile(r'/\*.*?\*/', re.DOTALL),                         SH_COMMENT),
    (re.compile(r'\b(' + '|'.join(_JS_KW) + r')\b'),             SH_KEYWORD),
    (re.compile(r'\b\d+\.?\d*\b'),                                 SH_NUMBER),
]

_LANG_PATS = {
    'python': _PY_PATS, 'py': _PY_PATS,
    'sql':    _SQL_PATS,
    'bash':   _BASH_PATS, 'sh': _BASH_PATS, 'shell': _BASH_PATS,
    'yaml':   _YAML_PATS, 'yml': _YAML_PATS,
    'json':   _JSON_PATS,
    'javascript': _JS_PATS, 'js': _JS_PATS,
    'typescript': _JS_PATS, 'ts': _JS_PATS,
}


def tokenize_line(line, lang):
    """Return list of (text, color) segments for a single code line."""
    pats = _LANG_PATS.get(lang)
    if not pats:
        return [(line, SH_DEFAULT)]
    return _tokenize(line, pats)

# Admonition styles
ADMONITION_STYLES = {
    "note":      ("#2563ab", "#eff6ff", "ℹ HINWEIS"),
    "info":      ("#2563ab", "#eff6ff", "ℹ INFO"),
    "tip":       ("#16a34a", "#f0fdf4", "✓ TIPP"),
    "warning":   ("#d97706", "#fffbeb", "⚠ WARNUNG"),
    "warn":      ("#d97706", "#fffbeb", "⚠ WARNUNG"),
    "important": ("#dc2626", "#fef2f2", "! WICHTIG"),
    "danger":    ("#dc2626", "#fef2f2", "! ACHTUNG"),
}

PAGE_W, PAGE_H = A4
M = 2.2 * cm


# ─────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────
def make_styles():
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        # Headings
        "h1": S("h1", fontSize=17, fontName="Helvetica-Bold",
                 textColor=C_HEADING, leading=22, spaceBefore=18, spaceAfter=4),
        "h2": S("h2", fontSize=13, fontName="Helvetica-Bold",
                 textColor=C_HEADING, leading=17, spaceBefore=14, spaceAfter=3),
        "h3": S("h3", fontSize=11, fontName="Helvetica-Bold",
                 textColor=C_SUBHEAD, leading=14, spaceBefore=10, spaceAfter=2),
        "h4": S("h4", fontSize=9.5, fontName="Helvetica-Bold",
                 textColor=C_SUBHEAD, leading=13, spaceBefore=8, spaceAfter=2),
        # Body
        "body":   S("body",   fontSize=9,  fontName="Helvetica",
                    textColor=C_INK, leading=14, spaceAfter=5),
        "italic": S("italic", fontSize=9,  fontName="Helvetica-Oblique",
                    textColor=C_MUTED, leading=13, spaceAfter=4),
        "bq":     S("bq",    fontSize=9,  fontName="Helvetica-Oblique",
                    textColor=C_SUBHEAD, leading=13, spaceAfter=4,
                    leftIndent=12, borderPadding=(0, 0, 0, 8)),
        # Lists
        "li":   S("li",   fontSize=9, fontName="Helvetica",
                   textColor=C_INK, leading=13, spaceAfter=2, leftIndent=14),
        "li2":  S("li2",  fontSize=9, fontName="Helvetica",
                   textColor=C_INK, leading=13, spaceAfter=2, leftIndent=28),
        # Code
        "code_line": S("code_line", fontSize=7.5, fontName="Courier",
                        textColor=C_CODE_FG, leading=11),
        "lang_badge": S("lang_badge", fontSize=7, fontName="Helvetica-Bold",
                         textColor=C_WHITE, leading=9),
        # Table
        "th":  S("th",  fontSize=8,   fontName="Helvetica-Bold",
                  textColor=C_TH_FG, alignment=TA_CENTER),
        "td":  S("td",  fontSize=8,   fontName="Helvetica",
                  textColor=C_INK, leading=10),
        "tdc": S("tdc", fontSize=8,   fontName="Helvetica",
                  textColor=C_INK, leading=10, alignment=TA_CENTER),
        "tdr": S("tdr", fontSize=8,   fontName="Helvetica",
                  textColor=C_INK, leading=10, alignment=TA_RIGHT),
        # Admonition
        "adm_title": S("adm_title", fontSize=8,   fontName="Helvetica-Bold",
                        textColor=C_WHITE, leading=10),
        "adm_body":  S("adm_body",  fontSize=8.5, fontName="Helvetica",
                        textColor=C_INK, leading=12),
        # TOC
        "toc1": S("toc1", fontSize=10, fontName="Helvetica-Bold",
                   textColor=C_HEADING, leading=14, spaceBefore=4),
        "toc2": S("toc2", fontSize=9, fontName="Helvetica",
                   textColor=C_INK, leading=13, leftIndent=14),
        "toc3": S("toc3", fontSize=8.5, fontName="Helvetica",
                   textColor=C_MUTED, leading=12, leftIndent=28),
        # Footer
        "footer": S("footer", fontSize=7.5, fontName="Helvetica",
                     textColor=C_MUTED, alignment=TA_CENTER, leading=10),
    }


# ─────────────────────────────────────────────────────────────────
# COVER PAGE
# ─────────────────────────────────────────────────────────────────
class Cover(Flowable):
    def __init__(self, title, subtitle="", meta=None):
        Flowable.__init__(self)
        self.title    = title
        self.subtitle = subtitle
        self.meta     = meta or []
        self.width    = PAGE_W - 2*M
        self.height   = 735

    def draw(self):
        c = self.canv
        h = self.height
        # Background
        c.setFillColor(C_PAGE_BG)
        c.rect(-M, 0, PAGE_W, h, fill=1, stroke=0)
        # Left accent bar
        c.setFillColor(C_RULE)
        c.rect(0, h * 0.25, 2, h * 0.55, fill=1, stroke=0)

        # Title (wrap if needed)
        title = self.title
        c.setFillColor(C_HEADING)
        if len(title) <= 36:
            c.setFont("Helvetica-Bold", 30)
            c.drawString(0.5*cm, h * 0.68, title)
            title_bottom = h * 0.68
        else:
            # Split into two lines
            words = title.split()
            mid   = len(words) // 2
            l1 = " ".join(words[:mid])
            l2 = " ".join(words[mid:])
            c.setFont("Helvetica-Bold", 26)
            c.drawString(0.5*cm, h * 0.71, l1)
            c.drawString(0.5*cm, h * 0.665, l2)
            title_bottom = h * 0.665

        # Subtitle
        if self.subtitle:
            c.setFillColor(C_SUBHEAD)
            c.setFont("Helvetica", 14)
            c.drawString(0.5*cm, title_bottom - 0.7*cm, self.subtitle)
            div_y = title_bottom - 1.05*cm
        else:
            div_y = title_bottom - 0.55*cm

        # Divider
        c.setStrokeColor(C_RULE)
        c.setLineWidth(0.8)
        c.line(0.5*cm, div_y, self.width, div_y)

        # Meta block
        y = div_y - 0.6*cm
        for label, val in self.meta:
            c.setFillColor(C_MUTED)
            c.setFont("Helvetica", 8.5)
            c.drawString(0.5*cm, y, label)
            c.setFillColor(C_INK)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(4.2*cm, y, val)
            y -= 0.52*cm

        # Bottom note
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(self.width / 2, h * 0.04,
                            "Erstellt mit md_to_pdf.py")


# ─────────────────────────────────────────────────────────────────
# CODE BLOCK with language badge
# ─────────────────────────────────────────────────────────────────
class CodeBlock(Flowable):
    """Renders a fenced code block with an optional language badge."""

    BADGE_H  = 16
    PAD      = 6

    def __init__(self, code, lang=""):
        Flowable.__init__(self)
        self.code  = code
        self.lang  = lang.lower().strip()
        self.lines = code.split("\n")

        # Measure
        self._font_size = 7.5
        self._line_h    = 11
        avail_w = PAGE_W - 2*M
        self.width = avail_w

        # Content height = lines * line_h + top/bottom padding + badge
        content_h   = len(self.lines) * self._line_h
        badge_h     = self.BADGE_H if self.lang else 0
        self.height = content_h + badge_h + self.PAD * 2

    def draw(self):
        c      = self.canv
        w      = self.width
        h      = self.height
        badge_h = self.BADGE_H if self.lang else 0

        # Background rect
        bg = colors.HexColor("#f4f4f4")
        c.setFillColor(bg)
        c.roundRect(0, 0, w, h, 4, fill=1, stroke=0)

        # Border
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 4, fill=0, stroke=1)

        # Language badge
        if self.lang:
            bg_col, fg_col = LANG_COLORS.get(self.lang, LANG_COLORS["default"])
            c.setFillColor(colors.HexColor(bg_col))
            c.roundRect(0, h - badge_h, w, badge_h, 4, fill=1, stroke=0)
            # Square off bottom corners of badge
            c.rect(0, h - badge_h, w, badge_h / 2, fill=1, stroke=0)
            c.setFillColor(colors.HexColor(fg_col))
            c.setFont("Helvetica-Bold", 7)
            c.drawString(self.PAD, h - badge_h + 4, self.lang.upper())

        # Code lines with syntax highlighting
        c.setFont("Courier", self._font_size)
        content_top = h - badge_h - self.PAD
        for idx, line in enumerate(self.lines):
            y = content_top - (idx + 1) * self._line_h + 2
            # Clip long lines visually
            max_chars = int((w - self.PAD * 2) / (self._font_size * 0.6))
            if len(line) > max_chars:
                line = line[:max_chars] + "…"
            # Draw syntax-highlighted segments
            segments = tokenize_line(line, self.lang)
            x = self.PAD
            for seg_text, seg_color in segments:
                if not seg_text:
                    continue
                c.setFillColor(seg_color)
                c.drawString(x, y, seg_text)
                x += c.stringWidth(seg_text, "Courier", self._font_size)


# ─────────────────────────────────────────────────────────────────
# ADMONITION BOX
# ─────────────────────────────────────────────────────────────────
class Admonition(Flowable):
    PAD = 8

    def __init__(self, kind, text, styles):
        Flowable.__init__(self)
        self.kind   = kind.lower()
        self.text   = text
        self.styles = styles

        border_c, bg_c, label = ADMONITION_STYLES.get(
            self.kind, ADMONITION_STYLES["note"])
        self._border_c = colors.HexColor(border_c)
        self._bg_c     = colors.HexColor(bg_c)
        self._label    = label

        self.width  = PAGE_W - 2*M
        # Estimate height: title row + body lines
        body_lines = max(1, len(text) // 80 + text.count("\n") + 1)
        self.height = 18 + body_lines * 14 + self.PAD * 2

    def draw(self):
        c   = self.canv
        w   = self.width
        h   = self.height
        p   = self.PAD

        # Background
        c.setFillColor(self._bg_c)
        c.roundRect(0, 0, w, h, 4, fill=1, stroke=0)
        # Left accent stripe
        c.setFillColor(self._border_c)
        c.rect(0, 0, 3, h, fill=1, stroke=0)
        # Title bar
        c.rect(0, h - 18, w, 18, fill=1, stroke=0)
        # Round top corners of title bar
        c.roundRect(0, h - 18, w, 18, 4, fill=1, stroke=0)

        # Label text
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(p + 3, h - 13, self._label)

        # Body text – simple line wrap
        c.setFillColor(C_INK)
        c.setFont("Helvetica", 8.5)
        chars_per_line = int((w - p * 2 - 3) / 5.1)
        words  = self.text.split()
        lines  = []
        cur    = ""
        for word in words:
            if len(cur) + len(word) + 1 <= chars_per_line:
                cur += (" " if cur else "") + word
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)

        y = h - 18 - p - 10
        for line in lines:
            c.drawString(p + 3, y, line)
            y -= 12


# ─────────────────────────────────────────────────────────────────
# TOC-FÄHIGES DOKUMENT-TEMPLATE
# ─────────────────────────────────────────────────────────────────
class TocDocTemplate(BaseDocTemplate):
    """
    BaseDocTemplate mit afterFlowable-Callback, der Überschriften
    automatisch beim TableOfContents-Widget registriert und so echte
    Seitenzahlen im Inhaltsverzeichnis erzeugt.
    """

    def __init__(self, filename, hf_func, **kwargs):
        BaseDocTemplate.__init__(self, filename, **kwargs)
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id='normal'
        )
        self.addPageTemplates([
            PageTemplate(id='main', frames=[frame], onPage=hf_func)
        ])

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        lvl = {'h1': 0, 'h2': 1, 'h3': 2}.get(flowable.style.name)
        if lvl is not None:
            self.notify('TOCEntry', (lvl, flowable.getPlainText(), self.page))


# ─────────────────────────────────────────────────────────────────
# HEADER / FOOTER
# ─────────────────────────────────────────────────────────────────
def make_hf(header_left, header_right="", footer_left="", footer_right=""):
    """
    header_left  – Kopfzeile links:  Thema / Dokumenttitel (Navigation)
    header_right – Kopfzeile rechts: Autor · Version
    footer_left  – Fußzeile links:   Datum
    footer_right – Fußzeile rechts:  Firma
    """
    def hf(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(C_RULE)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7.5)
        # ── Kopfzeile ───────────────────────────────────────────
        canvas.line(M, h - 1.1*cm, w - M, h - 1.1*cm)
        canvas.drawString(M, h - 0.85*cm, header_left)
        if header_right:
            canvas.drawRightString(w - M, h - 0.85*cm, header_right)
        # ── Fußzeile ────────────────────────────────────────────
        canvas.line(M, 1.1*cm, w - M, 1.1*cm)
        if footer_left:
            canvas.drawString(M, 0.7*cm, footer_left)
        canvas.drawCentredString(w / 2, 0.7*cm, f"– {doc.page} –")
        if footer_right:
            canvas.drawRightString(w - M, 0.7*cm, footer_right)
        canvas.restoreState()
    return hf


# ─────────────────────────────────────────────────────────────────
# INLINE MARKDOWN → REPORTLAB XML
# ─────────────────────────────────────────────────────────────────
def inline_md(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold + italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_',   r'<i>\1</i>', text)
    # Inline code
    text = re.sub(
        r'`(.+?)`',
        r'<font face="Courier" size="8" color="#444444">\1</font>', text)
    # Links [text](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: (f'<link href="{m.group(2)}">'
                   f'<u><font color="#2563ab">{m.group(1)}</font></u></link>'),
        text)
    # Bare URLs
    text = re.sub(
        r'(?<![">])(https?://\S+)',
        lambda m: (f'<link href="{m.group(1)}">'
                   f'<u><font color="#2563ab">{m.group(1)}</font></u></link>'),
        text)
    return text


# ─────────────────────────────────────────────────────────────────
# MARKDOWN TABLE → REPORTLAB TABLE
# ─────────────────────────────────────────────────────────────────
def parse_table(lines, styles):
    rows       = []
    alignments = []

    for line in lines:
        stripped = line.strip().strip("|")
        # Separator row – detect alignment
        if re.match(r'^[\s|:\-]+$', stripped):
            for cell in stripped.split("|"):
                cell = cell.strip()
                if cell.startswith(":") and cell.endswith(":"):
                    alignments.append("center")
                elif cell.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")
            continue
        rows.append([c.strip() for c in stripped.split("|")])

    if not rows:
        return None

    n_cols = max(len(r) for r in rows)
    if not alignments:
        alignments = ["left"] * n_cols

    avail_w = PAGE_W - 2*M
    col_w   = [avail_w / n_cols] * n_cols

    data = []
    for i, row in enumerate(rows):
        while len(row) < n_cols:
            row.append("")
        if i == 0:
            data.append([Paragraph(inline_md(c), styles["th"]) for c in row])
        else:
            cells = []
            for j, c in enumerate(row):
                align = alignments[j] if j < len(alignments) else "left"
                st    = {"center": "tdc", "right": "tdr"}.get(align, "td")
                cells.append(Paragraph(inline_md(c), styles[st]))
            data.append(cells)

    ts = TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C_TH_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_BORDER),
        ("LINEBELOW",      (0, 0), (-1, 0),  0.6, C_RULE),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ])
    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(ts)
    return t


# ─────────────────────────────────────────────────────────────────
# MAIN PARSER: MARKDOWN → STORY
# ─────────────────────────────────────────────────────────────────
def md_to_story(md_text, styles, include_toc=False):
    story    = []
    lines    = md_text.splitlines()
    headings = []   # (level, text) for TOC
    i        = 0

    def rule():
        return HRFlowable(width="100%", thickness=0.5,
                          color=C_RULE, spaceAfter=4, spaceBefore=2)

    # ── TOC placeholder ─────────────────────────────────────────
    if include_toc:
        toc = TableOfContents()
        toc.levelStyles = [styles["toc1"], styles["toc2"], styles["toc3"]]
        story.append(Paragraph("Inhaltsverzeichnis", styles["h2"]))
        story.append(rule())
        story.append(toc)
        story.append(PageBreak())

    # ── Line-by-line parse ───────────────────────────────────────
    while i < len(lines):
        line = lines[i]

        # ── Page break ──────────────────────────────────────────
        if re.match(r'<!--\s*pagebreak\s*-->', line, re.IGNORECASE):
            story.append(PageBreak())
            i += 1
            continue

        # ── Horizontal rule ─────────────────────────────────────
        if re.match(r'^[-*_]{3,}\s*$', line):
            story.append(rule())
            i += 1
            continue

        # ── Admonition: > [!NOTE] text ──────────────────────────
        # Supports: > [!NOTE], > [!WARNING], > [!TIP], > [!IMPORTANT]
        adm_match = re.match(r'^>\s*\[!(NOTE|INFO|TIP|WARNING|WARN|IMPORTANT|DANGER)\](.*)',
                              line, re.IGNORECASE)
        if adm_match:
            kind      = adm_match.group(1).lower()
            first_txt = adm_match.group(2).strip()
            body_lines = [first_txt] if first_txt else []
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                body_lines.append(lines[i].lstrip("> ").strip())
                i += 1
            story.append(Admonition(kind, " ".join(body_lines), styles))
            story.append(Spacer(1, 6))
            continue

        # ── Blockquote (non-admonition) ──────────────────────────
        if line.startswith(">"):
            bq_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                bq_lines.append(lines[i].lstrip("> ").strip())
                i += 1
            story.append(Paragraph(inline_md(" ".join(bq_lines)), styles["bq"]))
            continue

        # ── Fenced code block ````lang` ──────────────────────────
        fence_m = re.match(r'^```(\w*)', line)
        if fence_m:
            lang       = fence_m.group(1).lower()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            # Remove common leading whitespace
            if code_lines:
                min_indent = min(
                    (len(l) - len(l.lstrip()) for l in code_lines if l.strip()),
                    default=0)
                code_lines = [l[min_indent:] for l in code_lines]
            story.append(CodeBlock("\n".join(code_lines), lang))
            story.append(Spacer(1, 6))
            continue

        # ── Table ────────────────────────────────────────────────
        if line.startswith("|"):
            tbl_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                tbl_lines.append(lines[i])
                i += 1
            t = parse_table(tbl_lines, styles)
            if t:
                story.append(t)
                story.append(Spacer(1, 6))
            continue

        # ── Headings ─────────────────────────────────────────────
        h_match = re.match(r'^(#{1,4})\s+(.*)', line)
        if h_match:
            level = len(h_match.group(1))
            text  = h_match.group(2).strip()
            skey  = f"h{min(level, 4)}"

            # Anchor for TOC
            anchor = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
            rl_text = f'<a name="{anchor}"/>{inline_md(text)}'

            p = Paragraph(rl_text, styles[skey])
            if level <= 2:
                story.append(p)
                story.append(rule())
            else:
                story.append(p)

            if include_toc and level <= 3:
                story[-1 if level > 2 else -2].keepWithNext = True
                headings.append((level, text, anchor))

            i += 1
            continue

        # ── Unordered list ───────────────────────────────────────
        li_m = re.match(r'^(\s*)[-*+]\s+(.*)', line)
        if li_m:
            indent = len(li_m.group(1))
            skey   = "li2" if indent >= 2 else "li"
            bullet = "◦" if indent >= 2 else "•"
            story.append(Paragraph(f"{bullet}  {inline_md(li_m.group(2))}",
                                   styles[skey]))
            i += 1
            continue

        # ── Ordered list ─────────────────────────────────────────
        ol_m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if ol_m:
            indent = len(ol_m.group(1))
            skey   = "li2" if indent >= 2 else "li"
            story.append(Paragraph(f"•  {inline_md(ol_m.group(2))}",
                                   styles[skey]))
            i += 1
            continue

        # ── Empty line ───────────────────────────────────────────
        if not line.strip():
            story.append(Spacer(1, 4))
            i += 1
            continue

        # ── Normal paragraph (collect continuation lines) ────────
        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if (not nxt.strip()
                    or nxt.startswith("#")
                    or nxt.startswith("|")
                    or nxt.startswith("```")
                    or nxt.startswith(">")
                    or re.match(r'^[-*+]\s', nxt)
                    or re.match(r'^\d+\.\s', nxt)
                    or re.match(r'^[-*_]{3,}\s*$', nxt)
                    or re.match(r'<!--\s*pagebreak', nxt, re.IGNORECASE)):
                break
            para_lines.append(nxt)
            i += 1

        story.append(Paragraph(inline_md(" ".join(para_lines)), styles["body"]))

    return story, headings


# ─────────────────────────────────────────────────────────────────
# YAML FRONTMATTER
# ─────────────────────────────────────────────────────────────────
def parse_frontmatter(md_text):
    """
    Liest optionalen YAML-Frontmatter am Dateianfang:

        ---
        title:   Mein Dokument
        author:  Marc Schubert
        subject: Data Engineering
        version: v1.0
        date:    12. April 2026
        company: Alsco GmbH · Data Engineering
        toc:     true
        cover:   true
        ---

    Gibt (meta_dict, rest_text) zurück.
    Bekannte boolesche Felder: toc, cover.
    """
    md_text = md_text.lstrip()
    if not md_text.startswith("---"):
        return {}, md_text

    end = md_text.find("\n---", 3)
    if end == -1:
        return {}, md_text

    fm_block  = md_text[3:end].strip()
    remaining = md_text[end + 4:].lstrip("\n")

    meta = {}
    for line in fm_block.splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip().strip('"').strip("'")
        if val.lower() in ("true", "yes"):
            val = True
        elif val.lower() in ("false", "no"):
            val = False
        meta[key] = val

    return meta, remaining


# ─────────────────────────────────────────────────────────────────
# DOCUMENT BUILD
# ─────────────────────────────────────────────────────────────────
def convert(md_path, pdf_path, title=None, author=None, subject=None,
            date_str=None, version=None, cover=True, include_toc=False,
            header_left=None, company=None):

    md_text = Path(md_path).read_text(encoding="utf-8")
    styles  = make_styles()

    # ── Frontmatter auslesen ─────────────────────────────────────
    fm, md_text = parse_frontmatter(md_text)

    # CLI-Argumente haben Vorrang; Frontmatter ist Fallback
    # cover / toc aus Frontmatter nur übernehmen wenn nicht explizit per CLI gesetzt
    if "toc" in fm and include_toc is False:
        include_toc = fm["toc"]
    if "cover" in fm and cover is True:
        cover = fm["cover"]

    # Auto-detect title from first H1
    auto_title = Path(md_path).stem.replace("_", " ").replace("-", " ").title()
    h1_match   = re.search(r'^#\s+(.+)', md_text, re.MULTILINE)
    if h1_match:
        auto_title = h1_match.group(1).strip()
        md_text    = md_text[:h1_match.start()] + md_text[h1_match.end():]

    doc_title   = title    or fm.get("title")   or auto_title
    doc_author  = author   or fm.get("author")  or ""
    doc_subject = subject  or fm.get("subject") or ""
    doc_date    = date_str or fm.get("date")    or dt_date.today().strftime("%d. %B %Y")
    doc_version = version  or fm.get("version") or ""
    company     = company  or fm.get("company") or ""

    # Cover meta
    cover_meta = []
    if doc_author:
        cover_meta.append(("Autor", doc_author))
    if doc_subject:
        cover_meta.append(("Thema", doc_subject))
    if doc_version:
        cover_meta.append(("Version", doc_version))
    cover_meta.append(("Datum", doc_date))

    # Kopf- und Fußzeilen-Texte zusammenbauen
    hl = header_left or doc_subject or doc_title
    hr = "  ·  ".join(filter(None, [doc_author, doc_version]))
    # Fußzeile links: Datum  |  Fußzeile rechts: Firma (falls gesetzt)
    fr = doc_date

    # Build story
    body_story, headings = md_to_story(md_text.strip(), styles, include_toc)

    story = []
    if cover:
        story.append(Cover(doc_title, doc_subject, cover_meta))
        story.append(PageBreak())
    story.extend(body_story)

    hf = make_hf(hl, hr, fr, company or "")

    doc_kwargs = dict(
        pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=1.7*cm, bottomMargin=1.5*cm,
        title=doc_title, author=doc_author, subject=doc_subject,
    )

    if include_toc:
        # TocDocTemplate registriert Überschriften via afterFlowable;
        # multiBuild läuft zweimal durch um Seitenzahlen aufzulösen.
        doc = TocDocTemplate(str(pdf_path), hf_func=hf, **doc_kwargs)
        doc.multiBuild(story)
    else:
        doc = SimpleDocTemplate(str(pdf_path), **doc_kwargs)
        doc.build(story, onFirstPage=hf, onLaterPages=hf)

    print(f"✓  PDF erstellt: {pdf_path}")


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Markdown → PDF Konverter für technische Dokumentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Verwendung:
  python md_to_pdf.py                          # alle *.md im aktuellen Verzeichnis
  python md_to_pdf.py ./docs/                  # alle *.md in einem Verzeichnis
  python md_to_pdf.py pipeline_doku.md         # einzelne Datei
  python md_to_pdf.py pipeline_doku.md out.pdf # einzelne Datei mit Ausgabepfad
      --author "Marc Schubert" --subject "Data Engineering"
      --date "12. April 2026" --version "v1.2" --toc

Admonition-Syntax:
  > [!NOTE] Hinweis    > [!WARNING] Warnung
  > [!TIP] Tipp        > [!IMPORTANT] Wichtig

Seitenumbruch:  <!--pagebreak-->
        """
    )
    parser.add_argument("input",  nargs="?",
                        help="Markdown-Datei (.md) oder Verzeichnis "
                             "(Standard: aktuelles Verzeichnis)")
    parser.add_argument("output", nargs="?",
                        help="Ausgabe-PDF (nur bei einzelner Eingabedatei)")
    parser.add_argument("--title",        help="Dokumenttitel")
    parser.add_argument("--author",       help="Autor")
    parser.add_argument("--subject",      help="Thema / Modul / Kurs")
    parser.add_argument("--date",         help='Datum, z.B. "12. April 2026"')
    parser.add_argument("--version",      help='Version, z.B. "v1.0"')
    parser.add_argument("--toc",          action="store_true",
                        help="Inhaltsverzeichnis einfügen")
    parser.add_argument("--no-cover",     action="store_true",
                        help="Kein Deckblatt erstellen")
    parser.add_argument("--header-left",  help="Linker Kopfzeilen-Text (Standard: Thema oder Titel)")
    parser.add_argument("--company",      help='Firmenangabe in der Fußzeile rechts, '
                                               'z.B. "Alsco GmbH · Data Engineering"')
    args = parser.parse_args()

    # ── Determine input mode ─────────────────────────────────────
    in_path = Path(args.input) if args.input else Path(".")

    def _run(md_file, pdf_file):
        convert(
            md_path     = md_file,
            pdf_path    = pdf_file,
            title       = args.title,
            author      = args.author,
            subject     = args.subject,
            date_str    = args.date,
            version     = args.version,
            cover       = not args.no_cover,
            include_toc = args.toc,
            header_left = args.header_left,
            company     = args.company,
        )

    if in_path.is_dir():
        # ── Batch mode: convert all *.md files in directory ──────
        md_files = sorted(in_path.glob("*.md"))
        if not md_files:
            print(f"Keine .md Dateien gefunden in: {in_path.resolve()}")
            sys.exit(0)
        print(f"Gefunden: {len(md_files)} Markdown-Datei(en) in {in_path.resolve()}")
        ok, fail = 0, 0
        for md_file in md_files:
            try:
                _run(md_file, md_file.with_suffix(".pdf"))
                ok += 1
            except Exception as exc:
                print(f"✗  Fehler bei {md_file.name}: {exc}")
                fail += 1
        print(f"\nFertig: {ok} erfolgreich" + (f", {fail} fehlgeschlagen" if fail else ""))
    else:
        # ── Single file mode ─────────────────────────────────────
        if not in_path.exists():
            print(f"Fehler: Datei nicht gefunden: {in_path}")
            sys.exit(1)
        if in_path.suffix.lower() != ".md":
            print(f"Fehler: Erwartet eine .md Datei, erhalten: {in_path}")
            sys.exit(1)
        out_path = Path(args.output) if args.output else in_path.with_suffix(".pdf")
        _run(in_path, out_path)


if __name__ == "__main__":
    main()
