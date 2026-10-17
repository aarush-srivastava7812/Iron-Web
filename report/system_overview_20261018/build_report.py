"""Render the source-grounded Markdown report without external assets or services."""
from pathlib import Path
import base64
import hashlib
import html
import json
import mimetypes
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = "245829251f5222fbabe0d1c25b00170e9edabd1c"
BASE = f"https://github.com/aarush-srivastava7812/Iron-Web/blob/{REVISION}/"
BASELINE_PATHS = set(subprocess.check_output([
    "git", "-c", "safe.directory=" + ROOT.as_posix(), "ls-tree", "-r", "--name-only", REVISION,
], cwd=ROOT, text=True).splitlines())


def inline(value):
    tokens = []

    def preserve(match):
        content = match.group(1)
        code = f"<code>{html.escape(content)}</code>"
        if content in BASELINE_PATHS:
            code = f'<a href="{BASE}{content}">{code}</a>'
        tokens.append(code)
        return f"ZZCODE{len(tokens) - 1}ZZ"

    value = re.sub(r"`([^`]+)`", preserve, value)
    value = html.escape(value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    for index, token in enumerate(tokens):
        value = value.replace(f"ZZCODE{index}ZZ", token)
    return value


def embedded_image(path):
    path = (HERE / path).resolve()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def render(lines):
    output, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("```"):
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            output.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            index += 1
            continue
        heading = re.match(r"(#{1,6}) (.*)", line)
        if heading:
            level, title = len(heading[1]), heading[2]
            anchor = "section-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            output.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            index += 1
            continue
        image = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image:
            output.append(f'<figure><img alt="{html.escape(image[1])}" src="{embedded_image(image[2])}"><figcaption>{html.escape(image[1])}</figcaption></figure>')
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\- ]+", c) for c in row):
                    rows.append(row)
                index += 1
            output.append("<table><thead><tr>" + "".join("<th>" + inline(c) + "</th>" for c in rows[0]) + "</tr></thead><tbody>")
            for row in rows[1:]:
                output.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in row) + "</tr>")
            output.append("</tbody></table>")
            continue
        if re.match(r"\d+\. ", line):
            output.append("<ol>")
            while index < len(lines) and re.match(r"\d+\. ", lines[index].strip()):
                output.append("<li>" + inline(re.sub(r"^\d+\. ", "", lines[index].strip())) + "</li>")
                index += 1
            output.append("</ol>")
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip():
            paragraph.append(lines[index].strip())
            index += 1
        output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(output)


CSS = """
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#e9edee;color:#24323e;font-family:Arial,Helvetica,sans-serif;font-size:11pt;line-height:1.55}main{max-width:1000px;margin:30px auto;background:white;padding:58px 70px;box-shadow:0 8px 40px #18282e15}a{color:#156b73;text-decoration:none}code{font:9pt Consolas,monospace;overflow-wrap:anywhere;background:#f2f5f5;padding:1px 3px;border-radius:3px}pre{padding:16px;background:#f1f5f5;border-left:3px solid #468d86;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5}pre code{padding:0;background:none}h2{font-size:21pt;line-height:1.2;letter-spacing:-.6px;margin:38px 0 15px;padding-top:14px;border-top:2px solid #b6d4cf;color:#162e35;break-after:avoid}h3{font-size:13pt;margin:24px 0 10px;break-after:avoid}p{margin:0 0 12px}table{width:100%;border-collapse:collapse;font-size:9.3pt;margin:18px 0 22px}thead{display:table-header-group}th{background:#1c3c42;color:white;text-align:left;font-weight:600}th,td{padding:9px 10px;border:1px solid #dce5e6;vertical-align:top}td:first-child{font-weight:600;min-width:72px}tr{break-inside:avoid}tbody tr:nth-child(even){background:#f7f9f9}figure{margin:22px 0;break-inside:avoid}img{display:block;max-width:100%;height:auto;border-radius:8px;border:1px solid #e0e7e9}figcaption{font-size:9pt;color:#657880;margin-top:8px}li{margin-bottom:7px}ol{padding-left:23px;margin:14px 0 20px}.cover{background:#18282e;color:#edf4f3;padding:54px 46px;min-height:850px;display:flex;flex-direction:column;justify-content:space-between;margin:-58px -70px 35px;break-after:page}.eyebrow{font:10pt Consolas,monospace;color:#8ce2cd;letter-spacing:2px}.cover h1{font-size:63pt;letter-spacing:-4px;margin:34px 0 5px;line-height:1.1}.cover h2{color:#e7efee;font-size:25pt;font-weight:400;border:0;padding:0;margin:8px 0 30px;max-width:570px}.cover p{color:#b7c9cc;max-width:620px;font-size:13pt}.cover .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:38px 0}.stat{border-top:1px solid #6c8d90;padding-top:13px;font-size:11pt;color:#bed1d2}.stat strong{display:block;font-size:29pt;font-weight:500;color:#e6e596}.cover .meta{font-size:10pt;line-height:1.8;border-top:1px solid #426066;padding-top:22px;color:#a7c0c3}.cover code{background:transparent;color:#a7c0c3;font-size:9pt}.notice{padding:15px 18px;background:#f1f6f5;border-left:3px solid #73aaa1;font-size:10pt;margin-bottom:20px}.toc{columns:2;column-gap:30px;font-size:10pt;padding-left:21px}.toc li{break-inside:avoid}.report-content>h2:first-of-type{margin-top:25px}.toolbar{max-width:1000px;margin:20px auto 0;color:#52656a;font-size:13px}.toolbar a{font-weight:bold;margin-left:15px}
@page{size:A4;margin:17mm 16mm 19mm}@media print{html{scroll-behavior:auto}body{background:white;font-size:10pt;line-height:1.48}main{box-shadow:none;margin:0;padding:0;max-width:none}.cover{margin:0;min-height:250mm;padding:30mm 12mm 14mm}.cover h1{font-size:60pt}.cover h2{font-size:26pt}.cover p{font-size:12pt}.cover .meta{font-size:9pt}.toolbar{display:none}h2{font-size:19pt;margin-top:25px;padding-top:12px}h3{font-size:12pt}table{font-size:8.5pt}th,td{padding:7px 8px}code{font-size:8pt}a{color:inherit}img{max-height:230mm;object-fit:contain}p{orphans:3;widows:3}pre{break-inside:avoid}}
"""


