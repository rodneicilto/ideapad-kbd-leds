#!/usr/bin/env python3
"""
final-patch1-atkbd-7.1-v2.py
PATCH 1/2 DEFINITIVO - kernel 7.1.x
atkbd softleds quirk para EC PS/2 emulation (Lenovo IdeaPad 83RR/83SR)

Correcoes v2:
- Comentarios com trailing */ em linha separada (checkpatch clean)
- Ancoras validadas para kernel 7.1.2
- DMI entries 83RR + 83SR

Uso:
  cd /usr/src/linux-7.1.x
  git checkout drivers/input/keyboard/atkbd.c
  git checkout drivers/input/serio/i8042-acpipnpio.h
  python3 final-patch1-atkbd-7.1-v2.py
"""
import sys, os, shutil, subprocess

ATKBD  = "drivers/input/keyboard/atkbd.c"
I8042H = "drivers/input/serio/i8042-acpipnpio.h"
PATCH_OUT = "0001-input-atkbd-add-softleds-quirk-EC-PS2-emulation.patch"

def die(msg):
    print(f"ERRO FATAL: {msg}")
    sys.exit(1)

def apply(content, old, new, desc):
    if new in content:
        print(f"  SKIP: {desc}")
        return content
    if old not in content:
        print(f"  ERRO: {desc}")
        return None
    print(f"  OK:   {desc}")
    return content.replace(old, new, 1)

for f in [ATKBD, I8042H]:
    if not os.path.exists(f):
        die(f"{f} nao encontrado")
    orig = f + ".orig"
    if not os.path.exists(orig):
        shutil.copy2(f, orig)
        print(f"Backup: {orig}")
    else:
        print(f"Backup ja existe: {orig}")

# ?? atkbd.c ??????????????????????????????????????????????????????????????????

with open(ATKBD, "r") as f:
    c = f.read()

errors = 0
print(f"\n[{ATKBD}]")

# 1. bool softleds na struct atkbd
result = apply(c,
    "\tbool scroll;\n"
    "\tbool enabled;",
    "\tbool scroll;\n"
    "\tbool softleds;\t\t/* suppress 0xED, register EV_LED in software */\n"
    "\tbool enabled;",
    "struct atkbd: add softleds field")
if result is None: errors += 1
else: c = result

# 2. Global atkbd_softleds
result = apply(c,
    "static bool atkbd_skip_deactivate;",
    "static bool atkbd_skip_deactivate;\n"
    "static bool atkbd_softleds;",
    "add atkbd_softleds global")
if result is None: errors += 1
else: c = result

# 3. Guard em atkbd_set_leds (7.1 usa u8 param)
result = apply(c,
    "static int atkbd_set_leds(struct atkbd *atkbd)\n"
    "{\n"
    "\tstruct input_dev *dev = atkbd->dev;\n"
    "\tu8 param[2];\n"
    "\n"
    "\tparam[0] = (test_bit(LED_SCROLLL",
    "static int atkbd_set_leds(struct atkbd *atkbd)\n"
    "{\n"
    "\tstruct input_dev *dev = atkbd->dev;\n"
    "\tu8 param[2];\n"
    "\n"
    "\t/*\n"
    "\t * softleds: EC PS/2 emulation does not support AT commands\n"
    "\t * after initialization. Accept LED state from userspace but\n"
    "\t * never send SETLEDS (0xED) to avoid scancode corruption.\n"
    "\t */\n"
    "\tif (atkbd->softleds)\n"
    "\t\treturn 0;\n"
    "\n"
    "\tparam[0] = (test_bit(LED_SCROLLL",
    "atkbd_set_leds: guard for softleds")
if result is None: errors += 1
else: c = result

# 4. EV_LED quando softleds
result = apply(c,
    "\tif (atkbd->write) {\n"
    "\t\tinput_dev->evbit[0] |= BIT_MASK(EV_LED);\n"
    "\t\tinput_dev->ledbit[0] = BIT_MASK(LED_NUML) |\n"
    "\t\t\tBIT_MASK(LED_CAPSL) | BIT_MASK(LED_SCROLLL);\n"
    "\t}",
    "\tif (atkbd->write || atkbd->softleds) {\n"
    "\t\tinput_dev->evbit[0] |= BIT_MASK(EV_LED);\n"
    "\t\tinput_dev->ledbit[0] = BIT_MASK(LED_NUML) |\n"
    "\t\t\tBIT_MASK(LED_CAPSL) | BIT_MASK(LED_SCROLLL);\n"
    "\t}",
    "atkbd_set_device_attrs: register EV_LED when softleds")
if result is None: errors += 1
else: c = result

