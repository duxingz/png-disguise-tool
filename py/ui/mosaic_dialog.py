# -*- coding: utf-8 -*-
"""
打码编辑对话框:马赛克/黑/白笔刷涂抹;完成后可「保存打码图」或「打码后伪装」。
"""
from __future__ import annotations

import os

from PIL import Image
from PySide6.QtCore import Qt, QPoint, QRect, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSlider,
    QFileDialog, QWidget, QMessageBox,
)

from pngdisguise import image_processor as ip


class MosaicCanvas(QWidget):
    """打码画布:图片完整适应窗口,滚轮缩放(以鼠标为锚点)、右键拖动平移、双击复位;
    涂抹在原图图层上进行,任意缩放级别下笔刷位置精确。"""

    MODE_MOSAIC, MODE_BLACK, MODE_WHITE = 0, 1, 2

    def __init__(self, img_path: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.orig = Image.open(img_path).convert("RGBA")
        self.img = self.orig.copy()
        self.brush = 24
        self.mode = self.MODE_MOSAIC
        self._painting = False
        self._panning = False
        self._pan_start = None
        self._undo_stack: list[Image.Image] = []
        # 源图缓存为 QImage(绘制用,避免每帧 PIL→bytes)
        data = self.orig.tobytes("raw", "RGBA")
        self._src = QImage(data, self.orig.width, self.orig.height, QImage.Format_RGBA8888).copy()
        self._zoom = 1.0          # 相对"适应窗口"的倍数(1 = 完整适应)
        self._pan = QPoint(0, 0)
        self._stroke_to(QPoint(0, 0)) if False else None

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
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f0f0f0"))
        sc, ox, oy = self._view()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        from PySide6.QtCore import QRectF
        p.drawImage(QRectF(ox, oy, self.orig.width * sc, self.orig.height * sc), self._src)
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
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._push_undo()
            self._painting = True
            self._stroke_to(e.position().toPoint())
        elif e.button() == Qt.RightButton:
            self._panning = True
            self._pan_start = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._painting:
            self._stroke_to(e.position().toPoint())
        elif self._panning and self._pan_start is not None:
            delta = e.position().toPoint() - self._pan_start
            self._pan += QPoint(delta.x(), delta.y())
            self._pan_start = e.position().toPoint()
            self._clamp_pan()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._painting = False
        elif e.button() == Qt.RightButton:
            self._panning = False

    def mouseDoubleClickEvent(self, e):
        self._fit()
        self.update()

    def _stroke_to(self, pos):
        fx, fy = self._to_imgf(pos)
        x, y = int(fx), int(fy)
        sc, _, _ = self._view()
        r = max(1, int(self.brush / 2 / sc))
        if self.mode == self.MODE_BLACK:
            self._paint_circle(x, y, r, (0, 0, 0, 255))
        elif self.mode == self.MODE_WHITE:
            self._paint_circle(x, y, r, (255, 255, 255, 255))
        else:
            self._paint_mosaic(x, y, r)
        self.update()

    def _paint_circle(self, cx, cy, r, color):
        from PIL import ImageDraw
        d = ImageDraw.Draw(self.img)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    def _paint_mosaic(self, cx, cy, r):
        """马赛克:以块采样填色。"""
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

    # ---- 撤销/重置 ----
    def _push_undo(self):
        self._undo_stack.append(self.img.copy())
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)

    def undo(self):
        if self._undo_stack:
            self.img = self._undo_stack.pop()
            self.update()
            return True
        return False

    def reset(self):
        self._undo_stack.clear()
        self.img = self.orig.copy()
        self._fit()
        self.update()


class MosaicDialog(QDialog):
    def __init__(self, parent, img_path: str, cover_path: str, badge: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("打码编辑")
        self.resize(720, 620)
        self.cover_path = cover_path
        self.badge = badge  # 批量时画进封面的导入序号
        self.result_path: str | None = None

        lay = QVBoxLayout(self)
        self.canvas = MosaicCanvas(img_path)
        lay.addWidget(self.canvas, 1)

        # 笔刷
        bar = QHBoxLayout()
        for text, mode in [("马赛克", MosaicCanvas.MODE_MOSAIC),
                           ("黑色", MosaicCanvas.MODE_BLACK),
                           ("白色", MosaicCanvas.MODE_WHITE)]:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setChecked(mode == MosaicCanvas.MODE_MOSAIC)
            b.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            self._mode_btns = getattr(self, "_mode_btns", [])
            self._mode_btns.append(b)
            bar.addWidget(b)
        bar.addStretch(1)
        self.lbl_size = QLabel("笔刷 24")
        bar.addWidget(self.lbl_size)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(8, 80)
        self.slider.setValue(24)
        self.slider.valueChanged.connect(lambda v: (setattr(self.canvas, "brush", v),
                                                    self.lbl_size.setText(f"笔刷 {v}")))
        bar.addWidget(self.slider)
        lay.addLayout(bar)

        # 撤销/重置
        row2 = QHBoxLayout()
        b_undo = QPushButton("撤销")
        b_undo.clicked.connect(lambda: self.canvas.undo())
        b_reset = QPushButton("重置")
        b_reset.clicked.connect(lambda: self.canvas.reset())
        row2.addWidget(b_undo)
        row2.addWidget(b_reset)
        row2.addStretch(1)
        lay.addLayout(row2)

        # 完成操作
        row3 = QHBoxLayout()
        b_save = QPushButton("保存打码图")
        b_save.setStyleSheet("font-size:15px;padding:8px 20px;")
        b_save.clicked.connect(self._save_mosaic)
        b_disguise = QPushButton("打码后伪装")
        b_disguise.setStyleSheet("font-size:15px;padding:8px 20px;")
        b_disguise.clicked.connect(self._mosaic_then_disguise)
        row3.addWidget(b_save)
        row3.addWidget(b_disguise)
        lay.addLayout(row3)

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
            cover = ip.make_cover(w, h, self.cover_path, badge=self.badge)
            data = ip.disguise_static(png, cover_image=cover)
            self.result_path = ip.save_temp(data)
            os.remove(png)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "伪装失败", str(e))

    def _write_temp_png(self):
        import tempfile
        fd, path = tempfile.mkstemp(prefix="mosaic_", suffix=".png")
        with os.fdopen(fd, "wb") as f:
            self.canvas.img.save(f, format="PNG")
        return path
