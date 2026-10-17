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
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
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
    """If the paragraph right after a heading is leftover template
    instructional text (not another heading or subsection, not empty),
    clear it and return its index so content can be inserted there.
    Otherwise return the heading index itself."""
    for j in range(heading_idx + 1, min(heading_idx + 1 + max_scan, len(doc.paragraphs))):
        p = doc.paragraphs[j]
        if _is_structural(p):
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
        if _is_structural(p):
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
                text = " ".join(item_parts).replace("**", "")
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

    # Cover page
    set_paragraph_text(doc.paragraphs[4], TITLE)
    for i, (name, reg) in enumerate(AUTHORS):
        set_paragraph_text(doc.paragraphs[6 + i], f"{name} - {reg}")
    set_paragraph_text(doc.paragraphs[20], REPORT_DATE)

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
    add_paragraph_after(anchor, doc, "Figure 3. Drift taxonomy: sudden, gradual, recurring, concept.")

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
    idx = find_paragraph(doc, "11. Early Simulation Output", style_prefix="Heading")
    # figure inserted at the end of that section's content; find the last
    # paragraph before section 12 and attach the picture there
    next_idx = find_paragraph(doc, "12. Initial Qualitative Risk List", style_prefix="Heading 1")
    anchor = doc.paragraphs[next_idx - 1]
    add_picture_after(anchor, doc, Path("results/pilot/pilot_performance_over_time.png"), width_inches=6.0)

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
    summary = hypotheses = main_log = None
    if results_ready:
        import pandas as pd

        from telltale.summarize import judge_hypotheses

        with open(summary_path) as f:
            summary = json.load(f)
        main_log = pd.read_csv(main_log_path)
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
    md_13_2 += "\n## 13.3 Ablation, failure analysis, sensitivity, false alarms\n\n"
    md_13_2 += "See the ablation bars, false alarm rate and S4 failure figures below.\n"

    # 14.1 prediction vs observed, 14.2 hypothesis verdicts
    h1 = hypotheses.get("H1", {})
    h3 = hypotheses.get("H3", {})
    h4 = hypotheses.get("H4", {})
    h5 = hypotheses.get("H5", {})

    md_14 = "## 14.1 Predicted versus observed\n\n"
    md_14 += "| Prediction | Predicted range | Observed | Held? |\n"
    md_14 += "|---|---|---|---|\n"
    h1_leads = [r["median_lead_time"] for r in h1.get("per_scenario", {}).values()]
    md_14 += f"| Early-warning lead time (median), S1/S2/S3 | about D windows (6-9) | {np.median(h1_leads):.1f} windows (median across scenarios) | {'yes' if h1.get('supported') else 'no'} |\n" if h1_leads else ""
    md_14 += f"| Retrain count ratio, M1 vs B1 | at most 0.60 | {h3.get('mean_retrain_ratio'):.3f} | {'yes' if h3.get('supported') else 'no'} |\n" if h3.get('mean_retrain_ratio') is not None else ""
    md_14 += f"| Backstop detection delay, S4 | D to D+3 (about 7-10) | {h4.get('backstop_median_delay')} windows | {'yes' if h4.get('supported') else 'no'} |\n"
    fa_vals = list(h5.get("rates", {}).values())
    md_14 += f"| False alarm rate, S0/S6 | 0 to 1 per 100 | {np.mean(fa_vals):.2f} per 100 (mean) | {'yes' if h5.get('supported') else 'no'} |\n" if fa_vals else ""

    md_14 += "\n## 14.2 Hypotheses\n\n"
    md_14 += "| Hypothesis | Verdict | Basis |\n"
    md_14 += "|---|---|---|\n"
    md_14 += f"| H1: label-free lead time >= D/2 over backstop | {'Supported' if h1.get('supported') else 'Not supported'} | Median lead time per scenario, paired Wilcoxon |\n"
    md_14 += "| H2: combined signal beats either alone on delay-vs-false-alarm | See ablation figure and table | M1 vs M1a vs M1b |\n"
    md_14 += f"| H3: retrains <= 60% of fixed schedule, recall within 3% | {'Supported' if h3.get('supported') else 'Not supported'} | Mean ratios across scenarios |\n"
    md_14 += f"| H4: label-free fails on S4, backstop catches it within D+5 | {'Supported' if h4.get('supported') else 'Not supported'} | S4 label-free alarm count, backstop median delay |\n"
    md_14 += f"| H5: false alarm rate <= 1/100 on S0, S6 | {'Supported' if h5.get('supported') else 'Not supported'} | Measured rate per strategy |\n"

    return md_13_2, md_14


def insert_results_figures(doc: Document) -> None:
    """13.3's figures (performance over time, detection delay vs severity,
    retrain vs recall, ablation, false alarms, S4 failure), inserted after
    the combined section 13 markdown is already in the document."""
    idx = find_paragraph(doc, "13.3", style_prefix=None)
    anchor = doc.paragraphs[idx]
    for fname, cap, num in [
        ("performance_over_time_s1_moderate.png", "Performance over time, S1 moderate.", "5"),
        ("detection_delay_vs_severity.png", "Detection delay versus drift severity.", "6"),
        ("retrain_vs_recall.png", "Retrain count versus time-averaged recall.", "7"),
        ("ablation_bars.png", "Ablation: detection delay and false alarm rate by signal.", "8"),
        ("false_alarm_rates.png", "False alarm rates, S0 and S6.", "9"),
        ("s4_failure.png", "S4 failure figure: label-free evidence stays flat while performance collapses.", "10"),
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
