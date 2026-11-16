# 04 - How WriteIMEI handles the serial number and the IMEI

WriteIMEI R21 is a Windows MFC factory-station tool. Its source is the UI and orchestration layer;
the protocol is in the closed `PhoneCommand.dll`.

## Run flow

1. `InitInstance` creates one phone handle with `SP_CreatePhone`.
2. `DevHound` watches COM ports (SetupAPI); the dialog also reacts to `WM_DEVICECHANGE`.
3. `SP_EnterModeProcess` puts the phone into calibration/NV-access mode; a timeout aborts the run.
4. `WriteFun()` runs the station check, writes serial numbers, then identifiers.
5. Results are logged and the phone leaves the mode (`SP_StopModeProcess`, optional power-off).

## Serial number

- Two serials, SN1 and SN2, each optional (`bChkSN1`, `bChkSN2`), manual or auto (`bChkAutoSN1/2`).
- Auto value: `AutoCreateSN` builds `YYYYMMDDhhmmss` from the current time and pads or trims to the
  requested length.
- Before writing, `SP_ReadProductFlash` reads a magic number. For SP09-type products the serial
  length must not exceed 24 characters, otherwise the run fails with a length error.
- Written with `SP_WriteSN(handle, isPrimary, buffer, length)`; read with `SP_ReadSN`.
- Failure message: "write SN fail" with the error code; the station result is marked failed.
- Length is set in the ini file (default 14, limit 64). The serial is stored in the `miscdata` phase-check record; see [07-serial-number.md](07-serial-number.md).

## IMEI

- Up to four IMEIs (`bChkIMEI` to `bChkIMEI4`), each with a generation mode: manual or scanner,
  auto from system time, or auto-increment (`GCODIMEI_E`). "Use same IMEI" copies one value to all.
- Validation (`CheckIMEI`): at least one item ticked; each IMEI exactly 15 characters; no duplicates
  among the four unless "same IMEI" is set; and not already used (`SearchImei` queries `IMEI.mdb`
  through Jet 4.0, or the text log).
- Auto-create: `AutoCreateIMEI` appends a Luhn check digit (`ComputeCD`) to a 14-digit base.
  `GetImeiCodePlus` increments the base with a carry at 12 digits and recomputes the check digit.
- Writing: `WriteMoc1` and `WriteMoc2` fill an NV parameter block with operation bits
  (`FNAMASK_WRITE_IMEI1`..`4`) and the IMEI as ASCII, then call `SP_NvWriteDirect` or
  `SP_FastWriteNvInfo` (my reading: Moc1 = two IMEIs + Bluetooth via NvWriteDirect; Moc2 = four IMEIs +
  Bluetooth + Wi-Fi via FastWriteNvInfo).
- The modem may refuse: `PC_ERR_WRITE_IMEI_REJECT` (39) shows "IMEI rejected".
- Verify: with "check IMEI after read" the values are read back with `SP_FastReadNvInfo`.
- Logging: `SaveImei` appends `date, IMEI:..., IMEI2:...` to `IMEI.txt` or inserts into `IMEI.mdb`.

## Other items in the same tool

Secure boot read/write/enable, anti-theft flag, program key with chip life cycle and repair state,
chip UID read, Widevine keybox, SIM-lock config, 24 "CU reference" fields, factory reset, power off.

## What it does not show

The diag packet format, the modem's internal encoding and storage locations, the factory-server
message format, and whether a given vendor's phone accepts these commands.
