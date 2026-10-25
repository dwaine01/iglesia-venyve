package org.iglesiavenyve.registro;

import android.content.Context;
import android.net.http.SslCertificate;
import android.os.Build;
import android.os.Bundle;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509TrustManager;

/**
 * Tabletas con Android viejo (Fire OS 5 = Android 5.1) no traen la raíz «ISRG Root X1» de
 * Let's Encrypt (llegó en Android 7.1.1) y rechazan el certificado del panel
 * (SSLHandshakeException). Silk funciona porque trae su propia lista.
 *
 * Aquí se confía en las raíces del SISTEMA y, además, en las raíces públicas oficiales que
 * vienen dentro de la app (assets/raices: ISRG Root X1/X2 y Google Trust Services). La
 * verificación es completa (cadena hasta la raíz, fechas y nombre del sitio); nunca se acepta
 * un certificado sin verificar. Para el navegador interno solo se aplica a panel.iglesiavenyve.org.
 */
final class ChurchTrust {
    private static final Set<String> TRUSTED_LEAVES = Collections.synchronizedSet(new HashSet<>());
    private static X509TrustManager trustManager;
    private static SSLSocketFactory socketFactory;

    private ChurchTrust() {
    }

    /** Lee los certificados raíz incluidos (archivos .pem de assets/raices). */
    static List<X509Certificate> bundledRoots(Context context) throws Exception {
        List<X509Certificate> roots = new ArrayList<>();
        CertificateFactory factory = CertificateFactory.getInstance("X.509");
        String[] names = context.getAssets().list("raices");
        for (String name : names == null ? new String[0] : names) {
            try (InputStream input = context.getAssets().open("raices/" + name)) {
                roots.add((X509Certificate) factory.generateCertificate(input));
            }
        }
        return roots;
    }

    /** Las del sistema y, si el sistema no la reconoce, las raíces incluidas (validación PKIX completa). */
    static synchronized X509TrustManager trustManager(Context context) throws Exception {
        if (trustManager == null) {
            trustManager = combine(systemTrust(), bundledTrust(bundledRoots(context)));
        }
        return trustManager;
    }

    static synchronized SSLSocketFactory socketFactory(Context context) throws Exception {
        if (socketFactory == null) {
            SSLContext tls = SSLContext.getInstance("TLS");
            tls.init(null, new TrustManager[]{trustManager(context)}, null);
            socketFactory = tls.getSocketFactory();
        }
        return socketFactory;
    }

    static X509TrustManager systemTrust() throws Exception {
        TrustManagerFactory factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        factory.init((KeyStore) null);
        return firstX509(factory.getTrustManagers());
    }

    static X509TrustManager bundledTrust(List<X509Certificate> roots) throws Exception {
        KeyStore store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null, null);
        for (int index = 0; index < roots.size(); index++) {
            store.setCertificateEntry("raiz-" + index, roots.get(index));
        }
        TrustManagerFactory factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        factory.init(store);
        return firstX509(factory.getTrustManagers());
    }

    private static X509TrustManager firstX509(TrustManager[] managers) {
        for (TrustManager manager : managers) {
            if (manager instanceof X509TrustManager) {
                return (X509TrustManager) manager;
            }
        }
        throw new IllegalStateException("Sin administrador de confianza X.509");
    }

    static X509TrustManager combine(final X509TrustManager system, final X509TrustManager bundled) {
        return new X509TrustManager() {
            @Override
            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                system.checkClientTrusted(chain, authType);
            }

            @Override
            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                try {
                    system.checkServerTrusted(chain, authType);
                } catch (CertificateException systemRejected) {
                    bundled.checkServerTrusted(chain, authType);  // si tampoco valida, se rechaza
                }
            }

            @Override
            public X509Certificate[] getAcceptedIssuers() {
                X509Certificate[] first = system.getAcceptedIssuers();
                X509Certificate[] second = bundled.getAcceptedIssuers();
                X509Certificate[] all = Arrays.copyOf(first, first.length + second.length);
                System.arraycopy(second, 0, all, first.length, second.length);
                return all;
            }
        };
    }

    /** Conexión al panel con esta confianza (el nombre del sitio lo sigue verificando Android). */
    static HttpURLConnection open(Context context, String url) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        if (connection instanceof HttpsURLConnection) {
            ((HttpsURLConnection) connection).setSSLSocketFactory(socketFactory(context));
        }
        return connection;
    }

    /** El certificado que recibió el navegador interno (en bytes), en cualquier versión de Android. */
    @SuppressWarnings("deprecation")
    static byte[] leafBytes(SslCertificate certificate) {
        if (certificate == null) {
            return null;
        }
        try {
            if (Build.VERSION.SDK_INT >= 29 && certificate.getX509Certificate() != null) {
                return certificate.getX509Certificate().getEncoded();
            }
            Bundle state = SslCertificate.saveState(certificate);
            return state == null ? null : state.getByteArray("x509-certificate");
        } catch (Exception error) {
            return null;
        }
    }

    static String fingerprint(byte[] encoded) {
        try {
            return KioskPolicy.hex(MessageDigest.getInstance("SHA-256").digest(encoded));
        } catch (Exception error) {
            return "";
        }
    }

    static boolean alreadyVerified(byte[] leaf) {
        return leaf != null && TRUSTED_LEAVES.contains(fingerprint(leaf));
    }

    /**
     * El navegador interno no deja cambiar su lista de raíces: si rechaza el certificado del
     * panel, la app abre su propia conexión verificada (cadena completa + nombre del sitio) y
     * solo continúa si el certificado que vio el navegador es EXACTAMENTE el mismo.
     */
    static boolean verifyPanelLeaf(Context context, byte[] leaf) {
        if (leaf == null) {
            return false;
        }
        if (alreadyVerified(leaf)) {
            return true;
        }
        HttpURLConnection connection = null;
        try {
            connection = open(context, "https://" + KioskPolicy.HOST + "/manifest.json");
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            connection.setRequestMethod("HEAD");
            connection.getResponseCode();
            Certificate[] chain = ((HttpsURLConnection) connection).getServerCertificates();
            if (chain.length > 0 && Arrays.equals(chain[0].getEncoded(), leaf)) {
                TRUSTED_LEAVES.add(fingerprint(leaf));
                return true;
            }
            return false;
        } catch (Exception error) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }
}
