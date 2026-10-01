package com.duxingz.pngdisguise;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;

/**
 * 手机版外壳:把网页版(单文件 index.html)装进 WebView,并补上手机才需要的两件事——
 * 1) 选图/选文件:走系统文件选择器(相册/文件管理器都能用);
 * 2) 下载:网页里所有下载都经过 downloadBlob(),这里注入一层覆盖,把 blob 以分块 base64
 *    交给原生,存进系统「下载」目录,随后弹出系统分享(可直接选 QQ 以「文件」发送,保住动画)。
 *
 * 不依赖任何第三方库,也不申请任何权限(MediaStore + content:// 分享)。
 */
public class MainActivity extends Activity {

    private static final int REQ_FILE = 1001;
    private static final int CHUNK = 262144;          // 与网页注入的分块大小一致(4 的倍数)
    private static final long SHARE_DELAY_MS = 900;   // 批量保存时合并成一次分享

    private WebView web;
    private ValueCallback<Uri[]> filePathCallback;

    private String pendingName;
    private ByteArrayOutputStream pendingBuf;
    private int pendingExpected;   // 预期 base64 总长(begin 时由网页给出)
    private int pendingReceived;   // 实际收到的 base64 长度(end 时核对,防存坏文件)
    private final ArrayList<Uri> savedUris = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable shareTask = new Runnable() {
        @Override public void run() { shareSaved(); }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        FrameLayout root = new FrameLayout(this);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);        // 设置记忆(localStorage)需要
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);

        // 允许用电脑 chrome://inspect 连上这个 WebView 排查问题(自用小工具,不涉隐私数据)
        WebView.setWebContentsDebuggingEnabled(true);

        web.addJavascriptInterface(new Saver(), "AndroidSaver");

        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) {
                injectDownloadBridge(view);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb,
                                             FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = cb;
                try {
                    Intent i = params.createIntent();
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(i, REQ_FILE);
                    return true;
                } catch (Exception e) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, "打不开文件选择器", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });

        // 兜底:万一有非 blob 的下载(正常流程不会走到这)
        web.setDownloadListener((url, ua, cd, mime, len) ->
                Toast.makeText(this, "该下载方式暂不支持,请用页面里的下载按钮", Toast.LENGTH_SHORT).show());

        loadApp();
    }

    /** 把 assets 里的单文件网页装进 WebView。用 https 假源加载,localStorage 才可用。 */
    private void loadApp() {
        try {
            InputStream in = getAssets().open("index.html");
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) {
                bo.write(buf, 0, n);
            }
            in.close();
            String html = bo.toString("UTF-8");
            web.loadDataWithBaseURL("https://app.local/", html, "text/html", "UTF-8", null);
        } catch (IOException e) {
            Toast.makeText(this, "载入失败: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    /**
     * 注入下载桥:覆盖网页里的 downloadBlob(),把 blob 分块 base64 交给原生。
     * 任何异常都退回网页原有实现,保证不会因为桥接问题导致"点了下载没反应"。
     */
    private void injectDownloadBridge(WebView view) {
        String js =
            "(function(){try{\n" +
            "  if(!window.downloadBlob||window.__apkBridge)return;\n" +
            "  var orig=window.downloadBlob;window.__apkBridge=true;\n" +
            "  window.downloadBlob=function(blob,name){\n" +
            "    try{\n" +
            "      var fr=new FileReader();\n" +
            "      fr.onload=function(){\n" +
            "        try{\n" +
            "          var b64=String(fr.result).split(',')[1]||'';\n" +
            "          AndroidSaver.begin(name,b64.length);\n" +
            "          for(var i=0;i<b64.length;i+=" + CHUNK + "){AndroidSaver.chunk(b64.substr(i," + CHUNK + "));}\n" +
            "          AndroidSaver.end();\n" +
            "        }catch(e){try{orig(blob,name);}catch(e2){}}\n" +
            "      };\n" +
            "      fr.onerror=function(){try{orig(blob,name);}catch(e){}};\n" +
            "      fr.readAsDataURL(blob);\n" +
            "    }catch(e){try{orig(blob,name);}catch(e2){}}\n" +
            "  };\n" +
            "}catch(e){}})();";
        view.evaluateJavascript(js, null);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE) {
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    result = new Uri[count];
                    for (int i = 0; i < count; i++) {
                        result[i] = data.getClipData().getItemAt(i).getUri();
                    }
                } else if (data.getData() != null) {
                    result = new Uri[]{ data.getData() };
                }
            }
            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(result);
                filePathCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    /** 网页侧调用的保存接口(分块传输,避免一次传几 MB 字符串)。 */
    private class Saver {
        @JavascriptInterface
        public void begin(String name, int totalBase64Length) {
            pendingName = (name == null || name.isEmpty()) ? "png伪装工具_输出.png" : name;
            pendingExpected = Math.max(0, totalBase64Length);
            pendingReceived = 0;
            pendingBuf = new ByteArrayOutputStream(Math.max(4096, totalBase64Length * 3 / 4));
        }

        @JavascriptInterface
        public void chunk(String base64Chunk) {
            if (pendingBuf == null || base64Chunk == null) return;
            try {
                pendingBuf.write(Base64.decode(base64Chunk, Base64.DEFAULT));
                pendingReceived += base64Chunk.length();
            } catch (Exception ignored) {
                // 单个分块解码失败:end 时长度对不上会拒存,不给用户坏文件
            }
        }

        @JavascriptInterface
        public void end() {
            final String name = pendingName;
            final byte[] bytes = (pendingBuf == null) ? null : pendingBuf.toByteArray();
            final int expected = pendingExpected, received = pendingReceived;
            pendingName = null;
            pendingBuf = null;
            pendingExpected = 0;
            pendingReceived = 0;
            if (bytes == null || bytes.length == 0) return;
            if (expected > 0 && received != expected) {
                handler.post(() -> Toast.makeText(MainActivity.this,
                        "传输不完整,文件未保存,请重试", Toast.LENGTH_LONG).show());
                return;
            }
            handler.post(new Runnable() {
                @Override public void run() { saveToDownloads(name, bytes); }
            });
        }
    }

    /** 按扩展名给 MIME:与 MediaStore 的预期不符时,它会擅自给文件名补后缀。 */
    private static String mimeOf(String name) {
        String n = name.toLowerCase();
        if (n.endsWith(".zip")) return "application/zip";
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
        if (n.endsWith(".gif")) return "image/gif";
        if (n.endsWith(".webp")) return "image/webp";
        return "application/octet-stream";
    }

    /** 写入系统「下载」目录,然后延时合并分享。 */
    private void saveToDownloads(String name, byte[] data) {
        try {
            ContentValues cv = new ContentValues();
            cv.put(MediaStore.Downloads.DISPLAY_NAME, name);
            cv.put(MediaStore.Downloads.MIME_TYPE, mimeOf(name));
            cv.put(MediaStore.Downloads.IS_PENDING, 1);
            Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
            if (uri == null) throw new IOException("无法创建下载项");
            OutputStream os = getContentResolver().openOutputStream(uri);
            if (os == null) throw new IOException("无法写入");
            os.write(data);
            os.flush();
            os.close();
            cv.clear();
            cv.put(MediaStore.Downloads.IS_PENDING, 0);
            getContentResolver().update(uri, cv, null, null);

            savedUris.add(uri);
            Toast.makeText(this, "已保存到「下载」: " + name, Toast.LENGTH_SHORT).show();

            handler.removeCallbacks(shareTask);
            handler.postDelayed(shareTask, SHARE_DELAY_MS);
        } catch (Exception e) {
            Toast.makeText(this, "保存失败: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    /** 弹系统分享(单个/多个一起);选 QQ 即可"以文件发送",保住动画。 */
    private void shareSaved() {
        if (savedUris.isEmpty()) return;
        Intent send;
        if (savedUris.size() == 1) {
            send = new Intent(Intent.ACTION_SEND);
            // MIME 用保存时的实际类型:批量下载的 zip 是 application/zip,GIF/JPEG 也不是 png
            String mime = getContentResolver().getType(savedUris.get(0));
            send.setType(mime != null ? mime : "image/png");
            send.putExtra(Intent.EXTRA_STREAM, savedUris.get(0));
        } else {
            send = new Intent(Intent.ACTION_SEND_MULTIPLE);
            send.setType("*/*");
            send.putParcelableArrayListExtra(Intent.EXTRA_STREAM, new ArrayList<>(savedUris));
        }
        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Intent chooser = Intent.createChooser(send, "发送伪装图(选 QQ = 以文件发送)");
        chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        savedUris.clear();
        try {
            startActivity(chooser);
        } catch (Exception ignored) {
            // 没有可分享的应用就静默算了,文件已经在「下载」里
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
