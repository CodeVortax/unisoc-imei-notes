# Realme C21Y (RMX3261/3263) IMEI & Network Restoration

Complete factory IMEI and cellular restoration for Realme C21Y.

## Quick Links

- **Main Tool:** [tools/c21y_imei_restore.py](../../tools/c21y_imei_restore.py)
- **Technical Deep Dive:** [HOW_IT_WORKS_C21Y.md](../../HOW_IT_WORKS_C21Y.md)
- **Original Repository:** Based on fanuverse's research

## Device Specifications

| Property | Value |
|----------|-------|
| Model | Realme C21Y |
| Model Numbers | RMX3261, RMX3263 |
| SoC | Unisoc UMS512 (Tiger T610) |
| Process | 12nm |
| CPU | Octa-core (2x A75 + 6x A55) |
| GPU | Mali-G52 |
| Modem | Integrated LTE Cat-7 |
| Display | 6.5" HD+ 720p |
| Battery | 5000mAh |

## The Problem

When you flash a Generic System Image (GSI) or wipe NVRAM:

1. Unisoc baseband detects missing/corrupted IMEI
2. Efuse secure boot check (0x10aa47c) rejects unsigned NVRAM
3. Modem CP zeros IMEI buffer to "000000000000000"
4. Carrier EIR rejects device registration
5. **Result:** No signal, emergency calls only

## Solution Overview

Three-layer patch approach:

```
┌─────────────────────────────────────┐
│ Layer 1: Userspace RIL              │
│ libimpl-ril.so - Returns IMEI to    │
│ Android framework                   │
├─────────────────────────────────────┤
│ Layer 2: Baseband Modem             │
│ l_modem.bin - Bypasses efuse        │
│ checks, SIMLOCK, uses default IMEIs │
├─────────────────────────────────────┤
│ Layer 3: Calibrated NVRAM           │
│ l_fixnv1.bin - Factory RF data      │
│ with your authentic IMEIs           │
└─────────────────────────────────────┘
```

## Usage

### Automatic Mode (Recommended)

```bash
# From repo root
python3 tools/c21y_imei_restore.py --flash

# Or with specific IMEIs
python3 tools/c21y_imei_restore.py \
    --imei1 123456789012345 \
    --imei2 123456789012346 \
    --flash
```

### Manual Mode (Generate only)

```bash
python3 tools/c21y_imei_restore.py \
    --imei1 123456789012345 \
    --imei2 123456789012346 \
    --no-flash \
    --output-dir ./output
```

Then flash manually:

```bash
su
dd if=./output/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv1_a bs=1M
dd if=./output/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv1_b bs=1M
dd if=./output/l_modem_patched.bin of=/dev/block/bootdevice/by-name/l_modem_a bs=1M
dd if=/dev/zero of=/dev/block/bootdevice/by-name/l_runtimenv1 bs=1M count=2
sync
reboot
```

## Requirements

- Root access (APatch or Magisk)
- Factory IMEIs from box sticker
- USB debugging enabled
- Python 3.7+ (on host PC)

## Verification

After flashing:

1. Settings → About Phone - Shows both IMEIs
2. Dial `*#06#` - Popup with IMEIs
3. Check signal bars - Should show network
4. USSD codes - Try `*804#` or `*123#`
5. Test call - Make a phone call

## Partition Details

| Partition | Size | Purpose |
|-----------|------|---------|
| l_fixnv1_a/b | 2MB | Primary NVRAM with RF calibration |
| l_fixnv2_a/b | 2MB | Backup NVRAM |
| l_modem_a/b | 26MB | Baseband CP RTOS firmware |
| l_runtimenv1/2 | 2MB | Runtime NVRAM (cleared) |
| l_agdsp_a/b | 6MB | Audio DSP |
| calinv | 2MB | Calibration data |

## Binary Patches Applied

### Modem Firmware (l_modem.bin)

| Address | Patch | Effect |
|---------|-------|--------|
| 0x010a981a | `01 20 70 47` | Bypass sp_a_imei_process |
| 0x10aa47c | `00 21 01 60 01 20 70 47` | Skip efuse check |
| 0x723b66 | `08 e0` | Bypass SIMLOCK |
| 0x1462dcc | ASCII IMEI 1 | Default IMEI table 1 |
| 0x1462ddb | ASCII IMEI 2 | Default IMEI table 2 |

See [HOW_IT_WORKS_C21Y.md](../../HOW_IT_WORKS_C21Y.md) for complete technical details.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid FixNV magic" | Template corrupted, use fresh backup |
| IMEI still 000... | Clear runtime NVRAM: `dd if=/dev/zero of=.../l_runtimenv1` |
| No signal after flash | Reboot twice, check module installed |
| Module won't install | Use APatch/Magisk Manager, not recovery |

## Templates Included

This repo includes C21Y templates in `templates/c21y/`:
- `l_fixnv1_template.bin` - Factory NVRAM backup
- `l_modem_template.bin` - Stock modem firmware
- `libimpl-ril64_template.so` - Stock RIL library
- `module_template/` - APatch/Magisk module skeleton

## Credits

- **Research & Tool:** fanuverse
- **Platform:** Unisoc UMS512 (Tiger T610)
- **Community:** XDA Developers, LineageOS

## Legal

This tool is for restoring your original factory IMEI only. Do not use to:
- Change IMEI to non-factory values
- Clone another device's IMEI
- Circumvent carrier locks illegally

See LICENSE for full terms.
