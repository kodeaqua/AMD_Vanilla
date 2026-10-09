#!/usr/bin/env python3
"""Verifikasi patch OpenCore (Kernel -> Patch) terhadap binary kernel macOS.

Hanya membaca: plist dan kernel tidak pernah diubah. Patch disimulasikan di memori.

Semantik mengikuti OpenCore (OcAppleKernelLib/KernelPatcher):
  - Mask kosong        -> semua byte Find dibandingkan.
  - Find cocok bila (data & Mask) == (Find & Mask).
  - ReplaceMask kosong -> seluruh Replace ditulis; selain itu
    new = (old & ~ReplaceMask) | (Replace & ReplaceMask).
  - Base               -> pencarian dimulai dari alamat simbol (tanpa Base: seluruh kernel).
  - Limit 0            -> sampai akhir citra; Skip = lewati N kecocokan pertama.
  - Count 0            -> patch semua kecocokan; selain itu hanya Count kecocokan pertama.

Pemakaian:
  python3 tools/verify.py [--plist patches.plist] [--kernel PATH] [--darwin 25.6.0]
                          [--all-versions] [--index N ...] [-v]

Status per patch:
  OK        cocok sesuai Count, panjang sama, diff terhitung
  NO-MATCH  Find tidak ditemukan
  MULTI     kecocokan lebih banyak dari Count (OpenCore hanya menambal Count pertama,
            tetapi unik-nya Find diragukan; periksa Base/Mask)
  FEWER     kecocokan kurang dari Count (Count > 0)
  LENGTH    panjang Find/Replace/Mask/ReplaceMask tidak konsisten
  NO-BASE   simbol Base tidak ada di tabel simbol kernel
  NOT-KERNEL Identifier bukan "kernel" (kext), tidak bisa diperiksa di sini
  N/A       di luar rentang MinKernel..MaxKernel untuk versi Darwin yang dipilih
"""
import argparse
import bisect
import os
import platform
import plistlib
import re
import subprocess
import sys

try:
    import lief
except ImportError:
    sys.exit("lief tidak ada. Jalankan lewat .venv: .venv/bin/python tools/verify.py")
try:
    import capstone
except ImportError:
    capstone = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL_STATUSES = {"NO-MATCH", "FEWER", "LENGTH", "NO-BASE"}
WARN_STATUSES = {"MULTI"}


def parse_ver(s):
    parts = [int(x) for x in re.findall(r"\d+", s)][:3]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def kernel_build():
    """Nama folder build dari `uname -v`, mis. xnu-12377.161.15.700.19."""
    out = subprocess.run(["uname", "-v"], capture_output=True, text=True).stdout
    m = re.search(r"root:(xnu-[\d.]+)", out)
    return m.group(1) if m else None


def applies(p, darwin):
    lo = parse_ver(p.get("MinKernel") or "0.0.0")
    hi = parse_ver(p.get("MaxKernel") or "999.99.99")
    return lo <= darwin <= hi


class Kernel:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        b = lief.parse(path)
        if b is None:
            sys.exit("lief gagal membaca %s" % path)
        if isinstance(b, lief.MachO.FatBinary):
            b = b.at(0)
        self.bin = b
        self.segs = [(s.name, s.virtual_address, s.file_offset, s.file_size)
                     for s in b.segments if s.name != "__LINKEDIT" and s.file_size]
        self.syms = {}
        for s in b.symbols:
            if s.value:
                self.syms.setdefault(s.name, s.value)
        self._sorted = sorted((v, n) for n, v in self.syms.items())
        self._addrs = [v for v, _ in self._sorted]

    def symbol_at(self, va):
        """Simbol terdekat di bawah/sama dengan va, sebagai 'nama+0xoff'."""
        i = bisect.bisect_right(self._addrs, va) - 1
        if i < 0:
            return "?"
        v, n = self._sorted[i]
        return "%s+0x%x" % (n, va - v)

    def vaddr_to_off(self, va):
        for _, v, o, sz in self.segs:
            if v <= va < v + sz:
                return o + (va - v)
        return None

    def off_to_vaddr(self, off):
        for _, v, o, sz in self.segs:
            if o <= off < o + sz:
                return v + (off - o)
        return None

    def ranges(self, start_off=None, limit=0):
        """Rentang file (start, end) yang dicari, hanya segmen non-LINKEDIT."""
        out = []
        for _, v, o, sz in self.segs:
            lo, hi = o, o + sz
            if start_off is not None:
                if hi <= start_off:
                    continue
                lo = max(lo, start_off)
            out.append((lo, hi))
        if limit and start_off is not None:
            out = [(lo, min(hi, start_off + limit)) for lo, hi in out if lo < start_off + limit]
        return out


