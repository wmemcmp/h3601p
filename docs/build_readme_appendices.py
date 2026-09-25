#!/usr/bin/env python3
"""Generate source-linked README appendices from the read-only source audit.

This does not modify source, firmware, existing release evidence or hardware.
Definitions are source constants, not an inferred vendor register datasheet.
"""
import collections
import csv
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'docs/audit'
BEGIN = '<!-- BEGIN GENERATED APPENDICES -->'
END = '<!-- END GENERATED APPENDICES -->'


def read_csv(name):
    return list(csv.DictReader((AUDIT / name).open()))


def esc(s):
    return str(s).replace('|', '&#124;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')


def code(s):
    return '`' + str(s).replace('|', '\\|').replace('`', '') + '`'


def link(path, label=None, line=None):
    target = quote(path, safe='/._-') + (f'#L{line}' if line else '')
    return f'[{esc(label or path)}]({target})'


ROLES = {
    'platsmp.c': 'SCU setup, IRAM publication and secondary CPU holding-pen handshake.',
    'headsmp.S': 'Secondary-core trampoline and embedded physical entry/release words.',
    'zx279128-pcie.h': 'Board-specific protected PCIe MMIO read interface.',
    'zx279128s-tm.c': 'Ethernet netdevices, TM/BMU setup, DMA/NAPI, raw forwarding and diagnostics.',
    'zx279128s-l3offload.c': 'Conntrack observation, classifier/hash/NAT tables, flow lifecycle and CPU fallback.',
    'zx279128s-idm.c': 'DMA ring/buffer allocation, mapping, descriptor encoding and completion accounting.',
    'zx279128s-idm-hw.c': 'Dedicated IDM device, register publication, IRQ/NAPI and transport lifetime.',
    'zx279128s-idm-wlan.c': 'Station authorization/epoch registry, callbacks and automatic enrollment work.',
    'zx279128s-wlan-flow.c': 'Validate and construct immutable paired WLAN NAT flow plans.',
    'zx279128s-wlan-fast.c': 'Flow admission, session/station state, direct forwarding and retirement.',
    'zx279128s-bufpool.c': 'Uncached payload allocation, pool-backed skb construction and safe recycling.',
    'mdio-zx279128s.c': 'Bounded clause-22 MDIO transactions and phylib bus registration.',
    'pcie-zx279128s.c': 'DesignWare host adaptation, reset/clock/PHY sequence, ATU and link handling.',
    'spi-zx279128s-sfc.c': 'SPI-mem PIO transactions, bounded polling, opcode validation and physical write gates.',
    'h3601p-flash.c': 'C image validator and fixed-window flash erase/write/readback helper; densely formatted.',
    'h3601p-upgrade.sh': 'Validate archive; RAM-stage storage transaction; commit CSP header last.',
    'install-bridge.sh': 'Verify/install the one-time upgrade bridge into the old recovery RAM environment.',
    'h3601p-upgrade-layout.c': 'Expose the rootfs-store view and enable the parent Bank B update view.',
    'h3601p-normal-overlay.sh': 'Locate/verify concat, mount JFFS2, process queued reset and pivot the root.',
    '80_mount_root': 'Normal preinit integration for the custom persistent root.',
    'jffs2reset': 'Queue reset for the next preinit instead of erasing the active upper filesystem.',
    'h3601p-write-fence.h': 'Physical NAND row allow-list with independent A/B/rootfs gates.',
    'h3601p-concat-fence.h': 'Earlier concat-stage physical write gate.',
    'h3601p-concat.sh': 'Earlier UBI concat/probe helper; historical design, not the final normal mount policy.',
    'h3601p-jffs2.sh': 'Earlier JFFS2 concat activation helper before the in-band correction.',
    'h3601p-inband.sh': 'r240 in-band JFFS2 concat probe/activation helper.',
    'h3601p-xattrs.c': 'Save, restore and verify overlay extended attributes during migration.',
    'h3601p-ubi-check.c': 'Inspect the expected UBI data/layout for the earlier storage path.',
    'migrate-jffs2.sh': 'Historical migration attempt using OOB markers; failed on physical remount.',
    'migrate-inband.sh': 'Corrected migration using in-band JFFS2 and restored overlay attributes.',
    'jffs2-inband-cleanmarkers.patch': 'Reserve/program a full data page for each NAND cleanmarker.',
    'prepare_nand_r240.py': 'Validate stock inputs; construct compatible CSP payload/header and recovery material.',
    'verify_cspboot.py': 'Exercise the original ARM bootloader code with scoped emulated inputs.',
    'verify_nand_bundle.py': 'Validate the packaged NAND experiment files and boundaries.',
    'build_rootfs.py': 'Compose LuCI/SquashFS root, preserve verified modules, install normal helpers and metadata.',
    'prepare_kernel.py': 'Build old-ABI bridge modules and normal built-in storage kernel/DTB.',
    'package_image.py': 'Build uImage/CSP objects, exact-member sysupgrade archive, metadata and bridge.',
    'rebuild.sh': 'Repeat-build orchestration for the prepared, pinned workspace.',
    'test_host.py': 'Archive, firmware, geometry, ABI/layout and release-object checks.',
    'test_cspboot.py': 'r241 matrix over original stock/UART-fixed ARM CSPBOOT code.',
    'test-fence.c': 'Enumerate physical row/gate behavior against the fence implementation.',
    'check_storage_headers.py': 'Check how candidate storage headers affect actual CSPBOOT scanning.',
    'setup_build.py': 'Prepare isolated concat-stage kernel build and toolchain context.',
    'build_images.py': 'Construct concat-stage probe/active RAM image candidates.',
    'patch_inband.py': 'Apply/generate the in-band cleanmarker kernel changes.',
    'inband-qemu-build_init.py': 'Construct a storage-test guest init environment.',
    '69_h3601p_overlay': 'Earlier initramfs preinit hook for persistent storage.',
    '68_h3601p_caldata': 'Experimental calibration hook; explicitly excluded from normal r241.',
    '99_network_tuning': 'First-boot UCI/network/radio/feed policy; overrides several builder defaults.',
    '02_network': 'Board-to-LAN/WAN interface defaults.',
    '00-rps': 'Packet-steering/RPS policy for this platform.',
    '10-wifi-detect': 'Wireless detection hotplug helper.',
    'rc.local': 'Runtime initialization/tuning inherited by the build composer.',
    'h3601p-debug': 'Collect platform debug status.',
    'h3601p-idm-status': 'Read IDM transport status.',
    'h3601p-idm-wlan-probe': 'Controlled IDM/WLAN bring-up probe helper.',
    'h3601p-measure': 'Collect bounded performance/counter samples.',
    'h3601p-nand': 'Earlier staged NAND load/check/write-control tooling; review storage assumptions.',
    'h3601p-wifi-up': 'Bring up configured radios during the earlier image workflow.',
    'h3601p-wlan-fast': 'Fast-path session/status/start/stop helper.',
    'h3601p-wlan-tx-stage': 'Controlled direct-TX staging and diagnostics.',
}

