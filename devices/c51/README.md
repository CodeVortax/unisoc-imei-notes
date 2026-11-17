# Realme C51 (RMX3830) IMEI & Network Restoration

## Device Information

| Property | Value |
|----------|-------|
| **Model** | Realme C51 |
| **Model Number** | RMX3830 |
| **SoC** | Unisoc UMS512 (Tiger T610) |
| **CPU** | Octa-core (2x A75 @ 1.8GHz + 6x A55 @ 1.8GHz) |
| **GPU** | Mali-G52 MP2 |
| **Modem** | Integrated 4G LTE Cat-7 |
| **Partitions** | A/B slots for modem and NVRAM |

## Problem Description

Same as C21Y: When flashing Generic System Images (GSI) or wiping NVRAM:
1. Unisoc baseband detects corrupted/missing IMEI
2. Efuse secure boot check rejects unsigned data
3. Modem zeros IMEI to "000000000000000"
4. Carrier rejects device registration
5. Result: No signal, emergency calls only

## Partition Layout

```
/dev/block/bootdevice/by-name/
├── l_fixnv1_a      (2MB) - Primary NVRAM Slot A
├── l_fixnv1_b      (2MB) - Primary NVRAM Slot B  
├── l_fixnv2_a      (2MB) - Backup NVRAM Slot A
├── l_fixnv2_b      (2MB) - Backup NVRAM Slot B
├── l_modem_a       (26MB) - Modem Firmware Slot A
├── l_modem_b       (26MB) - Modem Firmware Slot B
├── l_runtimenv1    (2MB) - Runtime NVRAM
├── l_runtimenv2    (2MB) - Runtime NVRAM backup
├── l_agdsp_a/b     (6MB) - Audio DSP
├── calinv          (2MB) - Calibration data
├── persist         (2MB) - Persistent data
└── misc/miscdata   (1MB) - Misc data
```

## Required Files from Your Device

You need to extract these from your working device BEFORE losing IMEI:

1. **l_fixnv1_a** - Contains factory RF calibration + IMEI slots
2. **l_modem_a** - Stock modem firmware for patching
3. **libimpl-ril.so** - Stock RIL library (from /vendor/lib64/)

### Extraction Commands

```bash
# Connect with ADB and root
adb shell su -c 'dd if=/dev/block/bootdevice/by-name/l_fixnv1_a of=/sdcard/l_fixnv1_a.bin'
adb shell su -c 'dd if=/dev/block/bootdevice/by-name/l_modem_a of=/sdcard/l_modem_a.bin'
adb shell su -c 'cp /vendor/lib64/libimpl-ril.so /sdcard/'

# Pull to PC
adb pull /sdcard/l_fixnv1_a.bin templates/c51/
adb pull /sdcard/l_modem_a.bin templates/c51/l_modem_template.bin
adb pull /sdcard/libimpl-ril.so templates/c51/libimpl-ril64_template.so
```

## Usage

### Quick Start

```bash
python3 tools/c51_imei_restore.py \
    --imei1 123456789012345 \
    --imei2 123456789012346 \
    --fixnv-template templates/c51/l_fixnv1_a \
    --modem-template templates/c51/l_modem_a \
    --output output_c51
```

### Manual Flashing

After generating files:

```bash
# Push to device
adb push output_c51/l_fixnv1.bin /sdcard/
adb push output_c51/l_modem_patched.bin /sdcard/

# Flash via root shell
adb shell su -c '
    dd if=/sdcard/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv1_a bs=1M
    dd if=/sdcard/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv1_b bs=1M
    dd if=/sdcard/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv2_a bs=1M
    dd if=/sdcard/l_fixnv1.bin of=/dev/block/bootdevice/by-name/l_fixnv2_b bs=1M
    dd if=/sdcard/l_modem_patched.bin of=/dev/block/bootdevice/by-name/l_modem_a bs=1M
    dd if=/sdcard/l_modem_patched.bin of=/dev/block/bootdevice/by-name/l_modem_b bs=1M
    dd if=/dev/zero of=/dev/block/bootdevice/by-name/l_runtimenv1 bs=1M count=2
    dd if=/dev/zero of=/dev/block/bootdevice/by-name/l_runtimenv2 bs=1M count=2
    sync
'
```

## Differences from C21Y

| Aspect | C21Y | C51 |
|--------|------|-----|
| Model | RMX3261/3263 | RMX3830 |
| Screen | 6.5" 720p | 6.74" 720p 90Hz |
| Battery | 5000mAh | 5000mAh 33W |
| Camera | 13MP | 50MP |
| **Baseband** | **Same UMS512** | **Same UMS512** |
| **Partitions** | **Same structure** | **Same structure** |

The C51 uses the **exact same Unisoc T610 platform** as C21Y, so the patching approach is identical. The addresses in the modem firmware are likely the same or very similar.

## Backup Your Partitions First!

```bash
#!/bin/bash
# backup_c51_partitions.sh

device="/dev/block/bootdevice/by-name"
backup_dir="/sdcard/c51_backup_$(date +%Y%m%d_%H%M%S)"

mkdir -p $backup_dir

echo "Backing up critical partitions..."

for part in l_fixnv1_a l_fixnv1_b l_fixnv2_a l_fixnv2_b \
            l_modem_a l_modem_b l_runtimenv1 l_runtimenv2 \
            calinv persist misc miscdata; do
    if [ -e $device/$part ]; then
        echo "Backing up $part..."
        dd if=$device/$part of=$backup_dir/${part}.bin bs=1M
    fi
done

echo "Backup complete at: $backup_dir"
```

## Troubleshooting

### Issue: "Invalid FixNV magic"
- Your NVRAM is already corrupted
- Use a backup from another C51 device (IMEI will need changing)

### Issue: No signal after flash
- Clear runtime NVRAM: `dd if=/dev/zero of=.../l_runtimenv1`
- Reboot twice (first boot regenerates runtime data)

### Issue: IMEI shows but no network
- Check if both SIM slots enabled
- Verify APN settings
- Toggle airplane mode

## Credits

- Tool based on C21Y research by fanuverse
- Adapted for RMX3830 by CodeVortax

## License

See LICENSE file in repository root.