def find_all(data, find, mask, ranges):
    """Semua offset tempat (data & mask) == (find & mask). Pakai anchor literal agar cepat."""
    n = len(find)
    # run terpanjang dengan mask == 0xFF sebagai anchor
    best = (0, 0)
    i = 0
    while i < n:
        if mask[i] == 0xFF:
            j = i
            while j < n and mask[j] == 0xFF:
                j += 1
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 1
    a, b = best
    hits = []
    for lo, hi in ranges:
        if b > a:
            anchor = find[a:b]
            pos = data.find(anchor, lo + a, hi)
            while pos != -1:
                st = pos - a
                if st >= lo and st + n <= hi:
                    if all((data[st + k] & mask[k]) == (find[k] & mask[k]) for k in range(n)):
                        hits.append(st)
                pos = data.find(anchor, pos + 1, hi)
        else:  # mask seluruhnya wildcard: tidak informatif
            for st in range(lo, hi - n + 1):
                hits.append(st)
    return sorted(set(hits))


def apply_replace(old, rep, rmask):
    return bytes((o & ~m & 0xFF) | (r & m) for o, r, m in zip(old, rep, rmask))


def disasm(kern, off, size, tag):
    if capstone is None:
        return ["    (capstone tidak terpasang)"]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    code = kern.data[off:off + size] if tag == "before" else tag
    va = kern.off_to_vaddr(off) or off
    lines = []
    covered = 0
    for ins in md.disasm(code, va):
        lines.append("    %016x  %-24s %s %s" % (
            ins.address, ins.bytes.hex(" "), ins.mnemonic, ins.op_str))
        covered += ins.size
    if covered < len(code):
        lines.append("    ... %d byte tidak terdisassemble: %s" % (
            len(code) - covered, code[covered:].hex(" ")))
    return lines


