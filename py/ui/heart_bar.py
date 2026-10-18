# -*- coding: utf-8 -*-
"""小独爱心「爱心瞳进度条」。

纯自绘：米色胶囊轨 + 天蓝胶囊填充，填充尽头骑一枚**心粉爱心**（左上白高光点）。
这是小独四色里"粉色"在本程序的**常驻合法落点**——套件规定粉色只许进爱心形状。

移植自 `unified_image_tool/app/ui/widgets.py::HeartProgressBar`（那边已过视觉验收），
色值全部读 `theme.current_palette()`，不手写颜色。
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QProgressBar

from .theme import current_palette


def heart_path(cx: float, cy: float, s: float) -> QPainterPath:
    """心形路径（进度条爱心瞳与空态爱心共用同一形状）。"""
    path = QPainterPath()
    path.moveTo(cx, cy + s * 0.32)
    path.cubicTo(cx - s * 0.58, cy - s * 0.04, cx - s * 0.26,
                 cy - s * 0.48, cx, cy - s * 0.14)
    path.cubicTo(cx + s * 0.26, cy - s * 0.48, cx + s * 0.58,
                 cy - s * 0.04, cx, cy + s * 0.32)
    path.closeSubpath()
    return path


class HeartProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setMinimumHeight(16)

    def paintEvent(self, event):
        pal = current_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        rad = r.height() / 2

        # 米轨胶囊
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal["track"]))
        p.drawRoundedRect(r, rad, rad)

        # 天蓝填充胶囊
        rng = max(1, self.maximum() - self.minimum())
        frac = 0.0 if rng == 0 else (self.value() - self.minimum()) / rng
        frac = min(1.0, max(0.0, frac))
        cw = int(round(r.width() * frac))
        chunk = QRect(r.x(), r.y(), max(0, cw), r.height())
        if cw > rad:
            p.setBrush(QColor(pal["accent"]))
            p.drawRoundedRect(chunk, rad, rad)

        # 爱心瞳骑在填充尽头（有进度才出现）——18px 级别，浅色底上也一眼认得
        if cw > r.height() * 0.8:
            cx = chunk.right() - r.height() * 0.42
            cy = r.center().y() + r.height() * 0.04
            s = r.height() * 1.55
            p.setPen(QPen(QColor(pal["surface"]), 1.4))
            p.setBrush(QColor(pal["sel_border"]))     # 心粉 = 点睛色
            p.drawPath(heart_path(cx, cy, s))
            # 左上白高光点（瞳孔图腾的高光）
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(cx - s * 0.17, cy - s * 0.20),
                          s * 0.09, s * 0.09)

        # 百分比文字：轨道区/填充区各自裁剪，两段底色各自配可读字色
        txt = f"{int(round(frac * 100))}%"
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        chunk_region = QRegion(chunk)
        rest = QRegion(r) - chunk_region
        p.save()
        p.setClipRegion(chunk_region)
        p.setPen(QColor(pal["accent_text"]))
        p.drawText(r, Qt.AlignCenter, txt)
        p.restore()
        p.save()
        p.setClipRegion(rest)
        p.setPen(QColor(pal["text"]))
        p.drawText(r, Qt.AlignCenter, txt)
        p.restore()

