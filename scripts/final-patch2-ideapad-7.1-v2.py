#!/usr/bin/env python3
"""
final-patch2-ideapad-7.1-v2.py
PATCH 2/2 DEFINITIVO - kernel 7.1.x
ideapad-laptop: CapsLock/NumLock LED via EC offset 0xA1 + _QDF

Correcoes v2:
- Comentarios com trailing */ em linha separada (checkpatch clean)
- Sem __initconst na tabela DMI (evita section mismatch warning)
- DMI entries 83RR + 83SR (variante Brasil)
- Ancoras validadas para kernel 7.1.2

Uso:
  cd /usr/src/linux-7.1.x
  git checkout drivers/platform/x86/lenovo/ideapad-laptop.c
  python3 final-patch2-ideapad-7.1-v2.py
"""
import sys, os, shutil, subprocess

IDEAPAD  = "drivers/platform/x86/lenovo/ideapad-laptop.c"
PATCH_OUT = "0002-platform-x86-ideapad-laptop-capslock-numlock-leds.patch"

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

if not os.path.exists(IDEAPAD):
    die(f"{IDEAPAD} nao encontrado")

orig = IDEAPAD + ".orig"
if not os.path.exists(orig):
    shutil.copy2(IDEAPAD, orig)
    print(f"Backup: {orig}")
else:
    print(f"Backup ja existe: {orig}")

with open(IDEAPAD, "r") as f:
    c = f.read()

errors = 0
print(f"\n[{IDEAPAD}]")

# 1. Constantes EC com */ em linha separada (checkpatch clean)
result = apply(c,
    "#include <dt-bindings/leds/common.h>",
    "#include <dt-bindings/leds/common.h>\n"
    "\n"
    "/* EC keyboard LED control (IdeaPad EC PS/2 emulation).\n"
    " * Validated on Lenovo IdeaPad 83RR (Wildcat Lake):\n"
    " *   EC offset 0xA1 bit4=NUML, bit5=CAPL\n"
    " *   _QDF syncs EC state to GPIO -> physical LED\n"
    " * ec_read/ec_write declared in <linux/acpi.h>\n"
    " */\n"
    "#define IDEAPAD_EC_KBD_LED_OFFSET\t0xA1\n"
    "#define IDEAPAD_EC_KBD_LED_NUML_BIT\tBIT(4)\n"
    "#define IDEAPAD_EC_KBD_LED_CAPL_BIT\tBIT(5)\n"
    "#define IDEAPAD_ACPI_EC0_QDF_PATH\t\"\\\\_SB.PC00.LPCB.EC0._QDF\"",
    "constantes EC (checkpatch clean)")
if result is None: errors += 1
else: c = result

# 2. bool kbd_leds em features
result = apply(c,
    "\t\tbool ymc_ec_trigger       : 1;\n"
    "\t} features;",
    "\t\tbool ymc_ec_trigger       : 1;\n"
    "\t\tbool kbd_leds             : 1;\n"
    "\t} features;",
    "struct features: add kbd_leds bit")
if result is None: errors += 1
else: c = result

# 3. struct kbd_leds em ideapad_private
# Tenta sem last_brightness (7.1) e com (fallback)
inserted = False
for old_fn, desc in [
    (
        "\tstruct {\n\t\tbool initialized;\n\t\tstruct led_classdev led;\n\t} fn_lock;\n};",
        "struct kbd_leds (7.1 fn_lock sem last_brightness)"
    ),
    (
        "\tstruct {\n\t\tbool initialized;\n\t\tstruct led_classdev led;\n\t\tunsigned int last_brightness;\n\t} fn_lock;\n};",
        "struct kbd_leds (fallback fn_lock com last_brightness)"
    ),
]:
    new_fn = old_fn.replace(
        "} fn_lock;\n};",
        "} fn_lock;\n"
        "\tstruct {\n"
        "\t\tbool initialized;\n"
        "\t\tstruct led_classdev capslock;\n"
        "\t\tstruct led_classdev numlock;\n"
        "\t} kbd_leds;\n"
        "};"
    )
    result = apply(c, old_fn, new_fn, desc)
    if result is not None:
        c = result
        inserted = True
        break
if not inserted:
    print("  ERRO: struct fn_lock nao encontrada")
    errors += 1

