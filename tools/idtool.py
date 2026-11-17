#!/usr/bin/env python3
"""idtool - read the serial number, Wi-Fi/Bluetooth MACs, and IMEIs from Unisoc dumps,
and make patched COPIES of those dumps.

Safety:
  * It only reads and writes ordinary files. It never touches a partition or a phone.
  * It never edits a file in place: patched output always goes to a new file.
  * Flashing a patched file back is a separate step and can fail or brick a phone.
    Keep the original dumps and their SHA-256 sums.

Layout facts (verified on one RMX3830 dump, see docs/01, docs/07 and docs/09):
  miscdata : magic 'SP09' (bytes 39 30 50 53) at 0, SN1 = 24 bytes at 0x04.
  prodnv   : ext4 image; wifimac.txt and btmac.txt hold the MACs as 'aa:bb:cc:dd:ee:ff'.
  l_fixnv* / l_runtimenv* : NV files holding IMEI 1 (record 0x0005) and IMEI 2 (record 0x0179).
Unknown: whether the 64-byte block at miscdata 0x2000 depends on the serial, or whether
the modem prioritizes sprd_ss secure storage over NV. A patched dump may be rejected by the phone.
"""
import argparse
import glob
import hashlib
import os
import re
import struct
import subprocess
import sys

MAGIC = b"90PS"
SN_OFF, SN_LEN = 0x04, 24
MAC_FMT = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
MAC_RAW = re.compile(rb"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
SERIAL_FMT = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
IMEI_IDS = {0x0005: "IMEI1", 0x0179: "IMEI2"}
IMEI_FMT = re.compile(r"^\d{15}$")


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


def mask_imei(s, on):
    return s if not on or len(s) <= 8 else s[:8] + "*" * (len(s) - 8)


def read_serial(path):
    try:
        with open(path, "rb") as f:
            d = f.read(0x100)
        if d[:4] != MAGIC:
            return None
        return d[SN_OFF:SN_OFF + SN_LEN].split(b"\0")[0].decode("ascii", "replace")
    except OSError:
        return None


def is_ext4(path):
    try:
        with open(path, "rb") as f:
            f.seek(1080)
            return f.read(2) == b"\x53\xef"
    except OSError:
        return False


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


def calc_unisoc_checksum(data: bytes) -> int:
    """Calculates standard Spreadtrum/Unisoc 16-bit one's complement checksum."""
    chkSum = 0
    l = len(data)
    idx = 0
    while l > 1:
        num = data[idx] | (data[idx + 1] << 8)
        chkSum += num
        idx += 2
        l -= 2
    if l:
        chkSum += data[idx]
    chkSum = (chkSum >> 16) + (chkSum & 0xffff)
    chkSum += (chkSum >> 16)
    return (~chkSum) & 0xffff


def compute_luhn(s14):
    """Compute 15th Luhn check digit for a 14-digit IMEI base string."""
    total = 0
    for i, c in enumerate(reversed(s14)):
        d = int(c)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10


def luhn_ok(s):
    total = 0
    for i, c in enumerate(reversed(s)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def decode_imei(rec):
    """8-byte NV record -> 15 digits, or None if the first nibble is not 0xA."""
    if len(rec) != 8 or (rec[0] & 0x0F) != 0xA:
        return None
    s = "".join("%X%X" % (b & 0x0F, b >> 4) for b in rec)[1:]
    return s if s.isdigit() and len(s) == 15 else None


def encode_imei(s):
    n = "A" + s
    return bytes(int(n[i + 1], 16) << 4 | int(n[i], 16) for i in range(0, 16, 2))


def parse_imei_arg(val, label, skip_luhn=False):
    if not val:
        return None
    val = val.strip()
    if not val.isdigit():
        sys.exit("%s must contain only digits" % label)
    if len(val) == 14:
        cd = compute_luhn(val)
        full = val + str(cd)
        print("Note: %s was 14 digits; computed Luhn check digit '%s' -> %s" % (label, cd, full))
        return full
    if len(val) == 15:
        if not skip_luhn and not luhn_ok(val):
            expected = compute_luhn(val[:14])
            sys.exit("%s '%s' has an invalid Luhn check digit (expected '%s', got '%s'). Use --skip-luhn to override."
                     % (label, val, expected, val[14]))
        return val
    sys.exit("%s must be 14 or 15 digits (got %d digits)" % (label, len(val)))


def read_imeis_from_data(data):
    """Return dict {rec_id: [(offset, imei_str), ...]} for all recognized IMEI records."""
    res = {}
    for rec_id in IMEI_IDS:
        pat = struct.pack("<HH", rec_id, 8)
        for m in re.finditer(re.escape(pat), data):
            rec = data[m.end():m.end() + 8]
            imei = decode_imei(rec)
            if imei and luhn_ok(imei):
                res.setdefault(rec_id, []).append((m.start(), imei))
    return res


def read_imeis(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return read_imeis_from_data(data)
    except OSError:
        return {}


def find_nv_files(path):
    """Return list of .bin files that contain valid IMEI NV records."""
    if os.path.isfile(path):
        return [path] if read_imeis(path) else []
    if os.path.isdir(path):
        matched = []
        for f in sorted(glob.glob(os.path.join(path, "**", "*.bin"), recursive=True)):
            if read_imeis(f):
                matched.append(f)
        return matched
    return []


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
    nvs = find_nv_files(a.path)
    if not mi and not pr and not nvs:
        sys.exit("nothing recognised: need miscdata.bin (SP09 record), prodnv.bin (ext4), or NV files (.bin)")
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
    if nvs:
        for nv in nvs:
            imeis = read_imeis(nv)
            for rec_id, entries in imeis.items():
                lbl = IMEI_IDS.get(rec_id, "IMEI 0x%04X" % rec_id)
                for off, imei_val in entries:
                    print("%s in %s at 0x%X: %s" % (lbl, os.path.basename(nv), off, mask_imei(imei_val, a.mask)))


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


def do_patch_imei_file(src, out, imei1=None, imei2=None, force=False, mask_output=False):
    guard_output(src, out, force)
    with open(src, "rb") as f:
        d = bytearray(f.read())

    targets = {}
    if imei1:
        targets[0x0005] = ("IMEI1", imei1)
    if imei2:
        targets[0x0179] = ("IMEI2", imei2)
    if not targets:
        sys.exit("at least one of --imei1 or --imei2 must be specified")

    new_d = bytearray(d)
    patched_info = []
    allowed_diff_indices = set()

    for rec_id, (label, new_val) in targets.items():
        pat = struct.pack("<HH", rec_id, 8)
        matches = list(re.finditer(re.escape(pat), bytes(d)))
        for m in matches:
            payload_off = m.end()
            old_bytes = bytes(d[payload_off:payload_off + 8])
            old_val = decode_imei(old_bytes)
            # Strict validation: Must decode to a valid 15-digit BCD IMEI with valid Luhn checksum!
            if not old_val or not luhn_ok(old_val):
                continue
            new_bytes = encode_imei(new_val)
            new_d[payload_off:payload_off + 8] = new_bytes
            allowed_diff_indices.update(range(payload_off, payload_off + 8))
            patched_info.append((label, rec_id, m.start(), old_val, new_val))

    if not patched_info:
        sys.exit("no genuine IMEI NV record(s) found in %s" % src)

    # If this file has a Unisoc FixNV 512-byte header, recalculate the body checksum
    if len(new_d) >= 512 and new_d[:4] == b"VN\x00\x00":
        magic, length, old_crc, ver = struct.unpack('<IIII', new_d[:16])
        if length <= len(new_d) - 512:
            body = bytes(new_d[512:512 + length])
            new_crc = calc_unisoc_checksum(body)
            struct.pack_into('<I', new_d, 8, new_crc)
            allowed_diff_indices.update(range(8, 12))
            patched_info.append(("FixNV CRC", 0x0000, 8, "0x%04X" % old_crc, "0x%04X" % new_crc))

    diff = changed_ranges(d, new_d)
    for idx in diff:
        if idx not in allowed_diff_indices:
            sys.exit("internal check failed: byte at 0x%X outside IMEI payload would change" % idx)

    with open(out, "wb") as f:
        f.write(new_d)

    print("wrote %s (%d byte(s) changed across %d record(s)):" % (out, len(diff), len(patched_info)))
    for label, rec_id, off, old_val, new_val in patched_info:
        old_str = mask_imei(old_val, mask_output)
        new_str = mask_imei(new_val, mask_output)
        print("  %s (0x%04X) at 0x%X: %s -> %s" % (label, rec_id, off, old_str, new_str))
    print("sha256 in :", sha(src))
    print("sha256 out:", sha(out))
    return True


def do_patch_imei(src, out, imei1=None, imei2=None, force=False, mask_output=False):
    if os.path.isfile(src):
        return do_patch_imei_file(src, out, imei1=imei1, imei2=imei2, force=force, mask_output=mask_output)
    if os.path.isdir(src):
        if os.path.exists(out) and not os.path.isdir(out):
            sys.exit("--out must be a directory when input is a directory")
        if os.path.abspath(src) == os.path.abspath(out):
            sys.exit("--out must not be the same directory as input")
        os.makedirs(out, exist_ok=True)
        nv_files = find_nv_files(src)
        if not nv_files:
            sys.exit("no NV files with IMEI records found in %s" % src)
        patched_count = 0
        for f in nv_files:
            rel = os.path.relpath(f, src)
            target_out = os.path.join(out, rel)
            os.makedirs(os.path.dirname(target_out), exist_ok=True)
            print("--- Patching %s ---" % rel)
            do_patch_imei_file(f, target_out, imei1=imei1, imei2=imei2, force=force, mask_output=mask_output)
            patched_count += 1
        print("Done. Successfully patched %d NV file(s) into %s" % (patched_count, out))
        return True
    sys.exit("%s: no such file or directory" % src)


def cmd_patch_serial(a):
    do_patch_serial(a.input, a.out, a.serial, a.force)


def cmd_patch_mac(a):
    do_patch_mac(a.input, a.out, a.old, a.new, a.force)


def cmd_patch_imei(a):
    imei1 = parse_imei_arg(a.imei1, "IMEI1", a.skip_luhn)
    imei2 = parse_imei_arg(a.imei2, "IMEI2", a.skip_luhn)
    if not imei1 and not imei2:
        sys.exit("specify at least one of --imei1 or --imei2")
    do_patch_imei(a.input, a.out, imei1=imei1, imei2=imei2, force=a.force, mask_output=a.mask)


def cmd_restore(a):
    b_mi, b_pr = find_inputs(a.from_backup)
    t_mi, t_pr = find_inputs(a.to)
    b_nvs = find_nv_files(a.from_backup)
    t_nvs = find_nv_files(a.to)

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

    # Check IMEIs in NV files
    b_imeis = {}
    for bf in b_nvs:
        for rid, entries in read_imeis(bf).items():
            if rid not in b_imeis and entries:
                b_imeis[rid] = entries[0][1]

    if b_imeis and t_nvs:
        for tf in t_nvs:
            t_imeis = read_imeis(tf)
            for rid, b_val in b_imeis.items():
                if rid in t_imeis:
                    t_val = t_imeis[rid][0][1]
                    lbl = IMEI_IDS.get(rid, "IMEI 0x%04X" % rid)
                    print("%-8s backup=%s  current=%s (%s)" % (
                        lbl, mask_imei(b_val, a.mask), mask_imei(t_val, a.mask), os.path.basename(tf)))
                    if b_val != t_val:
                        plan.append(("imei", tf, rid, b_val, t_val))

    if not plan:
        print("nothing to restore: the values already match (or one side could not be read)")
        return
    if not a.yes:
        print("dry run: %d change(s) would be made. Add --yes to write patched copies to %s" % (len(plan), a.out))
        return
    os.makedirs(a.out, exist_ok=True)
    cur = {}
    for item in plan:
        kind = item[0]
        if kind == "serial":
            _, target, new, old = item
            base = os.path.basename(target)
            src = cur.get(base, target)
            out = os.path.join(a.out, base)
            if os.path.abspath(out) == os.path.abspath(target):
                sys.exit("--out must not be the folder that holds the current dump")
            do_patch_serial(src, out, new, force=True)
            cur[base] = out
        elif kind in ("wifi", "bt"):
            _, target, new, old = item
            base = os.path.basename(target)
            src = cur.get(base, target)
            out = os.path.join(a.out, base)
            if os.path.abspath(out) == os.path.abspath(target):
                sys.exit("--out must not be the folder that holds the current dump")
            do_patch_mac(src, out, old, new, force=True)
            cur[base] = out
        elif kind == "imei":
            _, target, rec_id, new_val, old_val = item
            base = os.path.basename(target)
            src = cur.get(base, target)
            out = os.path.join(a.out, base)
            if os.path.abspath(out) == os.path.abspath(target):
                sys.exit("--out must not be the folder that holds the current dump")
            imei1_val = new_val if rec_id == 0x0005 else None
            imei2_val = new_val if rec_id == 0x0179 else None
            do_patch_imei_file(src, out, imei1=imei1_val, imei2=imei2_val, force=True, mask_output=a.mask)
            cur[base] = out
    print("done. Patched copies are in", a.out, "- originals untouched.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get", help="show serial / MACs / IMEIs found in a dump file or folder")
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

    p = sub.add_parser("patch-imei", help="write a patched COPY of NV file(s) with new IMEI(s)")
    p.add_argument("input", help="NV .bin file or folder containing NV .bin files")
    p.add_argument("--imei1", "--imei", dest="imei1", help="14- or 15-digit IMEI 1")
    p.add_argument("--imei2", dest="imei2", help="14- or 15-digit IMEI 2")
    p.add_argument("--out", required=True, help="output file (or folder if input is a folder)")
    p.add_argument("--skip-luhn", action="store_true", help="allow IMEIs with non-standard check digits")
    p.add_argument("--mask", action="store_true", help="hide digits in stdout")
    p.add_argument("--force", action="store_true", help="overwrite existing output file")
    p.set_defaults(fn=cmd_patch_imei)

    r = sub.add_parser("restore", help="take serial/MACs/IMEIs from a backup folder and patch copies of current dump")
    r.add_argument("--from-backup", required=True)
    r.add_argument("--to", required=True, help="folder with the current dump files")
    r.add_argument("--out", required=True)
    r.add_argument("--yes", action="store_true", help="actually write the patched copies (default is a dry run)")
    r.add_argument("--mask", action="store_true")
    r.set_defaults(fn=cmd_restore)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