PATCH_ROLES = {
 '140': 'Firmware RX owned by NAPI; controlled firmware polling and dual-HIF transition.',
 '150': 'Route affected PCIe reads through the shared PL310 serialization guard.',
 '160': 'Station authorization/lifetime hooks for IDM integration.',
 '170': 'Use SCHED_NORMAL for the transmit worker.',
 '180': 'Initial bounded direct-TX integration.',
 '181': 'Connect IDM packet delivery to the direct transmit path.',
 '182': 'Scoped AQL bypass for the controlled direct path.',
 '183': 'Track bounded direct-TX credits.',
 '184': 'Preserve packet order under queueing/backpressure.',
 '185': 'Batch direct transmit work.',
 '186': 'Armed worker state and idle-transition coordination.',
 '187': 'Completion wakeup handling.',
 '188': 'Adjustable credit control.',
 '189': 'Historical credit default of 256; later patches change the final limit.',
 '190': 'Association-safe station resolution.',
 '191': 'Diagnostic reduction and lifetime-path refinements.',
 '192': 'IDM NAPI inline-transmit optimization.',
 '193': 'TXWI preparation/batching in the IDM NAPI path.',
 '194': 'Experimental stock hardware-TXP probe; not a supported final host mode.',
 '195': 'Experimental exact stock TXP layout.',
 '196': 'Experimental multi-MSDU host TXP layout.',
 '197': 'Experimental dual-TXP handling.',
 '198': 'Experimental host-TXP length marker.',
 '199': 'Reject host-TXP enablement; retain supported WA-TXP operation.',
 '200': 'Bounded work in transmit worker context.',
 '201': 'Integrate the uncached payload pool.',
 '202': 'Batch worker doorbell notifications.',
 '203': 'Credit/FIFO/TXWI pool changes for the later baseline.',
 '204': 'Reduce eligible direct-frame completion cost.',
 '205': 'NAPI placement and lean transmit scheduling.',
}


