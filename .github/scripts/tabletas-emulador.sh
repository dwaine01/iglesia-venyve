#!/usr/bin/env bash
# Prueba en el emulador (APK de prueba): mientras corre, se guarda la captura del registro dibujado.
set -u
OUT=capturas; mkdir -p "$OUT"
DIR=/sdcard/Android/data/org.iglesiavenyve.registro.prueba/files
(gradle -p android-kiosk --no-daemon connectedDebugAndroidTest > gradle-emulador.log 2>&1; echo $? > gradle-emulador.exit) &
for i in $(seq 1 240); do
  if adb shell ls "$DIR/registro-dibujado.png" >/dev/null 2>&1; then adb pull "$DIR/registro-dibujado.png" "$OUT/registro-dibujado-api$(adb shell getprop ro.build.version.sdk | tr -d '\r').png"; break; fi
  sleep 2
done
wait
tail -60 gradle-emulador.log
adb logcat -d -s RegistroVenyVe:I RegistroVenyVePrueba:I chromium:I | tail -60
exit "$(cat gradle-emulador.exit)"
