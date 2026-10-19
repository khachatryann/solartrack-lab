"""Deterministic static site assembly; no network, npm or account required."""
from pathlib import Path
import shutil
import re
import markdown
from write_report import main as write_report

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
if not (ROOT / "results/manifest.json").is_file():
    raise SystemExit("Run python scripts/generate.py first")
write_report()
if DIST.exists():
    shutil.rmtree(DIST)
shutil.copytree(ROOT / "website", DIST)
shutil.copytree(ROOT / "results", DIST / "data")
shutil.copytree(ROOT / "docs", DIST / "docs")
shutil.copy2(ROOT / "README.md", DIST / "README.md")
index = (ROOT / "website/index.html").read_text()
head = index.split('<body>')[0].replace('<script src="app.js" defer></script>', '')
sidebar = index.split('<aside class="sidebar">')[1].split('</aside>')[0]
sidebar = sidebar.replace('class="nav-item active"', 'class="nav-item"')
sidebar = sidebar.replace('href="#sweep"', 'href="./#sweep"')
pages = {"methodology": ("methodology.md", "The model behind the experiment."),
         "learning": ("learning-guide.md", "A field guide to the power peak."),
         "report": ("report.md", "What the experiments found."),
         "verification": ("verification.md", "Evidence you can inspect.")}
for slug, (source, title) in pages.items():
    content = (ROOT / "docs" / source).read_text()
    # Rebase repository-document links for standalone site pages.
    for old, new in (("../results/", "data/"), ("system.svg", "docs/system.svg"), ("control-loop.svg", "docs/control-loop.svg"),
                     ("methodology.md", "methodology.html"), ("learning-guide.md", "learning.html"), ("report.md", "report.html"),
                     ("test-results.xml", "docs/test-results.xml"), ("browser-qa.json", "docs/browser-qa.json")):
        content = content.replace(']('+old, ']('+new)
    body = markdown.markdown(content, extensions=["tables", "fenced_code", "toc"])
    body = re.sub(r'<h1[^>]*>.*?</h1>', '', body, count=1)
    body = body.replace('id="verification-protocol"', 'id="verification"')
    # Wide documentation tables can scroll without widening mobile pages.
    body = body.replace('<table>', '<div class="table-scroll"><table>').replace('</table>', '</table></div>')
    html = head.replace('<title>SolarTrack Lab — Finding maximum solar power</title>', f'<title>{title} — SolarTrack Lab</title>')
    html += f'''<body><a class="skip" href="#main">Skip to content</a><aside class="sidebar">{sidebar}</aside>
<main id="main" class="doc-main"><header class="topbar"><a href="./">← EXPERIMENT LAB</a><a href="report.html">Technical report ↗</a></header>
<section class="intro"><div><span class="eyebrow">SOLARTRACK LAB / RESEARCH NOTES</span><h1>{title}</h1></div></section>
<article class="prose">{body}</article><footer><a href="./">☀ SolarTrack Lab</a><a href="https://github.com/khachatryann/solartrack-lab">Source repository ↗</a></footer></main></body></html>'''
    (DIST / f"{slug}.html").write_text(html)
(DIST / ".nojekyll").touch()
print(f"Built static demo: {DIST}")
