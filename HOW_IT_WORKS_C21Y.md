# Realme C21Y IMEI & Network Restoration - Technical Deep Dive

> **For:** Realme C21Y (RMX3261 / RMX3263)  
> **SoC:** Unisoc UMS512 (Tiger T610)  
> **Solution Type:** Native Software-Only (No Hardware Dongles)

---

## Table of Contents

1. [The Core Problem](#the-core-problem)
2. [Unisoc Security Model](#unisoc-security-model)
3. [Three-Layer Architecture](#three-layer-architecture)
4. [Implementation Details](#implementation-details)
5. [Binary Patch Reference](#binary-patch-reference)
6. [NVRAM Structure](#nvram-structure)
7. [Flashing Procedures](#flashing-procedures)
8. [Verification & Testing](#verification--testing)

---

## The Core Problem

### Symptom Chain

```
User flashes Generic System Image (GSI) or wipes NVRAM
    ↓
Unisoc T610 baseband detects missing/corrupted IMEI
    ↓
Efuse secure boot check (0x10aa47c) rejects unsigned data
    ↓
Modem CP zeros internal IMEI buffer
    ↓
Device reports "000000000000000" to cell tower
    ↓
Carrier EIR rejects registration
    ↓
Result: Emergency calls only, no data, no USSD
```

### Why Traditional Tools Fail

| Tool | Failure Reason |
|------|----------------|
| Miracle Box | Requires hardware dongle, expensive |
| Pandora Box | Proprietary, doesn't bypass efuse |
| QFIL/SP Flash | Overwrites entire flash, loses calibration |
| Manual NV edit | Checksum validation fails |

---

## Unisoc Security Model

### Boot-Time Verification Chain

```
1. Primary Bootloader (PBL) loads modem firmware
   ↓
2. CP RTOS initializes at 0x10000000
   ↓
3. sp_a_imei_process() called at 0x010a981a
   ↓
4. Reads efuse block 0x24 at 0x10aa47c
   ↓
5. If secure boot enabled:
   - Requires ENIMEI1_DATA/ENIMEI2_DATA tokens (153 bytes each)
   - Tokens signed with device-unique key
   - Without tokens: IMEI → 0x00...
```

### NVRAM Item Structure

```c
struct nvitem_header {
    uint32_t magic;      // 0x00004e56 ("NV\0\0")
    uint32_t length;     // Body length
    uint32_t checksum;   // Unisoc CRC
    uint32_t version;    // 0x00010000
} __attribute__((packed));

struct nvitem_entry {
    uint16_t item_id;    // Item number
    uint16_t item_size;  // Data size
    uint8_t  data[];     // Variable length
} __attribute__((packed));
```

---

## Three-Layer Architecture

### Visual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: Android Framework (Userspace)                           │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  Settings.app → TelephonyService → RIL (Radio Interface Layer)│ │
│ │                     ↓                                       │ │
│ │         libimpl-ril.so [PATCHED]                            │ │
│ │         └─→ Hooks IMEI queries                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 2: Baseband Modem (CP RTOS)                              │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  l_modem.bin [PATCHED]                                     │ │
│ │  ├─ sp_a_imei_process @ 0x010a981a → return 1              │ │
│ │  ├─ efuse_check @ 0x10aa47c → skip verification            │ │
│ │  ├─ simlock_verify @ 0x723b66 → bypass                     │ │
│ │  └─ default_imei_table @ 0x1462dcc → authentic IMEIs       │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 3: Hardware/NVRAM (Persistent Storage)                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  l_fixnv1.bin / l_fixnv2.bin [REGENERATED]                 │ │
│ │  ├─ Factory RF calibration data (antenna matching)         │ │
│ │  ├─ Item 0x0005: IMEI 1 (8 bytes BCD)                      │ │
│ │  ├─ Item 0x0179: IMEI 2 (8 bytes BCD)                      │ │
│ │  └─ Valid 16-bit one's complement checksum                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### IMEI Encoding (3GPP BCD)

**Input:** `123456789012345` (15 digits)

**BCD Encoding Process:**

```
Byte 0: (digit[0] << 4) | 0x0A
       = (1 << 4) | 10 = 0x1A

Bytes 1-7: Pack digits in pairs, reversed nibble order
  Byte 1: (digit[2] << 4) | digit[1] = (3 << 4) | 2 = 0x32
  Byte 2: (digit[4] << 4) | digit[3] = (5 << 4) | 4 = 0x54
  Byte 3: (digit[6] << 4) | digit[5] = (7 << 4) | 6 = 0x76
  Byte 4: (digit[8] << 4) | digit[7] = (9 << 4) | 8 = 0x98
  Byte 5: (digit[10] << 4) | digit[9] = (1 << 4) | 0 = 0x10
  Byte 6: (digit[12] << 4) | digit[11] = (3 << 4) | 2 = 0x32
  Byte 7: (digit[14] << 4) | digit[13] = (5 << 4) | 4 = 0x54

Result: 1A 32 54 76 98 10 32 54 (8 bytes)
```

**Python Implementation:**

```python
def encode_bcd_imei(imei_str: str) -> bytes:
    digits = [int(c) for c in imei_str]
    b0 = (digits[0] << 4) | 0x0a
    raw = [b0]
    for i in range(1, 15, 2):
        d1 = digits[i]
        d2 = digits[i+1]
        raw.append((d2 << 4) | d1)
    return bytes(raw)
```

### Unisoc Checksum Algorithm

```python
def calc_unisoc_checksum(data: bytes) -> int:
    chkSum = 0
    idx = 0
    # Process 16-bit words in little-endian
    while len(data) - idx > 1:
        num = data[idx] | (data[idx+1] << 8)
        chkSum += num
        idx += 2
    # Handle odd byte
    if idx < len(data):
        chkSum += data[idx]
    # Fold 32-bit into 16-bit
    chkSum = (chkSum >> 16) + (chkSum & 0xffff)
    chkSum += (chkSum >> 16)
    # One's complement
    return (~chkSum) & 0xffff
```

---

## Binary Patch Reference

### Patch 1: IMEI Process Bypass

| Field | Value |
|-------|-------|
| **Address** | `0x010a981a` |
| **Original** | Complex validation logic |
| **Patch** | `01 20 70 47` |
| **Assembly** | `movs r0, #1; bx lr` |
| **Effect** | Forces return value 1 (success) |

**ARM Thumb Disassembly:**
```asm
0x010a981a: 01 20    movs r0, #1      ; Return true
0x010a981c: 70 47    bx   lr          ; Return to caller
```

### Patch 2: Efuse Security Bypass

| Field | Value |
|-------|-------|
| **Address** | `0x10aa47c` |
| **Patch** | `00 21 01 60 01 20 70 47` |
| **Size** | 8 bytes |

**ARM Thumb Disassembly:**
```asm
0x10aa47c: 00 21    movs r1, #0      ; Load 0
0x10aa47e: 01 60    str  r1, [r0, #0] ; *r0 = 0
0x10aa480: 01 20    movs r0, #1      ; Return 1
0x10aa482: 70 47    bx   lr          ; Return
```

### Patch 3: SIMLOCK Bypass

| Field | Value |
|-------|-------|
| **Address** | `0x723b66` |
| **Patch** | `08 e0` |
| **Assembly** | `b #0x723b7a` |
| **Offset** | +20 bytes (skips memcmp) |

### Patch 4 & 5: Default IMEI Tables

| Field | Patch 4 | Patch 5 |
|-------|---------|---------|
| **Address** | `0x1462dcc` | `0x1462ddb` |
| **Content** | IMEI 1 ASCII | IMEI 2 ASCII |
| **Size** | 15 bytes | 15 bytes |
| **Padding** | Null terminator | Null terminator |

---

## NVRAM Structure

### Memory Layout (2MB Total)

```
Offset      Size        Content
─────────────────────────────────────
0x000000    512 bytes   Header (magic, length, CRC, version)
0x000200    variable    NV Item array
...                     
0x1FFFFF    -           End of partition
```

### Item ID Reference

| Item ID | Description | Size |
|---------|-------------|------|
| 0x0005 | IMEI 1 (BCD) | 8 bytes |
| 0x0179 | IMEI 2 (BCD) | 8 bytes |
| 0x0186 | IMEI 2 Alt | 8 bytes |
| 0xFFFF | End marker | - |

### NVRAM Generation Flow

```python
def generate_fixnv(template, imei1, imei2):
    # 1. Load template with factory RF calibration
    data = bytearray(open(template, "rb").read())
    
    # 2. Extract body (skip 512-byte header)
    body = data[512:512+length]
    
    # 3. Iterate through items
    offset = 4
    while offset < len(body) - 4:
        item_id, item_size = struct.unpack('<HH', body[offset:offset+4])
        
        if item_id == 0x0005:
            body[offset+4:offset+4+8] = encode_bcd_imei(imei1)
        elif item_id == 0x0179:
            body[offset+4:offset+4+8] = encode_bcd_imei(imei2)
            
        offset += 4 + item_size
        offset = (offset + 3) & ~3  # Align to 4 bytes
    
    # 4. Recalculate checksum
    new_crc = calc_unisoc_checksum(body)
    data[8:12] = struct.pack('<I', new_crc)
    
    return bytes(data)
```

---

## Flashing Procedures

### Automatic (via ADB)

```bash
python3 c21y_imei_restore.py \
    --imei1 <15_DIGIT_IMEI1> \
    --imei2 <15_DIGIT_IMEI2> \
    --flash
```

**Steps Executed:**
1. Validates IMEI format (Luhn checksum)
2. Generates l_fixnv1.bin with injected IMEIs
3. Patches l_modem.bin (5 patches)
4. Builds flashable module zip
5. Backups existing partitions
6. Flashes to both slots (A/B)
7. Clears runtime NVRAM
8. Installs module
9. Reboots device

### Manual (via Termux)

```bash
# 1. Copy files to phone
adb push l_fixnv1.bin /sdcard/
adb push l_modem_patched.bin /sdcard/

# 2. Root shell
su

# 3. Detect partition path
PART="/dev/block/bootdevice/by-name"
[ -d "$PART" ] || PART="/dev/block/by-name"

# 4. Flash NVRAM (both slots)
dd if=/sdcard/l_fixnv1.bin of=$PART/l_fixnv1_a bs=1M
dd if=/sdcard/l_fixnv1.bin of=$PART/l_fixnv1_b bs=1M
dd if=/sdcard/l_fixnv1.bin of=$PART/l_fixnv2_a bs=1M
dd if=/sdcard/l_fixnv1.bin of=$PART/l_fixnv2_b bs=1M

# 5. Flash modem (both slots)
dd if=/sdcard/l_modem_patched.bin of=$PART/l_modem_a bs=1M
dd if=/sdcard/l_modem_patched.bin of=$PART/l_modem_b bs=1M

# 6. Clear runtime NVRAM
dd if=/dev/zero of=$PART/l_runtimenv1 bs=1M count=2
dd if=/dev/zero of=$PART/l_runtimenv2 bs=1M count=2

# 7. Sync and reboot
sync
reboot
```

---

## Verification & Testing

### Immediate Verification

```bash
# Check IMEI in Android properties
adb shell getprop gsm.baseband.imei
adb shell getprop gsm.baseband.imei2

# Check RIL registration
adb shell dumpsys telephony.registry | grep -i imei

# Check network registration
adb shell dumpsys telephony.registry | grep -i "mServiceState"
```

### Functional Tests

| Test | Command/Action | Expected Result |
|------|----------------|-----------------|
| IMEI Display | Settings → About Phone | Shows both IMEIs |
| IMEI Query | Dial `*#06#` | Popup with IMEI 1 & 2 |
| USSD | Dial `*804#` | Balance/credit info |
| Voice Call | Make test call | Connects successfully |
| Mobile Data | Disable Wi-Fi, browse | 4G/LTE works |
| Signal Bars | Check status bar | Shows signal strength |

### Troubleshooting

| Problem | Diagnostic | Solution |
|---------|------------|----------|
| Still shows 000... | Check `l_runtimenv1` cleared | Zero runtime NVRAM |
| No signal after flash | Check module installed | Re-flash module zip |
| IMEI in Settings wrong | RIL not hooked | Verify libimpl-ril.so patched |
| Emergency only | SIMLOCK still active | Re-verify Patch 3 applied |
| Random reboots | Corrupted modem | Re-flash with fresh template |

---

## Technical Specifications

### File Sizes

| File | Size | Purpose |
|------|------|---------|
| l_fixnv1_template.bin | 2,097,152 bytes | NVRAM template |
| l_modem_template.bin | 26,214,400 bytes | Stock modem firmware |
| libimpl-ril64_template.so | 352,312 bytes | Userspace RIL |

### Partition Mapping

```
/dev/block/bootdevice/by-name/
├── l_fixnv1_a      → Slot A primary NVRAM
├── l_fixnv1_b      → Slot B primary NVRAM
├── l_fixnv2_a      → Slot A backup NVRAM
├── l_fixnv2_b      → Slot B backup NVRAM
├── l_modem_a       → Slot A modem firmware
├── l_modem_b       → Slot B modem firmware
├── l_runtimenv1    → Runtime NVRAM (cleared)
└── l_runtimenv2    → Runtime NVRAM backup (cleared)
```

### SoC Information

| Property | Value |
|----------|-------|
| Manufacturer | Unisoc |
| SoC | UMS512 (Tiger T610) |
| CPU | Octa-core (2x A75 + 6x A55) |
| GPU | Mali-G52 |
| Process | 12nm |
| Baseband | Integrated LTE Cat-7 |

---

## Legal & Ethical Notice

### Permitted Use Cases

✅ Restoring original factory IMEI after accidental flash corruption  
✅ Recovering device after NVRAM wipe during ROM development  
✅ Repairing devices with valid ownership proof  

### Prohibited Use Cases

❌ Changing IMEI to non-factory values  
❌ Cloning another device's IMEI  
❌ Bypassing carrier locks on stolen devices  
❌ Any activity violating local telecommunications laws  

**Disclaimer:** This tool is for educational and repair purposes. Users assume full responsibility for compliance with applicable laws.

---

## Credits

**Tool Author:** fanuverse  
**Platform:** Unisoc/Spreadtrum UMS512  
**Tested Devices:** Realme C21Y (RMX3261, RMX3263)  
**Android Versions:** 11, 12, 13, 14, 15, 16 (GSI compatible)

**Acknowledgments:**
- Unisoc documentation and reference implementations
- Android Open Source Project (AOSP)
- APatch and Magisk open-source communities
- LineageOS and GSI device maintainers

---

*Document Version: 1.0*  
*Last Updated: 2024*