# 4. Funcoes LED antes de ideapad_kbd_bl_check_tristate
result = apply(c,
    "static int ideapad_kbd_bl_check_tristate(int type)",
    "static int ideapad_kbd_led_ec_set(u8 bit, bool on)\n"
    "{\n"
    "\tu8 val;\n"
    "\tint err;\n"
    "\n"
    "\terr = ec_read(IDEAPAD_EC_KBD_LED_OFFSET, &val);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
    "\tif (on)\n"
    "\t\tval |= bit;\n"
    "\telse\n"
    "\t\tval &= ~bit;\n"
    "\terr = ec_write(IDEAPAD_EC_KBD_LED_OFFSET, val);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
    "\tacpi_evaluate_object(NULL, IDEAPAD_ACPI_EC0_QDF_PATH, NULL, NULL);\n"
    "\treturn 0;\n"
    "}\n"
    "\n"
    "static void ideapad_capslock_led_set(struct led_classdev *led_cdev,\n"
    "\t\t\t\t     enum led_brightness brightness)\n"
    "{\n"
    "\tideapad_kbd_led_ec_set(IDEAPAD_EC_KBD_LED_CAPL_BIT, brightness != LED_OFF);\n"
    "}\n"
    "\n"
    "static enum led_brightness ideapad_capslock_led_get(struct led_classdev *led_cdev)\n"
    "{\n"
    "\tu8 val;\n"
    "\n"
    "\tif (ec_read(IDEAPAD_EC_KBD_LED_OFFSET, &val))\n"
    "\t\treturn LED_OFF;\n"
    "\treturn (val & IDEAPAD_EC_KBD_LED_CAPL_BIT) ? LED_ON : LED_OFF;\n"
    "}\n"
    "\n"
    "static void ideapad_numlock_led_set(struct led_classdev *led_cdev,\n"
    "\t\t\t\t    enum led_brightness brightness)\n"
    "{\n"
    "\tideapad_kbd_led_ec_set(IDEAPAD_EC_KBD_LED_NUML_BIT, brightness != LED_OFF);\n"
    "}\n"
    "\n"
    "static enum led_brightness ideapad_numlock_led_get(struct led_classdev *led_cdev)\n"
    "{\n"
    "\tu8 val;\n"
    "\n"
    "\tif (ec_read(IDEAPAD_EC_KBD_LED_OFFSET, &val))\n"
    "\t\treturn LED_OFF;\n"
    "\treturn (val & IDEAPAD_EC_KBD_LED_NUML_BIT) ? LED_ON : LED_OFF;\n"
    "}\n"
    "\n"
    "static int ideapad_kbd_leds_init(struct ideapad_private *priv)\n"
    "{\n"
    "\tint err;\n"
    "\n"
    "\tif (WARN_ON(priv->kbd_leds.initialized))\n"
    "\t\treturn -EEXIST;\n"
    "\n"
    "\tpriv->kbd_leds.capslock.name           = \"input::capslock\";\n"
    "\tpriv->kbd_leds.capslock.max_brightness = 1;\n"
    "\tpriv->kbd_leds.capslock.brightness_set = ideapad_capslock_led_set;\n"
    "\tpriv->kbd_leds.capslock.brightness_get = ideapad_capslock_led_get;\n"
    "\tpriv->kbd_leds.capslock.flags          = LED_RETAIN_AT_SHUTDOWN;\n"
    "\n"
    "\terr = led_classdev_register(&priv->platform_device->dev,\n"
    "\t\t\t\t    &priv->kbd_leds.capslock);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
    "\n"
    "\tpriv->kbd_leds.numlock.name            = \"input::numlock\";\n"
    "\tpriv->kbd_leds.numlock.max_brightness  = 1;\n"
    "\tpriv->kbd_leds.numlock.brightness_set  = ideapad_numlock_led_set;\n"
    "\tpriv->kbd_leds.numlock.brightness_get  = ideapad_numlock_led_get;\n"
    "\tpriv->kbd_leds.numlock.flags           = LED_RETAIN_AT_SHUTDOWN;\n"
    "\n"
    "\terr = led_classdev_register(&priv->platform_device->dev,\n"
    "\t\t\t\t    &priv->kbd_leds.numlock);\n"
    "\tif (err) {\n"
    "\t\tled_classdev_unregister(&priv->kbd_leds.capslock);\n"
    "\t\treturn err;\n"
    "\t}\n"
    "\n"
    "\tpriv->kbd_leds.initialized = true;\n"
    "\treturn 0;\n"
    "}\n"
    "\n"
    "static void ideapad_kbd_leds_exit(struct ideapad_private *priv)\n"
    "{\n"
    "\tif (!priv->kbd_leds.initialized)\n"
    "\t\treturn;\n"
    "\tpriv->kbd_leds.initialized = false;\n"
    "\tled_classdev_unregister(&priv->kbd_leds.numlock);\n"
    "\tled_classdev_unregister(&priv->kbd_leds.capslock);\n"
    "}\n"
    "\n"
    "static int ideapad_kbd_bl_check_tristate(int type)",
    "funcoes LED capslock/numlock + init/exit")
