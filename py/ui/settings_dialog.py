# -*- coding: utf-8 -*-
"""设置对话框:伪装首帧封面。"""
from __future__ import annotations

import os
import shutil

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from pngdisguise import image_processor as ip
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox,
)


class SettingsDialog(QDialog):
    def __init__(self, parent, current_cover: str, bg_color: str = "#2563EB",
                 transparent: bool = False, keep_meta: bool = False):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self._current = current_cover
        self._selected = current_cover
        self._bg_color = bg_color
        self._transparent = transparent
        self._keep_meta = keep_meta

        lay = QVBoxLayout(self)
        title = QLabel("伪装首帧封面")
        title.setStyleSheet("font-size:16px;font-weight:600;")
        lay.addWidget(title)
        tip = QLabel("生成伪装图时,默认展示这张封面;\n按图片尺寸等比缩放居中,四周蓝底补齐。")
        tip.setStyleSheet("color:#777;")
        lay.addWidget(tip)

        # 与网页端一致的提醒:封面不需要太大
        warn = QLabel("⚠ 封面图不需要太大:过大的图片会被自动缩小到 512px 以内,\n太大还会拖慢处理速度。建议直接使用 512×512 左右的图片。")
        warn.setStyleSheet("background:#fff7e6;border-left:4px solid #f59e0b;color:#92600a;padding:6px 10px;")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        # 背景色:色谱选择 + 透明开关
        bg_row = QHBoxLayout()
        bg_label = QLabel("封面背景")
        bg_row.addWidget(bg_label)
        from PySide6.QtWidgets import QColorDialog, QCheckBox
        self.btn_color = QPushButton(self._bg_color)
        self.btn_color.setFixedSize(70, 28)
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self.btn_color.clicked.connect(self._pick_color)
        self._update_color_btn()
        bg_row.addWidget(self.btn_color)
        self.chk_transparent = QCheckBox("透明(不补底)")
        self.chk_transparent.setChecked(self._transparent)
        self.chk_transparent.toggled.connect(lambda v: setattr(self, "_transparent", v))
        bg_row.addWidget(self.chk_transparent)
        bg_row.addStretch(1)
        lay.addLayout(bg_row)

        # 元数据开关:默认去除原图元数据,可选保留
        self.chk_meta = QCheckBox("保留原图元数据(EXIF/NovelAI 参数,默认去除)")
        self.chk_meta.setChecked(self._keep_meta)
        self.chk_meta.toggled.connect(lambda v: setattr(self, "_keep_meta", v))
        lay.addWidget(self.chk_meta)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(180, 180)
        self.preview.setStyleSheet("background:#f0f0f0;border:1px solid #ddd;")
        lay.addWidget(self.preview, alignment=Qt.AlignHCenter)
        self._update_preview()

        row = QHBoxLayout()
        btn_pick = QPushButton("选择封面图片…")
        btn_pick.clicked.connect(self._pick)
        btn_reset = QPushButton("恢复内置默认")
        btn_reset.clicked.connect(self._reset)
        row.addWidget(btn_pick)
        row.addWidget(btn_reset)
        lay.addLayout(row)

        self.lbl_path = QLabel("")
        self.lbl_path.setStyleSheet("color:#999;font-size:11px;")
        self.lbl_path.setWordWrap(True)
        lay.addWidget(self.lbl_path)
        self._update_path_label()

        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _update_preview(self):
        try:
            img = Image.open(self._selected or self._current)
            img.thumbnail((170, 170), Image.LANCZOS)
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            self.preview.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            self.preview.setText("(无封面)")

    def _update_path_label(self):
        self.lbl_path.setText(f"当前: {os.path.basename(self._selected)}" if self._selected else "当前: 内置默认")

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择封面图片", "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            # 复制到用户数据目录(打包版也可写;不依赖原文件);过大自动缩小到 512px 内
            try:
                from PIL import Image as PILImage
                with PILImage.open(path) as im:
                    im = im.convert("RGBA")
                    if max(im.size) > 512:
                        sc = 512 / max(im.size)
                        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), PILImage.LANCZOS)
                        shrunk = True
                    else:
                        shrunk = False
                dest = os.path.join(ip.user_data_dir(), "custom_cover.png")
                im.save(dest, "PNG")
                self._selected = dest
                self._update_preview()
                self._update_path_label()
                if shrunk:
                    QMessageBox.information(self, "封面已设置", "图片较大,已自动缩小到 512px 以内。\n(封面不需要太大,建议直接使用 512×512 左右)")
            except Exception as e:
                QMessageBox.warning(self, "设置失败", str(e))

    def _reset(self):
        self._selected = ""
        self._update_preview()
        self._update_path_label()

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(
            QColor(self._bg_color), self, "选择封面背景色")
        if color.isValid():
            self._bg_color = color.name()          # "#rrggbb"
            self._transparent = False              # 选了具体颜色即退出透明
            self.chk_transparent.setChecked(False)
            self._update_color_btn()

    def _update_color_btn(self):
        self.btn_color.setStyleSheet(
            f"background:{self._bg_color}; border:1px solid #999; border-radius:4px;")
        self.btn_color.setText("")

    def selected_cover(self) -> str:
        # 返回实际封面路径(为空=内置默认)
        if self._selected and os.path.isfile(self._selected):
            return self._selected
        return os.path.join(ip.resources_dir(), "default_cover.png")

    def selected_bg(self) -> str:
        return self._bg_color

    def selected_transparent(self) -> bool:
        return self._transparent

    def selected_keep_meta(self) -> bool:
        return self._keep_meta
