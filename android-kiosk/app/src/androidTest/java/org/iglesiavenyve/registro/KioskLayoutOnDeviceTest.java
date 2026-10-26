package org.iglesiavenyve.registro;

import static org.junit.Assert.assertTrue;

import android.app.UiAutomation;
import android.content.Context;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.util.Log;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Assume;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.FileInputStream;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Tamaño y comodidad del registro en el navegador interno REAL de Android, en pantallas de
 * tableta de 10" (800 × 1280 y 1200 × 1920, vertical y horizontal), con el teclado abierto.
 * Usa la página local de prueba (http://localhost:4310, datos de PRUEBA, nada se guarda).
 * Solo corre con «-e maqueta 1» (flujo «Tabletas · Tamaño del registro»).
 */
@RunWith(AndroidJUnit4.class)
public class KioskLayoutOnDeviceTest {
    private static final String TAG = "RegistroVenyVeMaqueta";
    private static final String PAGE = "http://localhost:4310/r/PRUEBA";
    private static final String SHOTS = "/data/local/tmp/maqueta";
    private static final String MEASURE = "(function(){var m=document.querySelector('[data-testid=kiosk-main]');"
            + "var f=document.querySelector('[data-testid=kiosk-next],[data-testid=kiosk-submit],[data-testid=kiosk-done]');"
            + "var small=0,els=document.querySelectorAll('[data-testid=kiosk-page] *');"
            + "for(var i=0;i<els.length;i++){var e=els[i];if(!e.offsetParent)continue;var t=false;for(var j=0;j<e.childNodes.length;j++){if(e.childNodes[j].nodeType===3&&e.childNodes[j].textContent.trim())t=true;}"
            + "if(t&&parseFloat(getComputedStyle(e).fontSize)<20)small++;}"
            + "return innerWidth+'x'+innerHeight+' desborde='+(m?m.scrollHeight-m.clientHeight:0)+'px pie='+(f?Math.round(f.getBoundingClientRect().bottom):'-')+' textos<20px='+small;})()";

    private UiAutomation ui;
    private ActivityScenario<MainActivity> scenario;
    private String prefix;
    private int count;

    private String shell(String command) {
        StringBuilder out = new StringBuilder();
        try (ParcelFileDescriptor descriptor = ui.executeShellCommand(command);
             FileInputStream input = new ParcelFileDescriptor.AutoCloseInputStream(descriptor)) {
            byte[] buffer = new byte[4096];
            for (int read = input.read(buffer); read > 0; read = input.read(buffer)) {
                out.append(new String(buffer, 0, read));
            }
        } catch (Exception error) {
            Log.w(TAG, "Comando: " + command, error);
        }
        return out.toString().trim();
    }

    private String js(String script) {
        AtomicReference<String> value = new AtomicReference<>();
        scenario.onActivity(activity -> {
            WebView web = (WebView) activity.root.getChildAt(0);
            web.evaluateJavascript(script, value::set);
        });
        for (int tries = 0; tries < 50 && value.get() == null; tries++) {
            SystemClock.sleep(100);
        }
        return value.get();
    }

    private void waitFor(String testId) {
        String found = "false";
        for (int tries = 0; tries < 40 && !"true".equals(found); tries++) {
            SystemClock.sleep(500);
            found = js("!!document.querySelector('[data-testid=" + testId + "]')");
        }
        assertTrue(prefix + ": no apareció " + testId, "true".equals(found));
        SystemClock.sleep(600);
    }

    private void click(String selector) {
        js("(function(){var e=document.querySelector(\"" + selector + "\");if(e){e.click();return 'ok';}return 'falta';})()");
        SystemClock.sleep(500);
    }

    private void fill(String testId, String text) {
        js("(function(){var e=document.querySelector('[data-testid=" + testId + "]');var set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
                + "set.call(e,'" + text + "');e.dispatchEvent(new Event('input',{bubbles:true}));return 'ok';})()");
        SystemClock.sleep(200);
    }

    private void shot(String name) {
        SystemClock.sleep(700);
        String measured = js(MEASURE);
        Log.i(TAG, prefix + " " + name + ": " + measured);
        // Captura del sistema en /data/local/tmp (se puede descargar en Android 7 y 11, y queda al desinstalar).
        shell("screencap -p " + String.format("%s/%s-%02d-%s.png", SHOTS, prefix, ++count, name));
    }

    /** Toque real (abre el teclado de la pantalla) en el centro de un campo. */
    private void tapField(String testId) {
        String where = js("(function(){var r=document.querySelector('[data-testid=" + testId + "]').getBoundingClientRect();return Math.round((r.left+r.width/2)*devicePixelRatio)+' '+Math.round((r.top+r.height/2)*devicePixelRatio);})()");
        String[] xy = where.replace("\"", "").split(" ");
        int[] offset = new int[2];
        scenario.onActivity(activity -> activity.root.getLocationOnScreen(offset));
        shell("input tap " + (Integer.parseInt(xy[0]) + offset[0]) + " " + (Integer.parseInt(xy[1]) + offset[1]));
        SystemClock.sleep(2500);
    }

    private void open() {
        scenario.onActivity(activity -> {
            activity.root.removeAllViews();
            WebView web = new WebView(activity);
            WebSettings settings = web.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setTextZoom(100);
            web.setWebViewClient(new WebViewClient());
            activity.root.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
            Log.i(TAG, "Navegador interno: " + settings.getUserAgentString());
            web.loadUrl(PAGE);
        });
    }

    private void walk() {
        count = 0;
        open();
        waitFor("kiosk-language");
        shot("idioma");
        click("[data-testid=kiosk-lang-es]");
        waitFor("kiosk-start");
        shot("bienvenida");
        click("[data-testid=kiosk-begin]");
        waitFor("kiosk-step-nombre");
        fill("kiosk-first-name", "María");
        fill("kiosk-last-name", "Prueba");
        click("[data-testid=kiosk-sex] button");
        shot("nombre");
        tapField("kiosk-preferred");
        shot("nombre-con-teclado");
        js("document.activeElement&&document.activeElement.blur(),'ok'");
        shell("input keyevent 111");
        SystemClock.sleep(1500);
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-contacto");
        fill("kiosk-phone", "5551234567");
        shot("contacto");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-vives");
        shot("vives");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-visita");
        shot("visita");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-fe");
        shot("fe");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-familia");
        click("[data-testid=kiosk-has-children] button");
        shot("familia");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-servir");
        click("[data-testid=kiosk-requests-prayer_me]");
        shot("servir");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-ayuda");
        click("[data-testid=kiosk-requests-counseling_personal]");
        shot("consejeria");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-notas");
        shot("notas");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-apoyo");
        shot("apoyo");
        click("[data-testid=kiosk-next]");
        waitFor("kiosk-step-cierre");
        click("[data-testid=kiosk-consent-followup] button");
        shot("cierre");
        click("[data-testid=kiosk-submit]");
        waitFor("kiosk-confirmation");
        shot("gracias");
    }

    @Test
    public void everyStepFitsOnA10InchTablet() {
        // El script fija el tamaño y el giro de la pantalla (adb) y pasa su nombre: «-e pantalla 800x1280-vertical».
        String screen = InstrumentationRegistry.getArguments().getString("pantalla");
        Assume.assumeTrue("solo con -e maqueta 1", "1".equals(InstrumentationRegistry.getArguments().getString("maqueta")) && screen != null);
        ui = InstrumentationRegistry.getInstrumentation().getUiAutomation();
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        // Sin código guardado: la app queda en su pantalla de preparación y no toca la página de prueba.
        context.getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE).edit().clear().commit();
        shell("mkdir -p " + SHOTS);
        prefix = screen;
        try (ActivityScenario<MainActivity> launched = ActivityScenario.launch(MainActivity.class)) {
            scenario = launched;
            SystemClock.sleep(2000);
            shell("am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS");
            walk();
        }
    }
}
