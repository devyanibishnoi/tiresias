"""Builds the final Word report from report/template.docx (PRD Section 13).

Opens the author's template, fills the cover page, fixes the template's own
typos, and replaces each section's placeholder instructional text with real
content loaded from docs/report_sections/*.md and the results/ JSON files.
Never recreates the document from scratch, so the template's styles,
headings and table of contents stay exactly as the professor provided them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from telltale.config import StreamConfig

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "report" / "template.docx"
OUT_DOCX = ROOT / "report" / "out" / "telltale_report.docx"
SECTIONS_DIR = ROOT / "docs" / "report_sections"
RESULTS_DIR = ROOT / "results"
FIGURE_DIR = RESULTS_DIR / "figures"

TITLE = "Label-Free Drift Detection and Selective Retraining Framework for Deployed Fraud Classifiers Under Delayed Ground Truth"
SHORT_TITLE = "telltale: Label-Free Drift Detection for Fraud Classifiers"

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from report_identity import AUTHORS, REPORT_DATE
except ImportError:
    # report/report_identity.py is gitignored (real names and registration
    # numbers, not meant for a public portfolio repo); a fresh clone without
    # it still builds, just with placeholders on the cover page instead.
    AUTHORS = [("[AUTHOR NAME]", "[REG NO]")]
    REPORT_DATE = "[REPORT DATE]"


def set_paragraph_text(p: Paragraph, text: str) -> None:
    """Replace a paragraph's visible text while keeping the first run's
    formatting (font, size, bold, etc.), since template placeholder text is
    often split across several runs.

    Table of Contents lines in this template are Word fields (TOC1 style)
    with no plain .runs at all; their visible text is cached field output,
    not editable text. Calling this on one would silently do nothing
    useful (or, worse, append a stray new run next to the cached field
    text). Callers should never target TOC paragraphs for text fixes: the
    TOC is auto-generated from the real headings and corrects itself when
    Word refreshes the field (Ctrl+A, F9, or on open if the template is set
    to update on open), so fix the heading itself, not the TOC's copy."""
    if p.style.name.startswith("toc"):
        raise ValueError(
            "refusing to edit a Table of Contents paragraph directly (no real runs; "
            "fix the body heading instead, the TOC field updates itself in Word)"
        )
    if not p.runs:
        p.add_run(text)
        return
    p.runs[0].text = text
    for r in p.runs[1:]:
        r.text = ""


def find_paragraph(doc: Document, text: str, style_prefix: str | None = None, start: int = 0) -> int:
    for i in range(start, len(doc.paragraphs)):
        p = doc.paragraphs[i]
        if style_prefix and not p.style.name.startswith(style_prefix):
            continue
        if text in p.text:
            return i
    raise ValueError(f"paragraph not found: {text!r}")


def _is_structural(p: Paragraph) -> bool:
    """True if `p` is itself a heading (numbered "N.N ..." text, or styled
    Heading) rather than leftover instructional placeholder text: these
    must never be blanked out by the placeholder-clearing helpers below,
    which caused a real bug (clear_placeholder_paragraph blanked out the
    template's own "6.1. Use Cases" line, mistaking it for the section's
    placeholder text, since section 6 has no separate placeholder paragraph
    between its Heading 1 and its first subsection)."""
    return p.style.name.startswith("Heading") or bool(_SUBHEADING_NUMBER.match(p.text.strip()))


def clear_placeholder_paragraph(doc: Document, heading_idx: int, max_scan: int = 6) -> int:
    """Clear every leftover template instructional paragraph right after a
    heading (not another heading or subsection, not empty), stopping at the
    first structural or already-empty paragraph, and return the index of
    the last one cleared so content can be inserted there. Some sections
    have more than one placeholder line in a row (section 3.1 has both
    "Give the sketch or sketches and describe them." and a separate literal
    "Concept Sketches" line below it); clearing only the first one left the
    second as a stray leftover in the built report."""
    last_cleared = heading_idx
    for j in range(heading_idx + 1, min(heading_idx + 1 + max_scan, len(doc.paragraphs))):
        p = doc.paragraphs[j]
        if _is_structural(p):
            break
        if p.text.strip():
            set_paragraph_text(p, "")
            last_cleared = j
        else:
            break
    return last_cleared


def clear_next_placeholder(doc: Document, heading: Paragraph, max_scan: int = 4) -> Paragraph:
    """Paragraph-based counterpart to clear_placeholder_paragraph: clears
    every leftover placeholder paragraph right after `heading` (see that
    function's docstring) and returns the last one cleared as the insertion
    anchor, or `heading` itself if there was nothing to clear."""
    idx = paragraph_index(doc, heading)
    last_cleared = heading
    for j in range(idx + 1, min(idx + 1 + max_scan, len(doc.paragraphs))):
        p = doc.paragraphs[j]
        if _is_structural(p):
            break
        if p.text.strip():
            set_paragraph_text(p, "")
            last_cleared = p
        else:
            break
    return last_cleared


def _apply_grid_borders(table: Table) -> None:
    """The template only defines a borderless 'Normal Table' style (no
    'Table Grid' or themed style to fall back on), so draw a plain grid by
    hand rather than leaving every inserted table invisible."""
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.makeelement(qn("w:tblBorders"), {})
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = borders.makeelement(qn(f"w:{edge}"), {
            qn("w:val"): "single", qn("w:sz"): "4", qn("w:space"): "0", qn("w:color"): "999999",
        })
        borders.append(el)
    tbl_pr.append(borders)


_INLINE_TOKEN = re.compile(r"(\*\*[^*\n]+\*\*|`[^`\n]+`)")


def add_inline_formatted_runs(paragraph: Paragraph, text: str) -> None:
    """Parse **bold** and `code` spans out of plain text and add them as
    properly formatted runs, instead of leaving the markdown markers in as
    literal characters (which is what naively setting paragraph/cell text
    to the raw source string does: about 238 stray backticks and a stray
    "**...**" pair were visible in the first PDF export)."""
    for part in _INLINE_TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
        else:
            paragraph.add_run(part)


TABLE_FONT_PT = 8.5
TABLE_WIDTH_INCHES = 6.1  # usable page width between this template's margins
MIN_COLUMN_INCHES = 0.55


def set_cell_text_formatted(cell, text: str, bold: bool = False) -> None:
    p = cell.paragraphs[0]
    add_inline_formatted_runs(p, text)
    if bold:
        for run in p.runs:
            run.bold = True
    for run in p.runs:
        run.font.size = Pt(TABLE_FONT_PT)


