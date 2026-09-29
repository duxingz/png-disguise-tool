# 手机端（Android APK）

把网页版（`html/` 构建出的单文件 `png伪装工具.html`）装进 WebView，并补上手机才需要的三件事。
**零第三方依赖、不申请任何权限**（保存走 MediaStore，分享用 content:// + 临时读权限）。

## 环境

- JDK 17+（实测 Temurin 21）
- Android SDK：`platforms;android-34`、`build-tools;34.0.0`、`platform-tools`
- Gradle 8.9+（AGP 8.7.3）

## 构建步骤

```bash
# 1) 先构建网页版（仓库根目录）
cd ../html && python build.py          # 生成 html/png伪装工具.html

# 2) 拷进 APK 的 assets（这一步是构建产物，不入库）
cp "png伪装工具.html" ../android/app/src/main/assets/index.html

# 3) 准备签名（首次；口令/别名要与 app/build.gradle 的 signingConfigs 一致）
keytool -genkeypair -v -keystore pngdisguise.jks -alias pngdisguise \
  -keyalg RSA -keysize 2048 -validity 10950 \
  -storepass pngdisguise -keypass pngdisguise -dname "CN=pngdisguise"

# 4) 写 SDK 路径
echo "sdk.dir=<你的 Android SDK 路径>" > local.properties

# 5) 打包
gradle assembleRelease                 # 产物：app/build/outputs/apk/release/app-release.apk
```

## 实现说明（`app/src/main/java/com/duxingz/pngdisguise/MainActivity.java`）

| 能力 | 做法 |
|---|---|
| 载入界面 | `loadDataWithBaseURL("https://app.local/", assets/index.html)`——用假 https 源，设置记忆（localStorage）才可用 |
| 选图 | `WebChromeClient.onShowFileChooser` → 系统相册/文件选择器 |
| 下载 | 注入覆盖网页的 `window.downloadBlob()`：blob 分块（256KB）base64 → `@JavascriptInterface` → 写入 MediaStore「下载」目录 |
| 发送 | 保存后延时 900ms 合并弹系统分享（单个 `ACTION_SEND`，批量 `ACTION_SEND_MULTIPLE`），选 QQ/微信即以**文件**发送（保住 APNG 动画） |

约束与注意：

- `minSdk 29`（Android 10+）：直接用 MediaStore，免存储权限
- `android/local.properties`、`android/.gradle/`、`android/app/build/`、`android/app/src/main/assets/index.html`、`*.jks` **都不入库**
- ⚠️ **签名私钥（`pngdisguise.jks`）务必自行备份**：换签名后无法覆盖安装，只能先卸载
- 网页侧改动后**必须重跑上面第 1、2 步**再打包，否则 APK 里还是旧页面
