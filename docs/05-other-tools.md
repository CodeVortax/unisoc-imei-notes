# 05 - Do the other tools do something different?

Short answer: they work at different **layers**, but none of the sources I read handles the
encrypted secure-storage file (`sprd_ss`) found in the example backup.

| Tool | Layer | How it reaches the IMEI | Notes |
|---|---|---|---|
| **WriteIMEI R21** | Phone in calibration/diag mode | Sends an NV write request through Spreadtrum's closed `PhoneCommand.dll`; the modem stores and can reject it | Also does serials, MACs, station check, secure-boot, keybox. Duplicate-IMEI database. |
| **SPRDNVEditor** | Boot mode (FDL1 -> FDL2) | Reads/writes the raw NV partition at virtual address `0x90000001` over its own HDLC implementation, then parses records | Item IDs `0x0005` / `0x0179`. Its protocol notes say the transport has no encryption; the code has no `prodnv`/`sprd_ss` handling. |
| **ResearchDownload** (XDA guide) | Boot mode, flashing | Flashes a `.pac` including `nvitem.bin`; "Active Read Flash" can back NV up (Base `0x90000001`, Size `0x10000`) | Ticking NV/Calibration overwrites the phone's own values with the pac's; the thread's fix is to untick them or flash an edited `nvitem.bin`. |
| **NVEditor + Project.rar** (XDA guide) | Offline file editing | You open a project, "Load Image" your `nvitem.bin`, edit `NV_IMEI` / `NV_IMEI2` byte arrays, "Save Image" | Not opened here (rar could not be unpacked); described from the forum posts. Errors like "interpret NV item 2137 fail" mean a profile mismatch. |
| **Hex editor** (XDA posts) | Offline file editing | Edit the 8 bytes directly using the BCD format in doc 02 | Must keep the file's structure valid. |

## What differs in practice

1. **Who writes the bytes.** WriteIMEI asks the modem to do it (and the modem can refuse). SPRDNVEditor
   and the file editors write raw bytes themselves, so anything the modem later regenerates or
   validates can override them.
2. **Which storage they know about.** All of them assume the IMEI is a plain NV item. The example
   backup shows a phone whose NV pair differs from what Android reports, with an encrypted
   `sprd_ss` file next to the MAC files. None of the reviewed code reads or writes that file.
3. **Extra safeguards in WriteIMEI.** Station-flow check (it refers to a product-info record), duplicate
   IMEI database, modem rejection (error 39), optional read-back.
4. **Newer vs older chips.** The XDA method comes from SC6820-era phones with a single `nvitem.bin`.
   Newer phones split NV across `l_fixnv*`, `l_runtimenv*`, `l_deltanv*`, `calinv` and `prodnv`.

## Inference marker

Point 2 ("the NV pair differs because the live IMEI is held elsewhere") is a hypothesis that fits the
data. It is not proven by the files.