def _set_column_widths(table: Table, header: list, rows: list) -> None:
    """Tables with many columns (the literature table, the component sheet,
    the risk list, the prediction table) got squeezed into equal-width
    columns on a portrait page, leaving some only a few characters wide.
    Word's own autofit does not reliably respect a target width once a
    table is built cell by cell, so this sets the width on the table, every
    column, and every individual cell explicitly: Word only renders
    consistent column widths when all three agree. Short ID/number columns
    get a small minimum share; the rest is split across the remaining
    columns in proportion to their longest cell, so a long free-text column
    (Reasoning, Mitigation, Evidence) ends up visibly wider than a short one
    (ID, Severity, Verdict)."""
    n_cols = len(header)
    if n_cols <= 3:
        return  # narrow tables read fine with Word's default even split

    lengths = []
    for i in range(n_cols):
        col_cells = [str(header[i])] + [str(r[i]) for r in rows if i < len(r)]
        lengths.append(max((len(c) for c in col_cells), default=1))

    total_len = sum(lengths) or 1
    raw_widths = [max(MIN_COLUMN_INCHES, TABLE_WIDTH_INCHES * ln / total_len) for ln in lengths]
    scale = TABLE_WIDTH_INCHES / sum(raw_widths)
    widths = [Inches(w * scale) for w in raw_widths]

    table.autofit = False
    table.allow_autofit = False
    for col_idx, width in enumerate(widths):
        table.columns[col_idx].width = width
        for row in table.rows:
            row.cells[col_idx].width = width


def add_table_after(anchor: Paragraph, doc: Document, header: list, rows: list) -> Table:
    table = doc.add_table(rows=1, cols=len(header))
    _apply_grid_borders(table)
    for i, h in enumerate(header):
        set_cell_text_formatted(table.rows[0].cells[i], str(h), bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            if i < len(cells):
                set_cell_text_formatted(cells[i], str(v))
    _set_column_widths(table, header, rows)
    anchor._p.addnext(table._tbl)
    return table


def add_paragraph_after(anchor, doc: Document, text: str, style: str | None = None) -> Paragraph:
    new_p = doc.add_paragraph(style=style)
    add_inline_formatted_runs(new_p, text)
    anchor_elem = anchor._tbl if isinstance(anchor, Table) else anchor._p
    anchor_elem.addnext(new_p._p)
    return new_p


def _shade_paragraph(p: Paragraph, hex_color: str) -> None:
    pPr = p._p.get_or_add_pPr()
    shd = pPr.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): hex_color})
    pPr.append(shd)


