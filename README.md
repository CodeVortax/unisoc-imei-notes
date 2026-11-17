# Unisoc / Spreadtrum IMEI notes

Research notes on where a Unisoc (Spreadtrum) phone keeps its IMEI, serial number and MAC addresses,
and how the common tools read or write them. Built from:

- the source of **WriteIMEI Tool R21** (Spreadtrum factory tool),
- the source of **SPRDNVEditor** (C# NV reader/editor),
- the XDA thread *"How to Root SpreadTrum SP6820"* (pages 7-9; NVEditor / Project.rar tutorial),
- a read-only analysis of one real NV backup (Realme RMX3830, Android 17).

## Device-Specific Restoration Tools

This repo now includes complete restoration tools for Unisoc devices:

| Device | Tool | Documentation |
|--------|------|---------------|
| Realme C21Y (RMX3261/3263) | [tools/c21y_imei_restore.py](tools/c21y_imei_restore.py) | [HOW_IT_WORKS_C21Y.md](HOW_IT_WORKS_C21Y.md) |
| Realme C51 (RMX3830) | [tools/c51_imei_restore.py](tools/c51_imei_restore.py) | [devices/c51/README.md](devices/c51/README.md) |

## Documentation Contents

| File | What it covers |
|---|---|
| [docs/01-where-the-imei-lives.md](docs/01-where-the-imei-lives.md) | Partitions and files that can hold the IMEI, and what was found in the backup |
| [docs/02-nv-format-and-imei-encoding.md](docs/02-nv-format-and-imei-encoding.md) | NV file layout, record format, the 8-byte IMEI encoding, check digit |
| [docs/03-mac-address-discovery.md](docs/03-mac-address-discovery.md) | Where the Wi-Fi/Bluetooth MAC is stored and how to find it |
| [docs/04-writeimei-serial-and-imei.md](docs/04-writeimei-serial-and-imei.md) | How WriteIMEI handles IMEI and serial number |
| [docs/05-other-tools.md](docs/05-other-tools.md) | Do the other tools do something different? |
| [docs/06-case-study-backup.md](docs/06-case-study-backup.md) | Findings from the real backup (identifiers masked) |
| [docs/07-serial-number.md](docs/07-serial-number.md) | Where the serial number is stored and how WriteIMEI handles it |
| [docs/08-realme-c51-forum-findings.md](docs/08-realme-c51-forum-findings.md) | Digest of a Realme C51 forum thread: partitions, backups, reports |
| [docs/09-serial-and-mac-tool.md](docs/09-serial-and-mac-tool.md) | How `idtool.py` works, its checks and its limits |
| [tools/scan_backup.py](tools/scan_backup.py) | Read-only scanner: finds IMEI NV records and MAC strings in a backup folder |
| [tools/parse_miscdata.py](tools/parse_miscdata.py) | Read-only parser for the `miscdata` phase-check record (serial, stations) |
| [tools/idtool.py](tools/idtool.py) | Read serial/MACs/IMEIs from dumps; make patched copies (never touches a device) |

## Scope and limits

- The scanner only **reads**. Nothing here writes identifiers to a phone.
- WriteIMEI's real phone protocol is inside a closed `PhoneCommand.dll` that is not in the source zip.
- `NVEditor.rar`, `Project.rar` and `nvitem.rar` could not be unpacked in the analysis environment,
  so those tools are described from the forum posts only.
- Some statements are inferences; each doc marks them as such.

## Legal note

The IMEI identifies a handset to mobile networks. Restoring the number printed on your own device is
a normal repair task. Writing an IMEI that does not belong to the device is illegal in many countries
and can get the phone blocked. These notes explain how the software is built; they are not a procedure
for changing identifiers.

## Quick start

```sh
python3 tools/scan_backup.py /path/to/backup_folder
python3 tools/scan_backup.py /path/to/backup_folder --reported 123456789012345 --mask
python3 tools/scan_backup.py /path/to/backup_folder --serial YOURSERIAL
python3 tools/parse_miscdata.py /path/to/miscdata.bin --mask
python3 tools/idtool.py get /path/to/dump_folder --mask
python3 tools/idtool.py patch-imei /path/to/l_fixnv1_a.bin --imei1 YOURIMEI1 --imei2 YOURIMEI2 --out /path/to/l_fixnv1_a_patched.bin
```
