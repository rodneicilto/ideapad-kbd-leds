# Lenovo IdeaPad 83RR/83SR Linux Keyboard Support

This repository contains Linux kernel patches and supporting packages to enable
full keyboard functionality on Lenovo IdeaPad laptops based on the Intel Wildcat
Lake SoC (models **83RR** worldwide and **83SR** Brazil regional variant).

## Problem

The internal keyboard on these models uses EC (Embedded Controller) PS/2
emulation that does not fully support the AT protocol. Specifically, sending the
`SETLEDS` command (`0xED`) after keyboard initialization causes the EC to return
corrupted scancodes (visible as `**` in `i8042.debug` output), rendering the
keyboard completely non-functional under Linux.

Additionally, the existing `SERIO_QUIRK_DUMBKBD` workaround — while resolving
the scancode corruption — causes the kernel to skip `EV_LED` capability
registration, making `CapsLock`/`NumLock`/`ScrollLock` state invisible to
userspace.

## Solution

Two kernel patches and a supporting userspace package provide a complete solution:

### Patch 1/2 — `input: atkbd`

Introduces `atkbd_softleds`: a DMI-detected mode that:
- Suppresses `0xED` SETLEDS commands to hardware (prevents scancode corruption)
- Registers `EV_LED` capabilities so LED state remains visible to userspace
- Detected via the existing `atkbd_dmi_quirk_table` mechanism

### Patch 2/2 — `platform/x86: ideapad-laptop`

Adds physical CapsLock/NumLock LED control via:
- Direct EC register access at offset `0xA1` (bit 5 = CAPL, bit 4 = NUML)
- ACPI `_QDF` method (`\_SB.PC00.LPCB.EC0._QDF`) to sync EC state to GPIO
- Discovered via DSDT analysis of the hardware firmware

**DSDT findings:**
```
EC offset 0xA1:
  bit 4 (0x10) = NUML  -> NumLock LED
  bit 5 (0x20) = CAPL  -> CapsLock LED

_QDF method:
  reads CAPL/NUML -> calls SGOV() -> drives GPIO to physical LED pin
  GPIO 0x001A1087 -> CapsLock LED
  GPIO 0x001A0485 -> NumLock LED
```

### Package — `ideapad-kbd-leds`

A Debian package providing a systemd service that bridges the virtual LED state
(registered by `atkbd/softleds`) to the physical LED driver (registered by
`ideapad-laptop`). This is a temporary workaround until a clean kernel-space
solution (Patch 3, planned) is implemented.

## Upstream Submission

Both patches have been submitted to the Linux kernel mailing lists:

| Patch | Destination | Maintainer |
|-------|-------------|------------|
| `input: atkbd` | `linux-input@vger.kernel.org` | Dmitry Torokhov |
| `platform/x86: ideapad-laptop` | `platform-driver-x86@vger.kernel.org` | Hans de Goede |

## Repository Structure

```
ideapad-83rr-linux-support/
├── README.md
├── patches/
│   ├── 0001-input-atkbd-add-softleds-quirk-EC-PS2-emulation.patch
│   └── 0002-platform-x86-ideapad-laptop-capslock-numlock-leds.patch
├── scripts/
│   ├── final-patch1-atkbd-7.1-v2.py    # Apply patch 1 to kernel source
│   └── final-patch2-ideapad-7.1-v2.py  # Apply patch 2 to kernel source
└── debian/
    └── ideapad-kbd-leds/               # Systemd LED sync service package
```

## Applying the Patches

Requirements: Linux kernel 7.1.x source tree.

```bash
cd /usr/src/linux-7.1.x

# Apply patch 1 (atkbd softleds)
git checkout drivers/input/keyboard/atkbd.c
git checkout drivers/input/serio/i8042-acpipnpio.h
python3 scripts/final-patch1-atkbd-7.1-v2.py

# Apply patch 2 (ideapad LED control)
git checkout drivers/platform/x86/lenovo/ideapad-laptop.c
python3 scripts/final-patch2-ideapad-7.1-v2.py

# Build
make -j$(nproc)
make install
```

Alternatively, apply the pre-generated patch files directly:

```bash
git apply patches/0001-input-atkbd-add-softleds-quirk-EC-PS2-emulation.patch
git apply patches/0002-platform-x86-ideapad-laptop-capslock-numlock-leds.patch
```

## Installing the LED Sync Package

```bash
sudo dpkg -i ideapad-kbd-leds_1.0.0-1_all.deb
```

The service will start automatically and sync LED state on every keypress.

## Technical Background

### Why `serio->id.extra` Cannot Be Used

`serio->id.extra` is defined as `__u8` (8 bits only) in
`include/linux/mod_devicetable.h`. The existing `SERIO_QUIRK_*` flags in
`i8042-acpipnpio.h` already use bits up to `BIT(15)`, making it impossible to
pass new quirk flags through this field from `i8042` to `atkbd`. This is why
the quirk is detected directly in `atkbd` via its own DMI table.

### LED Architecture

```
Keyboard press
    └── atkbd (softleds mode)
            └── EV_LED event -> input3::capslock (virtual, no hw callback)
                    └── ideapad-kbd-leds service (polling)
                            └── input::capslock (physical callback)
                                    └── ec_write(0xA1, val)
                                            └── acpi_evaluate_object(_QDF)
                                                    └── SGOV() -> GPIO -> LED
```

### Planned Patch 3

Replace the polling systemd service with a clean kernel-space solution using
an `input_handler` in `ideapad-laptop` that monitors `EV_LED` events from the
associated input device and triggers the EC write directly, eliminating the
userspace bridge entirely.

## Affected Hardware

| Model | Region | Status |
|-------|--------|--------|
| Lenovo IdeaPad 83RR |
| Lenovo IdeaPad 83SR |

## Debugging

```bash
# Verify keyboard is functional
cat /proc/bus/input/devices | grep -A10 'AT Translated'
# Expected: B: EV=120013 (includes EV_LED)

# Verify atkbd softleds DMI match
dmesg | grep -i softleds

# Verify physical LED control
echo 1 | sudo tee /sys/class/leds/input::capslock/brightness

# Monitor LED sync service
journalctl -fu ideapad-kbd-leds
```

## License

Kernel patches are licensed under GPL-2.0-only, consistent with the Linux kernel.
The `ideapad-kbd-leds` package is licensed under GPL-2.0-only.

## Author

Rodnei Cilto

Developed as part of Bellatrix Linux distribution kernel engineering efforts.