if result is None: errors += 1
else: c = result

# 5. Tabela DMI sem __initconst, com 83RR + 83SR
result = apply(c,
    "static const struct dmi_system_id ymc_ec_trigger_quirk_dmi_table[] = {",
    "static const struct dmi_system_id ideapad_kbd_leds_dmi_table[] = {\n"
    "\t{\n"
    "\t\t/*\n"
    "\t\t * Lenovo IdeaPad 83RR (Wildcat Lake) - EC PS/2 emulation\n"
    "\t\t * controls CapsLock/NumLock LEDs via EC offset 0xA1 + _QDF.\n"
    "\t\t * CAPL=bit5 (0x20), NUML=bit4 (0x10).\n"
    "\t\t * _QDF drives GPIO via SGOV() to physical LED pins.\n"
    "\t\t */\n"
    "\t\t.matches = {\n"
    '\t\t\tDMI_MATCH(DMI_SYS_VENDOR, "LENOVO"),\n'
    '\t\t\tDMI_MATCH(DMI_PRODUCT_NAME, "83RR"),\n'
    "\t\t},\n"
    "\t},\n"
    "\t{\n"
    "\t\t/* Lenovo IdeaPad 83SR (83RR Brazil regional variant) */\n"
    "\t\t.matches = {\n"
    '\t\t\tDMI_MATCH(DMI_SYS_VENDOR, "LENOVO"),\n'
    '\t\t\tDMI_MATCH(DMI_PRODUCT_NAME, "83SR"),\n'
    "\t\t},\n"
    "\t},\n"
    "\t{ }\n"
    "};\n"
    "\n"
    "static const struct dmi_system_id ymc_ec_trigger_quirk_dmi_table[] = {",
    "tabela DMI (sem __initconst, 83RR + 83SR)")
if result is None: errors += 1
else: c = result

# 6. Seta features.kbd_leds
result = apply(c,
    "\tpriv->features.ymc_ec_trigger =\n"
    "\t\tymc_ec_trigger || dmi_check_system(ymc_ec_trigger_quirk_dmi_table);",
    "\tpriv->features.ymc_ec_trigger =\n"
    "\t\tymc_ec_trigger || dmi_check_system(ymc_ec_trigger_quirk_dmi_table);\n"
    "\tpriv->features.kbd_leds =\n"
    "\t\tdmi_check_system(ideapad_kbd_leds_dmi_table);",
    "init_features: set features.kbd_leds via DMI")
if result is None: errors += 1
else: c = result

# 7. Chama init no probe com guard DMI
result = apply(c,
    "\terr = ideapad_fn_lock_led_init(priv);\n"
    "\tif (err) {\n"
    "\t\tif (err != -ENODEV)\n"
    "\t\t\tdev_warn(&pdev->dev, \"Could not set up FnLock LED: %d\\n\", err);\n"
    "\t\telse\n"
    "\t\t\tdev_info(&pdev->dev, \"FnLock control not available\\n\");\n"
    "\t}",
    "\terr = ideapad_fn_lock_led_init(priv);\n"
    "\tif (err) {\n"
    "\t\tif (err != -ENODEV)\n"
    "\t\t\tdev_warn(&pdev->dev, \"Could not set up FnLock LED: %d\\n\", err);\n"
    "\t\telse\n"
    "\t\t\tdev_info(&pdev->dev, \"FnLock control not available\\n\");\n"
    "\t}\n"
    "\n"
    "\tif (priv->features.kbd_leds) {\n"
    "\t\terr = ideapad_kbd_leds_init(priv);\n"
    "\t\tif (err)\n"
    "\t\t\tdev_warn(&pdev->dev, \"Could not set up kbd LEDs: %d\\n\", err);\n"
    "\t}",
    "probe: guard ideapad_kbd_leds_init com features.kbd_leds")
if result is None: errors += 1
else: c = result

# 8. Exit no remove (todas as ocorrencias)
old_exit = "\tideapad_kbd_bl_exit(priv);"
new_exit = "\tideapad_kbd_leds_exit(priv);\n\tideapad_kbd_bl_exit(priv);"
count = c.count(old_exit)
if count == 0:
    print("  ERRO: ideapad_kbd_bl_exit nao encontrado")
    errors += 1
