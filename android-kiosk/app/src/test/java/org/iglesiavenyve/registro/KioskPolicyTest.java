package org.iglesiavenyve.registro;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Lista blanca de dominio, código de la tableta y PIN (sin Android). */
public class KioskPolicyTest {
    private static void expect(KioskPolicy.Decision expected, String url) {
        KioskPolicy.Decision actual = KioskPolicy.decide(url);
        System.out.println("LISTA BLANCA: " + url + " -> " + (actual == KioskPolicy.Decision.LOAD ? "PERMITIDO" : actual == KioskPolicy.Decision.RETRY ? "REINTENTAR" : "BLOQUEADO"));
        assertEquals(url, expected, actual);
    }

    @Test
    public void onlyThePanelIsAllowed() {
        expect(KioskPolicy.Decision.LOAD, "https://panel.iglesiavenyve.org/r/ABCD2345?app=apk");
        expect(KioskPolicy.Decision.LOAD, "https://PANEL.iglesiavenyve.org/r/ABCD2345");
        expect(KioskPolicy.Decision.LOAD, "https://panel.iglesiavenyve.org:443/r/ABCD2345");
        expect(KioskPolicy.Decision.LOAD, KioskPolicy.OFFLINE_PAGE);
        expect(KioskPolicy.Decision.RETRY, KioskPolicy.RETRY_URL);
        // Cualquier otro sitio, otro esquema o un truco con el nombre: bloqueado.
        expect(KioskPolicy.Decision.BLOCK, "http://panel.iglesiavenyve.org/r/ABCD2345");
        expect(KioskPolicy.Decision.BLOCK, "https://www.google.com/");
        expect(KioskPolicy.Decision.BLOCK, "https://iglesiavenyve.org/");
        expect(KioskPolicy.Decision.BLOCK, "https://panel.iglesiavenyve.org.otro-sitio.com/");
        expect(KioskPolicy.Decision.BLOCK, "https://otro-sitio.com/panel.iglesiavenyve.org");
        expect(KioskPolicy.Decision.BLOCK, "https://panel.iglesiavenyve.org@otro-sitio.com/");
        expect(KioskPolicy.Decision.BLOCK, "https://usuario@panel.iglesiavenyve.org/");
        expect(KioskPolicy.Decision.BLOCK, "https://panel.iglesiavenyve.org:8443/");
        expect(KioskPolicy.Decision.BLOCK, "https://iglesia-venyve-production.up.railway.app/api/visitors/links");
        expect(KioskPolicy.Decision.BLOCK, "file:///sdcard/Download/algo.html");
        expect(KioskPolicy.Decision.BLOCK, "file:///android_asset/otra.html");
        expect(KioskPolicy.Decision.BLOCK, "javascript:alert(1)");
        expect(KioskPolicy.Decision.BLOCK, "intent://scan/#Intent;scheme=zxing;end");
        expect(KioskPolicy.Decision.BLOCK, "market://details?id=algo");
        expect(KioskPolicy.Decision.BLOCK, "data:text/html,hola");
        expect(KioskPolicy.Decision.BLOCK, "about:blank");
        expect(KioskPolicy.Decision.BLOCK, "https://panel.iglesiavenyve.org\\@otro-sitio.com/");
        expect(KioskPolicy.Decision.BLOCK, null);
    }

    @Test
    public void tabletCode() {
        assertEquals("ABCD2345", KioskPolicy.normalizeCode(" abcd-2345 "));
        assertTrue(KioskPolicy.validCode("ABCD2345"));
        assertFalse("sin 0, O, 1, I ni L", KioskPolicy.validCode("ABCD0O1I"));
        assertFalse(KioskPolicy.validCode("ABC"));
        assertFalse(KioskPolicy.validCode(null));
        assertEquals("https://panel.iglesiavenyve.org/r/ABCD2345?app=apk", KioskPolicy.tabletUrl("ABCD2345"));
    }

    @Test
    public void pinIsStoredOnlyAsAHash() {
        assertTrue(KioskPolicy.validPin("2468"));
        assertFalse(KioskPolicy.validPin("12"));
        assertFalse(KioskPolicy.validPin("12ab"));
        String salt = KioskPolicy.newSalt();
        String hash = KioskPolicy.hashPin("2468", salt, 1000);
        assertFalse(hash.contains("2468"));
        assertEquals(64, hash.length());
        assertTrue(KioskPolicy.verifyPin("2468", salt, 1000, hash));
        assertFalse(KioskPolicy.verifyPin("2469", salt, 1000, hash));
        assertNotEquals("cada tableta usa su propia sal", hash, KioskPolicy.hashPin("2468", KioskPolicy.newSalt(), 1000));
    }
}
