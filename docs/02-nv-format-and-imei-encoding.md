# 02 - NV file format and IMEI encoding

## File layout (as seen in `l_fixnv*` and parsed by SPRDNVEditor)

- The file starts with a short header. In the example it begins `56 4e` ("VN") followed by version
  and size fields.
- After the header come records: `[id : u16 LE][length : u16 LE][data ...]`, padded to an alignment
  boundary. SPRDNVEditor's parser walks the file this way (it skips a 4-byte header for the older
  format).
- Items are interpreted by a *project/profile* that maps each ID to a type (string, integers, IPv4,
  MAC, IMEI, raw hex). That is why NVEditor needs a `.prj` first, and why "interpret NV item N fail"
  means the profile does not match the chip or modem build.

I did not find a file-level checksum in the part of SPRDNVEditor that I read. An earlier claim that
NVEditor's save dialog rebuilds integrity data was a guess.

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
