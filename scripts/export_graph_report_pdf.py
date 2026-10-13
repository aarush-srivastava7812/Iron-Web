"""Export the factual Markdown analysis as a paginated PDF with readable tables."""

import argparse
from html import escape
from pathlib import Path
import re


def inline(text):
    text = escape(text)
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    args = parser.parse_args()
    report = Path(args.report).resolve()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            spaceAfter=16,
            textColor=colors.black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=9,
            textColor=colors.black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            fontName="Helvetica",
            fontSize=8.3,
            leading=10.5,
            textColor=colors.black,
        )
    )
    for level in (1, 2, 3):
        style = styles["Heading" + str(level)]
        style.textColor = colors.black
        style.fontName = "Helvetica-Bold"
        style.spaceBefore = 14
        style.spaceAfter = 7
    doc = SimpleDocTemplate(
        str(report / "report.pdf"),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=38,
        bottomMargin=38,
        title="Twenty percent graph storage analysis",
        author="",
        subject="Measured graph backend ingestion and retrieval comparison",
    )
    story = []
    lines = (report / "report.md").read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append(cells)
                index += 1
            headers = rows[0]
            weights = [
                2.6
                if h == "Backend"
                else 2.2
                if h == "Profile"
                else 1.4
                if h == "Dataset"
                else 1.0
                for h in headers
            ]
            widths = [doc.width * w / sum(weights) for w in weights]
            cells = [
                [Paragraph(inline(c), styles["Cell"]) for c in row] for row in rows
            ]
            tab = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
            tab.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7edf3")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f7f8fa")],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cdd2d7")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend([tab, Spacer(1, 10)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["ReportTitle"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["Heading1"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["Heading2"]))
        elif line.startswith("- "):
            story.append(
                Paragraph(inline(line[2:]), styles["ReportBody"], bulletText="•")
            )
        else:
            story.append(Paragraph(inline(line), styles["ReportBody"]))
        index += 1
    figures = report / "figures"
    if figures.exists():
        story.append(Paragraph("Measured time comparisons", styles["Heading1"]))
        for filename in (
            "vector.png",
            "default_hybrid.png",
            "reranked_hybrid.png",
            "ingestion.png",
            "quality.png",
            "ingestion_curve.png",
        ):
            path = figures / filename
            if path.exists():
                from PIL import Image as PILImage

                with PILImage.open(path) as picture:
                    w, h = picture.size
                story.append(
                    Image(str(path), width=doc.width, height=doc.width * h / w)
                )
                story.append(Spacer(1, 12))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#505050"))
        canvas.drawString(36, 22, "Iron Web graph storage analysis")
        canvas.drawRightString(A4[0] - 36, 22, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(str(report / "report.pdf"))


if __name__ == "__main__":
    main()