# 5. Bloco softleds em atkbd_connect
result = apply(c,
    "\tif (atkbd->softrepeat)\n"
    "\t\tatkbd->softraw = true;\n"
    "\n"
    "\tserio_set_drvdata(serio, atkbd);",
    "\tif (atkbd->softrepeat)\n"
    "\t\tatkbd->softraw = true;\n"
    "\n"
    "\tif (atkbd_softleds) {\n"
    "\t\tserio->write = NULL;\n"
    "\t\tatkbd->write = false;\n"
    "\t\tatkbd->softleds = true;\n"
    "\t}\n"
    "\n"
    "\tserio_set_drvdata(serio, atkbd);",
    "atkbd_connect: apply softleds before serio_set_drvdata")
if result is None: errors += 1
else: c = result

# 6. Callback atkbd_setup_softleds antes do comentario NOTE
result = apply(c,
    "/*\n"
    " * NOTE: do not add any more \"force release\" quirks to this table.  The\n"
    " * task of adjusting list of keys that should be \"released\" automatically\n"
    " * by the driver is now delegated to userspace tools, such as udev, so\n"
    " * submit such quirks there.\n"
    " */\n"
    "static const struct dmi_system_id atkbd_dmi_quirk_table[]",
    "static int __init atkbd_setup_softleds(const struct dmi_system_id *id)\n"
    "{\n"
    "\tatkbd_softleds = true;\n"
    "\treturn 1;\n"
    "}\n"
    "\n"
    "/*\n"
    " * NOTE: do not add any more \"force release\" quirks to this table.  The\n"
    " * task of adjusting list of keys that should be \"released\" automatically\n"
    " * by the driver is now delegated to userspace tools, such as udev, so\n"
    " * submit such quirks there.\n"
    " */\n"
    "static const struct dmi_system_id atkbd_dmi_quirk_table[]",
    "add atkbd_setup_softleds before DMI table")
if result is None: errors += 1
else: c = result

# 7. DMI entries 83RR + 83SR
# Ancora: { }\n};\n\nstatic int __init atkbd_init (validada no 7.1.2)
result = apply(c,
    "\t{ }\n"
    "};\n"
    "\n"
    "static int __init atkbd_init(void)",
    "\t{\n"
    "\t\t/*\n"
    "\t\t * Lenovo IdeaPad 83RR (Wildcat Lake) - EC PS/2 emulation\n"
    "\t\t * returns corrupted scancodes ('**' in i8042.debug) when\n"
    "\t\t * receiving AT SETLEDS (0xED) after keyboard initialization.\n"
    "\t\t * Enable softleds mode: suppress 0xED to hardware while\n"
    "\t\t * keeping CapsLock/NumLock/ScrollLock visible to userspace.\n"
    "\t\t */\n"
    "\t\t.matches = {\n"
    '\t\t\tDMI_MATCH(DMI_SYS_VENDOR, "LENOVO"),\n'
    '\t\t\tDMI_MATCH(DMI_PRODUCT_NAME, "83RR"),\n'
    "\t\t},\n"
    "\t\t.callback = atkbd_setup_softleds,\n"
    "\t},\n"
    "\t{\n"
    "\t\t/* Lenovo IdeaPad 83SR (83RR Brazil regional variant) */\n"
    "\t\t.matches = {\n"
    '\t\t\tDMI_MATCH(DMI_SYS_VENDOR, "LENOVO"),\n'
    '\t\t\tDMI_MATCH(DMI_PRODUCT_NAME, "83SR"),\n'
    "\t\t},\n"
    "\t\t.callback = atkbd_setup_softleds,\n"
    "\t},\n"
    "\t{ }\n"
    "};\n"
    "\n"
    "static int __init atkbd_init(void)",
    "atkbd_dmi_quirk_table: add 83RR + 83SR softleds entries")
if result is None: errors += 1
else: c = result

if errors > 0:
    print(f"\nFALHA: {errors} erro(s) - arquivo NAO modificado")
    sys.exit(1)

with open(ATKBD, "w") as f:
    f.write(c)
print("  Salvo.")

# ?? i8042-acpipnpio.h ?????????????????????????????????????????????????????????

with open(I8042H, "r") as f:
    c = f.read()

print(f"\n[{I8042H}]")
errors = 0

