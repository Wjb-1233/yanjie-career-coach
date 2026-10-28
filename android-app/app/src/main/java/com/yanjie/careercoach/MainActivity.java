package com.yanjie.careercoach;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final String PREFS = "server_settings";
    private static final String SERVER_KEY = "server_origin";
    private static final int MICROPHONE_REQUEST = 41;
    private static final int RESUME_FILE_REQUEST = 42;

    private WebView webView;
    private ValueCallback<Uri[]> resumeFileCallback;
    private SpeechRecognizer speechRecognizer;
    private TextToSpeech textToSpeech;
    private String serverOrigin;
    private String pendingUtterance;
    private boolean textToSpeechReady;
    private boolean microphoneRequested;
    private boolean connectionDialogVisible;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        String savedOrigin = preferences.getString(SERVER_KEY, null);
        if (savedOrigin != null && savedOrigin.contains(".trycloudflare.com")) {
            preferences.edit().remove(SERVER_KEY).apply();
            savedOrigin = null;
        }
        serverOrigin = savedOrigin != null ? savedOrigin : getString(R.string.default_server_url);
        createScreen();
        prepareSpeechOutput();
        openServer();
    }

    private void createScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(244, 247, 245));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(16), 0, dp(8), 0);
        toolbar.setBackgroundColor(Color.rgb(16, 37, 43));
        root.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(48)));

        TextView title = new TextView(this);
        title.setText("言阶 · 职场沟通教练");
        title.setTextColor(Color.WHITE);
        title.setTextSize(16);
        title.setContentDescription("言阶职场沟通教练");
        toolbar.addView(title, new LinearLayout.LayoutParams(0, -2, 1));

        Button settingsButton = new Button(this);
        settingsButton.setAllCaps(false);
        settingsButton.setText("服务器设置");
        settingsButton.setTextColor(Color.WHITE);
        settingsButton.setTextSize(12);
        settingsButton.setContentDescription("设置电脑服务器地址");
        settingsButton.setBackgroundColor(Color.TRANSPARENT);
        settingsButton.setOnClickListener(view -> showServerSettings());
        toolbar.addView(settingsButton, new LinearLayout.LayoutParams(dp(112), dp(48)));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(244, 247, 245));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        // The system document picker returns content:// URIs for DOCX uploads.
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.addJavascriptInterface(new SpeechBridge(), "AndroidSpeechBridge");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame() || isConfiguredOrigin(request.getUrl().toString())) return false;
                Intent external = new Intent(Intent.ACTION_VIEW, request.getUrl());
                startActivity(external);
                return true;
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if ((url.startsWith("http://") || url.startsWith("https://")) && !isConfiguredOrigin(url)) {
                    return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", null,
                            new ByteArrayInputStream(new byte[0]));
                }
                return null;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        android.webkit.WebResourceError error) {
                if (request.isForMainFrame()) runOnUiThread(() -> showConnectionError());
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (resumeFileCallback != null) resumeFileCallback.onReceiveValue(null);
                resumeFileCallback = callback;
                Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                picker.addCategory(Intent.CATEGORY_OPENABLE);
                picker.setType("application/vnd.openxmlformats-officedocument.wordprocessingml.document");
                picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try {
                    startActivityForResult(picker, RESUME_FILE_REQUEST);
                    return true;
                } catch (ActivityNotFoundException error) {
                    resumeFileCallback = null;
                    Toast.makeText(MainActivity.this, "未找到可用的文件管理器", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void openServer() {
        webView.loadUrl(serverOrigin + "/");
    }

    private boolean isConfiguredOrigin(String candidate) {
        try {
            URI expected = new URI(serverOrigin);
            URI actual = new URI(candidate);
            return expected.getScheme().equalsIgnoreCase(actual.getScheme())
                    && expected.getHost().equalsIgnoreCase(actual.getHost())
                    && expected.getPort() == actual.getPort();
        } catch (URISyntaxException | NullPointerException error) {
            return false;
        }
    }

    private void showConnectionError() {
        if (connectionDialogVisible || isFinishing()) return;
        connectionDialogVisible = true;
        new AlertDialog.Builder(this)
                .setTitle("连接不到电脑服务器")
                .setMessage("请确认电脑和手机在同一 Wi-Fi、电脑项目正在运行。当前地址：" + serverOrigin)
                .setPositiveButton("修改地址", (dialog, which) -> showServerSettings())
                .setNegativeButton("重试", (dialog, which) -> openServer())
                .setOnDismissListener(dialog -> connectionDialogVisible = false)
                .show();
    }

    private void showServerSettings() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(serverOrigin);
        input.setSelectAllOnFocus(true);
        input.setHint("http://电脑局域网IP:4173");
        LinearLayout container = new LinearLayout(this);
        container.setPadding(dp(22), dp(8), dp(22), 0);
        container.addView(input, new LinearLayout.LayoutParams(-1, -2));
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("电脑服务器地址")
                .setMessage("与电脑连接同一 Wi-Fi 后填写电脑的 IPv4 地址。仅测试版允许局域网 HTTP。")
                .setView(container)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存并连接", null)
                .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String normalized = normalizeServer(input.getText().toString());
            if (normalized == null) {
                input.setError("请输入 HTTPS 地址或局域网 IPv4 地址，例如 http://192.168.1.5:4173");
                return;
            }
            serverOrigin = normalized;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(SERVER_KEY, normalized).apply();
            webView.clearHistory();
            openServer();
            dialog.dismiss();
        }));
        dialog.show();
    }

    private String normalizeServer(String value) {
        try {
            URI uri = new URI(value.trim());
            String scheme = uri.getScheme();
            String host = uri.getHost();
            if (scheme == null || host == null || uri.getUserInfo() != null || uri.getFragment() != null) return null;
            int port = uri.getPort();
            if (port < -1 || port > 65535 || port == 0) return null;
            if (!"https".equalsIgnoreCase(scheme)
                    && !("http".equalsIgnoreCase(scheme) && isPrivateIpv4(host))) return null;
            return scheme.toLowerCase(Locale.ROOT) + "://" + host.toLowerCase(Locale.ROOT)
                    + (port == -1 ? "" : ":" + port);
        } catch (URISyntaxException error) {
            return null;
        }
    }

    private boolean isPrivateIpv4(String host) {
        String[] parts = host.split("\\.");
        if (parts.length != 4) return false;
        int[] octets = new int[4];
        try {
            for (int index = 0; index < 4; index++) {
                octets[index] = Integer.parseInt(parts[index]);
                if (octets[index] < 0 || octets[index] > 255) return false;
            }
        } catch (NumberFormatException error) {
            return false;
        }
        return octets[0] == 10 || octets[0] == 127
                || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
                || (octets[0] == 192 && octets[1] == 168);
    }

    private void emitSpeechEvent(String status, String value) {
        JSONObject detail = new JSONObject();
        try {
            detail.put("status", status);
            detail.put("value", value);
        } catch (JSONException ignored) {
            return;
        }
        String script = "window.dispatchEvent(new CustomEvent('yanjie:native-speech', {detail: "
                + detail.toString() + "}))";
        runOnUiThread(() -> webView.evaluateJavascript(script, null));
    }

    private void beginListening() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            microphoneRequested = true;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MICROPHONE_REQUEST);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            emitSpeechEvent("error", "手机没有可用的语音识别服务，可切换文字模式。");
            return;
        }
        if (speechRecognizer != null) speechRecognizer.destroy();
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { emitSpeechEvent("start", ""); }
            @Override public void onBeginningOfSpeech() { }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() { }
            @Override public void onError(int code) {
                String message = code == SpeechRecognizer.ERROR_NO_MATCH || code == SpeechRecognizer.ERROR_SPEECH_TIMEOUT
                        ? "没有听清，请再说一次。" : "语音识别未完成，请检查手机语音服务或改用文字模式。";
                emitSpeechEvent("error", message);
                emitSpeechEvent("end", "");
            }
            @Override public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) emitSpeechEvent("result", matches.get(0));
                emitSpeechEvent("end", "");
            }
            @Override public void onPartialResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) emitSpeechEvent("interim", matches.get(0));
            }
            @Override public void onEvent(int eventType, Bundle params) { }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        speechRecognizer.startListening(intent);
    }

    private void prepareSpeechOutput() {
        textToSpeech = new TextToSpeech(this, status -> {
            textToSpeechReady = status == TextToSpeech.SUCCESS;
            if (textToSpeechReady) {
                textToSpeech.setLanguage(Locale.SIMPLIFIED_CHINESE);
                if (pendingUtterance != null) {
                    String text = pendingUtterance;
                    pendingUtterance = null;
                    speak(text);
                }
            }
        });
        textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String utteranceId) { emitSpeechEvent("speaking-start", ""); }
            @Override public void onDone(String utteranceId) { emitSpeechEvent("speaking-end", ""); }
            @Override public void onError(String utteranceId) {
                emitSpeechEvent("speaking-end", "");
                emitSpeechEvent("error", "语音播报失败，请直接阅读文字回复。");
            }
        });
    }

    private void speak(String text) {
        if (!textToSpeechReady) {
            pendingUtterance = text;
            return;
        }
        textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "interviewer-response");
    }

    private final class SpeechBridge {
        @JavascriptInterface public void startListening() {
            runOnUiThread(() -> beginListening());
        }
        @JavascriptInterface public void stopListening() {
            runOnUiThread(() -> { if (speechRecognizer != null) speechRecognizer.stopListening(); });
        }
        @JavascriptInterface public void speak(String text) {
            runOnUiThread(() -> MainActivity.this.speak(text));
        }
        @JavascriptInterface public void stopSpeaking() {
            runOnUiThread(() -> {
                pendingUtterance = null;
                if (textToSpeech != null) textToSpeech.stop();
                emitSpeechEvent("speaking-end", "");
            });
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != MICROPHONE_REQUEST || !microphoneRequested) return;
        microphoneRequested = false;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) beginListening();
        else emitSpeechEvent("error", "麦克风权限被拒绝，可在手机设置中允许，或使用文字模式。");
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != RESUME_FILE_REQUEST || resumeFileCallback == null) return;
        Uri uri = resultCode == RESULT_OK && data != null ? data.getData() : null;
        resumeFileCallback.onReceiveValue(uri == null ? null : new Uri[]{uri});
        resumeFileCallback = null;
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (resumeFileCallback != null) {
            resumeFileCallback.onReceiveValue(null);
            resumeFileCallback = null;
        }
        if (speechRecognizer != null) speechRecognizer.destroy();
        if (textToSpeech != null) textToSpeech.shutdown();
        webView.destroy();
        super.onDestroy();
    }
}
