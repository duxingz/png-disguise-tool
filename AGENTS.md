# png-disguise-tool — 共享决策与规格

极简"APNG 图片伪装/还原 + 打码"工具,伪装格式从 ChatChatBar 抽取。

## 已确认需求(用户拍板)
- 名称:**png伪装工具**。
- 两端:**电脑 exe(PySide6)+ 网页单文件 html,功能尽量一致**。
- 主功能:**APNG 伪装(静态图 + GIF 动态伪装)+ 伪装还原**;打码是**附带功能**,二级界面。
- 首帧封面:**默认内置一张 + 设置里可配置(背景色可设/透明可选)**;封面完整居中(等比缩小不裁剪)。
- 元数据(2026-09-09 定稿):默认**彻底清除**。NovelAI V3 把提示词隐写在 alpha 通道低位(写在 255↔254 的不透明像素上,解码器按像素顺序读 alpha 低位直到 NUL),所以伪装与还原都必须**全像素清 alpha LSB + 全透明像素 RGB 透白**,且该变换必须**幂等**(伪装↔还原循环零漂移);设置里可选"保留元数据"(伪装文件附带原 tEXt/iTXt/zTXt/eXIf 块,供其他工具还原;本工具还原输出仍是不带元数据的干净图)。
- 防吞序号(2026-10-01 定稿,可关;**exe 默认开、网页端默认关**,用户手动改过后按其选择记忆):实测 QQ 按**解码后的图像内容**做指纹去重——同一张图(普通图也一样)第一次发可见,之后重发静默秒吞,换封面序号=新内容=可发。对策:开启后每次伪装/导出(复制/导出/拖出/下载)都随机换一个 **000~999 前导零序号**画进封面并重新生成文件(连续导出不重复;导出文件名带 `_序号`);关闭则恢复旧行为(批量=导入序号,单张=无序号)。**内容/格式都不变,只有封面序号像素变**。
- 还原兼容:本工具双真图帧文件、原版 ChatChatBar [真图, 1×1保活帧] 文件、v4.0 双真图帧文件都能还原——静态取"与画布同尺寸且 **blend=0(真实内容帧,保活帧恒为 blend=1)** 的最后一帧"(2026-10-01 修正:纯尺寸过滤在 1×1 画布下会误选保活帧)。

## 架构(当前)
- `py/`:PySide6 桌面版(app.py + ui/ + pngdisguise/)。pngdisguise/apng_codec.py = 纯 Python APNG 编解码(伪装写入/检测/还原);image_processor.py = 图像处理、元数据与隐写清理。
- `html/`:纯 JS 单文件版(core.js 编解码核心 + template.html 界面 + build.py 合成单文件)。与 py 端格式契约一致,双端可互相还原(有像素级交叉回归)。
- 旧 Kotlin 模块(core/desktop/android)已彻底删除(2026-09-08)。

## 文件格式(与原 ChatChatBar 双向兼容)
`IHDR → acTL → tEXt("ChatBarApngDisguise\0ver;STATIC|ANIMATED;count") → IDAT×N(封面) → fcTL+fdAT(真图) → fcTL+fdAT(1×1 保活帧,静态) → IEND`
- 静态 = **单份真图 + 1×1 全透明保活帧(blend=1)**(原版 ChatChatBar 结构;合成时画面不变,两帧内容不同→解码器按动画处理)。exe 端 2026-09-10 起用此结构做体积优化(**只存一份真图**);**兼容读取** v4.0 的双真图帧 `[nudged, clean]` 与旧版文件。
- 帧压缩:exe 端用 Pillow 的 C 编码器(默认档:自适应滤波含 Paeth + zlib6);apng_codec 保留纯 Python 的 None 直写作为默认/兜底(`ApngWriter(compress=...)` 钩子)。**别再试自己写滤波**:曾用 Pillow 算子实现逐行自适应(None/Sub/Up),实测真实图片反而比 Pillow 默认大 0~3%(且 3~4 倍耗时),已回退。
- 封面与静态真图写入前都做隐写清理(全像素 alpha LSB 清零 + 全透明透白 + 剥离元数据块;keep_meta=True 时附带元数据块并跳过白名单重组)。
- GIF 动态伪装:真图帧 = GIF 各帧原样写入(GIF 无 8 位 alpha 通道,无隐写可能,不做清理)。

