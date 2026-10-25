#!/usr/bin/env bash
# Instala la APK FINAL (release, firmada) en el emulador, la prepara como lo haría una persona
# (código + PIN con toques y teclado) y toma capturas. El código de prueba no existe: debe salir
# «Este código ya no funciona». Eso prueba que la APK final arranca y que la conexión segura con
# el panel funciona en Android viejo (si el certificado fallara, saldría «Sin conexión»).
set -u
OUT=capturas; mkdir -p "$OUT"
PKG=org.iglesiavenyve.registro
shot() { adb exec-out screencap -p > "$OUT/$1.png"; echo "captura: $1"; }
tap_field() {  # $1 = número de campo de texto (1, 2, 3…)
  adb shell uiautomator dump /sdcard/pantalla.xml >/dev/null 2>&1; adb pull /sdcard/pantalla.xml pantalla.xml >/dev/null 2>&1
  python3 - "$1" <<'PY'
import re, sys, subprocess
xml = open('pantalla.xml', encoding='utf-8').read()
fields = re.findall(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
x1, y1, x2, y2 = map(int, fields[int(sys.argv[1]) - 1])
subprocess.run(['adb', 'shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2)])
PY
}
tap_text() {
  adb shell uiautomator dump /sdcard/pantalla.xml >/dev/null 2>&1; adb pull /sdcard/pantalla.xml pantalla.xml >/dev/null 2>&1
  python3 - "$1" <<'PY'
import re, sys, subprocess
xml = open('pantalla.xml', encoding='utf-8').read()
node = re.search(r'text="' + re.escape(sys.argv[1]) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
x1, y1, x2, y2 = map(int, node.groups())
subprocess.run(['adb', 'shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2)])
PY
}
adb install -r apk/registro-venyve.apk
adb shell dumpsys package "$PKG" | grep -E "versionName|versionCode" | head -2
adb logcat -c
adb shell am start -n "$PKG/.MainActivity"; sleep 8
shot 1-primera-vez
tap_field 1; adb shell input text PRUEBA23; adb shell input keyevent 111; sleep 1
tap_field 2; adb shell input text 2468; adb shell input keyevent 111; sleep 1
tap_field 3; adb shell input text 2468; adb shell input keyevent 111; sleep 1
shot 2-codigo-y-pin
tap_text "Guardar y abrir el registro"; sleep 20
shot 3-resultado
adb logcat -d -s RegistroVenyVe:I | tail -40
adb shell uiautomator dump /sdcard/pantalla.xml >/dev/null 2>&1; adb pull /sdcard/pantalla.xml pantalla.xml >/dev/null 2>&1
if grep -q "Este código ya no funciona" pantalla.xml; then echo "OK: la APK final muestra «Este código ya no funciona»"; else echo "FALLA: no salió «Este código ya no funciona»"; grep -o 'text="[^"]*"' pantalla.xml | head -20; exit 1; fi
