# 09 - idtool: read the serial and MACs, and make patched copies

`tools/idtool.py` reads the serial number and the Wi-Fi/Bluetooth MACs from dump files, compares a
backup with the current dump, and writes **patched copies** of the dump files.

## What it does not do

- It never touches a partition or a phone. It only reads and writes ordinary files.
- It never edits a file in place. Patched output goes to a new file or folder, and it refuses to
  overwrite its input.
- It does not read or write the IMEI or any NV item.
- It does not flash anything. Writing a patched file back to a partition is a separate step that can
  fail or brick a phone. Keep the original dumps and their SHA-256 sums.

## Where the values live

| Value | File in a dump | Location |
|---|---|---|
| Serial (SN1) | `miscdata.bin` | 24-byte ASCII field at offset `0x04`, after the `SP09` marker |
| Wi-Fi MAC | `prodnv.bin` (ext4 image) | `wifimac.txt`, text `aa:bb:cc:dd:ee:ff` |
| Bluetooth MAC | `prodnv.bin` | `btmac.txt`, same format |

See [07-serial-number.md](07-serial-number.md) and [03-mac-address-discovery.md](03-mac-address-discovery.md).

## Usage

Show what a dump holds (works on a file or on a folder with `miscdata.bin` / `prodnv.bin`):

```sh
python3 tools/idtool.py get /path/to/dump --mask
```

`get` reads the MAC files with `debugfs` (package `e2fsprogs`). Without it the tool falls back to
listing MAC-like strings found in the image.

Compare a backup with the current dump (dry run, nothing is written):

```sh
python3 tools/idtool.py restore --from-backup /path/to/backup --to /path/to/current --out /path/to/out --mask
```

Add `--yes` to write patched copies of `miscdata.bin` and/or `prodnv.bin` into `--out`. Only values
that differ are patched.

Single changes, each writing a new file:

```sh
python3 tools/idtool.py patch-serial miscdata.bin --serial ABC123 --out miscdata_new.bin
python3 tools/idtool.py patch-mac prodnv.bin --old aa:bb:cc:dd:ee:01 --new aa:bb:cc:dd:ee:02 --out prodnv_new.bin
```

## Built-in checks

- The serial must be 1-24 characters from `A-Z a-z 0-9 _ -`.
- `miscdata` must start with the `SP09` marker, and only bytes inside the SN1 field may change; the
  tool aborts otherwise.
- A MAC must have six octets, must not be all zeros, and must be unicast (first octet even).
- `patch-mac` replaces the exact old MAC string and lists every offset it changed. It aborts if the old
  MAC is not found.
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
