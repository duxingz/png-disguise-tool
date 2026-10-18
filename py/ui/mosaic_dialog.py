# -*- coding: utf-8 -*-
"""打码编辑对话框:马赛克/黑/白笔刷涂抹;完成后可「保存打码图」或「打码后伪装」。

v1.23.0
- 修掉一个真 bug:`MainWindow._open_mosaic()` 一直传 `brush_size=` / `brush_type=`,
  但本类的 `__init__` 没有这两个参数 → 点「打码编辑…」直接 TypeError,对话框
  永远打不开(打包版没控制台,表现就是"点了没反应")。现在参数接上了,笔刷记忆
  也真的生效。
- 换肤:颜色/字号/圆角全部走 `ui/theme.py`(套件掉件),不再有内联 15px 字号;
  画布底色取 palette 的 sunken。
- 加一行操作提示(滚轮缩放/右键平移/双击复位)——这三个手势原本没有任何提示。
"""
from __future__ import annotations

import os

from PIL import Image
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSlider,
    QFileDialog, QWidget, QMessageBox,
)

from pngdisguise import image_processor as ip
from .theme import SPACE, TYPE, current_palette, set_variant

_BRUSH_MODES = {"mosaic": 0, "black": 1, "white": 2}


class MosaicCanvas(QWidget):
    """打码画布:图片完整适应窗口,滚轮缩放(以鼠标为锚点)、右键拖动平移、双击复位;
    涂抹在原图图层上进行,任意缩放级别下笔刷位置精确。

    v1.23.1 修：**画布从来不显示笔迹** —— paintEvent 画的是 __init__ 里给原图拍的
    那张快照 `_src`，而所有涂抹都改在 PIL 的 `self.img` 上，两者从此再没同步过。
    现在维护一份 QImage 镜像 `_qimg`，每次落笔只把**笔刷外接框那几十像素**从 PIL
    拷进镜像（整图转换在 8MP 上会卡死鼠标移动）。
    同时补上：笔刷圆环光标（跟随缩放与笔刷大小）、快速拖动时的插值（原来是分段圆点）。
    """

    MODE_MOSAIC, MODE_BLACK, MODE_WHITE = 0, 1, 2

    def __init__(self, img_path: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.orig = Image.open(img_path).convert("RGBA")
        self.img = self.orig.copy()
        self.brush = 24
        self.mode = self.MODE_MOSAIC
        self._painting = False
        self._panning = False
        self._pan_start = None
        self._undo_stack: list[Image.Image] = []
        # 显示用镜像：内容必须始终等于 self.img（paintEvent 只画它）
        self._qimg = self._to_qimage(self.orig)
        self._zoom = 1.0          # 相对"适应窗口"的倍数(1 = 完整适应)
        self._pan = QPoint(0, 0)
        self._mouse_pos = None    # 控件坐标，用来画笔刷圆环
        self._last_img_pt = None  # 上一个落笔点（图像坐标），用于插值

    # ---- QImage 镜像 ----
    @staticmethod
    def _to_qimage(pil_img: Image.Image) -> QImage:
        data = pil_img.tobytes("raw", "RGBA")
        return QImage(data, pil_img.width, pil_img.height,
                      QImage.Format_RGBA8888).copy()

    def _rebuild_mirror(self):
        self._qimg = self._to_qimage(self.img)

    def _sync_region(self, x0, y0, x1, y1):
        """把 PIL 图的一块同步进 QImage 镜像（笔刷级增量，很便宜）。"""
        w, h = self.img.size
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(w, int(x1)), min(h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        crop = self.img.crop((x0, y0, x1, y1))
        data = crop.tobytes("raw", "RGBA")
        qi = QImage(data, x1 - x0, y1 - y0, 4 * (x1 - x0),
                    QImage.Format_RGBA8888).copy()
        p = QPainter(self._qimg)
        p.drawImage(x0, y0, qi)
        p.end()

    # ---- 视图变换 ----
    def _contain(self):
        s = min(self.width() / self.orig.width, self.height() / self.orig.height)
        return s if s > 0 else 1.0

    def _view(self):
        """返回 (scale, ox, oy):图像→控件的完整变换(contain×zoom + 居中 + 平移)。"""
        base = self._contain() * self._zoom
        dw, dh = self.orig.width * base, self.orig.height * base
        cx, cy = (self.width() - dw) / 2, (self.height() - dh) / 2
        return base, cx + self._pan.x(), cy + self._pan.y()

    def _clamp_pan(self):
        base = self._contain() * self._zoom
        dw, dh = self.orig.width * base, self.orig.height * base
        max_x = max(0, (dw - self.width()) / 2)
        max_y = max(0, (dh - self.height()) / 2)
        self._pan = QPoint(int(min(max(self._pan.x(), -max_x), max_x)),
                           int(min(max(self._pan.y(), -max_y), max_y)))

    def _fit(self):
        self._zoom = 1.0
        self._pan = QPoint(0, 0)

    # ---- 绘制 ----
    def paintEvent(self, e):
        pal = current_palette()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal["sunken"]))
        sc, ox, oy = self._view()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(ox, oy, self.orig.width * sc, self.orig.height * sc), self._qimg)
        # 笔刷圆环光标（屏幕像素 = 笔刷像素 × 当前缩放）
        if self._mouse_pos is not None and not self._panning:
            rad = max(3.0, self.brush / 2.0 * sc)
            center = QPointF(self._mouse_pos)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(0, 0, 0, 150), 3.0))
            p.drawEllipse(center, rad, rad)
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            p.drawEllipse(center, rad, rad)
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._clamp_pan()
        self.update()

    def _redraw(self):
        self.update()

    # ---- 坐标换算 ----
    def _to_imgf(self, pos):
        sc, ox, oy = self._view()
        return (pos.x() - ox) / sc, (pos.y() - oy) / sc

    # ---- 交互:滚轮缩放 / 右键平移 / 双击复位 / 左键涂抹 ----
    def wheelEvent(self, e):
        anchor = e.position().toPoint()
        img_pt = self._to_imgf(anchor)
        factor = 1.25 if e.angleDelta().y() > 0 else 0.8
        self._zoom = min(10.0, max(1.0, self._zoom * factor))
        if self._zoom <= 1.0:
            self._pan = QPoint(0, 0)
        else:
            sc, _, _ = self._view()
            self._pan = QPoint(int(anchor.x() - img_pt[0] * sc), int(anchor.y() - img_pt[1] * sc))
            self._clamp_pan()
        self._mouse_pos = anchor
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._push_undo()
            self._painting = True
            self._last_img_pt = None
            self._stroke_to(e.position().toPoint())
        elif e.button() == Qt.RightButton:
            self._panning = True
            self._pan_start = e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            self.update()

    def mouseMoveEvent(self, e):
        self._mouse_pos = e.position().toPoint()
        if self._painting:
            self._stroke_to(e.position().toPoint())
        elif self._panning and self._pan_start is not None:
            delta = e.position().toPoint() - self._pan_start
            self._pan += QPoint(delta.x(), delta.y())
            self._pan_start = e.position().toPoint()
            self._clamp_pan()
            self.update()
        else:
            self.update()          # 只为了让圆环跟着鼠标走

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._painting = False
            self._last_img_pt = None
        elif e.button() == Qt.RightButton:
            self._panning = False
            self.setCursor(Qt.CrossCursor)
            self.update()

    def mouseDoubleClickEvent(self, e):
        self._fit()
        self.update()

    def leaveEvent(self, e):
        self._mouse_pos = None
        self.update()
        super().leaveEvent(e)

    def _stroke_to(self, pos):
        """落笔：与上一个点之间按 1/4 笔刷步长插值，快速拖动也不会画成虚线。"""
        fx, fy = self._to_imgf(pos)
        sc, _, _ = self._view()
        r = max(1, int(self.brush / 2 / sc))
        points = [(fx, fy)]
        if self._last_img_pt is not None:
            lx, ly = self._last_img_pt
            dist = ((fx - lx) ** 2 + (fy - ly) ** 2) ** 0.5
            step = max(1.0, r * 0.5)
            n = int(dist // step)
            if n > 1:
                points = [((lx + (fx - lx) * i / n), (ly + (fy - ly) * i / n))
                          for i in range(1, n)] + [(fx, fy)]
        self._last_img_pt = (fx, fy)

        box = None
        for (px, py) in points:
            b = self._stamp(int(px), int(py), r)
            if b is None:
                continue
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
        if box is not None:
            self._sync_region(*box)
        self.update()

    def _stamp(self, x, y, r):
        if self.mode == self.MODE_BLACK:
            self._paint_circle(x, y, r, (0, 0, 0, 255))
            return (x - r - 1, y - r - 1, x + r + 2, y + r + 2)
        if self.mode == self.MODE_WHITE:
            self._paint_circle(x, y, r, (255, 255, 255, 255))
            return (x - r - 1, y - r - 1, x + r + 2, y + r + 2)
        return self._paint_mosaic(x, y, r)

    def _paint_circle(self, cx, cy, r, color):
        from PIL import ImageDraw
        d = ImageDraw.Draw(self.img)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    def _paint_mosaic(self, cx, cy, r):
        """马赛克:以块采样填色。返回被改动的外接框（供增量同步镜像）。"""
        from PIL import ImageDraw
        block = max(6, r // 3)
        d = ImageDraw.Draw(self.img)
        w, h = self.img.size
        x0 = max(0, (cx - r) // block * block)
        y0 = max(0, (cy - r) // block * block)
        x1 = min(w, ((cx + r + block - 1) // block * block) + block)
        y1 = min(h, ((cy + r + block - 1) // block * block) + block)
        for by in range(y0, y1, block):
            for bx in range(x0, x1, block):
                sx = min(max(bx + block // 2, 0), w - 1)
                sy = min(max(by + block // 2, 0), h - 1)
                color = self.img.getpixel((sx, sy))
                d.rectangle([bx, by, min(bx + block, w), min(by + block, h)], fill=color)
        return (x0, y0, x1 + 1, y1 + 1)

    # ---- 撤销/重置 ----
    def _push_undo(self):
        self._undo_stack.append(self.img.copy())
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)

    def undo(self):
        if self._undo_stack:
            self.img = self._undo_stack.pop()
            self._rebuild_mirror()      # 镜像必须跟着回滚，否则画面不变
            self.update()
            return True
        return False

    def reset(self):
        self._undo_stack.clear()
        self.img = self.orig.copy()
        self._rebuild_mirror()
        self._fit()
        self.update()


class MosaicDialog(QDialog):
    def __init__(self, parent, img_path: str, cover_path: str, badge: int | None = None,
                 bg_color: str = "#2563EB", transparent: bool = False,
                 brush_size: int = 24, brush_type: str = "mosaic"):
        super().__init__(parent)
        self.setWindowTitle("打码编辑")
        self.resize(760, 640)
        self.cover_path = cover_path
        self.badge = badge  # 批量时画进封面的导入序号
        self.bg_color = bg_color
        self.transparent = transparent
        self.result_path: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        lay.setSpacing(SPACE["sm"])
        self.canvas = MosaicCanvas(img_path)
        self.canvas.brush = max(8, min(80, int(brush_size or 24)))
        self.canvas.mode = _BRUSH_MODES.get(brush_type or "mosaic", 0)
        lay.addWidget(self.canvas, 1)

        # 笔刷：三档模式(可勾选,选中态由主题 QSS 的 QPushButton:checked 呈现)
        bar = QHBoxLayout()
        bar.setSpacing(SPACE["sm"])
        self._mode_btns = []
        for text, mode in (("马赛克", MosaicCanvas.MODE_MOSAIC),
                           ("黑色", MosaicCanvas.MODE_BLACK),
                           ("白色", MosaicCanvas.MODE_WHITE)):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setChecked(mode == self.canvas.mode)
            b.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            self._mode_btns.append(b)
            bar.addWidget(b)
        bar.addSpacing(SPACE["md"])
        self.lbl_size = QLabel(f"笔刷 {self.canvas.brush}")
        self.lbl_size.setObjectName("hint")
        bar.addWidget(self.lbl_size)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(8, 80)
        self.slider.setValue(self.canvas.brush)
        self.slider.setMinimumWidth(140)
        self.slider.valueChanged.connect(self._on_brush)
        bar.addWidget(self.slider, 1)
        lay.addLayout(bar)

        # 手势提示(滚轮/右键/双击原本无任何提示)
        hint = QLabel("滚轮缩放 · 右键拖动平移 · 双击复位 · Ctrl+Z 撤销")
        hint.setObjectName("hint")
        lay.addWidget(hint)

        # 撤销/重置
        row2 = QHBoxLayout()
        row2.setSpacing(SPACE["sm"])
        b_undo = QPushButton("撤销")
        set_variant(b_undo, "ghost")
        b_undo.setShortcut("Ctrl+Z")
        b_undo.clicked.connect(lambda: self.canvas.undo())
        b_reset = QPushButton("重置")
        set_variant(b_reset, "ghost")
        b_reset.clicked.connect(lambda: self.canvas.reset())
        row2.addWidget(b_undo)
        row2.addWidget(b_reset)
        row2.addStretch(1)
        lay.addLayout(row2)

        # 完成操作：打码后伪装是主路径(这是伪装工具)，单独保存是次路径
        row3 = QHBoxLayout()
        row3.setSpacing(SPACE["sm"])
        b_save = QPushButton("只保存打码图")
        b_save.clicked.connect(self._save_mosaic)
        b_disguise = QPushButton("打码后直接伪装")
        set_variant(b_disguise, "primary")
        b_disguise.clicked.connect(self._mosaic_then_disguise)
        row3.addStretch(1)
        row3.addWidget(b_save)
        row3.addWidget(b_disguise)
        lay.addLayout(row3)

    def _on_brush(self, v):
        self.canvas.brush = v
        self.lbl_size.setText(f"笔刷 {v}")

    def _set_mode(self, m):
        self.canvas.mode = m
        for i, b in enumerate(self._mode_btns):
            b.setChecked(i == m)

    def _save_mosaic(self):
        """保存打码 PNG(内部临时),复制/导出交给主窗口。"""
        # 把打码图写临时 PNG,设置结果并 accept
        self.result_path = self._write_temp_png()
        self.accept()

    def _mosaic_then_disguise(self):
        png = self._write_temp_png()
        try:
            from PIL import Image as _Img
            with _Img.open(png) as probe:
                w, h = probe.size
            cover = ip.make_cover(w, h, self.cover_path, badge=self.badge,
                                  bg_color=self._hex_to_rgb(self.bg_color),
                                  transparent=self.transparent)
            data = ip.disguise_static(png, cover_image=cover)
            self.result_path = ip.save_temp(data)
            # 保留打码源图:主窗口导出"换号重伪装"时要用它重新生成
            self.mosaic_source_path = png
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "伪装失败", str(e))

    @staticmethod
    def _hex_to_rgb(hexstr):
        hexstr = (hexstr or "#2563EB").lstrip("#")
        return tuple(int(hexstr[i:i+2], 16) for i in (0, 2, 4))

    def _write_temp_png(self):
        import tempfile
        fd, path = tempfile.mkstemp(prefix="mosaic_", suffix=".png")
        with os.fdopen(fd, "wb") as f:
            self.canvas.img.save(f, format="PNG")
        return path

