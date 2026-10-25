package org.iglesiavenyve.registro;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.graphics.Bitmap;
import android.os.SystemClock;
import android.util.Log;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.atomic.AtomicReference;

/**
 * En un emulador de Android real (GitHub): la app abre el panel de la iglesia, la
 * página del registro funciona en su navegador interno y no se puede ir a otro sitio.
 */
@RunWith(AndroidJUnit4.class)
public class KioskOnDeviceTest {
    private static final String TAG = "RegistroVenyVePrueba";

    private static String evaluate(ActivityScenario<MainActivity> scenario, String script) {
        AtomicReference<String> value = new AtomicReference<>();
        scenario.onActivity(activity -> activity.web.evaluateJavascript(script, value::set));
        for (int tries = 0; tries < 50 && value.get() == null; tries++) {
            SystemClock.sleep(100);
        }
        return value.get();
    }

    private static String url(ActivityScenario<MainActivity> scenario) {
        AtomicReference<String> value = new AtomicReference<>();
        scenario.onActivity(activity -> value.set(activity.web.getUrl()));
        return value.get();
    }

    /** Captura de pantalla para el informe (el script del emulador la descarga mientras la prueba espera). */
    private static void saveScreenshot(Context context, String name) {
        try {
            Bitmap picture = InstrumentationRegistry.getInstrumentation().getUiAutomation().takeScreenshot();
            File file = new File(context.getExternalFilesDir(null), name);
            try (FileOutputStream output = new FileOutputStream(file)) {
                picture.compress(Bitmap.CompressFormat.PNG, 100, output);
            }
            Log.i(TAG, "Captura guardada: " + file);
            SystemClock.sleep(8000);
        } catch (Exception error) {
            Log.w(TAG, "No se pudo guardar la captura", error);
        }
    }

    @Test
    public void realServerSaysAnOldCodeNoLongerWorks() {
        // Consulta REAL al panel (por el mismo dominio): un código que no existe responde 401.
        StringBuilder detail = new StringBuilder();
        KioskPolicy.Check result = MainActivity.checkOnline(InstrumentationRegistry.getInstrumentation().getTargetContext(), "PRUEBA23", detail);
        Log.i(TAG, "Código PRUEBA23 en el servidor real: " + result + " (" + detail + ")");
        assertEquals(KioskPolicy.Check.CODE_INVALID, result);
    }

    @Test
    public void opensThePanelAndNeverAnotherSite() {
        // Para probar la lista blanca se abre el registro aunque el código de prueba no exista.
        MainActivity.checkerForTests = (code, detail) -> KioskPolicy.Check.OK;
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        String salt = KioskPolicy.newSalt();
        // Código de prueba (no existe en el servidor: la página muestra «necesita el enlace nuevo»).
        context.getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE).edit().clear().putString(MainActivity.KEY_CODE, "PRUEBA23")
                .putString(MainActivity.KEY_PIN_SALT, salt).putInt(MainActivity.KEY_PIN_ITERATIONS, 1000)
                .putString(MainActivity.KEY_PIN_HASH, KioskPolicy.hashPin("2468", salt, 1000)).commit();
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            // La página del registro se dibuja en el navegador interno (React funciona en este WebView).
            String drawn = "false";
            for (int tries = 0; tries < 60 && !"true".equals(drawn); tries++) {
                SystemClock.sleep(1000);
                drawn = evaluate(scenario, "(function(){return !!document.querySelector('[data-testid=kiosk-page]');})()");
            }
            Log.i(TAG, "Página abierta: " + url(scenario) + " · registro dibujado: " + drawn);
            SystemClock.sleep(2000);
            saveScreenshot(context, "registro-dibujado.png");
            assertEquals("el registro se dibujó", "true", drawn);
            assertTrue(url(scenario).startsWith("https://panel.iglesiavenyve.org/"));

            // Intento de ir a otro sitio desde la página: se bloquea y sigue en el panel.
            evaluate(scenario, "window.location.href='https://example.com/'; 'ok'");
            SystemClock.sleep(5000);
            String after = url(scenario);
            Log.i(TAG, "Después de intentar abrir example.com: " + after);
            assertTrue("sigue en el panel: " + after, after.startsWith("https://panel.iglesiavenyve.org/"));

            evaluate(scenario, "window.open('https://www.google.com/'); 'ok'");
            SystemClock.sleep(4000);
            after = url(scenario);
            Log.i(TAG, "Después de intentar abrir google.com: " + after);
            assertTrue("sigue en el panel: " + after, after.startsWith("https://panel.iglesiavenyve.org/"));
        } finally {
            MainActivity.checkerForTests = null;
        }
    }
}
