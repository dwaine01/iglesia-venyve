package org.iglesiavenyve.registro;

import java.net.URI;
import java.net.URISyntaxException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Locale;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

/**
 * Reglas de la app de tabletas, sin nada de Android (se prueban en la computadora):
 * qué direcciones se pueden abrir (solo el panel de la iglesia), el código de la
 * tableta y el PIN de administrador (se guarda solo su huella cifrada, nunca el PIN).
 */
public final class KioskPolicy {
    public static final String HOST = "panel.iglesiavenyve.org";
    public static final String OFFLINE_PAGE = "file:///android_asset/offline.html";
    public static final String RETRY_URL = "registro://reintentar";
    /** Mismas letras y números que usa el servidor para el código corto (sin 0/O ni 1/I/L). */
    public static final String CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
    static final int PIN_ITERATIONS = 20000;

    public enum Decision { LOAD, RETRY, BLOCK }

    private KioskPolicy() {
    }

    /** Lista blanca: solo https://panel.iglesiavenyve.org (y la página propia «Sin conexión»). */
    public static Decision decide(String url) {
        if (url == null) {
            return Decision.BLOCK;
        }
        if (url.equals(RETRY_URL)) {
            return Decision.RETRY;
        }
        if (url.equals(OFFLINE_PAGE) || url.startsWith(OFFLINE_PAGE + "?") || url.startsWith(OFFLINE_PAGE + "#")) {
            return Decision.LOAD;
        }
        URI uri;
        try {
            uri = new URI(url);
        } catch (URISyntaxException error) {
            return Decision.BLOCK;
        }
        String host = uri.getHost();
        boolean allowed = "https".equalsIgnoreCase(uri.getScheme()) && host != null && host.equalsIgnoreCase(HOST)
                && (uri.getPort() == -1 || uri.getPort() == 443) && uri.getRawUserInfo() == null;
        return allowed ? Decision.LOAD : Decision.BLOCK;
    }

    /** Para los registros: el dominio de una dirección (o «dirección inválida»). */
    public static String hostOf(String url) {
        try {
            String host = new URI(url).getHost();
            return host == null ? String.valueOf(url) : host;
        } catch (URISyntaxException | NullPointerException error) {
            return "dirección inválida";
        }
    }

    /** «abcd-2345 » → «ABCD2345». */
    public static String normalizeCode(String raw) {
        StringBuilder code = new StringBuilder();
        for (char letter : (raw == null ? "" : raw).toUpperCase(Locale.ROOT).toCharArray()) {
            if ((letter >= 'A' && letter <= 'Z') || (letter >= '0' && letter <= '9')) {
                code.append(letter);
            }
        }
        return code.toString();
    }

    public static boolean validCode(String code) {
        if (code == null || code.length() < 6 || code.length() > 12) {
            return false;
        }
        for (char letter : code.toCharArray()) {
            if (CODE_ALPHABET.indexOf(letter) < 0) {
                return false;
            }
        }
        return true;
    }

    public static String tabletUrl(String code) {
        return "https://" + HOST + "/r/" + code + "?app=apk";
    }

    /** PIN de 4 a 8 números. */
    public static boolean validPin(String pin) {
        return pin != null && pin.matches("[0-9]{4,8}");
    }

    public static String newSalt() {
        byte[] salt = new byte[16];
        new SecureRandom().nextBytes(salt);
        return hex(salt);
    }

    /** Huella del PIN (PBKDF2): no se puede volver al PIN a partir de ella. */
    public static String hashPin(String pin, String salt, int iterations) {
        try {
            PBEKeySpec spec = new PBEKeySpec(pin.toCharArray(), unhex(salt), iterations, 256);
            return hex(SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1").generateSecret(spec).getEncoded());
        } catch (Exception error) {
            throw new IllegalStateException("No se pudo cifrar el PIN", error);
        }
    }

    public static boolean verifyPin(String pin, String salt, int iterations, String expected) {
        if (pin == null || salt == null || expected == null) {
            return false;
        }
        return MessageDigest.isEqual(hashPin(pin, salt, iterations).getBytes(), expected.getBytes());
    }

    static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder();
        for (byte value : bytes) {
            text.append(String.format(Locale.ROOT, "%02x", value));
        }
        return text.toString();
    }

    static byte[] unhex(String text) {
        byte[] bytes = new byte[text.length() / 2];
        for (int index = 0; index < bytes.length; index++) {
            bytes[index] = (byte) Integer.parseInt(text.substring(index * 2, index * 2 + 2), 16);
        }
        return bytes;
    }
}