def role(row):
    p = Path(row['path'])
    if row['category'] == 'mt76 patch series':
        return PATCH_ROLES[p.name[:3]]
    if p.name in ROLES:
        return ROLES[p.name]
    if p.name == 'platform.sh':
        return ('Normal board check, RAM dependencies and upgrade/error entry points.'
                if 'r241' in str(p) else 'Historical target upgrade stub; replaced in the r241 composer.')
    if p.suffix == '.h': return 'Definitions and interfaces for the corresponding implementation; see subsystem text.'
    if p.suffix == '.dts': return 'Board memory, buses, interrupts and partitions; normal.dts is the normal-release variant.'
    if p.name.startswith('test_'): return 'Focused storage/boot/helper test for the named historical stage.'
    if p.name.startswith('package_'): return 'Package and validate the named earlier storage-stage artifacts.'
    if p.suffix == '.patch': return 'Kernel integration patch; exact affected paths and +/- counts are indexed below.'
    if p.name in {'Makefile', 'Kconfig', 'target.mk'}: return 'Build-system registration and target/package selection.'
    if 'config' in p.name or p.name in {'network', 'wireless', 'firewall'}: return 'Configuration/template, including inherited upstream selections; not all lines are new code.'
    if 'repositories' in str(p) or p.suffix == '.list': return 'Package-feed template; first-boot behavior is documented separately.'
    if p.suffix == '.conf': return 'Runtime sysctl/platform tuning defaults.'
    return 'Build integration/support file; follow the source link for exact behavior.'


def shipping_platform(rows):
    out = []
    for r in rows:
        p = r['path']
        if ('files-6.18/' in p and Path(p).suffix in {'.c', '.h', '.S'}
                and not p.endswith('spi-zx279128s-sfc.c')) or p in {
                'out/r241-normal/spi-zx279128s-sfc.c',
                'out/r241-normal/h3601p-write-fence.h'}:
            out.append(r)
    return out


def defines(path):
    lines = (ROOT / path).read_text().splitlines()
    i = 0
    while i < len(lines):
        start = i + 1
        s = lines[i]
        i += 1
        if not re.match(r'^\s*#\s*define\s+', s): continue
        while s.rstrip().endswith('\\') and i < len(lines):
            s = s.rstrip()[:-1] + ' ' + lines[i].strip()
            i += 1
        s = re.sub(r'/\*.*?\*/', '', s)
        m = re.match(r'^\s*#\s*define\s+(\w+(?:\([^)]*\))?)\s+(.+)', s)
        if not m: continue
        symbol, value = m.groups()
        value = re.sub(r'\s+', ' ', value).strip()
        if symbol.startswith('_') or symbol in {'pr_fmt'}: continue
        yield start, symbol, value


