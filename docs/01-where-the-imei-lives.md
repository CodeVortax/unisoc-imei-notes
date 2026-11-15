# 01 - Where the IMEI lives

The IMEI is not in Android's filesystem. It belongs to the **modem** (the baseband processor), which
keeps it in non-volatile (NV) storage and reads it at boot. Android only *asks* the modem for it
(that is what Settings > About > IMEI and `*#06#` show).

## Partitions on a modern Unisoc phone

| Partition / file | Size in the example backup | Role |
|---|---|---|
| `l_fixnv1_a/b`, `l_fixnv2_a/b` | 2 MB each | Factory-fixed NV (LTE-era name `l_fixnv`). Holds IMEI items. A/B copies; `1` and `2` are two modem images. |
| `l_runtimenv1/2` | 2 MB each | Runtime NV, working copy the modem updates in use. Same IMEI items. |
| `l_deltanv_a/b` | 1 MB each | Small delta/override NV. No IMEI in the example. |
| `calinv` | 2 MB | RF calibration. **All zeros** in the example backup. |
| `prodnv` | 64 MB | An **ext4 filesystem** ("productinfo"). Holds MAC address files, display tuning XML, sensor calibration and an encrypted `sprd_ss` secure-storage file. |

Older chips (SC6820 era, the XDA thread) use `fixnv`, `backupfixnv`, `runtimenv`, `productinfo`
and a single `nvitem.bin` instead.

## IMEI records

Inside the NV files the IMEI is a record with ID **`0x0005`** (IMEI 1) or **`0x0179`** (IMEI 2),
8 bytes long. SPRDNVEditor's default mapping uses the same IDs. See
[02-nv-format-and-imei-encoding.md](02-nv-format-and-imei-encoding.md) for the byte format.

In the example backup the record headers sit at:

| File | IMEI 1 record | IMEI 2 record |
|---|---|---|
| `l_fixnv1_a/b`, `l_fixnv2_a/b` | `0x16f0` | `0x15338` |
| `l_runtimenv1/2` | `0x212ec` | `0x34f34` |

All copies agreed with each other.

## Important: the NV IMEI may not be the one Android shows

In the example, the NV records held one IMEI pair while the phone reported a different pair. The
`prodnv` partition contains `productinfo/sprd_ss/0`, a 60 KB file with random-looking content
(entropy about 8 bits per byte), which looks like Spreadtrum secure storage.

Inference, not proven: newer phones keep the live IMEI in secure storage and the modem prefers it.
If so, editing only the NV files will not change what Android reports, and restoring only part of a
backup can leave NV and secure storage disagreeing. Restore a backup as a complete set.

## How to check your own device

1. Note the IMEI from the sticker/box and from `*#06#`.
2. Run `tools/scan_backup.py` on your backup folder.
3. If the NV records match the phone, the NV is the source. If not, see the paragraph above.
