# 02 - NV file format and IMEI encoding

## File layout (as seen in `l_fixnv*` and verified against Realme C21Y / C51 tools)

- The file starts with a **512-byte header**:
  - `0x00 - 0x03`: Magic `0x00004e56` (`56 4E 00 00`, ASCII `"VN\0\0"`).
  - `0x04 - 0x07`: Body Length as `u32 LE` (usually `0x00100000` = 1,048,576 bytes).
  - `0x08 - 0x0B`: **Unisoc 16-bit one's complement checksum** of the body (`data[512 : 512 + length]`).
  - `0x0C - 0x0F`: Version as `u32 LE` (typically `0x00000065`).
  - `0x10 - 0x1FF`: Zero padding up to byte 512.
- After the 512-byte header come records: `[id : u16 LE][length : u16 LE][data ...]`, padded to a 4-byte
  alignment boundary (`(offset + 3) & ~3`). SPRDNVEditor's parser walks the file this way.
- **Header Checksum Algorithm**:
  Whenever any NV item in the body changes, the 16-bit one's complement sum must be recalculated and
  stored at offset `0x08`. If the checksum does not match, the bootloader or modem rejects the NVRAM image.
  ```python
  def calc_unisoc_checksum(data: bytes) -> int:
      chkSum = 0
      l, idx = len(data), 0
      while l > 1:
          chkSum += data[idx] | (data[idx + 1] << 8)
          idx += 2
          l -= 2
      if l:
          chkSum += data[idx]
      chkSum = (chkSum >> 16) + (chkSum & 0xffff)
      chkSum += (chkSum >> 16)
      return (~chkSum) & 0xffff
  ```
- Items are interpreted by a *project/profile* that maps each ID to a type (string, integers, IPv4,
  MAC, IMEI, raw hex). That is why NVEditor needs a `.prj` first, and why "interpret NV item N fail"
  means the profile does not match the chip or modem build.

## The 8-byte IMEI record

It is the 3GPP BCD "mobile identity" format:

| Byte | Content |
|---|---|
| 0 | low nibble `A` (identity type, odd digit count); high nibble = **digit 1** |
| 1-7 | the other 14 digits, two per byte, **swapped** (low nibble = earlier digit) |

Example for `123456789012345`:

```
1A 32 54 76 98 10 32 54
```

Decoding rule: for each byte output the low nibble then the high nibble, concatenate, drop the first
character (`A`). The XDA thread's "left-padded zero" (writing `0x6` for `0x06`) is only how
NVEditor displays a byte.

## Check digit

The 15th digit is the Luhn check digit of the first 14. WriteIMEI computes it with `ComputeCD()`:
double every second digit starting from the rightmost digit of the 14-digit base, sum the digits,
and take `(10 - sum % 10) % 10`.

## Where the format shows up in code

- `SPRDNVEditor/NVParser.cs` decodes an 8-byte IMEI item this way.
- `WriteIMEI/WriteFlashDlg.cpp` does **not** encode it: it passes the IMEI as an ASCII string
  (`szImei1`...) and the library and modem encode it.
