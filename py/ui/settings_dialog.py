# -*- coding: utf-8 -*-
"""设置对话框:伪装首帧封面。"""
from __future__ import annotations

import os
import shutil

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from pngdisguise import image_processor as ip
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox,
)


class SettingsDialog(QDialog):
    def __init__(self, parent, current_cover: str):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(360)
        self._current = current_cover
        self._selected = current_cover

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

    def selected_cover(self) -> str:
        # 返回实际封面路径(为空=内置默认)
        if self._selected and os.path.isfile(self._selected):
            return self._selected
        return os.path.join(ip.resources_dir(), "default_cover.png")