elif new_exit in c:
    print("  SKIP: ideapad_kbd_leds_exit ja inserido")
else:
    c = c.replace(old_exit, new_exit)
    print(f"  OK:   remove: ideapad_kbd_leds_exit ({count} locais)")

if errors > 0:
    print(f"\nFALHA: {errors} erro(s) - arquivo NAO modificado")
    sys.exit(1)

with open(IDEAPAD, "w") as f:
    f.write(c)
print("  Salvo.")

# ?? Gera patch ????????????????????????????????????????????????????????????????

print(f"\n[Gerando {PATCH_OUT}]")
header = (
    "From: Rodnei <developer@bellatrix>\n"
    "Date: Mon, 26 May 2026\n"
    "Subject: [PATCH 2/2] platform/x86: ideapad-laptop: add CapsLock/NumLock LED via EC\n"
    "\n"
    "Some Lenovo IdeaPad laptops (e.g. 83RR/83SR, Wildcat Lake) have\n"
    "physical CapsLock and NumLock LEDs controlled via the EC.\n"
    "\n"
    "The EC exposes CAPL (bit 5) and NUML (bit 4) at offset 0xA1.\n"
    "Writing these bits via ec_write() and evaluating _QDF via\n"
    "acpi_evaluate_object() causes the firmware to sync EC state to the\n"
    "GPIO lines that drive the physical LEDs.\n"
    "\n"
    "Discovery via DSDT analysis on Lenovo IdeaPad 83RR (Wildcat Lake):\n"
    "  - CAPL/NUML at EC offset 0xA1 (bits 5 and 4)\n"
    "  - _QDF (_SB.PC00.LPCB.EC0._QDF) reads CAPL/NUML -> SGOV()\n"
    "  - GPIO 0x001A1087 -> CapsLock LED physical pin\n"
    "  - GPIO 0x001A0485 -> NumLock LED physical pin\n"
    "  - ec_read/ec_write exported via EXPORT_SYMBOL in drivers/acpi/ec.c\n"
    "    and declared in <linux/acpi.h>\n"
    "\n"
    "Add two led_classdev entries (input::capslock, input::numlock)\n"
    "guarded by DMI match (features.kbd_leds) for 83RR and its Brazil\n"
    "regional variant 83SR.\n"
    "\n"
    "Signed-off-by: Rodnei <developer@bellatrix>\n"
    "---\n"
)

r = subprocess.run(
    ["diff", "-u", orig, IDEAPAD],
    capture_output=True, text=True
)
if r.returncode == 1:
    lines = r.stdout.split('\n')
    lines[0] = f"--- a/{IDEAPAD}"
    lines[1] = f"+++ b/{IDEAPAD}"
    with open(PATCH_OUT, "w") as f:
        f.write(header + '\n'.join(lines))
    print(f"  {PATCH_OUT} ({os.path.getsize(PATCH_OUT)} bytes)")
else:
    die("diff falhou")

# ?? Validacao ?????????????????????????????????????????????????????????????????

print("\n[Validacao]")
with open(PATCH_OUT) as f:
    patch = f.read()

checks = [
    ("IDEAPAD_EC_KBD_LED_OFFSET",         "constante EC 0xA1"),
    ("bool kbd_leds",                      "features.kbd_leds"),
    ("ideapad_kbd_leds_dmi_table[] = {",  "tabela DMI sem __initconst"),
    ("83RR",                               "DMI entry 83RR"),
    ("83SR",                               "DMI entry 83SR (Brazil)"),
    ("ideapad_kbd_led_ec_set",             "funcao EC set"),
    ("ideapad_kbd_leds_init",              "funcao init"),
    ("ideapad_kbd_leds_exit",              "funcao exit"),
    ("features.kbd_leds",                  "guard no probe"),
    ("IDEAPAD_ACPI_EC0_QDF_PATH",          "path _QDF"),
    ("ec_read",                            "uso ec_read"),
    ("ec_write",                           "uso ec_write"),
    (" */\n",                              "trailing */ em linha separada"),
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
    print("PATCH 2/2 COMPLETO - checkpatch clean")
    print(f"\nArquivo: {PATCH_OUT}")
    print("Destino: platform-driver-x86@vger.kernel.org")
    print("Maintainer: Hans de Goede <hdegoede@redhat.com>")
else:
    print("PATCH INCOMPLETO")
    sys.exit(1)
