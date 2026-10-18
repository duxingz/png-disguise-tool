# -*- coding: utf-8 -*-
"""界面自检 + 视觉 QA 渲染（v1.23.0 起随源码走）。

跑法（必须用 miniconda 的那个 python）：

    C:\\Users\\qu\\miniconda3\\python.exe qa_render.py            # 两套皮肤都跑
    C:\\Users\\qu\\miniconda3\\python.exe qa_render.py xiaodu      # 只跑浅色

产物：`_qa_shots/<皮肤>_<场景>.png`（空态 / 单图 / 双视角 / 队列 / 队列完成 /
小窗 / 设置 / 打码，共 8 张 × 2 皮肤）。

它同时是一道**回归门**（任一断言失败 exit code 1）：

1. 动作按钮高度一律 32px、字号 13px（旧版 39/35/25 三套混排）；
2. 队列两枚按钮宽度封顶 200px（旧版被拉满到半屏）；
3. 队列卡选中只切 `sel` 属性，不再给子控件套蓝框；
4. 预览框：空态 `empty=1`，载图后 `empty=0`；
5. **打码对话框必须能用 `brush_size` / `brush_type` 构造**——它此前签名不匹配，
   点「打码编辑…」直接 TypeError、对话框永远打不开（v1.23.0 修）；
6. 主题切换后样式表里应出现该皮肤的招牌色；
7. 伪装 → 还原 往返像素级一致（核心功能不被皮肤改动带坏）。

注意：脚本把 QSettings 重定向到临时目录，**不碰**用户真实设置。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from PySide6.QtCore import QSettings, QSize  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import (QApplication, QPushButton, QStyleFactory,  # noqa: E402
                               QFrame)

OUT = HERE / "_qa_shots"
OUT.mkdir(exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="pngtool_qa_"))
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.Scope.UserScope, str(TMP))

app = QApplication.instance() or QApplication([])
for _p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
           r"C:\Windows\Fonts\segoeui.ttf"):
    if os.path.exists(_p):
        QFontDatabase.addApplicationFont(_p)
app.setFont(QFont("Microsoft YaHei UI", 9))
for _s in ("windows11", "windowsvista", "Fusion"):
    if _s in QStyleFactory.keys():
        app.setStyle(_s)
        break

from PIL import Image, ImageDraw  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import CONTROL_FONT, CONTROL_H, apply_theme  # noqa: E402
from pngdisguise import image_processor as ip  # noqa: E402

FAILS = []

# 小独四色（套件 tokens 里的角色色值，亮/暗各一套）——用于"四色齐"门禁。
# 每个角色给多个合法取值：填充档、软底档、作文字用的深档都算这色"出现了"。
ROLE_COLOURS = {
    "xiaodu": {
        "底": ["#FAF6EF", "#FFFFFF"],
        "天蓝": ["#2478A8", "#1E6A94", "#E9F2F8"],
        "蜜橙": ["#FDEBDD", "#A8471A", "#F0824C"],
        "心粉": ["#F27BAE", "#B22F5E", "#FBE7EE"],
    },
    "xiaodunight": {
        "底": ["#211E1A", "#322D28"],
        "天蓝": ["#4E9CCB", "#63ABD6", "#1E3442"],
        "蜜橙": ["#3A2A1E", "#F5A76B", "#F49B63"],
        "心粉": ["#F591BD", "#F7AFCB", "#3C2733"],
    },
}


def count_roles(pm, theme: str) -> dict:
    from collections import Counter

    cnt = Counter()
    img = pm.toImage()
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            cnt[img.pixelColor(x, y).name().upper()] += 1
    return {role: sum(cnt.get(h.upper(), 0) for h in hexes)
            for role, hexes in ROLE_COLOURS[theme].items()}


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def photo(path, tone=40):
    im = Image.new("RGB", (420, 300), (tone, tone + 20, tone + 60))
    d = ImageDraw.Draw(im)
    d.ellipse([100, 60, 320, 240], fill=(220, 190, 170))
    d.text((14, 14), Path(path).name, fill=(255, 255, 255))
    im.save(path)
    return str(path)


def shoot(widget, name, size=None):
    if size:
        widget.resize(*size)
    widget.show()
    for _ in range(5):
        app.processEvents()
    pm = widget.grab()
    pm.save(str(OUT / f"{name}.png"))
    print(f"      {name}.png  {pm.width()}x{pm.height()}")
    return pm


def run_theme(theme: str):
    print(f"\n=== {theme} ===")
    apply_theme(app, theme)
    check(f"[{theme}] 样式表已挂到 QApplication",
          bool(app.styleSheet()) and len(app.styleSheet()) > 4000)
    signature = {"xiaodu": "#FAF6EF", "xiaodunight": "#211E1A"}[theme]
    check(f"[{theme}] 样式表里是该皮肤的招牌底色 {signature}",
          signature.upper() in app.styleSheet().upper())

    paths = [photo(TMP / f"{theme}_p{i}.png", 30 + i * 20) for i in range(4)]
    w = MainWindow()
    w._theme = theme
    w.resize(1000, 680)
    w.show()
    for _ in range(4):
        app.processEvents()

    # 1) 空态（同时也是四色齐的第一张证据图：爱心=粉、关键词=橙、主按钮=蓝）
    pm_empty = shoot(w, f"{theme}_empty", (1000, 680))
    got = count_roles(pm_empty, theme)
    check(f"[{theme}] 空态四色齐（暖白/天蓝/蜜橙/心粉）",
          all(v > 0 for v in got.values()), got)
    check(f"[{theme}] 空态预览框 empty=1", w.preview_stack.property("empty") == "1")

    # 2) 单图（≥3 色：蓝主按钮 + 橙描边「打码编辑…」 + 暖白；粉色留给空态/批量/选中）
    w.add_images([paths[0]])
    app.processEvents()
    pm_single = shoot(w, f"{theme}_single", (1000, 680))
    got = count_roles(pm_single, theme)
    check(f"[{theme}] 单图态至少三色", sum(1 for v in got.values() if v > 0) >= 3, got)
    check(f"[{theme}] 载图后预览框 empty=0", w.preview_stack.property("empty") == "0")

    # 按钮度量：动作条上的每个按钮都该 32 高 / 13 号字
    btns = [b for b in w.findChildren(QPushButton)
            if b.isVisible() and b.objectName() != "cardDelete"]
    bad = [(b.text(), b.height(), b.font().pixelSize()) for b in btns
           if b.height() != CONTROL_H or b.font().pixelSize() != CONTROL_FONT]
    check(f"[{theme}] 按钮统一 {CONTROL_H}px 高 / {CONTROL_FONT}px 字",
          not bad, bad[:4])

    # 3) 双视角
    cover = ip.make_cover(420, 300, str(HERE / "assets" / "default_cover.png"),
                          bg_color=(0x25, 0x63, 0xEB))
    dis = ip.save_temp(ip.disguise_static(paths[0], cover_image=cover))
    w._show_disguise_result(dis)
    for _ in range(3):
        app.processEvents()
    shoot(w, f"{theme}_dual", (1000, 680))

    # 4) 队列
    w.add_images(paths[1:])
    app.processEvents()
    shoot(w, f"{theme}_queue", (1000, 680))
    check(f"[{theme}] 队列两枚按钮宽度封顶 200",
          w.btn_all.width() <= 200 and w.btn_export_all.width() <= 200,
          (w.btn_all.width(), w.btn_export_all.width()))

    # 5) 队列里含完成/处理中
    w.status[paths[1]] = "done"
    w.results[paths[1]] = dis
    w.status[paths[2]] = "processing"
    w._refresh_queue_list()
    w.current_source = paths[1]
    w._show_queue_item(paths[1])
    w._sync_card_highlight()
    for _ in range(3):
        app.processEvents()
    shoot(w, f"{theme}_queue_done", (1000, 680))

    cards = [w.list.itemWidget(w.list.item(i)) for i in range(w.list.count())]
    sel_cards = [c for c in cards if c is not None
                 and c.property("state") in ("current", "selected")]
    check(f"[{theme}] 选中/当前卡用 state 属性标记（不是给子控件套样式）",
          len(sel_cards) == 1, len(sel_cards))
    # 子控件不该被写上 border（旧 bug：无选择器的 setStyleSheet 级联）
    leaked = [c for c in cards if c is not None and "border" in c.styleSheet()]
    check(f"[{theme}] 卡片自身没有内联 border 样式", not leaked, len(leaked))

    # 5b) 失败态 + 批量进度条 + 「选中(粉环)/当前(蓝环)」两种卡片状态
    #     —— 同时也是「四色齐」的证据图：暖白底、天蓝环/进度、蜜橙胶囊、心粉爱心+选中环
    w.status[paths[2]] = "failed"
    w._refresh_queue_list()
    w.progress.setVisible(True)
    w.progress.setRange(0, 100)
    w.progress.setValue(42)
    # 再勾一张"非当前"的卡 → 它会拿到心粉选中环
    sel_row = 2 if len(w.queue) > 2 else 0
    w.list.blockSignals(True)
    w.list.item(sel_row).setSelected(True)
    w.list.blockSignals(False)
    w._sync_card_highlight()
    for _ in range(3):
        app.processEvents()
    pm = shoot(w, f"{theme}_queue_failed", (1000, 680))
    pills = [lbl.objectName() for lbl in w.findChildren(type(w.lbl_queue))
             if lbl.objectName().startswith("pill")]
    check(f"[{theme}] 队列里有失败胶囊", "pillFailed" in pills, sorted(set(pills)))
    check(f"[{theme}] 批量进度条可显示并带填充", w.progress.isVisible()
          and w.progress.value() == 42)
    states = sorted({c.property("state") for c in
                     (w.list.itemWidget(w.list.item(i)) for i in range(w.list.count()))
                     if c is not None})
    check(f"[{theme}] 选中／当前两种卡片状态各自出现", {"current", "selected"} <= set(states),
          states)
    # ---- 四色齐（套件 v2.3.0 的硬规则）----
    got = count_roles(pm, theme)
    check(f"[{theme}] 批量进行中四色齐（暖白/天蓝/蜜橙/心粉）",
          all(v > 0 for v in got.values()), got)
    w.progress.setVisible(False)

    # 6) 小窗
    w.add_images(paths)
    app.processEvents()
    shoot(w, f"{theme}_queue_small", (760, 500))
    over = [b for b in w.findChildren(QPushButton)
            if b.isVisible() and b.mapTo(w, b.rect().topLeft()).y() + b.height()
            > w.height()]
    check(f"[{theme}] 小窗下没有控件越出窗口底边", not over, len(over))

    # 7) 设置
    from ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(w, str(HERE / "assets" / "default_cover.png"),
                         bg_color="#2563EB", theme=theme)
    shoot(dlg, f"{theme}_settings")
    check(f"[{theme}] 设置里主题下拉可读出当前皮肤", dlg.selected_theme() == theme,
          dlg.selected_theme())
    dlg.close()

    # 8) 打码（回归锁：此前 brush_size/brush_type 会 TypeError）
    from ui.mosaic_dialog import MosaicDialog
    md = MosaicDialog(w, paths[0], str(HERE / "assets" / "default_cover.png"),
                      brush_size=42, brush_type="black")
    pm = shoot(md, f"{theme}_mosaic")
    check(f"[{theme}] 打码对话框可用 brush_size/brush_type 构造",
          md.canvas.brush == 42 and md.canvas.mode == 1,
          (md.canvas.brush, md.canvas.mode))

    # 8b) 落笔必须真的画到**屏幕上**（v1.23.1 修：以前画的是 __init__ 里的原图快照，
    #     涂了半天画面一点不变 —— 用户报的「无法显示笔刷」就是这个）
    from PySide6.QtCore import QPoint
    cvs = md.canvas
    cvs.resize(560, 400)
    for _ in range(3):
        app.processEvents()

    def grab_canvas():
        for _ in range(3):
            app.processEvents()
        return cvs.grab().toImage()

    sc, ox, oy = cvs._view()
    cx = int(ox + cvs.orig.width * 0.5 * sc)
    cy = int(oy + cvs.orig.height * 0.5 * sc)
    img0 = grab_canvas()
    cvs._push_undo()
    cvs._last_img_pt = None
    cvs._stroke_to(QPoint(cx, cy))          # 黑色笔刷落一笔
    img1 = grab_canvas()
    changed = 0
    for dy in range(-14, 15, 2):
        for dx in range(-14, 15, 2):
            if img0.pixelColor(cx + dx, cy + dy) != img1.pixelColor(cx + dx, cy + dy):
                changed += 1
    check(f"[{theme}] 打码落笔后画布像素确实变化（笔迹可见）", changed > 40,
          f"changed={changed}/225")

    # 8c) 镜像与 PIL 结果必须一致（防止两边再次脱节）
    pil_px = cvs.img.getpixel((cvs.orig.width // 2, cvs.orig.height // 2))
    q_px = cvs._qimg.pixelColor(cvs.orig.width // 2, cvs.orig.height // 2)
    check(f"[{theme}] 画布镜像与打码结果一致",
          abs(pil_px[0] - q_px.red()) <= 2 and abs(pil_px[1] - q_px.green()) <= 2
          and abs(pil_px[2] - q_px.blue()) <= 2,
          f"pil={pil_px[:3]} q={q_px.name()}")

    # 8d) 撤销后画面回到原图
    cvs.undo()
    img2 = grab_canvas()
    back = sum(1 for dy in range(-14, 15, 4) for dx in range(-14, 15, 4)
               if img2.pixelColor(cx + dx, cy + dy) == img0.pixelColor(cx + dx, cy + dy))
    check(f"[{theme}] 撤销后画布回到落笔前", back >= 56, f"same={back}/64")

    # 8e) 笔刷圆环光标可见（跟随鼠标、随缩放变大）
    # 注意：圆环是半透明白描边叠在照片上，不保证出现"纯白像素"，所以按
    # "设置鼠标位置前后有多少像素变了"来判断，不按亮度阈值。
    cvs._mouse_pos = QPoint(cx, cy)
    img3 = grab_canvas()
    ring = sum(1 for dy in range(-40, 41) for dx in range(-40, 41)
               if img3.pixelColor(cx + dx, cy + dy) != img2.pixelColor(cx + dx, cy + dy))
    check(f"[{theme}] 笔刷圆环光标画出来了", ring >= 30, f"changed_px={ring}")

    md.close()

    w.close()


def check_roundtrip():
    """核心功能回归：伪装 → 还原 必须逐像素还原（与皮肤无关，防手滑碰到处理链）。"""
    print("\n=== 往返像素校验 ===")
    src = photo(TMP / "roundtrip.png", 90)
    cover = ip.make_cover(420, 300, str(HERE / "assets" / "default_cover.png"),
                          bg_color=(0x25, 0x63, 0xEB))
    disguised = ip.save_temp(ip.disguise_static(src, cover_image=cover))
    check("伪装文件被识别为 DISGUISE",
          ip.inspect_file(disguised)["kind"] == "DISGUISE")
    restored = ip.save_temp(ip.restore_file(disguised))
    a = Image.open(src).convert("RGB")
    b = Image.open(restored).convert("RGB")
    same = a.size == b.size and a.tobytes() == b.tobytes()
    diff = None
    if not same:
        import numpy as np
        diff = float(np.abs(np.asarray(a, dtype=int) - np.asarray(b, dtype=int)).mean()) \
            if a.size == b.size else "size mismatch"
    check("还原后与原图逐像素一致", same, "" if same else f"mean diff={diff}")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    themes = ["xiaodu", "xiaodunight"] if which == "both" else [which]
    try:
        for t in themes:
            run_theme(t)
        check_roundtrip()
    finally:
        # 别在 %TEMP% 里留脚手架（每次跑都会 mkdtemp 一个）
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"\nshots -> {OUT}")
    if FAILS:
        print(f"\n{len(FAILS)} 项失败：")
        for f in FAILS:
            print("  -", f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

