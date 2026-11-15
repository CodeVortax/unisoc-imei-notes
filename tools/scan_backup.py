#!/usr/bin/env python3
"""Read-only scanner for Unisoc/Spreadtrum NV backups.

Finds IMEI NV records (IDs 0x0005 and 0x0179, 8 bytes, BCD format) and MAC address strings
in every .bin file of a folder. Optionally searches for IMEIs you already know (--reported)
in several encodings. It never writes to any file.
"""
import argparse, glob, os, re, struct, sys

IMEI_IDS = {0x0005: "IMEI1", 0x0179: "IMEI2"}


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


def mask(s, keep_left, enabled):
    return s if not enabled else s[:keep_left] + "*" * (len(s) - keep_left)


def scan_nv(data, name, do_mask):
    for id_, label in IMEI_IDS.items():
        pat = struct.pack("<HH", id_, 8)
        for m in re.finditer(re.escape(pat), data):
            rec = data[m.end():m.end() + 8]
            imei = decode_imei(rec)
            if imei:
                print("  %s  record 0x%04X at 0x%X: %s  luhn=%s"
                      % (label, id_, m.start(), mask(imei, 12, do_mask), luhn_ok(imei)))


def scan_mac(data, do_mask):
    seen = set()
    for m in re.finditer(rb"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", data):
        mac = m.group().decode()
        if mac not in seen and len(seen) < 10:
            seen.add(mac)
            shown = mac if not do_mask else mac[:8] + ":**:**:" + mac[-2:]
            print("  MAC string at 0x%X: %s" % (m.start(), shown))


def scan_reported(data, imeis):
    for s in imeis:
        forms = {
            "nv-bcd": encode_imei(s), "ascii": s.encode(),
            "utf16": s.encode("utf-16-le"), "ascii14": s[:14].encode(),
        }
        for label, pat in forms.items():
            n = data.count(pat)
            if n:
                print("  reported %s... found as %s x%d" % (s[:8], label, n))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder")
    ap.add_argument("--reported", nargs="*", default=[], help="IMEIs shown by the phone to look for")
    ap.add_argument("--mask", action="store_true", help="hide the last digits in the output")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.folder, "**", "*.bin"), recursive=True))
    if not files:
        sys.exit("no .bin files found in %s" % a.folder)
    for f in files:
        data = open(f, "rb").read()
        print("%s (%d bytes)%s" % (os.path.relpath(f, a.folder), len(data),
                                   "  [all zero]" if not any(data) else ""))
        scan_nv(data, f, a.mask)
        scan_mac(data, a.mask)
        if a.reported:
            scan_reported(data, a.reported)


if __name__ == "__main__":
    main()
