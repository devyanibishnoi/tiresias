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

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "report" / "template.docx"
OUT_DOCX = ROOT / "report" / "out" / "telltale_report.docx"
SECTIONS_DIR = ROOT / "docs" / "report_sections"
RESULTS_DIR = ROOT / "results"
FIGURE_DIR = RESULTS_DIR / "figures"

AUTHORS = [
    ("Devyani Bishnoi", "24BCI0167"),
    ("Anshika Agarwal", "24BCE0989"),
    ("Hridya Sharma", "24BAI0182"),
]
TITLE = "Label-Free Drift Detection and Selective Retraining Framework for Deployed Fraud Classifiers Under Delayed Ground Truth"
REPORT_DATE = "October 17, 2026"


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


def clear_placeholder_paragraph(doc: Document, heading_idx: int, max_scan: int = 6) -> int:
    """If the paragraph right after a heading is leftover template
    instructional text (not another heading, not empty), clear it and
    return its index so content can be inserted there. Otherwise return the
    heading index itself (insert right after the heading)."""
    for j in range(heading_idx + 1, min(heading_idx + 1 + max_scan, len(doc.paragraphs))):
        p = doc.paragraphs[j]
        if p.style.name.startswith("Heading"):
            return heading_idx
        if p.text.strip():
            set_paragraph_text(p, "")
            return j
    return heading_idx


def clear_next_placeholder(doc: Document, heading: Paragraph, max_scan: int = 4) -> Paragraph:
    """Paragraph-based counterpart to clear_placeholder_paragraph: if the
    paragraph right after `heading` is leftover template instructional
    text, clear it and return it as the insertion anchor; otherwise return
    `heading` itself."""
    idx = paragraph_index(doc, heading)
    for j in range(idx + 1, min(idx + 1 + max_scan, len(doc.paragraphs))):
        p = doc.paragraphs[j]
        if p.style.name.startswith("Heading") or _SUBHEADING_NUMBER.match(p.text.strip()):
            return heading
        if p.text.strip():
            set_paragraph_text(p, "")
            return p
    return heading


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


def add_table_after(anchor: Paragraph, doc: Document, header: list, rows: list) -> Table:
    table = doc.add_table(rows=1, cols=len(header))
    _apply_grid_borders(table)
    for i, h in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = str(h)
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            if i < len(cells):
                cells[i].text = str(v)
    anchor._p.addnext(table._tbl)
    return table


def add_paragraph_after(anchor, doc: Document, text: str, style: str | None = None) -> Paragraph:
    new_p = doc.add_paragraph(text, style=style)
    anchor_elem = anchor._tbl if isinstance(anchor, Table) else anchor._p
    anchor_elem.addnext(new_p._p)
    return new_p


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


def insert_markdown_after(anchor, doc: Document, markdown_text: str, next_heading_idx: int | None = None):
    """next_heading_idx: paragraph index of the NEXT top-level section
    heading (or len(doc.paragraphs) if this is the last section), used as
    the search boundary for matching existing template subheadings so a
    subheading from a different, later section is never matched by
    mistake."""
    lines = markdown_text.strip("\n").split("\n")
    i = 0
    last = anchor
    search_end = next_heading_idx if next_heading_idx is not None else len(doc.paragraphs)

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
            if match and isinstance(last, Paragraph):
                start_search = paragraph_index(doc, last) + 1
                existing_idx = _find_existing_subheading(doc, start_search, search_end, match.group(1))
            if existing_idx is not None:
                existing_p = doc.paragraphs[existing_idx]
                set_paragraph_text(existing_p, heading_text)
                last = clear_next_placeholder(doc, existing_p)
            else:
                p = add_paragraph_after(last, doc, "")
                run = p.add_run(heading_text)
                run.bold = True
                last = p
            i += 1
            continue

        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            header = [c.strip() for c in table_lines[0].strip("|").split("|")]
            body_lines = [l for l in table_lines[2:]] if len(table_lines) > 1 else []
            rows = [[c.strip() for c in bl.strip("|").split("|")] for bl in body_lines]
            last = add_table_after(last, doc, header, rows)
            continue

        if stripped.startswith("- ") or stripped.startswith("1. "):
            bullet_lines = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or re.match(r"^\d+\.\s", lines[i].strip())):
                bullet_lines.append(lines[i].strip())
                i += 1
            for bl in bullet_lines:
                text = re.sub(r"^-\s+", "", bl)
                text = re.sub(r"^\d+\.\s+", "", text)
                last = add_paragraph_after(last, doc, text, style="Bulleted List")
            continue

        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            p = add_paragraph_after(last, doc, "\n".join(code_lines))
            for run in p.runs:
                run.font.name = "Consolas"
                run.font.size = Pt(9)
            last = p
            continue

        # Plain paragraph: accumulate until a blank line.
        para_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip():
            para_lines.append(lines[i].strip())
            i += 1
        text = " ".join(para_lines)
        text = text.replace("**", "")  # light markdown bold marker cleanup
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

    next_idx = len(doc.paragraphs)
    for later_heading in TOP_LEVEL_HEADINGS[TOP_LEVEL_HEADINGS.index(
        next(h for h in TOP_LEVEL_HEADINGS if h in heading_text or heading_text in h)
    ) + 1:]:
        try:
            next_idx = find_paragraph(doc, later_heading, style_prefix="Heading 1", start=idx + 1)
            break
        except ValueError:
            continue

    insert_markdown_after(anchor, doc, markdown_text, next_heading_idx=next_idx)


if __name__ == "__main__":
    print("report/build_report.py: run as part of Phase 7 once all results exist. "
          "Importable helpers are ready; section-by-section assembly is added as "
          "each piece of content is finalised (see docs/report_sections/).")
