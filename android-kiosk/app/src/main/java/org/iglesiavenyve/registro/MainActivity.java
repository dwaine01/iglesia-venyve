package org.iglesiavenyve.registro;

import android.annotation.SuppressLint;
import android.annotation.TargetApi;
import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.InputFilter;
import android.text.InputType;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.WindowManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.InputStream;

/**
 * Registro Ven y Ve: abre SOLO el registro de visitantes de la tableta en pantalla
 * completa. Sin barra de direcciones, sin «Atrás» y sin otros sitios. Si no hay
 * internet muestra «Sin conexión» con «Reintentar» y recarga sola cuando vuelve.
 * Salida de administrador: mantener presionada la esquina superior izquierda 5
 * segundos y escribir el PIN (en la tableta se guarda solo su huella cifrada).
 */
public class MainActivity extends Activity {
    static final String TAG = "RegistroVenyVe";
    static final String PREFS = "registro";
    static final String KEY_CODE = "code";
    static final String KEY_PIN_HASH = "pin_hash";
    static final String KEY_PIN_SALT = "pin_salt";
    static final String KEY_PIN_ITERATIONS = "pin_iterations";
    static final String KEY_PIN_ON_OPEN = "pin_screen_on_open";
    static final long CORNER_HOLD_MS = 5000;
    static final long AUTO_RETRY_MS = 15000;

    private static final int NAVY = 0xFF14213D;
    private static final int BACKGROUND = 0xFFF7F5EF;
    private static final int MUTED = 0xFF475467;

    SharedPreferences prefs;
    FrameLayout root;
    WebView web;
    KioskClient client;
    boolean offline;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private ConnectivityManager.NetworkCallback networkCallback;
    private int wrongPins;
    private long lockedUntil;
    private final Runnable autoRetry = new Runnable() {
        @Override
        public void run() {
            if (offline) {
                Log.i(TAG, "Reintento automático");
                loadTablet();
            }
        }
    };
    private final Runnable openAdmin = new Runnable() {
        @Override
        public void run() {
            askPin();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        root = new FrameLayout(this);
        root.setBackgroundColor(BACKGROUND);
        setContentView(root);
        keepAboveKeyboard();
        if (hasCode() && hasPin()) {
            showWeb();
        } else {
            showSetup(!hasPin());
        }
        watchNetwork();
    }

    @Override
    protected void onResume() {
        super.onResume();
        immersive();
        if (prefs.getBoolean(KEY_PIN_ON_OPEN, false) && !inLockTask()) {
            try {
                startLockTask();  // «Fijar pantalla»: Fire OS pide confirmarlo la primera vez.
            } catch (RuntimeException error) {
                Log.w(TAG, "No se pudo fijar la pantalla", error);
            }
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            immersive();
        }
    }

    /** «Atrás» deshabilitado: la persona nunca sale del registro. */
    @SuppressLint("MissingSuperCall")
    @Override
    public void onBackPressed() {
        Log.i(TAG, "Botón atrás ignorado");
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (networkCallback != null) {
            try {
                connectivity().unregisterNetworkCallback(networkCallback);
            } catch (RuntimeException ignored) {
                // ya no estaba registrado
            }
        }
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }

    // ------------------------------------------------------------------ pantalla completa y teclado
    @SuppressWarnings("deprecation")
    void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    /**
     * En pantalla completa Android no achica la ventana al abrir el teclado: se mide el
     * área visible y el contenido se ajusta a ella (la página usa ese alto para que el
     * campo que se escribe quede a la vista).
     */
    private void keepAboveKeyboard() {
        final View decor = getWindow().getDecorView();
        decor.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() {
            private int last = -1;

            @Override
            public void onGlobalLayout() {
                Rect visible = new Rect();
                decor.getWindowVisibleDisplayFrame(visible);
                int height = visible.bottom;
                if (height > 0 && height != last) {
                    last = height;
                    ViewGroup.LayoutParams params = root.getLayoutParams();
                    if (params != null) {
                        params.height = height;
                        root.setLayoutParams(params);
                    }
                }
            }
        });
    }

