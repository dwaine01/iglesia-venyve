package org.iglesiavenyve.registro;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.robolectric.Shadows.shadowOf;

import android.content.Context;
import android.content.SharedPreferences;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowLog;

/** La app en un Android simulado (Robolectric): qué abre, qué bloquea y cómo se comporta. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class MainActivityTest {
    private SharedPreferences prefs;

    @Before
    public void setUp() {
        ShadowLog.stream = System.out;  // los registros «Permitido / BLOQUEADO» quedan en el log de GitHub
        prefs = RuntimeEnvironment.getApplication().getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE);
        prefs.edit().clear().commit();
        MainActivity.checkerForTests = (code, detail) -> KioskPolicy.Check.OK;  // el servidor acepta el código
    }

    @After
    public void tearDown() {
        MainActivity.checkerForTests = null;
    }

    private static boolean hasText(View view, String value) {
        if (view instanceof android.widget.TextView && ((android.widget.TextView) view).getText().toString().contains(value)) {
            return true;
        }
        if (view instanceof ViewGroup) {
            for (int index = 0; index < ((ViewGroup) view).getChildCount(); index++) {
                if (hasText(((ViewGroup) view).getChildAt(index), value)) {
                    return true;
                }
            }
        }
        return false;
    }

    private MainActivity configured() {
        String salt = KioskPolicy.newSalt();
        prefs.edit().putString(MainActivity.KEY_CODE, "ABCD2345").putString(MainActivity.KEY_PIN_SALT, salt)
                .putInt(MainActivity.KEY_PIN_ITERATIONS, 1000).putString(MainActivity.KEY_PIN_HASH, KioskPolicy.hashPin("2468", salt, 1000)).commit();
        return Robolectric.buildActivity(MainActivity.class).setup().get();
    }

    private static int count(View view, Class<?> type) {
        int found = type.isInstance(view) ? 1 : 0;
        if (view instanceof ViewGroup) {
            for (int index = 0; index < ((ViewGroup) view).getChildCount(); index++) {
                found += count(((ViewGroup) view).getChildAt(index), type);
            }
        }
        return found;
    }

    @Test
    public void firstOpenAsksForTheCodeAndPin() {
        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();
        assertNull("sin código no se abre ninguna página", activity.web);
        assertEquals("código + PIN + repetir PIN", 3, count(activity.root, EditText.class));
    }

    @Test
    public void opensOnlyThePanelAndBlocksEverythingElse() {
        MainActivity activity = configured();
        assertNotNull(activity.web);
        String start = "https://panel.iglesiavenyve.org/r/ABCD2345?app=apk";
        assertEquals(start, shadowOf(activity.web).getLastLoadedUrl());
        System.out.println("ABRE: " + shadowOf(activity.web).getLastLoadedUrl());

        assertTrue("otro sitio: bloqueado", activity.client.shouldOverrideUrlLoading(activity.web, "https://www.google.com/"));
        assertTrue("truco con el nombre: bloqueado", activity.client.shouldOverrideUrlLoading(activity.web, "https://panel.iglesiavenyve.org.otro-sitio.com/"));
        assertTrue("http sin cifrar: bloqueado", activity.client.shouldOverrideUrlLoading(activity.web, "http://panel.iglesiavenyve.org/"));
        assertEquals("la página no cambió", start, shadowOf(activity.web).getLastLoadedUrl());
        assertFalse("el mismo panel: permitido", activity.client.shouldOverrideUrlLoading(activity.web, "https://panel.iglesiavenyve.org/r/ABCD2345"));
    }

    @Test
    public void offlinePageAndRetry() {
        MainActivity activity = configured();
        activity.client.onReceivedError(activity.web, -2, "net::ERR_INTERNET_DISCONNECTED", "https://panel.iglesiavenyve.org/r/ABCD2345?app=apk");
        assertTrue(activity.offline);
        assertTrue("«Sin conexión» con el detalle", shadowOf(activity.web).getLastLoadedUrl().startsWith(KioskPolicy.OFFLINE_PAGE + "#"));
        // «Reintentar» vuelve a abrir el registro.
        assertTrue(activity.client.shouldOverrideUrlLoading(activity.web, KioskPolicy.RETRY_URL));
        assertFalse(activity.offline);
        assertEquals("https://panel.iglesiavenyve.org/r/ABCD2345?app=apk", shadowOf(activity.web).getLastLoadedUrl());
    }

    @Test
    public void oldCodeShowsChangeCodeInsteadOfOffline() {
        MainActivity.checkerForTests = (code, detail) -> { detail.append("HTTP 401"); return KioskPolicy.Check.CODE_INVALID; };
        MainActivity activity = configured();
        assertEquals("code_invalid", activity.screen);
        assertFalse(activity.offline);
        assertTrue(hasText(activity.root, "Este código ya no funciona") && hasText(activity.root, "This code no longer works"));
        assertTrue(hasText(activity.root, "Cambiar código"));
        assertNull("no se abre el registro con un código viejo", shadowOf(activity.web).getLastLoadedUrl());
        System.out.println("CÓDIGO VIEJO → pantalla «Este código ya no funciona» con «Cambiar código»");
    }

    @Test
    public void noNetworkShowsOfflineWithDetail() {
        MainActivity.checkerForTests = (code, detail) -> { detail.append("no se encuentra panel.iglesiavenyve.org"); return KioskPolicy.Check.OFFLINE; };
        MainActivity activity = configured();
        assertEquals("offline", activity.screen);
        assertTrue(activity.offline);
        assertTrue(shadowOf(activity.web).getLastLoadedUrl().startsWith(KioskPolicy.OFFLINE_PAGE + "#"));
        // Vuelve la red y el código sirve: abre el registro.
        MainActivity.checkerForTests = (code, detail) -> KioskPolicy.Check.OK;
        activity.loadTablet();
        assertEquals("web", activity.screen);
        assertEquals("https://panel.iglesiavenyve.org/r/ABCD2345?app=apk", shadowOf(activity.web).getLastLoadedUrl());
    }

    @Test
    public void backDoesNotLeaveAndScreenStaysOn() {
        MainActivity activity = configured();
        activity.onBackPressed();
        assertFalse(activity.isFinishing());
        assertTrue((activity.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) != 0);
    }

    @Test
    public void pinIsNotStoredInClear() {
        MainActivity activity = configured();
        activity.savePin("975310");
        assertFalse(prefs.getAll().toString().contains("975310"));
        assertTrue(KioskPolicy.verifyPin("975310", prefs.getString(MainActivity.KEY_PIN_SALT, null), prefs.getInt(MainActivity.KEY_PIN_ITERATIONS, 0), prefs.getString(MainActivity.KEY_PIN_HASH, null)));
        assertNotNull(activity);
    }
}
