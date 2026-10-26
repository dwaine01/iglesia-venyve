#!/usr/bin/env bash
# Tamaño del registro en el navegador interno REAL (emulador): página local de PRUEBA + capturas
# de cada paso en 800×1280 y 1200×1920, vertical y horizontal, con el teclado abierto.
set -u
OUT=capturas; mkdir -p "$OUT"
API=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
DIR=/sdcard/Android/data/org.iglesiavenyve.registro.prueba/files
node .github/scripts/kiosk-mock.js "$PWD/frontend/build" 4310 > mock.log 2>&1 &
sleep 2
adb reverse tcp:4310 tcp:4310
(gradle -p android-kiosk --no-daemon connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.maqueta=1 \
  -Pandroid.testInstrumentationRunnerArguments.class=org.iglesiavenyve.registro.KioskLayoutOnDeviceTest > gradle-maqueta.log 2>&1; echo $? > gradle-maqueta.exit) &
pull_new() {
  for f in $(adb shell ls "$DIR" 2>/dev/null | tr -d '\r' | grep '\.png$'); do
    [ -f "$OUT/maqueta-api$API-$f" ] || adb pull "$DIR/$f" "$OUT/maqueta-api$API-$f" >/dev/null 2>&1
  done
}
while [ ! -f gradle-maqueta.exit ]; do pull_new; sleep 3; done
pull_new
tail -40 gradle-maqueta.log
adb logcat -d -s RegistroVenyVeMaqueta:I chromium:I | grep -v "INFO:library_loader" | tail -80
echo "capturas: $(ls "$OUT" | wc -l)"
exit "$(cat gradle-maqueta.exit)"
