#!/usr/bin/env python3
"""Recount the H3601P documentation snapshot without counting vendor trees as our code.

Run from any directory. Read-only toward firmware; writes only docs/audit/*.
Physical lines include comments and blanks. Patch additions/deletions exclude
the +++/--- headers. Historical snapshots are catalogued, not added to the
current implementation total. No source contents or device secrets are copied.
"""
import collections
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/audit'
SKIP = {'.git', 'build_dir', 'staging_dir', 'dl', 'rootfs', 'root', 'build',
        'e2631-linux', 'feeds', 'tmp', 'iperf-build', 'ghidra_projects',
        '__pycache__', '.pc', 'rootfs_extracted', 'stock', 'ida_analysis',
        'decompiled', 'audit'}
EXTS = {'.c', '.h', '.S', '.py', '.sh', '.patch', '.dts', '.dtsi', '.mk'}


def walk(base):
    for directory, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(names):
            p = Path(directory) / name
            if p.is_file() and not p.is_symlink():
                yield p


def info(path, category):
    data = path.read_bytes()
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    row = dict(path=path.relative_to(ROOT).as_posix(), category=category,
               bytes=len(data), lines=len(lines), nonblank=sum(bool(s.strip()) for s in lines),
               sha256=hashlib.sha256(data).hexdigest(), added='', removed='')
    if path.suffix == '.patch':
        row['added'] = sum(s.startswith('+') and not s.startswith('+++') for s in lines)
        row['removed'] = sum(s.startswith('-') and not s.startswith('---') for s in lines)
    return row


def text_file(p):
    data = p.read_bytes()
    return b'\0' not in data and not p.name.endswith(('.mod.c', '.o.cmd'))


def current_sources():
    result = {}
    trees = {
        'openwrt/target/linux/zte': 'target overlay',
        'openwrt/package/kernel/mt76/patches': 'mt76 patch series',
        'openwrt/files': 'runtime helpers and defaults',
    }
    for prefix, category in trees.items():
        for p in walk(ROOT / prefix):
            if p.suffix.lower() in {'.md', '.txt'} or not text_file(p):
                continue
            result[p] = category
    for folder, category in {
        'out/r241-normal': 'normal firmware implementation',
        'out/r240-concat': 'concat and JFFS2 implementation/tests',
        'out/cspboot-analysis': 'CSPBOOT validation tools',
    }.items():
        for p in (ROOT / folder).iterdir():
            if p.is_file() and (p.suffix in EXTS or p.name in {'80_mount_root', 'jffs2reset', '69_h3601p_overlay'}):
                if text_file(p):
                    result[p] = category
    for name in ['out/r241-normal/layout-module/h3601p-upgrade-layout.c',
                 'out/r241-normal/layout-module/Makefile',
                 'out/r241-normal/openwrt-normal-packages.config',
                 'out/prepare_nand_r240.py']:
        p = ROOT / name
        if p.exists():
            result[p] = 'normal firmware implementation' if 'r241' in name else 'CSPBOOT packaging'
            if p.name == 'openwrt-normal-packages.config':
                result[p] = 'normal package configuration; generated Kconfig selections'
    for name in ['openwrt/include/feeds.mk',
                 'openwrt/package/kernel/mt76/Makefile',
                 'openwrt/target/linux/generic/config-6.18',
                 'openwrt/h3601p.config']:
        p = ROOT / name
        if p.exists():
            result[p] = 'upstream-based build context; not original authored LOC'
    return [info(p, c) for p, c in sorted(result.items())]


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    markdown, historical = [], []
    for p in walk(ROOT):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith('docs/') or rel == 'README.md':
            continue
        if p.suffix.lower() == '.md':
            category = 'project record' if not rel.startswith('openwrt/') or 'zte/' in rel or p.name == 'README-H3601P.md' else 'upstream documentation'
            markdown.append(info(p, category))
        if rel.startswith('out/') and p.suffix in EXTS and text_file(p):
            historical.append(info(p, 'archive; may include upstream code and duplicate snapshots'))
    current = current_sources()
    groups = {}
    for row in current:
        g = groups.setdefault(row['category'], dict(files=0, lines=0, nonblank=0, bytes=0, added=0, removed=0))
        for key in ('lines', 'nonblank', 'bytes'):
            g[key] += row[key]
        g['files'] += 1
        g['added'] += row['added'] or 0
        g['removed'] += row['removed'] or 0
    duplicates = collections.defaultdict(list)
    for r in current:
        duplicates[r['sha256']].append(r['path'])
    summary = dict(method='physical splitlines, comments/blanks included; patch +/- separately; not an authorship metric',
                   markdown_files=len(markdown), markdown_bytes=sum(r['bytes'] for r in markdown),
                   markdown_unique_content=len(set(r['sha256'] for r in markdown)),
                   project_markdown_files=sum(r['category'] == 'project record' for r in markdown),
                   current_groups=groups, current_files=len(current),
                   archive_files=len(historical),
                   identical_current_files=[v for v in duplicates.values() if len(v) > 1],
                   excluded_tree_names=sorted(SKIP))
    tracked = []
    try:
        base = subprocess.check_output(['git', '-C', str(ROOT / 'openwrt'),
                                        'rev-parse', 'HEAD'], text=True).strip()
        delta = subprocess.check_output(['git', '-C', str(ROOT / 'openwrt'),
            'diff', '--numstat', '--', 'include/feeds.mk',
            'package/kernel/mt76/Makefile', 'target/linux/generic/config-6.18'], text=True)
        for line in delta.splitlines():
            added, removed, path = line.split('\t')
            tracked.append(dict(path='openwrt/' + path, added=int(added),
                                removed=int(removed), base_commit=base))
        summary['tracked_build_context_diff_base'] = base
    except (subprocess.SubprocessError, FileNotFoundError):
        summary['tracked_build_context_diff_base'] = 'unavailable; snapshot files still counted'
    write_csv('markdown-inventory.csv', markdown)
    write_csv('current-source-inventory.csv', current)
    write_csv('historical-source-inventory.csv', historical)
    write_csv('tracked-build-context-deltas.csv', tracked)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
