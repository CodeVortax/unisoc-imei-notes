# 07 - Serial number

## What WriteIMEI does with serial numbers

Source: `WriteFlashDlg.cpp` (R21.0.0001).

- Two serials exist, SN1 (primary) and SN2 (secondary). Each is optional, manual or auto.
- Write and read go through `SP_WriteSN(handle, isPrimary, buffer, length)` and `SP_ReadSN(...)`
  in the closed `PhoneCommand.dll`.
- Length comes from the ini file (constants `SZ_KEY_SN1LEN` / `SZ_KEY_SN2LEN`). Default 14,
  clamped to 1-64 characters (`WIMEI_SN_LENGTH_MAXIMIZE` = 0x40). This matches a forum poster who had
  a 16-character serial but a tool build limited to 14 and "found where the length changes".
- Before writing, the tool reads a magic number with `SP_ReadProductFlash`. If it equals
  `SP09_SPPH_MAGIC_NUMBER`, the serial may not exceed 24 characters.
- Auto serial: `AutoCreateSN` builds `YYYYMMDDhhmmss` and pads or trims it.
- Station-check errors are named `SPPH_INVALID_PRODUCTINFO` and `SPPH_WRITE_PRODUCTINFO_FAIL`.
  SPPH is Spreadtrum's phase-check record. The serial and the station results share that record
  (my reading of the names and the magic-number check; the struct itself is not in the zip).

## Where the serial is stored (inference)

On the Realme C51 the 4PDA thread calls the phase-check partition **PhaseCheck (`miscdata`)**.
A poster who erased NV_LTE, `prodnv` and `miscdata` together reported the serial turning into
`0123456789ABCDEF`, the IMEI disappearing and the MACs resetting. That shows the serial is in one of
those three partitions. It does not show which. The code points to the phase-check record, so
`miscdata` is the most likely home.

## What the example backup shows

| Check | Result |
|---|---|
| Default placeholder `0123456789ABCDEF` | Not present in any file |
| Serial-like strings in `l_fixnv*`, `l_runtimenv*`, `l_deltanv*` | None found (the strings there are modem version, carrier names and filler) |
| Files in the `prodnv` filesystem | MAC files, a 64-hex-character `GUID`, display and sensor data, secure storage; no serial file |
| `miscdata` / PhaseCheck | **Not in the backup** |

Conclusion: the serial is most likely in `miscdata`, which this backup lacks. A forum post claiming
that `prodnv` holds the serial is not supported by this backup. The `GUID` file is a hash-like
identifier and was not identified as the serial.

## Other reports from the thread

- After flashing with a factory tool, one user kept the correct serial while the IMEI was lost.
- Another entered the serial in a flasher's "Input SN" prompt and flashing started before the full
  serial was typed.
- A user wrote that after writing an IMEI, the serial field showed the IMEI. Unverified.

## Check it on your own phone

```sh
adb shell getprop ro.serialno
```

Compare with Settings > About phone and the sticker. To locate the stored copy, back up `miscdata`
(read-only, with the flasher's Active Read Flash), then search the dump for your serial:

```sh
python3 tools/scan_backup.py <folder> --serial YOURSERIAL
```
