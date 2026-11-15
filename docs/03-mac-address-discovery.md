# 03 - MAC address discovery

## What was found

The Wi-Fi MAC shown in Android (Settings > About > Status > "Device Wi-Fi MAC address") was found
in the backup, which confirmed that the backup belongs to that phone.

In the example, `prodnv.bin` is an ext4 image. Its files include:

| File in the image | Content |
|---|---|
| `wifimac.txt` | Wi-Fi MAC as text, e.g. `5c:a0:6c:xx:xx:13` |
| `btmac.txt` | Bluetooth MAC as text; one lower than the Wi-Fi MAC in the example |

The same strings also appear at 4 KB-aligned offsets when you scan the raw image, which is how
they were first spotted (`0x4ad000` and `0x4ae000` in the example).

## How to discover it

1. Read the MAC from the phone and write it down (format `aa:bb:cc:dd:ee:ff`).
2. Run `tools/scan_backup.py <folder>`: it lists every `xx:xx:xx:xx:xx:xx` string it finds.
3. To see the files, extract the image on Linux with e2fsprogs (read-only):
   ```sh
   mkdir out && debugfs -R "rdump / out" prodnv.bin
   cat out/wifimac.txt out/btmac.txt
   ```
4. A match between the phone's MAC and `wifimac.txt` shows the backup is from the same device.

Note: Android may show a per-network *randomized* MAC for a connected network. Use the
"Device Wi-Fi MAC address" entry, not the per-network one.

## How WriteIMEI handles the MAC addresses

- Fields: Bluetooth address and Wi-Fi MAC are 12 hex characters (the constant `BT_ADDR_STR_LENGTH`
  is 13, including the terminator).
- Source of the value, per setting: auto-generated (`AutoCreateBTAddr`: random number plus day,
  hour, minute, second; `AutoCreateWifiAddr`: a configured prefix plus random digits), taken from a
  configured start/end range with a running counter (`CustomBtAddrComp`, `CustomWifiAddrComp`),
  or read from a file.
- Written with the operation bits `FNAMASK_WRITE_BTADDR` and `FNAMASK_WRITE_WIFIADDR` inside the same
  NV write request as the IMEI.
- The tool treats the MAC as a plain ASCII field; the library and modem place it in storage.