    // ------------------------------------------------------------------ registro (WebView)
    boolean hasCode() {
        return KioskPolicy.validCode(prefs.getString(KEY_CODE, null));
    }

    boolean hasPin() {
        return prefs.getString(KEY_PIN_HASH, null) != null && prefs.getString(KEY_PIN_SALT, null) != null;
    }

    @SuppressLint("SetJavaScriptEnabled")
    void showWeb() {
        root.removeAllViews();
        if (web == null) {
            web = new WebView(this);
            WebSettings settings = web.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);  // nombre de la tableta y cola sin internet
            settings.setDatabaseEnabled(true);
            settings.setAllowFileAccess(false);
            settings.setAllowContentAccess(false);
            settings.setAllowFileAccessFromFileURLs(false);
            settings.setAllowUniversalAccessFromFileURLs(false);
            settings.setSupportMultipleWindows(false);
            settings.setJavaScriptCanOpenWindowsAutomatically(false);
            settings.setGeolocationEnabled(false);
            settings.setSupportZoom(false);
            settings.setBuiltInZoomControls(false);
            settings.setDisplayZoomControls(false);
            settings.setTextZoom(100);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            if (Build.VERSION.SDK_INT >= 26) {
                settings.setSafeBrowsingEnabled(true);
            }
            settings.setUserAgentString(settings.getUserAgentString() + " RegistroVenyVe/" + versionName());
            if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
                WebView.setWebContentsDebuggingEnabled(true);
            }
            client = new KioskClient();
            web.setWebViewClient(client);
            web.setWebChromeClient(new WebChromeClient());
            web.setOverScrollMode(View.OVER_SCROLL_NEVER);
            web.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View view) {
                    return false;  // los campos de texto conservan pegar/seleccionar
                }
            });
            loadTablet();
        }
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        addAdminCorner();
    }

    void loadTablet() {
        handler.removeCallbacks(autoRetry);
        offline = false;
        String url = KioskPolicy.tabletUrl(prefs.getString(KEY_CODE, ""));
        Log.i(TAG, "Abriendo " + KioskPolicy.hostOf(url));
        web.loadUrl(url);
    }

    void showOffline(String reason) {
        Log.w(TAG, "Sin conexión: " + reason);
        offline = true;
        web.stopLoading();
        web.loadUrl(KioskPolicy.OFFLINE_PAGE);
        handler.removeCallbacks(autoRetry);
        handler.postDelayed(autoRetry, AUTO_RETRY_MS);
    }

    /** Lista blanca de dominio y página «Sin conexión». */
    class KioskClient extends WebViewClient {
        boolean allow(String url) {
            KioskPolicy.Decision decision = KioskPolicy.decide(url);
            if (decision == KioskPolicy.Decision.RETRY) {
                Log.i(TAG, "Reintentar (botón)");
                loadTablet();
                return false;
            }
            if (decision == KioskPolicy.Decision.BLOCK) {
                Log.w(TAG, "BLOQUEADO: " + KioskPolicy.hostOf(url) + " no es " + KioskPolicy.HOST);
                return false;
            }
            Log.i(TAG, "Permitido: " + KioskPolicy.hostOf(url));
            return true;
        }

        @SuppressWarnings("deprecation")
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            return !allow(url);
        }

        @TargetApi(24)
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            return !allow(request.getUrl().toString());
        }

        @Override
        public void onPageStarted(WebView view, String url, Bitmap favicon) {
            // Segunda barrera (p. ej. una redirección en Android viejo): nada fuera del panel.
            if (KioskPolicy.decide(url) == KioskPolicy.Decision.BLOCK) {
                Log.w(TAG, "BLOQUEADO al cargar: " + KioskPolicy.hostOf(url));
                view.stopLoading();
                loadTablet();
            }
        }

        @SuppressWarnings("deprecation")
        @Override
        public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
            if (failingUrl != null && failingUrl.startsWith("https://" + KioskPolicy.HOST)) {
                showOffline(description);
            }
        }

        @TargetApi(23)
        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) {
                showOffline(String.valueOf(error.getDescription()));
            }
        }

        @TargetApi(23)
        @Override
        public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (request.isForMainFrame() && response.getStatusCode() >= 500) {
                showOffline("el servidor respondió " + response.getStatusCode());
            }
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler sslHandler, SslError error) {
            sslHandler.cancel();  // nunca se acepta un certificado inválido
            showOffline("certificado inválido");
        }
    }

    // ------------------------------------------------------------------ internet
    private ConnectivityManager connectivity() {
        return (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
    }

    /** Al volver el internet se recarga sola (si estaba en «Sin conexión»). */
    private void watchNetwork() {
        try {
            networkCallback = new ConnectivityManager.NetworkCallback() {
                @Override
                public void onAvailable(Network network) {
                    handler.postDelayed(new Runnable() {
                        @Override
                        public void run() {
                            if (offline && web != null) {
                                Log.i(TAG, "Volvió el internet: recargando");
                                loadTablet();
                            }
                        }
                    }, 1500);
                }
            };
            connectivity().registerNetworkCallback(new NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), networkCallback);
        } catch (RuntimeException error) {
            Log.w(TAG, "No se puede vigilar la conexión", error);
            networkCallback = null;
        }
    }

    // ------------------------------------------------------------------ administrador
    /** Esquina superior izquierda: mantener presionada 5 segundos. */
    @SuppressLint("ClickableViewAccessibility")
    private void addAdminCorner() {
        View corner = new View(this);
        corner.setContentDescription("Administrador");
        corner.setOnTouchListener(new View.OnTouchListener() {
            @Override
            public boolean onTouch(View view, MotionEvent event) {
                int action = event.getActionMasked();
                if (action == MotionEvent.ACTION_DOWN) {
                    handler.postDelayed(openAdmin, CORNER_HOLD_MS);
                } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                    handler.removeCallbacks(openAdmin);
                }
                return true;
            }
        });
        int size = dp(72);
        root.addView(corner, new FrameLayout.LayoutParams(size, size, Gravity.TOP | Gravity.START));
    }

    void askPin() {
        if (SystemClock.elapsedRealtime() < lockedUntil) {
            Toast.makeText(this, "Demasiados intentos. Espere un minuto.", Toast.LENGTH_LONG).show();
            return;
        }
        final EditText pin = pinField("PIN de administrador");
        new AlertDialog.Builder(this)
                .setTitle("Administrador")
                .setView(padded(pin))
                .setPositiveButton("Entrar", (dialog, which) -> {
                    if (KioskPolicy.verifyPin(pin.getText().toString(), prefs.getString(KEY_PIN_SALT, null),
                            prefs.getInt(KEY_PIN_ITERATIONS, KioskPolicy.PIN_ITERATIONS), prefs.getString(KEY_PIN_HASH, null))) {
                        wrongPins = 0;
                        showAdminMenu();
                    } else {
                        wrongPins++;
                        if (wrongPins >= 5) {
                            wrongPins = 0;
                            lockedUntil = SystemClock.elapsedRealtime() + 60000;
                        }
                        Toast.makeText(this, "PIN incorrecto", Toast.LENGTH_LONG).show();
                        immersive();
                    }
                })
                .setNegativeButton("Cancelar", (dialog, which) -> immersive())
                .setOnCancelListener(dialog -> immersive())
                .show();
    }

    void showAdminMenu() {
        final boolean pinOnOpen = prefs.getBoolean(KEY_PIN_ON_OPEN, false);
        String[] options = {
                "Recargar el registro",
                "Cambiar el código de la tableta",
                "Cambiar el PIN",
                pinOnOpen ? "Fijar pantalla al abrir: SÍ (tocar para apagar)" : "Fijar pantalla al abrir: NO (tocar para encender)",
                "Salir de la app",
        };
        new AlertDialog.Builder(this)
                .setTitle("Administrador · versión " + versionName())
                .setItems(options, (dialog, which) -> {
                    switch (which) {
                        case 0:
                            if (web != null) {
                                loadTablet();
                            }
                            break;
                        case 1:
                            showSetup(false);
                            break;
                        case 2:
                            changePin();
                            break;
                        case 3:
                            prefs.edit().putBoolean(KEY_PIN_ON_OPEN, !pinOnOpen).apply();
                            if (pinOnOpen) {
                                stopPinning();
                            } else {
                                onResume();
                            }
                            break;
                        default:
                            stopPinning();
                            finish();
                    }
                    immersive();
                })
                .setNegativeButton("Cancelar", (dialog, which) -> immersive())
                .show();
    }

    private void changePin() {
        final EditText first = pinField("PIN nuevo (4 a 8 números)");
        final EditText second = pinField("Repita el PIN nuevo");
        LinearLayout box = column();
        box.addView(first);
        box.addView(second);
        new AlertDialog.Builder(this)
                .setTitle("Cambiar el PIN")
                .setView(padded(box))
                .setPositiveButton("Guardar", (dialog, which) -> {
                    String pin = first.getText().toString();
                    if (!KioskPolicy.validPin(pin) || !pin.equals(second.getText().toString())) {
                        Toast.makeText(this, "El PIN debe tener de 4 a 8 números y ser igual las dos veces. No se cambió.", Toast.LENGTH_LONG).show();
                    } else {
                        savePin(pin);
                        Toast.makeText(this, "PIN cambiado", Toast.LENGTH_LONG).show();
                    }
                    immersive();
                })
                .setNegativeButton("Cancelar", (dialog, which) -> immersive())
                .show();
    }

    void savePin(String pin) {
        String salt = KioskPolicy.newSalt();
        prefs.edit().putString(KEY_PIN_SALT, salt).putInt(KEY_PIN_ITERATIONS, KioskPolicy.PIN_ITERATIONS)
                .putString(KEY_PIN_HASH, KioskPolicy.hashPin(pin, salt, KioskPolicy.PIN_ITERATIONS)).apply();
    }

    private boolean inLockTask() {
        ActivityManager manager = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
        if (Build.VERSION.SDK_INT >= 23) {
            return manager.getLockTaskModeState() != ActivityManager.LOCK_TASK_MODE_NONE;
        }
        return isInLockTaskModeLegacy(manager);
    }

    @SuppressWarnings("deprecation")
    private static boolean isInLockTaskModeLegacy(ActivityManager manager) {
        return manager.isInLockTaskMode();
    }

    private void stopPinning() {
        try {
            if (inLockTask()) {
                stopLockTask();
            }
        } catch (RuntimeException error) {
            Log.w(TAG, "No se pudo quitar la fijación", error);
        }
    }

    // ------------------------------------------------------------------ primera vez: código y PIN
    /** Al instalar: el código de la tableta (Visitantes › Enlaces) y, la primera vez, el PIN. */
    void showSetup(final boolean askPin) {
        root.removeAllViews();
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout box = column();
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        int pad = dp(28);
        box.setPadding(pad, pad, pad, pad);
        scroll.addView(box);

        Bitmap emblem = asset("emblema.png");
        if (emblem != null) {
            ImageView logo = new ImageView(this);
            logo.setImageBitmap(emblem);
            logo.setAdjustViewBounds(true);
            box.addView(logo, new LinearLayout.LayoutParams(dp(220), ViewGroup.LayoutParams.WRAP_CONTENT));
        }
        box.addView(text("Registro Ven y Ve", 32, NAVY, true));
        box.addView(text(askPin ? "Preparar esta tableta" : "Cambiar el código de la tableta", 22, MUTED, false));

        final EditText code = new EditText(this);
        code.setHint("Ej.: ABCD2345");
        code.setTextSize(TypedValue.COMPLEX_UNIT_SP, 30);
        code.setSingleLine(true);
        code.setGravity(Gravity.CENTER);
        code.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        code.setFilters(new InputFilter[]{new InputFilter.LengthFilter(16), new InputFilter.AllCaps()});
        code.setText(prefs.getString(KEY_CODE, ""));
        box.addView(label("1. Código de la tableta"));
        box.addView(text("Está en Visitantes › Enlaces: las letras y números después de «/r/».", 18, MUTED, false));
        box.addView(code, wide());

        final EditText pin = pinField("PIN (4 a 8 números)");
        final EditText again = pinField("Repita el PIN");
        if (askPin) {
            box.addView(label("2. PIN de administrador"));
            box.addView(text("Sirve para salir de la app: mantener presionada la esquina superior izquierda 5 segundos. Anótelo en un lugar seguro.", 18, MUTED, false));
            box.addView(pin, wide());
            box.addView(again, wide());
        }

        final TextView error = text("", 19, 0xFFB42318, true);
        box.addView(error);

        Button save = new Button(this);
        save.setText("Guardar y abrir el registro");
        save.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24);
        save.setAllCaps(false);
        save.setTextColor(Color.WHITE);
        save.setBackgroundColor(NAVY);
        save.setPadding(dp(24), dp(18), dp(24), dp(18));
        save.setOnClickListener(view -> {
            String value = KioskPolicy.normalizeCode(code.getText().toString());
            if (!KioskPolicy.validCode(value)) {
                error.setText("Revise el código: son de 6 a 12 letras y números, y nunca lleva 0, O, 1, I ni L.");
                return;
            }
            if (askPin) {
                String chosen = pin.getText().toString();
                if (!KioskPolicy.validPin(chosen)) {
                    error.setText("El PIN debe tener de 4 a 8 números.");
                    return;
                }
                if (!chosen.equals(again.getText().toString())) {
                    error.setText("Los dos PIN no son iguales.");
                    return;
                }
                savePin(chosen);
            }
            prefs.edit().putString(KEY_CODE, value).apply();
            Log.i(TAG, "Código de la tableta guardado");
            boolean reopen = web != null;
            showWeb();
            if (reopen) {
                loadTablet();  // código nuevo: se abre ya con él
            }
        });
        LinearLayout.LayoutParams buttonParams = wide();
        buttonParams.topMargin = dp(18);
        box.addView(save, buttonParams);
        if (!askPin) {
            Button cancel = new Button(this);
            cancel.setText("Cancelar");
            cancel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
            cancel.setAllCaps(false);
            cancel.setOnClickListener(view -> showWeb());
            box.addView(cancel, wide());
        }
        root.addView(scroll, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    // ------------------------------------------------------------------ piezas
    private EditText pinField(String hint) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        field.setSingleLine(true);
        field.setGravity(Gravity.CENTER);
        field.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        field.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8)});
        return field;
    }

    private LinearLayout column() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        return box;
    }

    private View padded(View view) {
        FrameLayout frame = new FrameLayout(this);
        int pad = dp(20);
        frame.setPadding(pad, dp(8), pad, 0);
        frame.addView(view);
        return frame;
    }

    private TextView label(String value) {
        TextView view = text(value, 22, NAVY, true);
        view.setPadding(0, dp(22), 0, dp(4));
        return view;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER);
        view.setPadding(0, dp(6), 0, dp(6));
        if (bold) {
            view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        }
        return view;
    }

    private LinearLayout.LayoutParams wide() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(6);
        return params;
    }

    private Bitmap asset(String name) {
        try (InputStream input = getAssets().open(name)) {
            return BitmapFactory.decodeStream(input);
        } catch (Exception error) {
            return null;
        }
    }

    private String versionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception error) {
            return "?";
        }
    }

    private int dp(int value) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, getResources().getDisplayMetrics()));
    }
}
