#!/usr/bin/env python3
"""idtool - read the serial number and Wi-Fi/Bluetooth MACs from Unisoc dumps, and make
patched COPIES of those dumps.

Safety:
  * It only reads and writes ordinary files. It never touches a partition or a phone.
  * It never edits a file in place: patched output always goes to a new file.
  * It does not handle the IMEI or any NV item.
  * Flashing a patched file back is a separate step and can fail or brick a phone.
    Keep the original dumps and their SHA-256 sums.

Layout facts (verified on one RMX3830 dump, see docs/07 and docs/09):
  miscdata : magic 'SP09' (bytes 39 30 50 53) at 0, SN1 = 24 bytes at 0x04.
  prodnv   : ext4 image; wifimac.txt and btmac.txt hold the MACs as 'aa:bb:cc:dd:ee:ff'.
Unknown: whether the 64-byte block at miscdata 0x2000 depends on the serial. A patched
miscdata may be rejected by the phone.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

MAGIC = b"90PS"
SN_OFF, SN_LEN = 0x04, 24
MAC_FMT = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
MAC_RAW = re.compile(rb"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
SERIAL_FMT = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mask_sn(s, on):
    return s if not on or len(s) <= 4 else s[:4] + "*" * (len(s) - 4)


def mask_mac(m, on):
    return m if not on else m[:8] + ":**:**:**"


def read_serial(path):
    with open(path, "rb") as f:
        d = f.read(0x100)
    if d[:4] != MAGIC:
        return None
    return d[SN_OFF:SN_OFF + SN_LEN].split(b"\0")[0].decode("ascii", "replace")


def is_ext4(path):
    with open(path, "rb") as f:
        f.seek(1080)
        return f.read(2) == b"\x53\xef"


def debugfs_cat(img, name):
    try:
        r = subprocess.run(["debugfs", "-R", "cat /" + name, img],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = r.stdout.strip()
    return out.decode("ascii", "replace") if out else None


def read_macs(img):
    """Return {'wifi': .., 'bt': ..} using debugfs, else {'raw': [(offset, mac), ...]}."""
    res = {}
    for key, name in (("wifi", "wifimac.txt"), ("bt", "btmac.txt")):
        v = debugfs_cat(img, name)
        if v and MAC_FMT.match(v.split()[0]):
            res[key] = v.split()[0]
    if res:
        return res
    with open(img, "rb") as f:
        data = f.read()
    return {"raw": [(m.start(), m.group().decode()) for m in MAC_RAW.finditer(data)][:10]}


def find_inputs(path):
    """Return (miscdata_path or None, prodnv_path or None) for a file or a folder."""
    if os.path.isdir(path):
        mi = os.path.join(path, "miscdata.bin")
        pr = os.path.join(path, "prodnv.bin")
        return (mi if os.path.isfile(mi) else None, pr if os.path.isfile(pr) else None)
    if read_serial(path) is not None:
        return path, None
    return None, (path if is_ext4(path) else None)


def cmd_get(a):
    mi, pr = find_inputs(a.path)
    if not mi and not pr:
        sys.exit("nothing recognised: need miscdata.bin (SP09 record) and/or prodnv.bin (ext4)")
    if mi:
        sn = read_serial(mi)
        print("serial (SN1) in %s: %s" % (os.path.basename(mi), mask_sn(sn, a.mask) if sn else "(empty)"))
    if pr:
        macs = read_macs(pr)
        for k in ("wifi", "bt"):
            if k in macs:
                print("%s MAC in %s: %s" % (k, os.path.basename(pr), mask_mac(macs[k], a.mask)))
        for off, m in macs.get("raw", []):
            print("MAC-like string at 0x%X: %s" % (off, mask_mac(m, a.mask)))


def guard_output(src, out, force):
    if os.path.exists(out):
        if os.path.samefile(src, out):
            sys.exit("refusing to overwrite the input file; choose a new --out")
        if not force:
            sys.exit("%s exists; use --force to replace it" % out)


def changed_ranges(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


def do_patch_serial(src, out, serial, force=False):
    if not SERIAL_FMT.match(serial):
        sys.exit("serial must be 1-24 characters from A-Z a-z 0-9 _ -")
    guard_output(src, out, force)
    with open(src, "rb") as f:
        d = bytearray(f.read())
    if d[:4] != MAGIC:
        sys.exit("%s does not start with the SP09 marker; layout unknown, aborting" % src)
    new = bytearray(d)
    new[SN_OFF:SN_OFF + SN_LEN] = serial.encode().ljust(SN_LEN, b"\0")
    diff = changed_ranges(d, new)
    if diff and not (min(diff) >= SN_OFF and max(diff) < SN_OFF + SN_LEN):
        sys.exit("internal check failed: bytes outside the SN1 field would change")
    with open(out, "wb") as f:
        f.write(new)
    print("wrote %s (%d byte(s) changed, all inside the SN1 field)" % (out, len(diff)))
    print("sha256 in :", sha(src))
    print("sha256 out:", sha(out))


def check_mac(m):
    if not MAC_FMT.match(m):
        sys.exit("MAC must look like aa:bb:cc:dd:ee:ff")
    first = int(m[:2], 16)
    if first & 1:
        sys.exit("%s is a multicast address (first octet is odd); not valid for a device" % m)
    if int(m.replace(":", ""), 16) == 0:
        sys.exit("all-zero MAC is not valid")


def do_patch_mac(src, out, old, new, force=False):
    check_mac(old)
    check_mac(new)
    guard_output(src, out, force)
    with open(src, "rb") as f:
        d = bytearray(f.read())
    pat = old.lower().encode()
    offs = []
    i = d.find(pat)
    while i != -1:
        offs.append(i)
        i = d.find(pat, i + 1)
    if not offs:
        sys.exit("the old MAC was not found in %s (case-sensitive lowercase match)" % src)
    new_b = new.lower().encode()
    out_d = bytearray(d)
    for o in offs:
        out_d[o:o + len(new_b)] = new_b
    with open(out, "wb") as f:
        f.write(out_d)
    print("replaced %d occurrence(s) at %s" % (len(offs), ", ".join(hex(o) for o in offs)))
    print("sha256 in :", sha(src))
    print("sha256 out:", sha(out))


def cmd_patch_serial(a):
    do_patch_serial(a.input, a.out, a.serial, a.force)


def cmd_patch_mac(a):
    do_patch_mac(a.input, a.out, a.old, a.new, a.force)


def cmd_restore(a):
    b_mi, b_pr = find_inputs(a.from_backup)
    t_mi, t_pr = find_inputs(a.to)
    plan = []
    if b_mi and t_mi:
        bs, ts = read_serial(b_mi), read_serial(t_mi)
        print("serial   backup=%s  current=%s" % (mask_sn(bs or "", a.mask), mask_sn(ts or "", a.mask)))
        if bs and bs != ts:
            plan.append(("serial", t_mi, bs, ts))
    if b_pr and t_pr:
        bm, tm = read_macs(b_pr), read_macs(t_pr)
        for k in ("wifi", "bt"):
            if k in bm and k in tm:
                print("%-8s backup=%s  current=%s" % (k + " MAC", mask_mac(bm[k], a.mask), mask_mac(tm[k], a.mask)))
                if bm[k].lower() != tm[k].lower():
                    plan.append((k, t_pr, bm[k], tm[k]))
    if not plan:
        print("nothing to restore: the values already match (or one side could not be read)")
        return
    if not a.yes:
        print("dry run: %d change(s) would be made. Add --yes to write patched copies to %s" % (len(plan), a.out))
        return
    os.makedirs(a.out, exist_ok=True)
    cur = {}
    for kind, target, new, old in plan:
        base = os.path.basename(target)
        src = cur.get(base, target)
        out = os.path.join(a.out, base)
        if os.path.abspath(out) == os.path.abspath(target):
            sys.exit("--out must not be the folder that holds the current dump")
        if kind == "serial":
            do_patch_serial(src, out, new, force=True)
        else:
            do_patch_mac(src, out, old, new, force=True)
        cur[base] = out
    print("done. Patched copies are in", a.out, "- originals untouched.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="show serial / MACs found in a dump file or folder")
    g.add_argument("path")
    g.add_argument("--mask", action="store_true")
    g.set_defaults(fn=cmd_get)
    s = sub.add_parser("patch-serial", help="write a patched COPY of miscdata with a new SN1")
    s.add_argument("input")
    s.add_argument("--serial", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_patch_serial)
    m = sub.add_parser("patch-mac", help="write a patched COPY of prodnv with one MAC replaced")
    m.add_argument("input")
    m.add_argument("--old", required=True)
    m.add_argument("--new", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--force", action="store_true")
    m.set_defaults(fn=cmd_patch_mac)
    r = sub.add_parser("restore", help="take serial/MACs from a backup folder and patch copies of the current dump")
    r.add_argument("--from-backup", required=True)
    r.add_argument("--to", required=True, help="folder with the current miscdata.bin / prodnv.bin")
    r.add_argument("--out", required=True)
    r.add_argument("--yes", action="store_true", help="actually write the patched copies (default is a dry run)")
    r.add_argument("--mask", action="store_true")
    r.set_defaults(fn=cmd_restore)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
