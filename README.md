# png伪装工具

把图片伪装成 APNG 动画：聊天软件里对方不点开时只能看到封面，点击原图即可查看到原本的图片，伪装过的图像导入回本工具即可还原。附带打码编辑、批量处理。全程本地处理，图片不会上传。

## 🚀 在线使用（已部署）

**https://spiffy-lolly-4f10ae.netlify.app/** —— 网页版直接在线用，无需下载，手机浏览器同样可用。

## 📦 下载

- **GitHub Release**: https://github.com/duxingz/png-disguise-tool/releases —— `png伪装工具.zip`（含 Windows exe 免安装版 + 网页版 html + 使用说明）
- 网页版也可直接下载本仓库 `deploy/index.html` 单文件，双击用浏览器打开即用

## ✨ 功能

- **APNG 伪装**：静态图/截图伪装成 APNG —— 对方不点开只见封面，点开才见真图
- **伪装还原**：把收到的伪装文件拖回本工具 →「还原真图」→ 逐像素还原原图
- **批量处理**：一次拖入文件夹/多图（上限 150），批量伪装，封面按导入顺序带序号角标
- **打码编辑**：马赛克 / 黑 / 白笔刷，支持缩放与平移（网页端支持双指捏合）
- **封面可配置**：内置默认封面，可自选（过大自动缩小到 512px）

## 🖥 双端形态

| 形态 | 说明 |
|---|---|
| **网页版** `deploy/index.html` / `html/` | 单文件 html，跨平台（Windows/Mac/手机浏览器），双击即用 |
| **桌面版** `py/`（Windows exe） | PySide6，拖放导入/拖动导出/Ctrl+V 粘贴截图，体验最顺 |

## 📖 使用要点（发到 QQ 等平台）

- QQ 以“图片消息”发送会把 APNG 压缩转码、丢失动画 —— 请伪装后【下载文件】，以**文件**方式发送（手机发图勾选「原图」）
- 对方保存文件后拖回本工具 → 能还原 = 文件完整

## 🔧 伪装格式（与原 ChatChatBar 双向兼容）

- 结构：`IHDR → acTL → tEXt("ChatBarApngDisguise") → IDAT(封面) → fcTL+fdAT(真图) [+1×1保活帧 blend=1] → IEND`
- 限制：单帧 ≤800 万像素；输出 ≤100MB

## 📁 仓库结构

| 路径 | 说明 |
|---|---|
| `html/` | **网页版源码**：`template.html`（界面+逻辑）、`core.js`（伪装编解码核心，与桌面版同格式）、`build.py`（把核心+封面内嵌生成单文件 html） |
| `deploy/index.html` | **已生成的网页版单文件**（部署用，Netlify/GitHub Pages 直接传这个） |
| `py/` | **Windows 桌面版源码**（PySide6，当前主版本）：`app.py` 入口、`pngdisguise/`（编解码+图像处理）、`ui/`（主窗/打码/设置）、`assets/`（内置封面）、`启动png伪装工具.bat` |
| `使用说明.txt` | 在分享 zip 内，面向普通用户的图文说明（源码同时收录在 `py/使用说明.txt`） |

## ⚙ 本地构建

- 网页版：改 `html/` 后运行 `python html/build.py`，输出单文件 `png伪装工具.html`
- exe：`cd py && python -m PyInstaller --onefile --windowed --name PngDisguiseTool --icon assets/app_icon.ico --add-data "assets;assets" app.py`