def main():
    rows = read_csv('current-source-inventory.csv')
    docs = read_csv('markdown-inventory.csv')
    summary = json.loads((AUDIT / 'summary.json').read_text())
    platform = shipping_platform(rows)
    assert (len(platform), sum(int(r['lines']) for r in platform), sum(int(r['bytes']) for r in platform)) == (22, 12420, 403344)
    out = ['','<a id="appendices"></a>', '## Generated engineering appendices', '',
           'Generated from this source snapshot. Counts include comments and blank lines. Expand individual sections for the complete file and constant indexes.', '',
           '### A. Accounting by source group', '',
           '| Group | Files | Physical lines | Nonblank | Bytes |',
           '| :--- | ---: | ---: | ---: | ---: |']
    for name,g in summary['current_groups'].items():
        out.append(f'| {esc(name)} | {g["files"]:,} | {g["lines"]:,} | {g["nonblank"]:,} | {g["bytes"]:,} |')
    out += ['', f'There are **{len(rows)} selected current/support/configuration files**. Do not sum these groups and label the result “all original code”: generated configurations, inherited build files, alternative-stage copies and patch context are intentionally visible.', '',
            'Machine-readable inventory: '+link('docs/audit/current-source-inventory.csv')+'.', '']
    tracked = AUDIT / 'tracked-build-context-deltas.csv'
    if tracked.exists():
        out += ['The tracked changes in the three inherited build files are much smaller than their full file lengths:', '',
                '| Tracked file | Added vs. pinned HEAD | Removed vs. pinned HEAD |',
                '| :--- | ---: | ---: |']
        for r in read_csv('tracked-build-context-deltas.csv'):
            out.append(f'| {link(r["path"])} | +{r["added"]} | −{r["removed"]} |')
        out += ['', 'Exact comparison base and counts: '+link('docs/audit/tracked-build-context-deltas.csv')+'.', '']
    groups = collections.defaultdict(list)
    for r in rows: groups[r['category']].append(r)
    out += ['### B. Every selected file, with its responsibility', '']
    for group, items in groups.items():
        out += ['<details>', f'<summary><strong>{esc(group)}</strong> — {len(items)} files</summary>', '',
                '| File | Lines | Nonblank | Bytes | Responsibility |',
                '| :--- | ---: | ---: | ---: | :--- |']
        for r in items:
            out.append(f'| {link(r["path"])} | {int(r["lines"]):,} | {int(r["nonblank"]):,} | {int(r["bytes"]):,} | {esc(role(r))} |')
        out += ['', '</details>', '']
    out += ['### C. Patch deltas and affected upstream files', '',
            'Additions/deletions are per patch, excluding `+++` / `---` file headers. Later patches may revise or disable earlier work; totals are not a unique final diff.', '']
    for group in ('mt76 patch series', 'target overlay', 'concat and JFFS2 implementation/tests'):
        items = [r for r in groups[group] if r['added'] != '']
        out += ['<details>', f'<summary><strong>{esc(group)}</strong> — patch details</summary>', '',
                '| Patch | Physical lines | Added | Removed | Affected paths |',
                '| :--- | ---: | ---: | ---: | :--- |']
        for r in items:
            paths = re.findall(r'^\+\+\+\s+(\S+)', (ROOT / r['path']).read_text(), re.M)
            paths = list(dict.fromkeys(p.removeprefix('b/') for p in paths))
            out.append(f'| {link(r["path"], Path(r["path"]).name)} | {r["lines"]} | +{r["added"]} | −{r["removed"]} | '+ '<br>'.join(f'`{esc(p)}`' for p in paths) + ' |')
        out += ['', '</details>', '']
    out += ['### D. Source constants: register offsets, bit fields and limits', '',
            '**This is a literal source index, not a list of absolute hardware addresses.** Expressions may be offsets, masks, counts, enum-like values or memory-layout constants. Use the subsystem base tables above and the linked accessors to determine the address space. Unknown source names are left unknown. Function-like macros are shown without evaluating them.', '']
    constants = []
    for r in platform:
        ds = list(defines(r['path']))
        if not ds: continue
        out += ['<details>', f'<summary><strong>{esc(Path(r["path"]).name)}</strong> — {len(ds)} definitions</summary>', '',
                '| Symbol | Source expression | Definition |', '| :--- | :--- | :--- |']
        for line, name, value in ds:
            out.append(f'| {code(name)} | {code(value)} | {link(r["path"], "line "+str(line), line)} |')
            constants.append({'path':r['path'], 'line':line, 'symbol':name, 'expression':value})
        out += ['', '</details>', '']
    with (AUDIT / 'source-constants.csv').open('w', newline='') as f:
        w = csv.DictWriter(f,fieldnames=['path','line','symbol','expression']);w.writeheader();w.writerows(constants)
    out += [f'Indexed **{len(constants)} definitions**. CSV: '+link('docs/audit/source-constants.csv')+'.', '',
            '### E. Complete project Markdown record index', '',
            'These documents preserve their original stage and may contain superseded instructions, uncertain hypotheses or an earlier partition numbering scheme. Read the current installation section before using any old procedure.', '',
            '<details>', '<summary><strong>154 project Markdown records</strong> — paths, physical lines and bytes</summary>', '',
            '| Record | Lines | Bytes |', '| :--- | ---: | ---: |']
    for r in docs:
        if r['category']=='project record':
            out.append(f'| {link(r["path"])} | {int(r["lines"]):,} | {int(r["bytes"]):,} |')
    out += ['', '</details>', '',
            'The complete Markdown CSV also includes the 11 scanned upstream documents: '+link('docs/audit/markdown-inventory.csv')+'.', '',
            '### F. Archived code and duplicate accounting', '',
            f'The historical CSV catalogs **{summary["archive_files"]:,} source/script/patch snapshots** under the scanned `out/` paths. It includes duplicates and some upstream-derived files. It is an archive index, not an additional current-code total: '+link('docs/audit/historical-source-inventory.csv')+'.', '',
            'Exact-content duplicates among selected files:', '']
    for paths in summary['identical_current_files']:
        out.append('- ' + '; '.join(link(p) for p in paths) + '.')
    out += ['', 'SHA-256 values in the CSV files identify the counted contents. Re-run the audit after changing source; do not update narrative claims by guessing new line counts.', '']
    path=ROOT/'README.md'
    s=path.read_text()
    assert s.count(BEGIN)==s.count(END)==1
    head, tail=s.split(BEGIN,1)
    _,tail=tail.split(END,1)
    path.write_text(head+BEGIN+'\n'+'\n'.join(out)+'\n'+END+tail)
    print(json.dumps({'selected_files':len(rows),'platform_files':len(platform),'constant_definitions':len(constants),'readme_lines':len(path.read_text().splitlines())},indent=2))


if __name__ == '__main__':
    main()