def verify_patch(kern, p):
    r = {"status": None, "notes": [], "hits": [], "changes": []}
    ident = p.get("Identifier", "kernel")
    if ident != "kernel":
        r["status"] = "NOT-KERNEL"
        r["notes"].append("Identifier = %r" % ident)
        return r
    find, rep = bytes(p["Find"]), bytes(p["Replace"])
    mask = bytes(p.get("Mask") or b"") or b"\xff" * len(find)
    rmask = bytes(p.get("ReplaceMask") or b"") or b"\xff" * len(rep)
    if len(find) != len(rep):
        r["notes"].append("len(Find)=%d != len(Replace)=%d" % (len(find), len(rep)))
    if len(mask) != len(find):
        r["notes"].append("len(Mask)=%d != len(Find)=%d" % (len(mask), len(find)))
    if len(rmask) != len(rep):
        r["notes"].append("len(ReplaceMask)=%d != len(Replace)=%d" % (len(rmask), len(rep)))
    if r["notes"]:
        r["status"] = "LENGTH"
        return r
    if not find:
        r["status"] = "LENGTH"
        r["notes"].append("Find kosong")
        return r
    # mask harus konsisten: byte Find di posisi wildcard seharusnya 00
    if any(f & ~m & 0xFF for f, m in zip(find, mask)):
        r["notes"].append("Find punya bit di luar Mask (diabaikan oleh OpenCore)")

    base = p.get("Base") or ""
    start = None
    if base:
        va = kern.syms.get(base)
        if va is None:
            r["status"] = "NO-BASE"
            r["notes"].append("simbol %r tidak ada di kernel%s" % (
                base, " (ada tanpa spasi/whitespace di tepi: %r)" % base.strip()
                if base.strip() in kern.syms else ""))
            return r
        start = kern.vaddr_to_off(va)
        if start is None:
            r["status"] = "NO-BASE"
            r["notes"].append("simbol %s (0x%x) di luar segmen" % (base, va))
            return r
        r["base_off"] = start
    hits = find_all(kern.data, find, mask, kern.ranges(start, p.get("Limit", 0)))
    skip, count = p.get("Skip", 0), p.get("Count", 0)
    avail = hits[skip:]
    applied = avail if count == 0 else avail[:count]
    r["hits_all"] = hits
    r["hits"] = applied
    if not hits:
        r["status"] = "NO-MATCH"
        return r
    if count and len(applied) < count:
        r["status"] = "FEWER"
        r["notes"].append("ditemukan %d, Count=%d" % (len(applied), count))
    elif count and len(avail) > count:
        r["status"] = "MULTI"
        r["notes"].append("total kecocokan %d, Count=%d (Skip=%d)" % (len(hits), count, skip))
    else:
        r["status"] = "OK"
    for off in applied:
        old = kern.data[off:off + len(find)]
        new = apply_replace(old, rep, rmask)
        diff = [(off + i, old[i], new[i]) for i in range(len(old)) if old[i] != new[i]]
        r["changes"].append((off, old, new, diff))
        if not diff:
            r["notes"].append("0x%x: patch tidak mengubah byte apa pun (no-op)" % off)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plist", default=os.path.join(ROOT, "patches.plist"))
    ap.add_argument("--kernel", help="default: kernels/<build dari uname -v>/kernel")
    ap.add_argument("--darwin", help="versi Darwin target, default platform.release()")
    ap.add_argument("--all-versions", action="store_true", help="abaikan MinKernel/MaxKernel")
    ap.add_argument("--index", type=int, nargs="*", help="hanya patch dengan indeks ini")
    ap.add_argument("-v", "--verbose", action="store_true", help="tampilkan disassembly sebelum/sesudah")
    a = ap.parse_args()

    kpath = a.kernel
    if not kpath:
        build = kernel_build()
        kpath = os.path.join(ROOT, "kernels", build or "", "kernel")
    if not os.path.isfile(kpath):
        sys.exit("kernel tidak ditemukan: %s" % kpath)
    darwin = parse_ver(a.darwin or platform.release())

    with open(a.plist, "rb") as f:
        patches = plistlib.load(f)["Kernel"]["Patch"]
    kern = Kernel(kpath)
    print("Kernel : %s" % os.path.relpath(kpath, ROOT))
    print("Darwin : %d.%d.%d%s" % (darwin + (" (semua versi)" if a.all_versions else "",)))
    print("Plist  : %s (%d patch)\n" % (os.path.relpath(a.plist, ROOT), len(patches)))

    results = []
    for i, p in enumerate(patches):
        if a.index is not None and i not in a.index:
            continue
        if not a.all_versions and not applies(p, darwin):
            res = {"status": "N/A", "notes": [], "hits": [], "changes": []}
        else:
            res = verify_patch(kern, p)
        results.append((i, p, res))

    for i, p, res in results:
        en = "on " if p.get("Enabled") else "off"
        print("[%02d] %-10s %s  %s" % (i, res["status"], en, p["Comment"]))
        print("     Base=%s Count=%s Skip=%s Kernel=%s..%s" % (
            p.get("Base") or "-", p.get("Count"), p.get("Skip"), p.get("MinKernel"), p.get("MaxKernel")))
        for n in res["notes"]:
            print("     ! %s" % n)
        if res["status"] in ("N/A", "NOT-KERNEL"):
            continue
        if "hits_all" in res:
            print("     kecocokan total=%d diterapkan=%d" % (len(res["hits_all"]), len(res["hits"])))
        for off, old, new, diff in res["changes"]:
            va = kern.off_to_vaddr(off)
            print("     @ file 0x%x  vaddr %s  (%d byte)  di %s" % (
                off, "0x%x" % va if va else "?", len(old), kern.symbol_at(va) if va else "?"))
            print("       sebelum: %s" % old.hex(" "))
            print("       sesudah: %s" % new.hex(" "))
            print("       diff   : %s" % (", ".join("+%d:%02x->%02x" % (o - off, x, y) for o, x, y in diff) or "-"))
            if a.verbose:
                ctx = 16
                print("     disassembly sebelum (ke depan %d byte dari match):" % ctx)
                for l in disasm(kern, off, len(old) + ctx, "before"):
                    print(l)
                print("     disassembly sesudah (match diganti, sisa byte asli):")
                tail = kern.data[off + len(old):off + len(old) + ctx]
                for l in disasm(kern, off, len(old), new + tail):
                    print(l)
        print()

    # tumpang tindih antar patch yang aktif dan berlaku
    spans = []
    for i, p, res in results:
        if p.get("Enabled") and res["status"] in ("OK", "MULTI"):
            for off, old, new, diff in res["changes"]:
                if diff:
                    spans.append((diff[0][0], diff[-1][0] + 1, i))
    overlaps = []
    for x in range(len(spans)):
        for y in range(x + 1, len(spans)):
            s1, s2 = spans[x], spans[y]
            if s1[2] != s2[2] and s1[0] < s2[1] and s2[0] < s1[1]:
                overlaps.append((s1[2], s2[2], max(s1[0], s2[0])))
    if overlaps:
        print("PERINGATAN: patch aktif yang menimpa byte yang sama:")
        for i, j, off in overlaps:
            print("  [%02d] dan [%02d] di file 0x%x" % (i, j, off))
        print()

    from collections import Counter
    c = Counter(res["status"] for _, _, res in results)
    print("Ringkasan: " + ", ".join("%s=%d" % kv for kv in sorted(c.items())))
    print("Catatan  : hasil di atas = BELUM DITES HARDWARE.")
    bad = [i for i, p, res in results if res["status"] in FAIL_STATUSES and p.get("Enabled")]
    warn = [i for i, p, res in results if res["status"] in WARN_STATUSES and p.get("Enabled")]
    if bad:
        print("GAGAL (aktif): %s" % bad)
    if warn:
        print("PERLU DICEK (aktif): %s" % warn)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
