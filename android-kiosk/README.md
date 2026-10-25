# Registro Ven y Ve: app de las tabletas Amazon Fire

Es una app mínima: abre **solo** `https://panel.iglesiavenyve.org/r/<código>`. Funciona así:

- Pantalla completa, siempre encendida y con giro libre.
- No tiene barra de direcciones, el botón «Atrás» no hace nada y no abre otros sitios.
- Si no hay internet muestra «Sin conexión» con el botón «Reintentar», y recarga sola cuando vuelve.
- No usa librerías de terceros.

GitHub la compila: flujo «Tabletas · APK», en `.github/workflows/tabletas-apk.yml`. Este repositorio **nunca** guarda llaves, contraseñas ni archivos `.apk`.

## Descargas (Releases de GitHub)

- **App final:** https://github.com/dwaine01/iglesia-venyve/releases/download/tabletas/registro-venyve.apk
  - Solo existe después de crear la llave (ver más abajo).
- **App de prueba:** https://github.com/dwaine01/iglesia-venyve/releases/download/tabletas-prueba/registro-venyve-prueba.apk
  - Se instala como «Registro Ven y Ve (prueba)» y usa la llave de depuración.
  - **No** se actualiza a la final: cuando instale la final, desinstale la de prueba.

En el panel, ambos enlaces están en Visitantes › Enlaces, en el botón «Descargar app de tabletas».

## Crear la llave de firma (una sola vez, todo en GitHub)

1. **Crear un token temporal.**
   - En GitHub, abra su foto › **Settings** › **Developer settings** › **Personal access tokens** › **Fine-grained tokens** › **Generate new token**.
   - Nombre: `llave tabletas`. Vencimiento: 7 días.
   - **Repository access:** *Only select repositories* › `iglesia-venyve`.
   - **Permissions** › **Repository permissions** › **Secrets**: *Read and write*.
   - Pulse **Generate token** y copie el token. No lo envíe a nadie.
2. **Guardar el token como secreto.**
   - En el repositorio: **Settings** › **Secrets and variables** › **Actions** › **New repository secret**.
   - Name: `KIOSK_SECRETS_TOKEN`. Secret: pegue el token. Pulse **Add secret**.
3. **Crear la llave.**
   - Vaya a **Actions** › **Tabletas · Crear llave de firma (una sola vez)** › **Run workflow**.
   - Escriba `CREAR` y pulse **Run workflow**. En 1 o 2 minutos debe quedar en verde.
4. **Revisar.** En **Settings** › **Secrets and variables** › **Actions** deben aparecer `KIOSK_KEYSTORE_B64` y `KIOSK_KEYSTORE_PASSWORD`.
   - Nadie puede ver su contenido, ni usted ni yo; GitHub solo lo usa para firmar.
5. **Borrar el token.**
   - Borre el secreto `KIOSK_SECRETS_TOKEN`.
   - Borre también el token en **Settings** › **Developer settings** › **Fine-grained tokens** › `llave tabletas` › **Delete**.
6. **Compilar la app final.**
   - Vaya a **Actions** › **Tabletas · APK** › **Run workflow**, con la rama `main`.
   - Al terminar, la app final queda en el enlace de arriba.

Si algún día se perdiera la llave, borrar los secretos de GitHub, por ejemplo, no se pierden datos. Solo habría que crear otra llave, desinstalar la app en las tabletas e instalar la nueva.

## Instalar en una tableta Amazon Fire

1. **Permitir la instalación.** En la tableta: **Configuración** › **Seguridad y privacidad** › **Aplicaciones de origen desconocido**.
   - Permita **Silk** (o **Archivos**, si va a pasar el archivo por cable).
2. **Descargar.** Abra en Silk el enlace de la app (final o de prueba) y descárguela.
   - Si la tableta no abre el sitio, conéctela por cable USB a una computadora y copie el `.apk` a la carpeta **Download**.
   - Luego ábralo con la app **Archivos**.
3. **Instalar.** Toque el archivo descargado › **Instalar** › **Abrir**.
4. **Escribir el código de la tableta.** Son las letras y números después de `/r/` en Visitantes › Enlaces.
5. **Crear el PIN de administrador** (4 a 8 números) y anotarlo. En la tableta solo se guarda su huella cifrada.
6. **Fijar la pantalla.**
   - Salida de administrador: mantenga presionada **la esquina superior izquierda 5 segundos** y escriba el PIN.
   - Toque **«Fijar pantalla al abrir: NO»** para encenderlo y acepte el aviso de Fire OS.
   - Para quitar la fijación, use el mismo menú. En la tableta también se puede con «Atrás» + «Recientes».

Para **actualizar**, instale el APK final nuevo encima del anterior. Se conservan el código y el PIN.

**Si la app dice «Este código ya no funciona»:** se generó un enlace nuevo en Visitantes › Enlaces. Toque «Cambiar código», escriba el PIN y luego el código nuevo (las letras después de `/r/`).
- También se puede cambiar desde el menú de administrador: esquina superior izquierda 5 segundos › PIN › «Cambiar el código de la tableta».

**«Sin conexión»** sale solo cuando la tableta no llega al sitio. Abajo, en letra pequeña, aparece el detalle técnico. Envíe una foto si no se resuelve.

## Para desarrolladores

- Compilar: `gradle -p android-kiosk testDebugUnitTest assembleDebug` (Gradle 8.11 y JDK 17).
- Pruebas:
  - `KioskPolicyTest` revisa la lista blanca, el código y el PIN.
  - `MainActivityTest` (Robolectric) revisa la carga, «Sin conexión», el botón atrás y la pantalla encendida.
  - `KioskOnDeviceTest` corre en el emulador de Android 11: abre el panel y prueba que no se puede salir a otro sitio.
