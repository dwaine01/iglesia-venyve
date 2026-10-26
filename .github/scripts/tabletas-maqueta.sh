#!/usr/bin/env bash
# Tamaño del registro en el navegador interno REAL (emulador): página local de PRUEBA + capturas
# de cada paso en 800×1280 y 1200×1920, vertical y horizontal, con el teclado abierto.
set -u
OUT=capturas; mkdir -p "$OUT"
API=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
node .github/scripts/kiosk-mock.js "$PWD/frontend/build" 4310 > mock.log 2>&1 &
sleep 2
adb reverse tcp:4310 tcp:4310
adb shell rm -rf /data/local/tmp/maqueta
adb shell settings put system accelerometer_rotation 0
STATUS=0
# Tabletas de 10": 800×1280 (mdpi) y 1200×1920 (mdpi), en vertical (0) y horizontal (1).
for SIZE in 800x1280 1200x1920; do
  for ROT in 0 1; do
    NAME="$SIZE-$([ $ROT = 0 ] && echo vertical || echo horizontal)"
    adb shell wm size "$SIZE"; adb shell wm density 160; adb shell settings put system user_rotation "$ROT"; sleep 4
    echo "== $NAME: $(adb shell wm size | tr -d '\r' | tail -1) · densidad $(adb shell wm density | tr -d '\r' | tail -1)"
    gradle -p android-kiosk --no-daemon connectedDebugAndroidTest \
      -Pandroid.testInstrumentationRunnerArguments.maqueta=1 -Pandroid.testInstrumentationRunnerArguments.pantalla="$NAME" \
      -Pandroid.testInstrumentationRunnerArguments.class=org.iglesiavenyve.registro.KioskLayoutOnDeviceTest >> gradle-maqueta.log 2>&1 || STATUS=1
  done
done
adb shell wm size reset; adb shell wm density reset; adb shell settings put system user_rotation 0
adb pull /data/local/tmp/maqueta crudas >/dev/null 2>&1
for f in $(find crudas -name '*.png' -size +1k 2>/dev/null); do cp "$f" "$OUT/maqueta-api$API-$(basename "$f")"; done
grep -E "tests completed|FAILED|Exception|Error|BUILD" gradle-maqueta.log | head -40
# Medidas de cada pantalla (desborde = cuánto habría que desplazar; pie = dónde termina el botón).
adb logcat -d -s RegistroVenyVeMaqueta:I | grep -v "	at " | tail -80
adb logcat -d -s chromium:I | grep -iE "error|uncaught" | tail -20
echo "capturas: $(ls "$OUT" | wc -l)"
exit $STATUS
