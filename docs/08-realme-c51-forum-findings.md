# 08 - Realme C51 (RMX3830) forum findings

Digest of a 4PDA discussion thread about the Realme C51 (Unisoc T612). Pages seen: search results
1-20 and 41-100; the page for results 21-40 was not available. Forum posts are anecdotes, not
verified facts.

## Partitions people tell you to back up

| Partition | Name in the thread | Why |
|---|---|---|
| `l_fixnv1_a` | NV_LTE | Modem NV including IMEI records |
| `prodnv` | ProdNV | Product info: MAC files, calibration |
| `miscdata` | PhaseCheck | Station and serial data (see doc 07) |
| `ocdt_a/b` | Oppo Component Data Table | Reported (by an AI-written post) to hold the project ID |

The thread says these are device-specific and are not replaced by a firmware package.

## Backing up (as posted)

In Research Download: load the firmware, open the settings (gears), keep only FDL1 and FDL2
selected, tick "Save file to local" on the Backup tab, and use Active Read Flash on the Flash
Operations tab to read the chosen partitions. Files land in the program's Backup/ReadFlash folders.
Posters stress copying them elsewhere at once; one lost a backup by moving it out of a folder that was
then cleaned. `spd_dump` on GitHub is mentioned as a lighter way to read partitions.

## What posters say causes IMEI loss

- Full flash with a factory tool, or a flasher fork that does not back up.
- Erasing NV_LTE, `prodnv` and `miscdata`.
- Downgrading, or the bootloader-unlock script, without backups.

## Behaviours reported

- A factory reset restored the IMEI for some users.
- After erasing NV_LTE, one user kept the IMEI for one reboot and lost it on the next.
- Some users saw the IMEI in the flasher or in backup files but the phone did not use it.
- After restoring backups, one user got a working second SIM slot but still no IMEI.
- NFC survived erasing the three partitions; one ID choice at the first firmware read
  (22716 vs 22718) was said to control NFC.
- Without an IMEI, Google sign-in was reported to fail.

## WriteIMEI reports

Mostly negative: "OK" shown but nothing changes, mode-entry timeouts on COM ports, and one success
after disconnecting the battery inside the phone. The source waits on a timeout for the phone to enter
its mode (doc 04), which fits the timeouts. Their build (R21.18.3901) is newer than the source
reviewed here.

## AI-written post

One reply is chatbot output pasted by a thread member. It lists `prodnv`, `l_fixnv`, `l_runtimenv`,
`ocdt` and `calinv`. Checked against a real backup: the IMEI records are in `l_fixnv` and
`l_runtimenv`; the MACs are in `prodnv`; the serial is not in `prodnv`; `ocdt` could not be checked.

## Cautions

- Copying another phone's IMEI is illegal in many places and can get a phone blocked.
- Paid "IMEI repair" tools and spoofing modules appear in the thread; they are outside these notes.
- Firmware, drivers and scripts linked in the thread were not checked here.
