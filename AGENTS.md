# png-disguise-tool — 共享决策与规格

极简"APNG 图片伪装/还原 + 打码"工具,伪装格式从 ChatChatBar 抽取。

## 已确认需求(用户拍板)
- 名称:**png伪装工具**。
- 两端:**电脑 exe(PySide6)+ 网页单文件 html,功能尽量一致**。
- 主功能:**APNG 伪装(静态图 + GIF 动态伪装)+ 伪装还原**;打码是**附带功能**,二级界面。
- 首帧封面:**默认内置一张 + 设置里可配置(背景色可设/透明可选)**;封面完整居中(等比缩小不裁剪)。
- 元数据(2026-09-09 定稿):默认**彻底清除**。NovelAI V3 把提示词隐写在 alpha 通道低位(写在 255↔254 的不透明像素上,解码器按像素顺序读 alpha 低位直到 NUL),所以伪装与还原都必须**全像素清 alpha LSB + 全透明像素 RGB 透白**,且该变换必须**幂等**(伪装↔还原循环零漂移);设置里可选"保留元数据"(伪装文件附带原 tEXt/iTXt/zTXt/eXIf 块,供其他工具还原;本工具还原输出仍是不带元数据的干净图)。
- 还原兼容:本工具双真图帧文件、原版 ChatChatBar [真图, 1×1保活帧] 文件、v4.0 双真图帧文件都能还原——静态取"与画布同尺寸的最后一帧真图"(过滤保活帧、避免取到角翻转帧)。

## 架构(当前)
- `py/`:PySide6 桌面版(app.py + ui/ + pngdisguise/)。pngdisguise/apng_codec.py = 纯 Python APNG 编解码(伪装写入/检测/还原);image_processor.py = 图像处理、元数据与隐写清理。
- `html/`:纯 JS 单文件版(core.js 编解码核心 + template.html 界面 + build.py 合成单文件)。与 py 端格式契约一致,双端可互相还原(有像素级交叉回归)。
- 旧 Kotlin 模块(core/desktop/android)已彻底删除(2026-09-08)。

## 文件格式(与原 ChatChatBar 双向兼容)
`IHDR → acTL → tEXt("ChatBarApngDisguise\0ver;STATIC|ANIMATED;count") → IDAT×N(封面) → fcTL+fdAT(真图·翻转帧) → fcTL+fdAT(真图·干净帧) → IEND`
- 静态 = **双真图帧 [nudged, clean]**(v4.0 手法:两帧强制差 1 像素,防解码器判静态;nudged = clean 的 [0,0] R+1)。取代旧版 1×1 保活帧;旧结构仍可读取还原。
- 封面与静态真图写入前都做隐写清理(全像素 alpha LSB 清零 + 全透明透白 + 剥离元数据块;keep_meta=True 时附带元数据块并跳过白名单重组)。
- GIF 动态伪装:真图帧 = GIF 各帧原样写入(GIF 无 8 位 alpha 通道,无隐写可能,不做清理)。

## 常量
- 格式版本 1;上限版本 2;输出 ≤100MB;单帧 ≤800 万像素。
- 默认封面:内置图(≤512px,蓝底 #2563EB)。

## 当前形态(重要,2026-09 定稿)
- **exe(PySide6)**:py/ 目录,主桌面版(项目根 png伪装工具.exe)。功能:伪装/还原/GIF 动态伪装/批量(150)/队列缩略图卡片(单选/多选/右键删除)/Ctrl+V 粘贴/拖动导出/双视角预览/打码(滚轮缩放+右键平移)/封面设置(背景色/透明/512 自动缩小)/元数据开关/窗口大小记忆/伪装 APNG 复制以文件方式。
- **html 单文件**:html/build.py 生成,免安装跨端(手机浏览器可用)。功能与 exe 对齐,差异:无 GIF 动态伪装(GIF 首帧静态伪装);下载/下载全部(≤30 逐张,>30 zip);封面设置/元数据开关 localStorage 持久化;打码支持双指捏合/平移。
- exe 伪装核心性能:滤波 None 直写(600 万像素 ~0.6s);html 靠 V8 JIT + CompressionStream。
- 已知外部限制:QQ 图片消息会转码丢 APNG 动画→引导用户"文件方式发送/勾选原图"(两端说明栏都有此提示);浏览器剪贴板消毒,html 无法复制文件到剪贴板。

## 交付物与发布规则(重要)
- `png伪装工具.exe`(项目根):PyInstaller 打包,**每次改 py/ 源码后必须重新打包并更新**
- `png伪装工具.html`(项目根):**每次改 core.js/template.html 后必须重新 build 并更新**
- `png伪装工具-分享版.zip`:对外分享包 = exe + html + 使用说明.txt + 测试图片;**exe 或 html 任何更新后必须同步重打**
- 打包命令:exe → `cd py && python -m PyInstaller PngDisguiseTool.spec --noconfirm`(spec 含版本元数据与 Qt 翻译);html → `cd html && python build.py`
- exe 内部名必须 ASCII(PngDisguiseTool),拷贝成中文名用 Python(勿用 bash cp,会乱码)
- **GitHub 更新规则(用户硬性要求):禁止主动 push/更新 GitHub(含代码/Release/资产)。只有用户明确说了才执行;可以提示用户"有更新可推送",但绝不自作主张**