## 常量
- 格式版本 1;上限版本 2;输出 ≤100MB;单帧 ≤1250 万像素(exe;网页端 GIF 帧仍为 800 万)。
- 默认封面:内置图(≤512px,蓝底 #2563EB)。用户已明确**不要"轻量封面"**(渐变+文字)功能——曾实现过,2026-09-10 按用户要求整块删除,别再提。

## 当前形态(重要,2026-09 定稿)
- **exe(PySide6)**:py/ 目录,主桌面版(项目根 png伪装工具.exe)。功能:伪装/还原/GIF 动态伪装/批量(150)/队列缩略图卡片(单选/多选/右键删除)/Ctrl+V 粘贴/拖动导出/双视角预览/打码(滚轮缩放+右键平移)/封面设置(背景色/透明/512 自动缩小)/元数据开关/**防吞序号(设置里开关,导出自动换号重伪装)**/窗口大小记忆/伪装 APNG 复制以文件方式。
- **html 单文件**:html/build.py 生成,免安装跨端(手机浏览器可用)。功能与 exe 对齐,差异:下载/下载全部(≤30 逐张,>30 zip);封面设置(背景色/透明/元数据/防吞序号,**2026-10-01 修复了弹窗控件从未绑定保存的 bug**——此前改动被静默丢弃)localStorage 持久化;打码支持双指捏合/平移;**下载伪装结果时自动换号重伪装**(文件名带 `_序号`)。**体积结构已与 exe 同步(单真图帧 + 1×1 保活帧)**。**GIF 动态伪装已支持(2026-09-10)**:用浏览器内置 `ImageDecoder` 取帧(直接拿到已合成帧 + 每帧时长,不用自己写 GIF 解析),限单帧 ≤800 万像素、总 ≤6000 万像素(**比 exe 的 3 亿保守**:浏览器要把所有帧读进内存);浏览器不支持(Chrome/Edge 94+、Safari 16.4+、Firefox 130+)或超限时**退回静态首帧并在状态栏说明原因**。**打码后的图也能直接「下载」保存**(打码 OK 后置 `_mosaicDone` 使下载按钮可用,文件名 `原名_打码.png`)。
- exe+html 体积优化(2026-09-10):① 静态伪装只存**一份真图** + 1×1 保活帧(不再双真帧,两端一致)② 帧压缩改用 **Pillow 的 C 编码器**(比原 None 直写小 ~20%,且更快)。实测伪装图 **−36%~−53%**(人像1 1145→735KB、风景1 1691→1027KB、11512 3963→1882KB);6MP 整张 ~0.66s。
- html 靠 V8 JIT + CompressionStream(JS 端本就是逐行自适应滤波,含 Paeth)。
- 已知外部限制:QQ 图片消息会转码丢 APNG 动画→引导用户"文件方式发送/勾选原图"(两端说明栏都有此提示);浏览器剪贴板消毒,html 无法复制文件到剪贴板。

## 界面（v1.23.0 起，改 UI 前必读）

- **皮肤 = 小独爱心 / 小独夜**（`D:\workwork\UI设计规则\xiaodu-heart-ui` 的字节级掉件
  `py/ui/theme_xiaoduheart.py`）。改色**只改套件** `tokens/tokens.json`，跑套件
  `scripts/check_tokens.py` 全绿后**重拷**掉件；`py/ui/theme.py` 只是薄壳 + 站点层。
- **四色配额（套件 v2.3.0 硬规则）**：每套 UI 至少一个「主正常态」四色同框，其余状态 ≥3 色。
  本程序四个落点：**粉** = 批量进度条的爱心瞳（`py/ui/heart_bar.py`）+ 队列选中环 + 空态爱心（`PreviewLabel`）；
  **橙** = 双视角胶囊 + 「打码编辑…」蜜橙描边（`variant="outlineEnergy"`）+ 空态关键词 + 处理中/警告；
  **蓝** = 主操作、「选择图片…」在队列空时升为主按钮（`_sync_open_button`）；**暖白** = 画布。
  自查：`check_usage.py --render py/_qa_shots/xiaodu_empty.png`（或任一主正常态截图）。
- **`py/ui/theme.py` 的三块**：① 度量令牌 `SPACE/RADIUS/TYPE`（与套件 `metric_qt` 同值，
  另有站点级 `display=20`）；② `_SITE_QSS` 站点层——按钮 32px 高/13px 字、三档变体
  （`primary` / 默认=次按钮 / `ghost` / `quietDanger`）、命名标签（`appTitle`、`previewHint`、
  `statusLine`、`duoChip`、`cardName`、`sectionTitle`、`hint`、`warnBox`、`coverPreview`）、
  预览框（`QFrame#previewBox` + `empty`/`dragging` 属性）、队列卡（`QFrame#queueCard` + `state`）、
  状态胶囊（`pillPending/Running/Done/Failed`）；③ `apply_theme/current_palette/set_variant`。
  队列卡的两种状态是 `state="selected"`（心粉环）/ `"current"`（天蓝环 + 浅蓝底）——别再合并成一个 `sel`。
- **两条死规矩**：
  1. **不要用无选择器的 `setStyleSheet`**——Qt 会把规则级联给该控件**所有子控件**。旧版
     选中队列卡时这么干，结果卡片里每个 QLabel 都套上 2px 蓝框（四层同心蓝框）。
     要换状态就改动态属性（`setProperty("state","selected")`）+ unpolish/polish。
  2. **不要用 `setFixedHeight` 硬顶按钮高度**——主题 QSS 的 `min-height` 会覆盖它；
     尺寸统一写进站点层，个别控件用只含度量的控件级样式表。
- **验收门 `py/qa_render.py`**（新增）：`C:\Users\qu\miniconda3\python.exe qa_render.py`
  → 两套皮肤各 9 张图落 `py/_qa_shots/`（不入库），并跑 36 条断言（含**四色齐**像素门禁：空态与批量进行中四色齐、单图态 ≥3 色）：按钮统一 32/13、
  队列按钮封顶 200、选中靠属性、预览空态标记、**打码对话框可用 brush_size/brush_type 构造**、
  皮肤招牌色、小窗不越界、以及**伪装→还原逐像素一致**。改 UI 后必须先跑它全绿。
- **打码对话框 bug（v1.23.0 修）**：`MainWindow._open_mosaic()` 一直传
  `brush_size=` / `brush_type=`，而 `MosaicDialog.__init__` 没这两个参数 → 点「打码编辑…」
  直接 TypeError、对话框永远打不开（打包版无控制台 = "点了没反应"）。现在参数接上，
  笔刷记忆真的生效；`qa_render.py` 里有回归锁。
- **离线渲染的坑**：`QT_QPA_PLATFORM=offscreen` 时 **windows11 样式画不出按钮底**
  （日志 `OpenThemeData() failed for theme 0 (BUTTON)`，实测填充=边框=`#EFEFEF`）。
  接 QSS 之前靠系统样式的地方，离屏图会显得"按钮只有文字"——那是假象，别当缺陷报；
  接了 QSS 之后按钮由样式表绘制，离屏才可信。

## 交付物与发布规则(重要)
- `png伪装工具.exe`(项目根):PyInstaller 打包,**每次改 py/ 源码后必须重新打包并更新**
- `png伪装工具.html`(项目根):**每次改 core.js/template.html 后必须重新 build 并更新**
- `png伪装工具.zip`:对外分享包 = `png伪装工具/` 目录下的 exe + html + **apk** + 使用说明.txt(**2026-10-02 起不再含测试图片**,用户指定;注意实际文件名是 `png伪装工具.zip`,不是早期文档写的「分享版」);**exe/html/apk 任何更新后必须同步重打**
- 打包命令:exe → `cd py && python -m PyInstaller PngDisguiseTool.spec --noconfirm`(spec 含版本元数据与 Qt 翻译);html → `cd html && python build.py`
- exe 内部名必须 ASCII(PngDisguiseTool),拷贝成中文名用 Python(勿用 bash cp,会乱码)
- **GitHub 更新规则(用户硬性要求):禁止主动 push/更新 GitHub(含代码/Release/资产)。只有用户明确说了才执行;可以提示用户"有更新可推送",但绝不自作主张**



