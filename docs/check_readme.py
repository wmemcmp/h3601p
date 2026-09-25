#!/usr/bin/env python3
"""Check the documentation artifact, its source links and pinned release facts.

No firmware tests are executed, and no router is contacted. External web links
are not crawled. Optional Markdown rendering needs the host markdown-it package.
"""
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'README.md'
s = README.read_text()
errors = []
checks = []


def check(value, message):
    (checks if value else errors).append(message)


check(s.count('<!-- BEGIN GENERATED APPENDICES -->') == 1 and
      s.count('<!-- END GENERATED APPENDICES -->') == 1, 'generated appendix markers')
check(s.count('<details>') == s.count('</details>'), 'balanced collapsible sections')
check('[GitHub: wmemcmp/h3601p](https://github.com/wmemcmp/h3601p)' in s,
      'confirmed publication repository')
fence = None
for n, line in enumerate(s.splitlines(), 1):
    m = re.match(r'^(`{3,}|~{3,})', line)
    if m:
        mark = m.group(1)
        if fence is None: fence = mark
        elif mark[0] == fence[0] and len(mark) >= len(fence): fence = None
check(fence is None, 'balanced fenced code blocks')
anchors = set(re.findall(r'<a\s+id="([^"]+)"', s))
links = re.findall(r'\]\(([^\s)]+)\)', s)
local = []
for raw in links:
    u = urlsplit(raw)
    if u.scheme or u.netloc: continue
    target = ROOT / unquote(u.path) if u.path else README
    if not target.exists(): errors.append(f'missing local target: {raw}'); continue
    local.append(raw)
    if u.fragment:
        if target == README and u.fragment not in anchors:
            errors.append(f'missing explicit README anchor: {raw}')
        elif u.fragment.startswith('L') and target.is_file():
            check(u.fragment[1:].isdigit() and int(u.fragment[1:]) <= len(target.read_text().splitlines()),
                  f'source line anchor: {raw}')
check(bool(local), 'local source/document links inspected')
rows = list(csv.DictReader((ROOT/'docs/audit/current-source-inventory.csv').open()))
for r in rows:
    data=(ROOT/r['path']).read_bytes()
    check(hashlib.sha256(data).hexdigest() == r['sha256'] and len(data.splitlines()) == int(r['lines']),
          'source inventory identity: '+r['path'])
summary=json.loads((ROOT/'docs/audit/summary.json').read_text())
check(len(rows)==summary['current_files']==151, '151-file selected inventory')
check(summary['project_markdown_files']==154, '154 project Markdown records')
check('22 selected files, 12,420 physical lines and 403,344 bytes' in s, 'platform accounting statement')
manifest=json.loads((ROOT/'out/normal-r241/manifest.json').read_text())
for name,entry in manifest['files'].items():
    p=ROOT/'out/normal-r241'/name
    data=p.read_bytes()
    check(len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'], 'release identity: '+name)
    check(entry['sha256'] in s, 'README release hash: '+name)
check('wifi_enabled: false' in s and 'retained first-boot script' in s, 'release-default discrepancy documented')
check('12345678' not in s, 'shared development key not repeated')
check('C:\\Users\\test' not in s and '/home/burak/' not in s, 'README uses portable source links')
check((ROOT/'out/normal-r241/h3601p-r241-normal-bundle.zip').stat().st_size==15607382, 'bundle byte count')
check(hex(7291135)=='0x6f40ff', 'recovery transfer byte/hex equivalence')
check(0x5000000+0x5700000==175112192, 'concat arithmetic')
check(0xa700000-0x6a00000==63963136, 'rootfs-store arithmetic')
ET.parse(ROOT/'docs/assets/h3601p-header.svg')
checks.append('valid SVG XML')
try:
    from markdown_it import MarkdownIt
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    tokens = md.parse(s)
    check(len([t for t in tokens if t.type == 'table_open']) >= 40, 'GFM-style tables parsed')
    check(len([t for t in tokens if t.type == 'fence' and t.info.strip() == 'mermaid']) == 2, 'two Mermaid diagrams preserved')
    html = md.render(s)
    check('&#124;' not in re.sub(r'<code>.*?</code>', '', html, flags=re.S), 'table entities parse without leaking into prose')
    preview = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3601P README preview</title><style>
    body{max-width:1100px;margin:40px auto;padding:0 26px;font:16px/1.65 system-ui,sans-serif;color:#1f2937;background:white}
    img{max-width:100%;height:auto}h1,h2,h3{line-height:1.25;color:#10283a}h1{font-size:38px}h2{border-bottom:1px solid #dbe3eb;padding-bottom:10px;margin-top:52px}a{color:#0969da;text-decoration:none}a:hover{text-decoration:underline}
    table{display:block;overflow:auto;border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{border:1px solid #dbe3eb;padding:9px 12px;text-align:left}th{background:#eef4f8}tr:nth-child(even){background:#f7fafc}pre{background:#f3f6fa;border:1px solid #dde5ed;border-radius:8px;padding:18px;overflow:auto;font-size:13px}code{font-family:ui-monospace,monospace;font-size:.88em}p code,td code{background:#eff3f7;padding:2px 4px;border-radius:3px}summary{cursor:pointer;padding:12px;background:#f1f6fa;border-radius:8px}details{margin:14px 0}blockquote{border-left:4px solid #26a69a;margin-left:0;padding:8px 22px;color:#43566a}
    </style><body>'''+html+'</body></html>'
    # A preview is kept outside the repository; inline the banner and use the
    # real repository root as a base for relative source links.
    preview=preview.replace('<meta charset="utf-8">', '<meta charset="utf-8"><base href="'+ROOT.as_uri()+'/">')
    Path('/tmp/h3601p-readme-preview.html').write_text(preview)
    checks.append('HTML preview rendered with MarkdownIt')
except ImportError:
    checks.append('MarkdownIt unavailable; structural/link checks completed without optional HTML preview')
report={'status':'PASS' if not errors else 'FAIL','scope':'documentation only; no new hardware/firmware test',
        'readme_lines':len(s.splitlines()),'readme_bytes':len(s.encode()),
        'local_links_checked':len(local),'checks_passed':len(checks),'errors':errors}
(ROOT/'docs/audit/documentation-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(bool(errors))