def main():
    text = (HERE / "report.md").read_text(encoding="utf-8")
    if re.search(r"nvapi-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}", text):
        raise ValueError("Credential-like value in report")
    body = text[text.index("## 1. Executive overview"):]
    headings = re.findall(r"^## (.*)$", body, re.M)
    toc = "<ol class='toc'>" + "".join(
        '<li><a href="#section-' + re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-") + '">' + html.escape(re.sub(r"^\d+\. ", "", h)) + "</a></li>" for h in headings
    ) + "</ol>"
    cover = """<section class="cover"><div><div class="eyebrow">SYSTEM REPORT / 18 OCTOBER 2026</div><h1>Iron Web<span style="color:#e6e596">.</span></h1><h2>Shared memory.<br>Specialized agents.<br>Visible evidence.</h2><p>A guide to the memory infrastructure, Voyara travel application, and independent live dashboard. Updated with finalisation evidence and the approved database recovery.</p><div class="stats"><div class="stat"><strong>03</strong>Memory tiers</div><div class="stat"><strong>09</strong>Registered memory actors</div><div class="stat"><strong>05</strong>Dashboard views</div></div></div><div class="meta">Historical source baseline: <code>245829251f5222fbabe0d1c25b00170e9edabd1c</code><br>Local finalisation addendum: finalise/2026-10-18 through eb3bf8e.<br>Approved recovery active. Fresh hosted and restart checks passed. No production certification.</div></section>"""
    document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Iron Web — complete system report</title><style>' + CSS + '</style></head><body><div class="toolbar">Iron Web · system report<a href="report.pdf">PDF</a><a href="report.md">Markdown source</a></div><main>' + cover + '<div class="notice"><strong>Reading this report:</strong> Implementation, historical measurements, current local observations, and proposed work are distinguished. Credentials and private runtime payloads are excluded.</div>' + toc + '<article class="report-content">' + render(body.splitlines()) + '</article></main></body></html>'
    (HERE / "index.html").write_text(document, encoding="utf-8")
    sources = [
        "README.md", "config.yaml", "docs/architecture.md", "docs/specification.md",
        "docs/application_memory_integration.md", "docs/three_tier_memory_usage.md",
        "docs/memory_evolution.md", "docs/shared_memory_service.md", "docs/travel_chat_catalog.md",
        "dashboard/README.md", "dashboard/backend/main.py", "memory/dashboard.py",
        "memory/observability.py", "agents/agentic.py", "agents/config.py",
        "agents/orchestration/graph.py", "agents/orchestration/checkpointing.py",
        "stitch_ai_travel_booking_platform/backend/app/agent_runtime.py",
        "stitch_ai_travel_booking_platform/backend/app/routers/bookings.py",
        "report/dashboard_live/summary.json", "report/full20_graph_analysis_20261013/report.md",
    ]
    manifest = {"prepared_date": "2026-10-18", "timezone": "Asia/Kolkata", "source_revision": REVISION,
                "finalisation_source": "Local finalise/2026-10-18 through eb3bf8e plus accompanying documentation/evidence; historical hyperlinks retain baseline revision",
                "method": "Source review plus dated hosted acceptance, isolated offline regressions and approved recovery-copy diagnostics; no new performance benchmark; hashes describe local files at render time",
                "report_words": len(text.split()), "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered report: {manifest['report_words']} words, {len(headings)} chapters; all figures embedded.")


if __name__ == "__main__":
    main()
