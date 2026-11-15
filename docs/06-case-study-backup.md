# 06 - Case study: one real backup (identifiers masked)

Device: Realme RMX3830, Android 17 (from screenshots). Backup folder `kopia zapasowa imei`
(10 files, extracted from a 7z).

## Files

`calinv.bin` (2 MB, all zeros), `l_deltanv_a/b.bin` (1 MB), `l_fixnv1_a/b.bin` and `l_fixnv2_a/b.bin`
(2 MB), `l_runtimenv1/2.bin` (2 MB), `prodnv.bin` (64 MB ext4).

## Findings

| Check | Result |
|---|---|
| IMEI records `0x0005` / `0x0179` in fixnv and runtimenv | Present, identical in every copy, valid Luhn digit |
| NV IMEI pair | `86740002*******` / `86740002*******` |
| IMEI pair shown by Android | `86552806*******` / `86552806*******` |
| Android's IMEIs anywhere in the backup (ASCII, UTF-16, BCD variants, 14-digit forms) | **Not found** |
| First 8 digits (type allocation code) | Differ between the two pairs |
| Wi-Fi MAC from Android | Found in `prodnv` as `wifimac.txt` (`5c:a0:6c:**:**:13`) |
| Bluetooth MAC | `btmac.txt`, one lower |
| `productinfo/sprd_ss/0` | 60 KB, random-looking, last changed 2 Oct 2026 |
| `calinv.bin` | All zeros - radio calibration missing from this backup |

## Reading

The backup is from the same phone (MAC match), but its NV does not hold the IMEIs Android reports.
Leading explanation (inference): the live IMEI is kept in encrypted secure storage; the NV pair is an
older or default pair. A second possibility is that the backup predates a change to the identifiers.

## Practical consequence

Do not restore only part of this backup. Putting the NV files back could set the NV pair again
while secure storage keeps another, and the modem's behavior in that state is unknown. Compare the
sticker or box IMEI with both pairs first.

The full numbers are not stored in this repo. Run `tools/scan_backup.py` on your own copy to see them.
