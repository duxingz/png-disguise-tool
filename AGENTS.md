# png-disguise-tool — 共享决策与规格

极简"图片打码 + APNG 伪装"工具,从 ChatChatBar 抽取伪装格式。

## 已确认需求(用户拍板)
- 名称:**png伪装工具**;手机存相册目录 `Pictures/png伪装工具`。
- 两端:**手机端 + 电脑端,功能严格一致**。
- 主功能:**APNG 伪装(静态图 + GIF 动态伪装)+ 伪装还原**;打码是**附带功能**,需进入二级界面才可用。
- 首帧封面:**默认内置一张 + 设置里可配置**;封面完整居中(等比缩小不裁剪),四周蓝底补齐(对齐 CCB 大象封面效果)。
- 主流程:一级界面预览 +「APNG伪装」(主)+「还原」+「导出」按钮 + 打码入口;点图也可导出/分享。
- 设置项:极简,仅封面设置(默认图可换/恢复)。
- 输入支持:PNG/JPEG/GIF(WebP 桌面第一版不支持);还原支持原版 ChatChatBar 伪装文件。
- 元数据:打码/伪装输出为全新重编码图,天然无 EXIF;不做"原样复制剥离"功能。

## 架构(已定)
- 单仓库多模块:Kotlin/JVM。模块:`core`(纯 JVM,无 Android/Compose 依赖)、`desktop`(Compose for Desktop)、`android`(后续,同 core)。
- `core` 放原版 ApngDisguiseCodec 移植 + 伪装服务(GIF 用第三方 gif-decoder 解码)。
- 文件格式:**沿用原版标记与帧结构**,`MARKER_KEYWORD=ChatBarApngDisguise`、tEXt 内容 `version;STATIC|ANIMATED;count`、封面默认帧 + fcTL/fdAT 真图帧 + 静态保活帧。与 ChatChatBar 双向兼容。

## 常量
- 版本 1;上限版本 2;输出上限 100MB;单帧 ≤800 万像素。
- 默认封面:用户提供的图(512×512,蓝底 #2563EB 扁平化),位于 py/assets/ 与 core 资源。

## 当前形态(重要,2026-09 定稿)
- **exe(PySide6)**:py/ 目录,主桌面版,唯一保留的 exe(项目根 png伪装工具.exe)。功能:伪装/还原/GIF 动态伪装/批量(150)/队列缩略图卡片/Ctrl+V 粘贴/拖动导出/双视角预览/打码(滚轮缩放+右键平移)/封面设置(512 自动缩小)/窗口大小记忆/伪装 APNG 复制以文件方式。
- **html 单文件**:html/build.py 生成,免安装跨端(手机浏览器可用)。功能与 exe 对齐,差异:无 GIF 动态伪装(GIF 首帧静态伪装);下载/下载全部(≤30 逐张,>30 zip);封面设置 localStorage 持久化;打码支持双指捏合/平移。
- Kotlin desktop/、android/、core/、gradle 构建:已彻底删除(本地与仓库)。
- exe 伪装核心性能:滤波已改 None 直写(600 万像素 ~0.6s);html 靠 V8 JIT。
- 已知外部限制:QQ 图片消息会转码丢 APNG 动画→引导用户"文件方式发送/勾选原图"(两端说明栏都有此提示);html 无法复制文件到剪贴板(浏览器消毒)。

## 交付物与发布规则(重要)
- `png伪装工具.exe`(项目根):PyInstaller 打包,**每次改 py/ 源码后必须重新打包并更新**
- `png伪装工具.html`(项目根):**每次改 core.js/template.html 后必须重新 build 并更新**
- `png伪装工具-分享版.zip`:对外分享包 = exe + html + 使用说明.txt + 测试图片;**exe 或 html 任何更新后必须同步重打**
- 打包命令:exe → `cd py && python -m PyInstaller --onefile --windowed --name PngDisguiseTool --icon assets/app_icon.ico --add-data "assets;assets" app.py`;html → `cd html && python build.py`
- exe 内部名必须 ASCII(PngDisguiseTool),拷贝成中文名用 Python(勿用 bash cp,会乱码)
