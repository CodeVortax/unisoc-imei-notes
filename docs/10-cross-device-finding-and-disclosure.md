# 10 - Cross-device comparison, and a public bypass report worth disclosing to Unisoc

## Finding 1 (independently verified here): the plain IMEI record is a stock template, not per-device

Comparing two separate RMX3830 dumps - the user's own phone, and a second unit with a different
serial number:

| NV record | Same on both phones? |
|---|---|
| Plain IMEI1 / IMEI2 (NV items `0x0005` / `0x0179`, see [02](02-nv-format-and-imei-encoding.md)) | **Identical**, byte for byte, at the same offsets |
| `enpcba` / `enimei1` / `enimei2` (the high-entropy items next to them, see case study) | **Different** on every phone |
| `miscdata` serial (SN1) | Different on every phone (as expected) |

Two different physical devices carry the exact same plain `IMEI` NV bytes. That record cannot be
each device's real identity - it is almost certainly a stock value baked into the factory NV
template/firmware image itself, not written per unit. This matches every earlier observation that
the plain NV pair never matched either phone's sticker IMEI.

The three high-entropy items next to it differ between the two phones even though the plain record
they sit beside is identical. Same plaintext context, different stored bytes per device, is the
signature of something that mixes in a per-device secret before being stored - consistent with
(but not proof of) a hardware-bound signing/encryption step, as opposed to a static, shared
transform.

## Finding 2 (third-party report, not verified by us): a public tool claims to defeat the check entirely

A public GitHub repository (by a different author, for a different Realme model - the C21Y,
Unisoc T610/UMS512, not our T612) describes, in its own README, a three-layer architecture:

1. A userspace RIL library patch.
2. **A patched baseband modem firmware (`l_modem`)** that the README says disables an
   IMEI-verification routine and an associated hardware efuse-state check, and alters a SIM-lock
   comparison, so the modem accepts any IMEI without the signature/token check succeeding.
3. Replacement NV calibration data.

The README also describes the failure behavior when that check is *not* bypassed: the modem zeroes
its internal buffer and reports an all-zero IMEI to the network, which matches independent reports
in other forum threads about phones reverting to `000000000000000` after a failed IMEI write.

We have not inspected or verified this tool's patch mechanics, and nothing from it is reproduced
here beyond this description. It is relevant to this repository only as public evidence that:

- NV items `0x0005` / `0x0179` are gated by a verification step in the baseband firmware, not just
  decorative values (the hardware-bound theory in [case study] has independent support).
- That verification step can apparently be removed by patching the modem's own firmware, which is a
  materially different and more serious class of issue than "the data format is undocumented" - it
  describes disabling a security check rather than restoring valid signed data.

## Why this belongs in a vendor report, not in a how-to

Restoring a device's own, already-assigned IMEI through an authorized channel is a repair activity.
Patching a baseband firmware image to remove its own integrity/identity verification is a different
thing: it is the mechanism that would let *any* IMEI be accepted on *any* device, which is also the
mechanism of IMEI cloning and carrier-identity fraud. That is why this document stops at describing
the reported existence and category of the bypass, and does not include its patch offsets, opcodes,
or any file from it.

## Reporting this to Unisoc

If you want to disclose this, treat it like a normal vendor security report:

1. Contact Unisoc's security/PSIRT channel (check their corporate site for a responsible-disclosure
   or security-contact page; many SoC vendors also accept reports via their OEM customers' security
   teams if no direct channel is listed).
2. Give them: the affected chip family (Unisoc T610/UMS512 per the report; worth asking whether T612
   and other Tiger-series chips share the same baseband code), the fact that a public tool claims to
   patch the baseband RTOS to remove IMEI-verification and an efuse-state check, and a link to the
   public repository as the evidence - don't attach or re-describe its binary patch yourself.
3. Mention the related, already-public bootROM-level work in this space (`CVE-2022-38694` and the
   `spd_dump`/`UnisocBypass` family referenced in [05](05-other-tools.md)), since a baseband-level
   bypass building on top of an unsigned-code execution path is a natural escalation of that known
   issue and the vendor may want to assess both together.
4. Expect them to ask for the repository link and device/chip identifiers above; that's normally
   sufficient for a vendor to start triage without you having to supply exploit code.

## What remains unresolved for this project

None of the above decodes what the `enimei1`/`enimei2`/`enpcba` blobs actually contain, or recovers
either device's real IMEI from its own NV data. It only strengthens the evidence that those items are
protected by a per-device, firmware-enforced check rather than being plainly readable.
