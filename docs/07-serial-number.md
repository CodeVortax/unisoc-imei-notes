# 07 - Serial number

## Confirmed: the serial lives in `miscdata`

A read-only dump of a Realme C51 (RMX3830) showed the serial number shown by the phone
(dialer device-information dialog) as ASCII at **offset `0x04` of `miscdata`**. It was not in any other
partition that was dumped (NV, `prodnv`, `persist`, `ocdt`, `opporeserve`, `oplusreserve*`), nor in an
older NV/`prodnv` backup, nor in the firmware package.

`miscdata` is Spreadtrum's **phase-check** record ("PhaseCheck" in the forum). WriteIMEI's serial
functions read and write this record (see "How WriteIMEI handles it" below).

## Record layout seen in the dump (1 MB partition)

| Offset | Size | Content in the example |
|---|---|---|
| `0x00` | 4 | Magic `SP09` (stored as bytes `39 30 50 53`, i.e. a little-endian 0x53503039) |
| `0x04` | 24 | **SN1**, ASCII, NUL-padded (the phone's serial; 14 digits here) |
| `0x1C` | 24 | **SN2**, empty here |
| `0x34` | 4 | Station count (7) |
| `0x38` | 15 x 10 | Station names, 10-byte slots: `DOWNLOAD`, `WRITESN`, `CFT`, `BBAT`, `WCN`, `ANTENNA`, `IMEI` |
| `0xDB` | 1 | A flag byte (1) |
| `0xDC` | 32 | Text result: `PASS` |
| `0xFC` | 2 | Test-sign bit mask (`0xFFFE`) |
| `0xFE` | 2 | Item bit mask (`0x7FFE`) |
| `0x100`-`0x1FFF` | | Mostly `0xFF` (erased), with a stray `0x30` byte at `0x300` and `0x3A0` |
| `0x2000` | 64 | Random-looking data (two repeated 16-byte patterns); not decoded |
| `0x2900` | ~32 | A small record starting `a5 a5 5a 5a`; not decoded |
| rest | | Zeros |

The layout follows the Spreadtrum phase-check structure as I remember it and was checked against
this one dump only. The two bit masks and everything from `0x100` on are not decoded. Treat offsets
after `0x38` as tentative.

## How WriteIMEI handles it

Source: `WriteFlashDlg.cpp` (R21.0.0001).

- Two serials, SN1 (primary) and SN2 (secondary), each optional, manual or auto.
- Read and write through `SP_ReadSN` / `SP_WriteSN(handle, isPrimary, buffer, length)`.
- Length comes from the ini file (`SZ_KEY_SN1LEN` / `SZ_KEY_SN2LEN`): default **14**, clamped to
  1-64 (`WIMEI_SN_LENGTH_MAXIMIZE` = 0x40). The dumped serial has exactly 14 digits, which matches the
  default but does not prove the tool wrote it.
- The tool first reads a magic number with `SP_ReadProductFlash`; if it equals
  `SP09_SPPH_MAGIC_NUMBER`, the serial may not exceed 24 characters. That is the same `SP09` marker
  found at the start of `miscdata`.
- Auto serial: `AutoCreateSN` builds `YYYYMMDDhhmmss` and pads or trims it.
- Station-check errors (`SPPH_INVALID_PRODUCTINFO`, `SPPH_WRITE_PRODUCTINFO_FAIL`) refer to the same
  record, which also stores the factory station results listed above.

## Related facts

| Check | Result |
|---|---|
| Android property `persist.sys.oppo.serialno` | Empty on the example phone |
| `ro.serialno` / `ro.boot.serialno` | Not visible to an ordinary Termux shell |
| Default placeholder `0123456789ABCDEF` | Not present |
| Forum report | Erasing NV_LTE, `prodnv` and `miscdata` together reset the serial to that placeholder |
| AI-written forum post claiming `prodnv` holds the serial | Not supported: no serial in `prodnv` |

## Check it on your own phone

```sh
# read-only dump (needs root), run in Termux
su -c 'dd if=/dev/block/by-name/miscdata of=/sdcard/miscdata.bin bs=1M'
python3 tools/parse_miscdata.py /sdcard/miscdata.bin --mask
```

Compare the serial it shows with Settings, the dialer device-information dialog and the sticker.

## What is still unknown

- Whether other partitions keep a second copy of the serial.
- Whether a damaged serial affects the IMEI. The IMEI records are in the NV partitions, not in this
  record, but the same tool run writes both.
- The meaning of the two bit masks and of the blocks at `0x2000` and `0x2900`.