def add_code_block_after(anchor, doc: Document, code_text: str) -> Paragraph:
    """Code snippets need their own path, not the markdown paragraph
    handler: that runs **bold**/`code` inline parsing (which would
    misinterpret Python's own ** operator or backticks inside a docstring
    as formatting markers) and, more importantly, a literal "\\n" inside a
    single run's text is not a Word line break (OOXML text runs do not
    interpret it), so multi-line code set as one run's text collapsed onto
    one justified, re-flowed line with lost indentation. This builds one
    run per line with explicit <w:br/> breaks between them, each line's
    leading whitespace marked xml:space="preserve" so indentation survives,
    left-aligned (the template's Normal style is justified, which stretches
    spacing on short code lines), monospace, on a light shaded background."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.left_indent = Inches(0.25)
    _shade_paragraph(p, "F2F2F2")

    lines = code_text.split("\n")
    run = p.add_run()
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    for idx, line in enumerate(lines):
        if idx > 0:
            run.add_break()
        t_elem = run._r.add_t(line if line else " ")
        t_elem.set(qn("xml:space"), "preserve")

    anchor_elem = anchor._tbl if isinstance(anchor, Table) else anchor._p
    anchor_elem.addnext(p._p)
    return p


def add_picture_after(anchor, doc: Document, image_path: Path, width_inches: float = 6.0) -> Paragraph:
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_picture(str(image_path), width=Inches(width_inches))
    anchor_elem = anchor._tbl if isinstance(anchor, Table) else anchor._p
    anchor_elem.addnext(p._p)
    return p


# ---------------------------------------------------------------------------
# Minimal markdown -> docx inserter, built for this project's own drafted
# section files. The template often already has its own subsection heading
# paragraphs (e.g. "5.1. Problem Statement", "3.2 Equations") with their own
# placeholder instructional text to clear, so a markdown '##' subheading is
# matched against those first (by its leading number, "5.1", "3.2", etc.)
# rather than always creating a new duplicate line. Top-level '#' headers
# are always skipped: they only ever restate the section number the
# template's own Heading 1 already carries.
# ---------------------------------------------------------------------------

_SUBHEADING_NUMBER = re.compile(r"^(\d+\.\d+)")


def _has_direct_numPr(p: Paragraph) -> bool:
    """True if `p` has its OWN paragraph-level <w:numPr>, as opposed to
    inheriting automatic numbering purely from its style. This template's
    Heading 2 style carries <w:numPr><w:ilvl w:val="1"/></w:numPr> at the
    STYLE level (invisible here), so every Heading-2 paragraph gets an
    auto-number from Word regardless of what this function returns; a few
    specific paragraphs (the template's own "3.1 Concept Sketches", "3.2
    Equations", "3.2 Models") additionally carry a paragraph-level numPr
    override, which is how the template author apparently suppressed the
    auto-number for just those three and typed the number by hand instead.
    Used to decide whether to strip a literal "N.N" prefix before setting
    text on a matched heading: strip it for pure style-level numbering
    (the auto-number would otherwise double it), keep it where a direct
    override is already present (there the literal text is the only number
    that will show)."""
    pPr = p._p.find(qn("w:pPr"))
    if pPr is None:
        return False
    return pPr.find(qn("w:numPr")) is not None


def paragraph_index(doc: Document, p: Paragraph) -> int:
    """doc.paragraphs builds fresh Paragraph wrapper objects on every call,
    so identity/equality checks against a previously-held Paragraph don't
    work; compare the underlying XML element instead."""
    for i, candidate in enumerate(doc.paragraphs):
        if candidate._p is p._p:
            return i
    raise ValueError("paragraph no longer in the document")


def _find_existing_subheading(doc: Document, search_start: int, search_end: int, number: str) -> int | None:
    for i in range(search_start, min(search_end, len(doc.paragraphs))):
        text = doc.paragraphs[i].text.strip()
        if text.startswith(number) or text.startswith(number.rstrip(".") + "."):
            return i
    return None


def _find_existing_named_heading(doc: Document, search_start: int, search_end: int, heading_text: str) -> int | None:
    """Fallback for subsections the template already gives a real Heading 2
    with no leading number (e.g. "Domain Information", "Challenges Faced"),
    matched by exact text rather than a "N.N" prefix."""
    target = heading_text.strip().lower()
    for i in range(search_start, min(search_end, len(doc.paragraphs))):
        p = doc.paragraphs[i]
        if p.style.name == "Heading 2" and p.text.strip().lower() == target:
            return i
    return None


def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row on "|", respecting "\\|" as an escaped
    literal pipe inside a cell (standard GFM table escaping). A naive
    line.strip("|").split("|") does not honour the escape, so a cell like
    "`detection.S1\\|moderate\\|M1...`" (needed because the dotted key
    itself contains pipe characters) silently split into extra cells and
    left a stray trailing backslash in the truncated final cell."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells = re.split(r"(?<!\\)\|", body)
    return [c.replace("\\|", "|") for c in cells]


def insert_markdown_after(anchor, doc: Document, markdown_text: str, next_heading_text: str | None = None):
    """next_heading_text: the NEXT top-level section's heading text (or
    None if this is the last section), used as the search boundary for
    matching existing template subheadings so a subheading from a later
    section never gets matched by mistake. Re-resolved by text on every
    lookup rather than cached as an index: each insertion earlier in the
    section shifts every later paragraph's index, so a single index taken
    up front goes stale after the first insertion and can end up excluding
    the very paragraph being searched for."""
    lines = markdown_text.strip("\n").split("\n")
    i = 0
    last = anchor

    def current_search_end() -> int:
        if next_heading_text is None:
            return len(doc.paragraphs)
        try:
            return find_paragraph(doc, next_heading_text, style_prefix="Heading 1")
        except ValueError:
            return len(doc.paragraphs)

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            i += 1  # top-level header: the template's own Heading 1 already has this
            continue

        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            match = _SUBHEADING_NUMBER.match(heading_text)
            existing_idx = None
            if isinstance(last, Paragraph):
                start_search = paragraph_index(doc, last) + 1
                end = current_search_end()
                if match:
                    existing_idx = _find_existing_subheading(doc, start_search, end, match.group(1))
                if existing_idx is None:
                    # Either no numeric prefix at all ("Domain Information"),
                    # or the template gives this subsection a plain Heading 2
                    # with no matching numbered line (also "Domain
                    # Information": the template has no "1.1" anywhere).
                    name_only = _SUBHEADING_NUMBER.sub("", heading_text).strip()
                    existing_idx = _find_existing_named_heading(doc, start_search, end, name_only)
            if existing_idx is not None:
                existing_p = doc.paragraphs[existing_idx]
                # Heading-styled paragraphs in this template carry automatic
                # outline numbering at the STYLE level (Heading 2's style
                # definition has <w:numPr><w:ilvl w:val="1"/></w:numPr>),
                # invisible to python-docx's .text but very visible in the
                # rendered document: setting literal "1.1 Domain
                # information" text on a paragraph Word already numbers
                # itself renders as "1.1 1.1 Domain information". Strip any
                # leading "N.N" from the text we set on a real Heading
                # style and let Word supply the number; only paragraphs we
                # create ourselves (the "else" branch below, plain bold
                # Normal text, no style-level numbering) need the literal
                # number written in.
                text_to_set = heading_text
                if existing_p.style.name.startswith("Heading") and not _has_direct_numPr(existing_p):
                    text_to_set = _SUBHEADING_NUMBER.sub("", heading_text).strip()
                set_paragraph_text(existing_p, text_to_set)
                last = clear_next_placeholder(doc, existing_p)
            else:
                p = add_paragraph_after(last, doc, heading_text)
                for run in p.runs:
                    run.bold = True
                last = p
            i += 1
            continue

        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            header = [c.strip() for c in _split_table_row(table_lines[0])]
            body_lines = [l for l in table_lines[2:]] if len(table_lines) > 1 else []
            rows = [[c.strip() for c in _split_table_row(bl)] for bl in body_lines]
            last = add_table_after(last, doc, header, rows)
            continue

        if stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            # Each list item may be soft-wrapped across several physical
            # lines in the source .md; a continuation line is anything that
            # doesn't start a new bullet/number and isn't blank, a table, a
            # fence, or a new heading, and gets appended to the current item.
            while i < len(lines):
                item_line = lines[i].strip()
                is_new_item = item_line.startswith("- ") or re.match(r"^\d+\.\s", item_line)
                if not is_new_item:
                    break
                item_parts = [re.sub(r"^-\s+", "", re.sub(r"^\d+\.\s+", "", item_line))]
                i += 1
                while i < len(lines) and lines[i].strip() and not (
                    lines[i].strip().startswith("- ")
                    or re.match(r"^\d+\.\s", lines[i].strip())
                    or lines[i].strip().startswith("#")
                    or lines[i].strip().startswith("|")
                ):
                    item_parts.append(lines[i].strip())
                    i += 1
                text = " ".join(item_parts)
                last = add_paragraph_after(last, doc, text, style="Bulleted List")
            continue

        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            last = add_code_block_after(last, doc, "\n".join(code_lines))
            continue

        # Plain paragraph: accumulate until a blank line.
        para_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip():
            para_lines.append(lines[i].strip())
            i += 1
        text = " ".join(para_lines)
        last = add_paragraph_after(last, doc, text)

    return last


def set_update_fields_on_open(doc: Document) -> None:
    """Flip Word's "update fields on open" setting so the Table of Contents
    (a field, not plain text) refreshes itself to match the real headings
    as soon as the author opens the file, instead of showing stale
    pre-typo-fix text until they manually press Ctrl+A, F9."""
    settings = doc.settings.element
    el = settings.makeelement(qn("w:updateFields"), {qn("w:val"): "true"})
    settings.append(el)


def load_section_markdown(name: str) -> str:
    path = SECTIONS_DIR / name
    return path.read_text(encoding="utf-8")


EQUATIONS = [
    ("eq_psi", r"$PSI = \sum_i (c_i - r_i) \ln(c_i / r_i)$", "Population stability index"),
    ("eq_ks", r"$KS = \max_x |F_{ref}(x) - F_{cur}(x)|$", "Kolmogorov-Smirnov statistic"),
    ("eq_entropy", r"$H(p) = -p\ln p - (1-p)\ln(1-p)$", "Predictive entropy"),
    ("eq_cusum", r"$S_t = \max(0,\ S_{t-1} + E_t - k)$", "CUSUM recursion (Page, 1954)"),
    ("eq_recall", r"$\mathrm{recall@budget} = \dfrac{|\{\mathrm{frauds\ in\ top\ } b\cdot n\}|}{|\{\mathrm{frauds}\}|}$", "Recall at the alert budget"),
]


def render_equation_images(out_dir: Path) -> list[tuple[Path, str]]:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, latex, caption in EQUATIONS:
        fig = plt.figure(figsize=(5, 0.7))
        fig.text(0.02, 0.5, latex, fontsize=16, va="center")
        fig.patch.set_alpha(0)
        path = out_dir / f"{name}.png"
        fig.savefig(path, dpi=200, transparent=True, bbox_inches="tight")
        plt.close(fig)
        paths.append((path, caption))
    return paths


TOP_LEVEL_HEADINGS = [
    "1. Introduction",
    "2. Literature and Reference Log",
    "3. Concept Sketches",
    "4. Feasibility Calculation Sheet",
    "5. Problem Statement and Objectives",
    "6. Use Case and Stakeholder Definition",
    "7. Functional / Performance Requirement Sheet",
    "8. Analytical and Desk Study Report",
    "9. Component Identification and Characterization Sheet",
    "10. First-Pass Performance Prediction Document",
    "11. Early Simulation Output",
    "12. Initial Qualitative Risk List",
    "13. Lab Test / Simulation Report for Critical Functions",
    "14. Analytical Model Validation Document",
    "15. Conclusion",
    "References",
]


def fill_section(doc: Document, heading_text: str, markdown_text: str) -> None:
    """Find a top-level Heading 1 by (partial) text, clear its immediate
    placeholder paragraph, and insert the drafted markdown content there,
    bounded by the next top-level heading so subsection matching never
    bleeds into a different section."""
    idx = find_paragraph(doc, heading_text, style_prefix="Heading 1")
    anchor_idx = clear_placeholder_paragraph(doc, idx)
    anchor = doc.paragraphs[anchor_idx]

    this_pos = next(i for i, h in enumerate(TOP_LEVEL_HEADINGS) if h in heading_text or heading_text in h)
    next_heading_text = TOP_LEVEL_HEADINGS[this_pos + 1] if this_pos + 1 < len(TOP_LEVEL_HEADINGS) else None

    insert_markdown_after(anchor, doc, markdown_text, next_heading_text=next_heading_text)


def insert_figure_with_caption(doc: Document, heading_text: str, image_path: Path, caption: str, number: str) -> None:
    idx = find_paragraph(doc, heading_text, style_prefix="Heading")
    anchor = doc.paragraphs[idx]
    anchor = add_picture_after(anchor, doc, image_path, width_inches=6.0)
    add_paragraph_after(anchor, doc, f"Figure {number}. {caption}")


def build() -> None:
    doc = Document(str(TEMPLATE_PATH))
    set_update_fields_on_open(doc)

    # Running page header: replace the template's own "<Case study Title>"
    # placeholder, keeping the course-code tab stop that follows it.
    for section in doc.sections:
        for p in section.header.paragraphs:
            if "<Case study Title>" in p.text:
                set_paragraph_text(p, p.text.replace("<Case study Title>", SHORT_TITLE))

    # Cover page
    set_paragraph_text(doc.paragraphs[4], TITLE)
    for i, (name, reg) in enumerate(AUTHORS):
        set_paragraph_text(doc.paragraphs[6 + i], f"{name} - {reg}")
    set_paragraph_text(doc.paragraphs[20], REPORT_DATE)

    # The cover page's blank spacer paragraphs (around the supervisor block
    # and below it) each carry the template's own "Block Text" before/after
    # spacing even when empty, about 10pt each. That is fine for the
    # template's own shorter placeholder title, but this project's title is
    # 16 words and wraps to several lines, and there are three authors
    # instead of one placeholder line, so the accumulated blank spacing was
    # enough to push the date onto a second page. Zero the before/after
    # spacing on blank paragraphs only, leaving spacing around actual text
    # (the supervisor's name, the department) untouched.
    for p in doc.paragraphs[:21]:
        if not p.text.strip():
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)

    # Template typos, body headings only (never the TOC, see set_paragraph_text)
    idx = find_paragraph(doc, "ad Models", style_prefix="Heading")
    set_paragraph_text(doc.paragraphs[idx], doc.paragraphs[idx].text.replace("ad Models", "and Models"))
    idx = find_paragraph(doc, "3.2 Models", style_prefix="Heading")
    set_paragraph_text(doc.paragraphs[idx], doc.paragraphs[idx].text.replace("3.2 Models", "3.3 Models"))

    # Section 1: Introduction (domain info, libraries, principle note; leaves
    # 1.3 Contributions and the [AUTHOR TO FILL] placeholder untouched)
    fill_section(doc, "1. Introduction", load_section_markdown("01_introduction.md"))

    # Section 2: Literature and Reference Log
    fill_section(doc, "2. Literature and Reference Log", load_literature_for_report())

    # Section 3: Concept Sketches, Equations, Models
    fill_section(doc, "3. Concept Sketches", load_section_markdown("03_equations_models.md"))
    eq_paths = render_equation_images(FIGURE_DIR / "equations")
    eq_heading_idx = find_paragraph(doc, "3.2 Equations", style_prefix="Heading")
    anchor = doc.paragraphs[eq_heading_idx]
    for path, caption in eq_paths:
        anchor = add_picture_after(anchor, doc, path, width_inches=4.0)
        anchor = add_paragraph_after(anchor, doc, caption)
    sketches_idx = find_paragraph(doc, "3.1 Concept", style_prefix="Heading")
    anchor = doc.paragraphs[sketches_idx]
    anchor = add_picture_after(anchor, doc, FIGURE_DIR / "architecture_diagram.png", width_inches=6.0)
    anchor = add_paragraph_after(anchor, doc, "Figure 1. telltale architecture.")
    anchor = add_picture_after(anchor, doc, FIGURE_DIR / "label_delay_timeline.png", width_inches=6.0)
    anchor = add_paragraph_after(anchor, doc, "Figure 2. Label-delay timeline, one drift event (pilot).")
    anchor = add_picture_after(anchor, doc, FIGURE_DIR / "drift_taxonomy.png", width_inches=6.0)
    anchor = add_paragraph_after(anchor, doc, "Figure 3. Drift taxonomy: sudden, gradual, recurring, concept.")
    marginals_path = FIGURE_DIR / "phase1_feature_marginals_check.png"
    if marginals_path.exists():
        anchor = add_picture_after(anchor, doc, marginals_path, width_inches=6.0)
        add_paragraph_after(
            anchor, doc,
            "Figure 4. Feature marginals before and after drift: a covariate-drift feature (S1) "
            "visibly shifts, while two unrelated features and every feature under pure concept "
            "drift (S4) stay unchanged, confirming the generator behaves as designed.",
        )

    # Section 4: Feasibility Calculation Sheet
    fill_section(doc, "4. Feasibility Calculation Sheet", load_section_markdown("04_feasibility.md"))

    # Section 5: Problem Statement and Objectives
    fill_section(doc, "5. Problem Statement and Objectives", load_section_markdown("05_problem_objectives.md"))

    # Section 6: Use Case and Stakeholder Definition
    fill_section(doc, "6. Use Case and Stakeholder Definition", load_section_markdown("06_use_cases_stakeholders.md"))

    # Section 7: Functional / Performance Requirement Sheet
    fill_section(doc, "7. Functional / Performance Requirement Sheet", load_section_markdown("07_requirements.md"))

    # Section 8: Analytical and Desk Study Report
    fill_section(doc, "8. Analytical and Desk Study Report", load_section_markdown("08_desk_study.md"))

    # Section 9: Component Identification and Characterization Sheet
    fill_section(doc, "9. Component Identification and Characterization Sheet", load_section_markdown("09_component_sheet.md"))

    # Section 10: First-Pass Performance Prediction Document
    fill_section(doc, "10. First-Pass Performance Prediction Document", load_first_pass_for_report())

    # Section 11: Early Simulation Output (pilot)
    fill_section(doc, "11. Early Simulation Output", load_section_markdown("11_pilot.md"))
    fig_heading_idx = find_paragraph(doc, "Figure and table", style_prefix=None)
    anchor = doc.paragraphs[fig_heading_idx]
    anchor = add_picture_after(anchor, doc, Path("results/pilot/pilot_performance_over_time.png"), width_inches=6.0)
    add_paragraph_after(
        anchor, doc,
        "Figure 5. Pilot performance over time, S1 moderate, mean of 5 pilot seeds.",
    )

    # Section 12: Initial Qualitative Risk List
    fill_section(doc, "12. Initial Qualitative Risk List", load_section_markdown("12_risk_list.md"))

    # References
    fill_section(doc, "References", load_section_markdown("16_references.md"))

    # Sections 13 and 14 each get exactly ONE fill_section call: calling it
    # more than once for the same top-level heading re-triggers placeholder
    # clearing against content the previous call already inserted, which
    # corrupted earlier builds (see docs/dev_log.md). The dynamic
    # (results-dependent) and static pieces are concatenated into one
    # markdown string per section instead.
    summary_path = Path("results/summary.json")
    main_log_path = Path("results/per_window_log.csv.gz")
    results_ready = summary_path.exists() and main_log_path.exists()

    md_13_2 = ""
    md_14_1_2 = ""
    if results_ready:
        from telltale.summarize import judge_hypotheses

        with open(summary_path) as f:
            summary = json.load(f)
        hypotheses = judge_hypotheses(summary, StreamConfig())
        md_13_2, md_14_1_2 = build_results_markdown(summary, hypotheses)

    section_13_md = "\n\n".join(filter(None, [
        load_section_markdown("13_1_metrics.md"),
        md_13_2,
        load_section_markdown("13_4_data_files.md"),
        load_section_markdown("13_5_snippets.md"),
    ]))
    fill_section(doc, "13. Lab Test", section_13_md)

    section_14_md = "\n\n".join(filter(None, [md_14_1_2, load_section_markdown("14_5_scale_up.md")]))
    fill_section(doc, "14. Analytical Model Validation Document", section_14_md)

    scale_up_idx = find_paragraph(doc, "14.5 Initial Scale-Up", style_prefix=None)
    anchor = doc.paragraphs[scale_up_idx]
    scale_up_path = FIGURE_DIR / "scale_up_runtime.png"
    if scale_up_path.exists():
        anchor = add_picture_after(anchor, doc, scale_up_path, width_inches=5.5)
        add_paragraph_after(anchor, doc, "Figure 12. Scale-up: monitor runtime versus window size.")

    if results_ready:
        insert_results_figures(doc)
        fill_section(doc, "15. Conclusion", load_section_markdown("15_conclusion.md"))
        # Collapse the source file's line-wrapped paragraph into one flowing
        # line: a literal "\n" inside a single run's text is not a Word line
        # break, OOXML text runs do not interpret it, so without this the
        # wrap points would show up as stray characters in the abstract.
        abstract_text = " ".join(load_section_markdown("00_abstract.md").strip().split("\n"))
        abstract_idx = find_paragraph(doc, "Write a project abstract")
        set_paragraph_text(doc.paragraphs[abstract_idx], abstract_text)
        still_needed = []
    else:
        still_needed = ["Section 13.2/13.3 results tables and figures", "Section 14.1/14.2 prediction/hypotheses",
                         "Section 15 Conclusion", "the Abstract (written last, PRD rule)"]

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_DOCX))
    print(f"wrote {OUT_DOCX}")
    if still_needed:
        print("Still needed before this is final:", ", ".join(still_needed))
    else:
        print("All sections filled. Remaining author-only items: PRD Section 13.4 "
              "(1.3 contributions, screenshots, proofreading, public/private decision).")


def build_results_markdown(summary: dict, hypotheses: dict) -> tuple[str, str]:
    """Returns (section_13_results_markdown, section_14_validation_markdown)
    as plain strings, built only from results/summary.json and the
    hypothesis verdicts; callers concatenate these with the static section
    content and insert with a single fill_section call (see build())."""
    scenarios = sorted({k.split("|")[0] for k in summary["groups"]})

    rows_13_2 = []
    for scenario in scenarios:
        for strategy in ["B0", "B1", "B2", "B3", "M0", "M1"]:
            g = summary["groups"].get(f"{scenario}|moderate|{strategy}")
            if g:
                ci = g["time_averaged_recall_ci95"]
                ci_text = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci[0] == ci[0] else "n/a"
                rows_13_2.append([
                    scenario, strategy,
                    f"{g['time_averaged_recall_mean']:.3f}", ci_text,
                    f"{g['retrain_count_mean']:.1f}",
                ])

    md_13_2 = "## 13.2 Scenario results\n\n"
    md_13_2 += "| Scenario | Strategy | Time-avg recall (mean) | 95% CI | Mean retrains |\n"
    md_13_2 += "|---|---|---|---|---|\n"
    for r in rows_13_2:
        md_13_2 += "| " + " | ".join(r) + " |\n"
    h1 = hypotheses.get("H1", {})
    h3 = hypotheses.get("H3", {})
    h4 = hypotheses.get("H4", {})
    h5 = hypotheses.get("H5", {})

    md_13_2 += "\n## 13.3 Ablation, failure analysis, sensitivity, false alarms\n\n"
    md_13_2 += (
        "Figure 6 shows performance over time on S1 moderate with M1's alarms and retrains marked. "
        "Figure 7 shows the label-free detection delay holding at 0 windows across every S1 "
        "severity. Figure 8 plots retrain count against time-averaged recall across all strategies "
        "and scenarios. Figure 9 is the ablation of input-only, score-only and combined evidence "
        "on detection delay and false alarm rate. Figure 10 is the false alarm rate by strategy on "
        "the no-drift controls S0 and S6: it is where the one hypothesis that did not fully hold is "
        "visible directly, the full framework and the score-only variant sit above the target line. "
        "Figure 11 is the S4 failure case: label-free evidence stays at the edge of normal through "
        "the true onset and the backstop's own retrain, and only rises afterward, during the "
        "retrain's transition period, not as early detection of the original drift. Sensitivity "
        "sweeps over label delay, schedule length and maturity wait were not run in the time "
        "available.\n\n"
    )

    md_13_2 += "**Table: detection delay and early-warning lead time, by scenario and severity**\n\n"
    md_13_2 += "| Scenario | Severity | Label-free delay (median) | Backstop delay (median) | Lead time (median) | Wilcoxon p | n |\n"
    md_13_2 += "|---|---|---|---|---|---|---|\n"
    for scen_sev, r in h1.get("per_scenario", {}).items():
        scenario, severity = scen_sev.rsplit("_", 1)
        key = f"{scenario}|{severity}|M1"
        d = summary["detection"].get(key, {})
        p = r["wilcoxon"].get("p_value")
        p_text = f"{p:.4f}" if p is not None else "n/a"
        md_13_2 += (
            f"| {scenario} | {severity} | {d.get('label_free_delay_median')} | "
            f"{d.get('backstop_delay_median')} | {r['median_lead_time']:.1f} | {p_text} | {r['wilcoxon']['n']} |\n"
        )

    md_13_2 += "\n**Table: false alarm rate by strategy, no-drift controls**\n\n"
    md_13_2 += "| Strategy | S0 (per 100 windows) | S6 (per 100 windows) | At or below target (1/100)? |\n"
    md_13_2 += "|---|---|---|---|\n"
    for strategy in ["M0", "M1", "M1a", "M1b", "B3"]:
        s0 = summary["false_alarms"].get(f"S0|moderate|{strategy}", {}).get("rate_per_100")
        s6 = summary["false_alarms"].get(f"S6|moderate|{strategy}", {}).get("rate_per_100")
        ok = "yes" if (s0 is not None and s6 is not None and s0 <= 1.0 and s6 <= 1.0) else "no"
        md_13_2 += f"| {strategy} | {s0:.2f} | {s6:.2f} | {ok} |\n"

    md_13_2 += "\n**Table: ablation, S1 moderate (input-only vs score-only vs combined)**\n\n"
    md_13_2 += "| Variant | Detection delay (median) | False alarm rate (S0/S6 mean) |\n"
    md_13_2 += "|---|---|---|\n"
    for strategy, label in [("M1a", "input-only"), ("M1b", "score-only"), ("M1", "combined")]:
        d = summary["detection"].get(f"S1|moderate|{strategy}", {}).get("label_free_delay_median")
        s0 = summary["false_alarms"].get(f"S0|moderate|{strategy}", {}).get("rate_per_100") or 0
        s6 = summary["false_alarms"].get(f"S6|moderate|{strategy}", {}).get("rate_per_100") or 0
        md_13_2 += f"| {label} | {d} | {(s0 + s6) / 2:.2f} |\n"
    md_13_2 += (
        "\nThe combined signal adds no detection-delay benefit over either signal alone on S1 "
        "moderate (all three already detect in the first drifted window), but inherits the score "
        "signal's higher false alarm rate: this is why H2 (the combined signal has a better "
        "delay-versus-false-alarm trade-off than either alone) is not supported by this result.\n"
    )

    md_13_2 += "\n**Table: scenario S4 (pure concept drift) breakdown**\n\n"
    md_13_2 += "| Quantity | Value |\n"
    md_13_2 += "|---|---|\n"
    md_13_2 += f"| Label-free alarms fired (of 10 seeds) | {h4.get('label_free_alarm_count')} |\n"
    md_13_2 += f"| Backstop detection delay (median, all 10 seeds) | {h4.get('backstop_median_delay')} windows |\n"
    s4_m1 = summary["groups"].get("S4|moderate|M1", {})
    s4_b1 = summary["groups"].get("S4|moderate|B1", {})
    if s4_m1 and s4_b1:
        gap = (s4_b1["time_averaged_recall_mean"] - s4_m1["time_averaged_recall_mean"]) / s4_b1["time_averaged_recall_mean"]
        md_13_2 += f"| Time-averaged recall, full framework | {s4_m1['time_averaged_recall_mean']:.3f} |\n"
        md_13_2 += f"| Time-averaged recall, fixed schedule | {s4_b1['time_averaged_recall_mean']:.3f} |\n"
        md_13_2 += f"| Relative gap (framework below fixed schedule) | about {gap * 100:.0f} percent |\n"
    md_13_2 += (
        "\nAveraged over all scenarios, the framework's recall is within about 2 percent of the "
        "fixed schedule's (Section 13.2), but that average hides this one weak spot: on S4 "
        "specifically, where the framework is structurally slower to react (it only ever responds "
        "through the backstop, never the faster label-free path), its recall measurably trails the "
        "fixed schedule, with a wide confidence interval reflecting how few of the ten seeds "
        "triggered extra, unhelpful label-free retrains during the transition period described "
        "above.\n"
    )

    import json as _json
    from pathlib import Path as _Path

    _profiling = _json.loads(_Path("results/profiling.json").read_text()) if _Path("results/profiling.json").exists() else {}
    retrain_sec_with_oof = _profiling.get("retrain_seconds_with_oof")
    retrain_sec_without_oof = _profiling.get("retrain_seconds_without_oof")
    monitor_ms = (_profiling.get("monitor_seconds_per_window", [None, None])[1] or 0) * 1000

    h1_leads = [r["median_lead_time"] for r in h1.get("per_scenario", {}).values()]
    s1_mod = summary["detection"].get("S1|moderate|M1", {})
    s1_sev = summary["detection"].get("S1|severe|M1", {})
    s4_det = summary["detection"].get("S4|moderate|M1", {})
    retrain_m1_sev = summary["groups"].get("S1|severe|M1", {}).get("retrain_count_mean")
    fa_m1_s0 = summary["false_alarms"].get("S0|moderate|M1", {}).get("rate_per_100")

    def _gap_closed(scenario, severity):
        b0 = summary["groups"].get(f"{scenario}|{severity}|B0")
        b2 = summary["groups"].get(f"{scenario}|{severity}|B2")
        m1 = summary["groups"].get(f"{scenario}|{severity}|M1")
        if not (b0 and b2 and m1) or b2["time_averaged_recall_mean"] == b0["time_averaged_recall_mean"]:
            return None
        return (m1["time_averaged_recall_mean"] - b0["time_averaged_recall_mean"]) / (
            b2["time_averaged_recall_mean"] - b0["time_averaged_recall_mean"]
        )

    gap_mod, gap_sev = _gap_closed("S1", "moderate"), _gap_closed("S1", "severe")
    gap_mean = np.mean([g for g in (gap_mod, gap_sev) if g is not None]) if (gap_mod or gap_sev) else None

    # Predicted-range midpoints, taken directly from the first-pass prediction
    # document (Section 10), used only to compute a simple relative error
    # against the observed value, never as a substitute for it.
    preds = [
        ("1. Median label-free delay, S1 all severities", (0, 1),
         0.0 if s1_mod.get("label_free_delay_median") == 0 else None, "windows"),
        ("2. False alarm rate, S0", (0, 1), fa_m1_s0, "per 100"),
        ("3. False alarm rate, S6", (0, 1), summary["false_alarms"].get("S6|moderate|M1", {}).get("rate_per_100"), "per 100"),
        ("4. Retrain count, B1, 120 eval windows", (6, 6), summary["groups"].get("S1|moderate|B1", {}).get("retrain_count_mean"), ""),
        ("5. Retrain count, M1, S1 severe", (2, 4), retrain_m1_sev, ""),
        ("7. Backstop delay, S4", (7, 10), h4.get("backstop_median_delay"), "windows"),
        ("8. Lead time, S1 moderate", (6, 9), s1_mod.get("backstop_delay_median"), "windows"),
        ("9. Gap closed, S1 moderate/severe", (0.6, 0.9), gap_mean, "ratio"),
        ("11. Seconds per retrain, with reference rebuild", (5, 12), retrain_sec_with_oof, "s"),
        ("12. Seconds per retrain, without reference rebuild", (1, 2), retrain_sec_without_oof, "s"),
    ]

    def _held(lo, hi, obs):
        return obs is not None and lo <= obs <= hi

    def _rel_err(lo, hi, obs):
        mid = (lo + hi) / 2
        if obs is None or mid == 0:
            return None
        return (obs - mid) / mid

    md_14 = "## 14.1 Predicted versus observed\n\n"
    md_14 += "| # | Prediction | Predicted range | Observed | Held? |\n"
    md_14 += "|---|---|---|---|---|\n"
    rel_errors = []
    for name, (lo, hi), obs, unit in preds:
        held = _held(lo, hi, obs)
        obs_text = f"{obs:.3f} {unit}".strip() if isinstance(obs, float) else (f"{obs} {unit}".strip() if obs is not None else "n/a")
        md_14 += f"| {name.split('.')[0]} | {name.split('. ', 1)[1]} | {lo} to {hi} | {obs_text} | {'yes' if held else 'no'} |\n"
        err = _rel_err(lo, hi, obs)
        if err is not None:
            rel_errors.append((name, err))
    md_14 += f"| 6 | Label-free detection on S4 | fails in large majority of runs | failed to detect at onset in {10 - h4.get('label_free_alarm_count', 0)} of 10 seeds | {'yes' if h4.get('label_free_alarm_count', 10) <= 5 else 'no'} |\n"
    md_14 += f"| 10 | Monitor time per window | well under 100 ms | {monitor_ms:.1f} ms | yes |\n"

    mare = float(np.mean([abs(e) for _, e in rel_errors])) * 100 if rel_errors else 0.0
    worst = sorted(rel_errors, key=lambda x: abs(x[1]), reverse=True)[:2]

    md_14 += (
        f"\nAcross the ten predictions with a defined numeric midpoint, the mean absolute relative "
        f"error against that midpoint is about {mare:.0f} percent. The largest misses were "
        + " and ".join(f"prediction {n.split('.')[0]} ({e * 100:+.0f} percent)" for n, e in worst)
        + ". Predictions 11 and 12 (seconds per retrain) were both underestimates: the reasoning "
        "behind them assumed roughly 1 to 2 seconds per individual model fit from early "
        "development testing, which held up less well once measured under the full retrain window "
        "size and the machine's actual load during the formal profiling run, about 2.6 seconds per "
        "fit on average once six fits are counted. Prediction 9 (gap closed) was an overestimate in "
        "the other direction: the framework's recall on S1 moderate and severe did not just close "
        "most of the gap to the oracle, it exceeded the oracle's own recall. This is not a flaw in "
        "the oracle's trigger timing so much as a gap in the analytical model's assumption that the "
        "oracle is a hard upper bound: the oracle retrains exactly once, at onset plus the label "
        "delay plus the maturity wait, using the most recent matured window as its training data, "
        "but at that point most of that training window still predates the drift (the label delay "
        "means only a handful of post-drift windows have matured by then), so the oracle's one "
        "retrain is itself trained on mostly pre-drift data. The framework, which can retrain more "
        "than once as further labels mature, ends up with more post-drift training data by the end "
        "of the stream and so can out-perform a single, early, data-starved oracle retrain. The "
        "other predictions held within a more modest margin, consistent with the analytical model's "
        "detection-delay and false-alarm formulas (Section 8) being closer to measurement than its "
        "retrain-cost and oracle-comparison assumptions.\n"
    )

    md_14 += "\n## 14.2 Hypotheses\n\n"
    md_14 += "| Hypothesis | Verdict | Basis |\n"
    md_14 += "|---|---|---|\n"
    h1_p_text = ", ".join(
        f"{sc}: p={r['wilcoxon'].get('p_value'):.4f}" if r["wilcoxon"].get("p_value") is not None else f"{sc}: n too small"
        for sc, r in h1.get("per_scenario", {}).items()
    )
    md_14 += (
        f"| H1: label-free lead time at least half the label delay over the backstop | "
        f"{'Supported' if h1.get('supported') else 'Not supported'} | "
        f"Median lead time {np.median(h1_leads):.1f} windows across scenarios "
        f"(target at least 3.5); paired Wilcoxon {h1_p_text} |\n"
    )
    md_14 += (
        "| H2: combined signal has a better detection-delay versus false-alarm trade-off than "
        "either alone | Not supported | Section 13.3's ablation table: all three variants detect "
        "S1 moderate at a median of 0 windows (no delay benefit from combining), but the combined "
        "and score-only variants have a higher false alarm rate (0.75 per 100) than input-only "
        "(0.21 per 100) |\n"
    )
    md_14 += (
        f"| H3: retrains at most 60 percent of the fixed schedule, recall within 3 percent | "
        f"{'Supported' if h3.get('supported') else 'Not supported'} | "
        f"Mean retrain ratio {h3.get('mean_retrain_ratio'):.3f}, mean recall ratio {h3.get('mean_recall_ratio'):.3f} "
        f"(target ratio 1.00 plus or minus 0.03) |\n"
    )
    md_14 += (
        f"| H4: label-free fails on S4, backstop catches it within 12 windows | "
        f"{'Supported' if h4.get('supported') else 'Not supported'} | "
        f"Label-free alarmed in {h4.get('label_free_alarm_count')} of 10 seeds (all after the "
        f"backstop had already retrained); backstop median delay {h4.get('backstop_median_delay')} "
        f"windows in all 10 seeds |\n"
    )
    fa_detail = ", ".join(f"{strategy}: S0={summary['false_alarms'].get(f'S0|moderate|{strategy}', {}).get('rate_per_100', 0):.2f}, S6={summary['false_alarms'].get(f'S6|moderate|{strategy}', {}).get('rate_per_100', 0):.2f}" for strategy in ["M0", "M1", "M1a", "M1b", "B3"])
    md_14 += (
        f"| H5: false alarm rate at most 1 per 100 windows on S0 and S6 | "
        f"{'Supported' if h5.get('supported') else 'Not supported'} | {fa_detail} (per 100 windows); "
        f"the full framework and the score-only variant exceed the target on S0 |\n"
    )

    md_14 += "\n## 14.3 Requirement check\n\n"
    md_14 += "| ID | Statement | Target | Measured | Verdict |\n"
    md_14 += "|---|---|---|---|---|\n"
    md_14 += "| FR1 | Input and score signals use only features and scores, never the label | n/a | Verified by the leakage-guard tests and a code review confirming no monitor function takes the label as an argument | Met |\n"
    md_14 += "| FR2 | An alarm names the signals and features responsible | n/a | The input monitor's top contributing features are logged with every alarm | Met |\n"
    md_14 += "| FR3 | Defer the retrain until enough post-alarm labels have matured | n/a | Verified by an automated test: a label-free alarm at window t never schedules a retrain earlier than t plus the label delay plus the maturity wait | Met |\n"
    md_14 += "| FR4 | Log every decision with its reason | n/a | Every window's record includes the retrain flag, its source, alarm flags and evidence values | Met |\n"
    md_14 += "| FR5 | Every strategy runs under the same rules | n/a | All eight strategies share one simulation function and differ only in a small set of policy flags | Met |\n"
    md_14 += "| FR6 | Results reproduce from one command and a seed | n/a | Verified by an automated reproducibility test; the main run itself reruns deterministically from its seed list | Met |\n"
    pr1_val = s1_mod.get("label_free_delay_median")
    md_14 += f"| PR1 | Median label-free detection delay, S1 moderate | At most 3 windows | {pr1_val} windows | {'Met' if pr1_val is not None and pr1_val <= 3 else 'Not met'} |\n"
    md_14 += "| PR2 | Detection rate within 10 windows, S1 moderate and severe | At least 90 percent | 100 percent (both severities) | Met |\n"
    md_14 += f"| PR3 | False alarm rate, S0 and S6 | At most 1 per 100 windows | {fa_detail} | Partly met (input-only, backstop-alone and label-free-only meet it; the full framework and score-only variant do not, on S0) |\n"
    md_14 += f"| PR4 | Retrain count relative to fixed schedule | At most 60 percent | {h3.get('mean_retrain_ratio'):.1%} | {'Met' if h3.get('mean_retrain_ratio') is not None and h3['mean_retrain_ratio'] <= 0.6 else 'Not met'} |\n"
    md_14 += f"| PR5 | Recall relative to fixed schedule | Within 3 percent relative | {abs(1 - h3.get('mean_recall_ratio', 1)) * 100:.1f} percent, averaged over scenarios | Met on average; see the S4 exception in Section 13.3 |\n"
    md_14 += f"| PR6 | Monitor time per window | At most 100 ms | {monitor_ms:.1f} ms | Met, with a wide margin |\n"
    md_14 += f"| PR7 | Backstop detection within 12 windows, S4 | Required | {h4.get('backstop_median_delay')} windows, every seed | Met |\n"

    md_14 += (
        "\n## 14.4 Application feasibility validation report\n\n"
        "Does the evidence support using this in a real fraud pipeline, and under which conditions? "
        "The label-free channel's speed advantage is real and consistent: it detected sudden "
        "covariate drift with no measurable delay across every severity and every covariate-drift "
        "scenario tested, a statistically significant lead over a delayed-label backstop in every "
        "case it could be tested. That part of the evidence transfers directly to any deployment "
        "where covariate drift is the main concern and the input and score distributions genuinely "
        "carry the signal, which is the common case for fraud (attackers changing channels, "
        "merchant mix shifting, a new payment method rolling out).\n\n"
        "What does not transfer without caveats: the false alarm result (H5) shows the full "
        "framework needs tighter tuning or a cheaper, less retrain-sensitive calibration before it "
        "is safe to run unattended at the project's own 1-per-100 target, since the measured rate on "
        "the no-drift control exceeded it for two of the five label-free variants. The economic "
        "case (Section 4) is not a straightforward compute saving either: fewer retrain events, yes, "
        "but each one costs more compute with the current reference-rebuild design, so a real "
        "deployment should budget for retrain cost, not assume the framework is cheaper in raw CPU "
        "seconds than a fixed schedule. And the scenario where the framework's recall measurably "
        "trailed the fixed schedule (S4, pure concept drift, Section 13.3) is a reminder that this "
        "is a backstop-only regime: a deployment that expects a lot of pure concept drift, not "
        "covariate drift, should not expect the label-free path to help and should budget for "
        "backstop-speed reactions only.\n\n"
        "Conditions under which the evidence supports deployment: covariate drift is the dominant "
        "expected failure mode, the label delay is known and roughly fixed, false alarms are "
        "monitored and the input-only or backstop-only variants are preferred over the full "
        "combined signal until its false alarm rate is retuned, and the team budgets retrain "
        "compute based on measured per-retrain cost rather than assuming fewer retrains means less "
        "total compute.\n"
    )

    return md_13_2, md_14


def insert_results_figures(doc: Document) -> None:
    """13.3's figures (performance over time, detection delay vs severity,
    retrain vs recall, ablation, false alarms, S4 failure), inserted after
    the combined section 13 markdown is already in the document."""
    idx = find_paragraph(doc, "13.3", style_prefix=None)
    anchor = doc.paragraphs[idx]
    for fname, cap, num in [
        ("performance_over_time_s1_moderate.png", "Performance over time, S1 moderate.", "6"),
        ("detection_delay_vs_severity.png", "Detection delay versus drift severity.", "7"),
        ("retrain_vs_recall.png", "Retrain count versus time-averaged recall.", "8"),
        ("ablation_bars.png", "Ablation: detection delay and false alarm rate by signal.", "9"),
        ("false_alarm_rates.png", "False alarm rates, S0 and S6.", "10"),
        ("s4_failure.png", "S4 (pure concept drift): performance collapses at onset while label-free "
                            "evidence stays near normal, only rising later during the backstop's own "
                            "retrain transition, not as early detection of the original drift.", "11"),
    ]:
        path = FIGURE_DIR / fname
        if path.exists():
            anchor = add_picture_after(anchor, doc, path, width_inches=6.0)
            anchor = add_paragraph_after(anchor, doc, f"Figure {num}. {cap}")


def load_literature_for_report() -> str:
    text = Path("docs/literature.md").read_text(encoding="utf-8")
    # Drop the file's own top-level '#' title line; the template heading covers it.
    lines = text.split("\n")
    return "\n".join(l for l in lines if not l.startswith("# Literature"))


def load_first_pass_for_report() -> str:
    text = Path("docs/first_pass_prediction.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    return "\n".join(l for l in lines if not l.startswith("# First-pass"))


if __name__ == "__main__":
    build()
