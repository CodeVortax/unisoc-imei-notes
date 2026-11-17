#!/usr/bin/env python3
"""
Realme C51 (RMX3830 - Unisoc T610 / UMS512)
Factory IMEI & Cellular Restoration Tool
Based on C21Y research and adapted for RMX3830
"""

import os
import sys
import struct
import zipfile
import hashlib
import subprocess
from datetime import datetime

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"""{BLUE}{BOLD}
=============================================================================
  Realme C51 (RMX3830) - Unisoc Tiger T610 Factory IMEI Restoration Tool
============================================================================={RESET}
""")

def luhn_checksum_valid(imei_str):
    digits = [int(c) for c in imei_str]
    total = 0
    for i in range(14):
        d = digits[i]
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d = (d // 10) + (d % 10)
        total += d
    check_digit = (10 - (total % 10)) % 10
    return check_digit == digits[14]

def validate_imei(imei_str, label="IMEI"):
    if len(imei_str) != 15:
        print(f"{RED}[-] Error: {label} must be exactly 15 digits{RESET}")
        return False
    if not imei_str.isdigit():
        print(f"{RED}[-] Error: {label} must contain only digits{RESET}")
        return False
    if not luhn_checksum_valid(imei_str):
        print(f"{YELLOW}[!] Warning: {label} fails Luhn check{RESET}")
    return True

def encode_bcd_imei(imei_str):
    digits = [int(c) for c in imei_str]
    b0 = (digits[0] << 4) | 0x0a
    raw = [b0]
    for i in range(1, 15, 2):
        raw.append((digits[i+1] << 4) | digits[i])
    return bytes(raw)

def calc_unisoc_checksum(data):
    chkSum = 0
    idx = 0
    l = len(data)
    while l > 1:
        num = data[idx] | (data[idx+1] << 8)
        chkSum += num
        idx += 2
        l -= 2
    if l:
        chkSum += data[idx]
    chkSum = (chkSum >> 16) + (chkSum & 0xffff)
    chkSum += (chkSum >> 16)
    return (~chkSum) & 0xffff

def generate_clean_fixnv(template_path, imei1, imei2):
    with open(template_path, "rb") as f:
        data = bytearray(f.read())
    
    if len(data) != 2097152:
        raise ValueError(f"Unexpected FixNV size: {len(data)}")
    
    hdr = data[:512]
    magic, length, old_crc, ver = struct.unpack('<IIII', hdr[:16])
    if magic != 0x00004e56:
        raise ValueError(f"Invalid FixNV magic: 0x{magic:08x}")
    
    body = data[512:512+length]
    offset = 4
    bcd_imei1 = encode_bcd_imei(imei1)
    bcd_imei2 = encode_bcd_imei(imei2)
    
    while offset < len(body) - 4:
        item_id, item_size = struct.unpack('<HH', body[offset:offset+4])
        if item_id == 0xffff:
            break
        if item_id == 0x0005:
            body[offset+4:offset+4+8] = bcd_imei1
        elif item_id in [0x0179, 0x0186]:
            body[offset+4:offset+4+8] = bcd_imei2
        offset += 4 + item_size
        offset = (offset + 3) & ~3
    
    new_crc = calc_unisoc_checksum(body)
    data[512:512+length] = body
    struct.pack_into('<I', data, 8, new_crc)
    
    print(f"{GREEN}  [+] FixNV generated: IMEI1={imei1}, IMEI2={imei2}{RESET}")
    return bytes(data)

def patch_modem_firmware(template_path, imei1, imei2):
    with open(template_path, "rb") as f:
        data = bytearray(f.read())
    
    print(f"{BLUE}  [i] Modem size: {len(data)} bytes{RESET}")
    
    # Patch 1: sp_a_imei_process
    data[0x010a981a:0x010a981a+4] = b'\x01\x20\x70\x47'
    
    # Patch 2: efuse check
    data[0x10aa47c:0x10aa47c+8] = b'\x00\x21\x01\x60\x01\x20\x70\x47'
    
    # Patch 3: SIMLOCK
    data[0x723b66:0x723b66+2] = b'\x08\xe0'
    
    # Patches 4 & 5: Default IMEIs
    data[0x1462dcc:0x1462dcc+15] = imei1.encode('ascii')
    data[0x1462ddb:0x1462ddb+15] = imei2.encode('ascii')
    
    print(f"{GREEN}  [+] Modem patched successfully{RESET}")
    return bytes(data)

def main():
    print_banner()
    
    import argparse
    parser = argparse.ArgumentParser(description="Realme C51 IMEI Restoration")
    parser.add_argument("--imei1", required=True, help="15-digit IMEI 1")
    parser.add_argument("--imei2", required=True, help="15-digit IMEI 2")
    parser.add_argument("--fixnv-template", required=True, help="Path to l_fixnv1_a stock dump")
    parser.add_argument("--modem-template", help="Path to l_modem_a stock dump")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()
    
    if not validate_imei(args.imei1, "IMEI 1") or not validate_imei(args.imei2, "IMEI 2"):
        sys.exit(1)
    
    os.makedirs(args.output, exist_ok=True)
    
    # Generate FixNV
    fixnv = generate_clean_fixnv(args.fixnv_template, args.imei1, args.imei2)
    with open(os.path.join(args.output, "l_fixnv1.bin"), "wb") as f:
        f.write(fixnv)
    with open(os.path.join(args.output, "l_fixnv2.bin"), "wb") as f:
        f.write(fixnv)
    
    # Patch Modem if provided
    if args.modem_template and os.path.exists(args.modem_template):
        modem = patch_modem_firmware(args.modem_template, args.imei1, args.imei2)
        with open(os.path.join(args.output, "l_modem_patched.bin"), "wb") as f:
            f.write(modem)
    
    print(f"\n{GREEN}[+] Files written to: {args.output}{RESET}")
    print(f"    Flash with:")
    print(f"    dd if={args.output}/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv1_a bs=1M")
    print(f"    dd if={args.output}/l_modem_patched.bin of=/dev/block/bootdevice/by-name/l_modem_a bs=1M")

if __name__ == "__main__":
    main()