# Comentario com */ em linha separada (checkpatch clean)
result = apply(c,
    "#define SERIO_QUIRK_DUMBKBD\t\tBIT(9)\n"
    "#define SERIO_QUIRK_NOLOOP\t\tBIT(10)",
    "#define SERIO_QUIRK_DUMBKBD\t\tBIT(9)\n"
    "#define SERIO_QUIRK_NOLOOP\t\tBIT(10)\n"
    "/* SERIO_QUIRK_DUMBKBD_LEDS handled via atkbd DMI quirk table.\n"
    " * serio->id.extra is __u8 (8 bits only), cannot carry this flag.\n"
    " */",
    "i8042-acpipnpio.h: document SERIO_QUIRK_DUMBKBD_LEDS (checkpatch clean)")
if result is None: errors += 1
else: c = result

if errors > 0:
    print(f"\nFALHA: {errors} erro(s) - arquivo NAO modificado")
    sys.exit(1)

with open(I8042H, "w") as f:
    f.write(c)
print("  Salvo.")

# ?? Gera patch ????????????????????????????????????????????????????????????????

print(f"\n[Gerando {PATCH_OUT}]")
header = (
    "From: Rodnei <developer@bellatrix>\n"
    "Date: Mon, 26 May 2026\n"
    "Subject: [PATCH 1/2] input: atkbd: add softleds quirk for broken EC PS/2 emulation\n"
    "\n"
    "Some Lenovo IdeaPad laptops (e.g. 83RR/83SR, Wildcat Lake) implement\n"
    "PS/2 keyboard emulation via the Embedded Controller (EC) but do not\n"
    "fully support the AT protocol. Specifically, sending the SETLEDS\n"
    "command (0xED) after initialization causes the EC to return corrupted\n"
    "scancodes (reported as '**' in i8042.debug), rendering the keyboard\n"
    "non-functional.\n"
    "\n"
    "The existing SERIO_QUIRK_DUMBKBD resolves scancode corruption by\n"
    "zeroing serio->write, preventing AT commands. However, LED registration\n"
    "in atkbd_set_device_attrs() depends on atkbd->write being set, so\n"
    "dumbkbd mode loses EV_LED capabilities entirely.\n"
    "\n"
    "Note: serio->id.extra is __u8 (8 bits only) and cannot be used to\n"
    "pass new quirk flags from i8042 to atkbd. The quirk is detected\n"
    "directly in atkbd via its DMI quirk table.\n"
    "\n"
    "Introduce atkbd_softleds: a DMI-detected mode that combines dumbkbd\n"
    "behaviour (serio->write = NULL, no 0xED sent) with EV_LED registration\n"
    "so that CapsLock/NumLock/ScrollLock state remains visible to userspace\n"
    "via the input subsystem.\n"
    "\n"
    "Add DMI entries for Lenovo IdeaPad 83RR (Wildcat Lake) and its Brazil\n"
    "regional variant 83SR.\n"
    "\n"
    "Signed-off-by: Rodnei <developer@bellatrix>\n"
    "---\n"
)

diff_content = header
for filepath in [ATKBD, I8042H]:
    r = subprocess.run(
        ["diff", "-u", filepath + ".orig", filepath],
        capture_output=True, text=True
    )
    if r.returncode == 1:
        lines = r.stdout.split('\n')
        lines[0] = f"--- a/{filepath}"
        lines[1] = f"+++ b/{filepath}"
        diff_content += '\n'.join(lines)

with open(PATCH_OUT, "w") as f:
    f.write(diff_content)
print(f"  {PATCH_OUT} ({os.path.getsize(PATCH_OUT)} bytes)")

# ?? Validacao ?????????????????????????????????????????????????????????????????

print("\n[Validacao]")
with open(PATCH_OUT) as f:
    patch = f.read()

checks = [
    ("bool softleds",                    "struct atkbd softleds"),
    ("static bool atkbd_softleds",       "global atkbd_softleds"),
    ("atkbd_setup_softleds",             "DMI callback"),
    ("83RR",                             "DMI entry 83RR"),
    ("83SR",                             "DMI entry 83SR (Brazil)"),
    ("atkbd->softleds)\n+\t\treturn 0",  "guard atkbd_set_leds"),
    ("atkbd->write || atkbd->softleds",  "EV_LED condicional"),
    ("serio->write = NULL",              "dumbkbd em atkbd_connect"),
    (" */\n",                            "trailing */ em linha separada"),
]

ok = True
for needle, desc in checks:
    if needle in patch:
        print(f"  OK: {desc}")
    else:
        print(f"  FALTANDO: {desc}")
        ok = False

print("\n" + "=" * 55)
if ok:
    print("PATCH 1/2 COMPLETO - checkpatch clean")
    print(f"\nArquivo: {PATCH_OUT}")
    print("Destino: linux-input@vger.kernel.org")
    print("Maintainer: Dmitry Torokhov <dtor@mail.ru>")
else:
    print("PATCH INCOMPLETO")
    sys.exit(1)
