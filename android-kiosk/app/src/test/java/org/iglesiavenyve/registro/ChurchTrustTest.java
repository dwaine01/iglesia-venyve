package org.iglesiavenyve.registro;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Assume;
import org.junit.Test;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.URL;
import java.net.UnknownHostException;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.List;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** Raíces incluidas en la app: bastan SOLAS para validar el certificado real del panel (como en Android viejo). */
public class ChurchTrustTest {
    private static List<X509Certificate> roots() throws Exception {
        List<X509Certificate> list = new ArrayList<>();
        CertificateFactory factory = CertificateFactory.getInstance("X.509");
        File folder = new File("src/main/assets/raices");
        File[] files = folder.listFiles();
        assertTrue("faltan las raíces en " + folder.getAbsolutePath(), files != null && files.length >= 2);
        for (File file : files) {
            try (InputStream input = new FileInputStream(file)) {
                X509Certificate root = (X509Certificate) factory.generateCertificate(input);
                System.out.println("RAÍZ INCLUIDA: " + root.getSubjectX500Principal().getName() + " (vence " + root.getNotAfter() + ")");
                list.add(root);
            }
        }
        return list;
    }

    @Test
    public void bundledRootsAloneValidateTheRealPanelCertificate() throws Exception {
        X509TrustManager onlyBundled = ChurchTrust.bundledTrust(roots());
        SSLContext tls = SSLContext.getInstance("TLS");
        tls.init(null, new TrustManager[]{onlyBundled}, null);
        HttpsURLConnection connection;
        try {
            connection = (HttpsURLConnection) new URL("https://" + KioskPolicy.HOST + "/api/kiosk/ping").openConnection();
            connection.setSSLSocketFactory(tls.getSocketFactory());
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(15000);
            int status = connection.getResponseCode();
            X509Certificate leaf = (X509Certificate) connection.getServerCertificates()[0];
            System.out.println("PANEL con SOLO las raíces incluidas: HTTP " + status + " · " + leaf.getSubjectX500Principal().getName() + " · emitido por " + leaf.getIssuerX500Principal().getName());
            assertEquals(200, status);
        } catch (UnknownHostException noNetwork) {
            Assume.assumeNoException("sin internet en este equipo", noNetwork);
        }
    }

    @Test
    public void systemFirstThenBundledAndRejectsIfNeitherValidates() throws Exception {
        final int[] calls = {0, 0};
        X509TrustManager rejects = fake(false, calls, 0);
        X509TrustManager accepts = fake(true, calls, 1);
        X509Certificate[] chain = new X509Certificate[0];
        ChurchTrust.combine(accepts, rejects).checkServerTrusted(chain, "ECDHE_ECDSA");
        assertEquals("si el sistema la acepta, no se consulta lo incluido", 0, calls[0]);
        ChurchTrust.combine(rejects, accepts).checkServerTrusted(chain, "ECDHE_ECDSA");
        assertEquals("si el sistema la rechaza, se valida con lo incluido", 2, calls[1]);
        try {
            ChurchTrust.combine(rejects, rejects).checkServerTrusted(chain, "ECDHE_ECDSA");
            fail("si ninguna valida, se rechaza");
        } catch (CertificateException expected) {
            assertFalse(expected.getMessage().isEmpty());
        }
    }

    private static X509TrustManager fake(final boolean ok, final int[] calls, final int slot) {
        return new X509TrustManager() {
            @Override
            public void checkClientTrusted(X509Certificate[] chain, String authType) {
            }

            @Override
            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                calls[slot]++;
                if (!ok) {
                    throw new CertificateException("no confiable");
                }
            }

            @Override
            public X509Certificate[] getAcceptedIssuers() {
                return new X509Certificate[0];
            }
        };
    }
}
