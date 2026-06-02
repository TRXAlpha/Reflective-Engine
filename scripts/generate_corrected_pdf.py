#!/usr/bin/env python3
"""Generate the corrected Reflective Engine PDF from a small Markdown source.

This script intentionally avoids LaTeX/Pandoc because they are not available in
the Codespaces image used during the correction pass.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


sys.path.insert(0, "/tmp/codex-reportlab")

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs" / "Reflective_Engine_corrected.md"
DEFAULT_OUTPUT = ROOT / "Reflective_Engine_corrected.pdf"


def clean_inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(0.72 * inch, 0.45 * inch, "Reflective Engine report")
    canvas.drawRightString(7.78 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#222222"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            spaceAfter=7,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=16,
            firstLineIndent=-9,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
    }


def parse_markdown(md: str, styles):
    story = []
    lines = md.splitlines()
    i = 0
    title_done = False

    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(clean_inline(line[2:]), styles["title"]))
            title_done = True
            i += 1
            continue

        if title_done and not line.startswith("## ") and not line.startswith("- ") and not line.startswith("|"):
            # The author/date/repo lines immediately after the title are subtitle metadata.
            if i < 8:
                story.append(Paragraph(clean_inline(line), styles["subtitle"]))
                i += 1
                continue

        if line.startswith("## "):
            story.append(Paragraph(clean_inline(line[3:]), styles["h2"]))
            i += 1
            continue

        if line.startswith("- "):
            story.append(Paragraph("- " + clean_inline(line[2:]), styles["bullet"]))
            i += 1
            continue

        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|\s*-+", lines[i]):
                    table_lines.append(lines[i])
                i += 1
            rows = []
            for tline in table_lines:
                cells = [c.strip() for c in tline.strip("|").split("|")]
                rows.append(cells)
            if rows:
                data = []
                for r, row in enumerate(rows):
                    style = styles["table_header"] if r == 0 else styles["table"]
                    data.append([Paragraph(clean_inline(cell), style) for cell in row])
                table = Table(data, colWidths=[1.75 * inch, 4.8 * inch], hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#30343b")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8bcc4")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 5),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 8))
            continue

        para = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if not nxt or nxt.startswith("#") or nxt.startswith("- ") or nxt.startswith("|"):
                break
            para.append(nxt)
            i += 1
        story.append(Paragraph(clean_inline(" ".join(para)), styles["body"]))

    return story


def main() -> None:
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_OUTPUT
    if not source.exists():
        raise SystemExit(f"Missing source: {source}")
    styles = build_styles()
    story = parse_markdown(source.read_text(encoding="utf-8"), styles)
    doc = BaseDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Reflective Engine: Corrected Technical Report",
        author="Christian Morogan",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=footer)])
    doc.build(story)
    print(output)


if __name__ == "__main__":
    main()
