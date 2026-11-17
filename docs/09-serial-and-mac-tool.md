# 09 - idtool: read serial, MACs, and IMEIs, and make patched copies

`tools/idtool.py` reads the serial number, Wi-Fi/Bluetooth MACs, and IMEI records from dump files,
compares a backup with the current dump, and writes **patched copies** of the dump files.

## What it does not do

- It never touches a partition or a phone. It only reads and writes ordinary files.
- It never edits a file in place. Patched output goes to a new file or folder, and it refuses to
  overwrite its input.
- It does not flash anything. Writing a patched file back to a partition is a separate step that can
  fail or brick a phone. Keep the original dumps and their SHA-256 sums.

## Where the values live

| Value | File in a dump | Location |
|---|---|---|
| Serial (SN1) | `miscdata.bin` | 24-byte ASCII field at offset `0x04`, after the `SP09` marker |
| Wi-Fi MAC | `prodnv.bin` (ext4 image) | `wifimac.txt`, text `aa:bb:cc:dd:ee:ff` |
| Bluetooth MAC | `prodnv.bin` | `btmac.txt`, same format |
| IMEI 1 | `l_fixnv1_a/b`, `l_fixnv2_a/b`, `l_runtimenv1/2` | Record `0x0005`, 8-byte 3GPP BCD format |
| IMEI 2 | `l_fixnv1_a/b`, `l_fixnv2_a/b`, `l_runtimenv1/2` | Record `0x0179`, 8-byte 3GPP BCD format |

See [07-serial-number.md](07-serial-number.md), [03-mac-address-discovery.md](03-mac-address-discovery.md),
[01-where-the-imei-lives.md](01-where-the-imei-lives.md), and [02-nv-format-and-imei-encoding.md](02-nv-format-and-imei-encoding.md).

## Usage

Show what a dump holds (works on a single file or a folder):

```sh
python3 tools/idtool.py get /path/to/dump --mask
```

`get` reads the serial from `miscdata.bin`, the MAC files with `debugfs` (package `e2fsprogs`), and
scans any NV `.bin` files for IMEI 1 / IMEI 2 records.

Compare a backup with the current dump (dry run, nothing is written):

```sh
python3 tools/idtool.py restore --from-backup /path/to/backup --to /path/to/current --out /path/to/out --mask
```

Add `--yes` to write patched copies of `miscdata.bin`, `prodnv.bin`, and/or NV files into `--out`.
Only values that differ are patched.

Single changes, each writing a new file:

```sh
python3 tools/idtool.py patch-serial miscdata.bin --serial ABC123 --out miscdata_new.bin
python3 tools/idtool.py patch-mac prodnv.bin --old aa:bb:cc:dd:ee:01 --new aa:bb:cc:dd:ee:02 --out prodnv_new.bin
python3 tools/idtool.py patch-imei l_fixnv1_a.bin --imei1 123456789012347 --imei2 987654321098765 --out l_fixnv1_a_new.bin
```

Patching an entire folder of NV dumps at once:

```sh
python3 tools/idtool.py patch-imei /path/to/nv_folder --imei1 123456789012347 --imei2 987654321098765 --out /path/to/patched_folder
```

## Built-in checks

- The serial must be 1-24 characters from `A-Z a-z 0-9 _ -`.
- `miscdata` must start with the `SP09` marker, and only bytes inside the SN1 field may change; the
  tool aborts otherwise.
- A MAC must have six octets, must not be all zeros, and must be unicast (first octet even).
- `patch-mac` replaces the exact old MAC string and lists every offset it changed. It aborts if the old
  MAC is not found.
- IMEI inputs can be 14 or 15 digits. If 14 digits are provided, the 15th Luhn check digit is automatically
  computed. If 15 digits are provided, the Luhn check digit is validated (override with `--skip-luhn`).
- `patch-imei` verifies that changes are strictly confined to the 8-byte IMEI payload of records `0x0005`
  and `0x0179`.
- **Automatic FixNV Header Checksum**: When an NV file contains the standard Unisoc 512-byte header
  (`"VN\0\0"`), the 16-bit one's complement checksum of the body is automatically recalculated and
  written to offset `0x08`, preventing modem rejection due to CRC mismatch.
- It prints SHA-256 sums of the input and output.

## Limits

- The 64-byte block at `miscdata` offset `0x2000` is undecoded. I tested it against MD5, SHA-1 and
  SHA-256 and CRC-32 of several record ranges and found no match, so I don't know whether it depends
  on the serial. **A patched `miscdata` may be rejected by the phone.**
- The IMEI is stored separately (see doc 01), so fixing the serial or MACs does not fix an IMEI.
- The serial and MACs may exist in other places (for example secure storage or Wi-Fi calibration data).
  Only the two copies above were found in the example dump.
- Tested only on copies of dumps from one RMX3830. Layout details outside the SN1 field are tentative.

## Legal note

Use it to put back the values your own device had, which you can check against its sticker and box.
Do not use it to make a device impersonate another one.
