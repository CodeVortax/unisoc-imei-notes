#!/usr/bin/env python3
"""Read-only parser for a Spreadtrum 'miscdata' (phase-check) dump.

Prints the serial numbers and the station list. Layout verified on one RMX3830 dump;
offsets after 0x38 are tentative. Never writes anything.
"""
import argparse
import struct
import sys

MAGIC = b"90PS"  # 'SP09' stored little-endian


def cstr(b):
    return b.split(b"\0")[0].decode("ascii", "replace")


def mask(s, keep, on):
    return s if not on or len(s) <= keep else s[:keep] + "*" * (len(s) - keep)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file")
    ap.add_argument("--mask", action="store_true", help="hide most of each serial")
    a = ap.parse_args()
    d = open(a.file, "rb").read()
    if len(d) < 0x100:
        sys.exit("file too small for a phase-check record")
    print("magic:", d[:4], "OK" if d[:4] == MAGIC else "NOT SP09 - layout unknown")
    print("SN1:", mask(cstr(d[0x04:0x1C]), 4, a.mask) or "(empty)")
    print("SN2:", mask(cstr(d[0x1C:0x34]), 4, a.mask) or "(empty)")
    n = struct.unpack("<I", d[0x34:0x38])[0]
    print("stations:", n)
    names = [cstr(d[0x38 + i * 10:0x38 + (i + 1) * 10]) for i in range(min(n, 15))]
    print("names:", ", ".join(names))
    print("result text @0xDC:", cstr(d[0xDC:0xFC]) or "(empty)")
    print("bit masks @0xFC/0xFE: 0x%04X 0x%04X" % struct.unpack("<HH", d[0xFC:0x100]))
    tail = d[0x100:]
    other = sum(1 for b in tail if b not in (0x00, 0xFF))
    print("bytes after 0x100 that are neither 0x00 nor 0xFF (not decoded):", other)


if __name__ == "__main__":
    main()
