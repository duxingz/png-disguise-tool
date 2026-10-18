# -*- coding: utf-8 -*-
"""设置对话框:伪装首帧封面 + 输出选项 + 界面主题。

v1.23.0 换肤:颜色/字号/圆角全部走 `ui/theme.py`(套件掉件),不再有内联色值;
长的复选框说明拆成两行;新增「界面主题」一栏(小独爱心 / 小独夜)。
"""
from __future__ import annotations

import os
import shutil

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from pngdisguise import image_processor as ip
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox, QComboBox, QCheckBox, QFrame,
)

from .theme import SPACE, current_palette, theme_labels, set_variant


class SettingsDialog(QDialog):
    def __init__(self, parent, current_cover: str, bg_color: str = "#2563EB",
                 transparent: bool = False, keep_meta: bool = False,
                 anti_swallow: bool = True, theme: str = "xiaodu"):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(480)
        self._current = current_cover
        self._selected = current_cover
        self._bg_color = bg_color
        self._transparent = transparent
        self._keep_meta = keep_meta
        self._anti_swallow = anti_swallow
        self._theme = theme

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        lay.setSpacing(SPACE["md"])

        # ---- 封面 ----
        lay.addWidget(self._section_title("封面"))

        # 提醒:封面不需要太大(浅橙底 + 左侧色条,不用 emoji)
        warn = QLabel("封面图不需要太大：超过 512px 会被自动缩小，太大还会拖慢处理。"
                      "建议直接用 512×512 左右的图片。")
        warn.setObjectName("warnBox")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        cover_row = QHBoxLayout()
        cover_row.setSpacing(SPACE["md"])
        self.preview = QLabel()
        self.preview.setObjectName("coverPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(132, 132)
        cover_row.addWidget(self.preview)

        right = QVBoxLayout()
        right.setSpacing(SPACE["sm"])
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACE["sm"])
        btn_pick = QPushButton("选择封面图片…")
        btn_pick.clicked.connect(self._pick)
        btn_reset = QPushButton("恢复内置默认")
        set_variant(btn_reset, "ghost")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_pick)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch(1)
        right.addLayout(btn_row)

        bg_row = QHBoxLayout()
        bg_row.setSpacing(SPACE["sm"])
        bg_label = QLabel("封面背景")
        bg_label.setObjectName("hint")
        bg_row.addWidget(bg_label)
        self.btn_color = QPushButton("")
        self.btn_color.setFixedSize(44, 26)
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self.btn_color.setToolTip("点一下换背景色")
        self.btn_color.clicked.connect(self._pick_color)
        self._update_color_btn()
        bg_row.addWidget(self.btn_color)
        self.chk_transparent = QCheckBox("透明（不补底）")
        self.chk_transparent.setChecked(self._transparent)
        self.chk_transparent.toggled.connect(lambda v: setattr(self, "_transparent", v))
        bg_row.addWidget(self.chk_transparent)
        bg_row.addStretch(1)
        right.addLayout(bg_row)

        self.lbl_path = QLabel("")
        self.lbl_path.setObjectName("hint")
        self.lbl_path.setWordWrap(True)
        right.addWidget(self.lbl_path)
        right.addStretch(1)
        cover_row.addLayout(right, 1)
        lay.addLayout(cover_row)
        self._update_preview()
        self._update_path_label()

        # ---- 输出 ----
        lay.addSpacing(SPACE["xs"])
        lay.addWidget(self._section_title("输出"))
        self.chk_meta = QCheckBox("保留原图元数据\n（EXIF / NovelAI 参数；默认去除，不去除会随图外流）")
        self.chk_meta.setChecked(self._keep_meta)
        self.chk_meta.toggled.connect(lambda v: setattr(self, "_keep_meta", v))
        lay.addWidget(self.chk_meta)

        self.chk_anti = QCheckBox("防吞序号：每次伪装 / 导出随机换号 000–999\n"
                                 "（同一张图重复发会被 QQ 吞；换号可避开，推荐开启）")
        self.chk_anti.setChecked(self._anti_swallow)
        self.chk_anti.toggled.connect(lambda v: setattr(self, "_anti_swallow", v))
        lay.addWidget(self.chk_anti)

        # ---- 界面 ----
        lay.addSpacing(SPACE["xs"])
        lay.addWidget(self._section_title("界面"))
        theme_row = QHBoxLayout()
        theme_row.setSpacing(SPACE["sm"])
        theme_label = QLabel("主题")
        theme_label.setObjectName("hint")
        theme_row.addWidget(theme_label)
        self.combo_theme = QComboBox()
        for key, label in theme_labels().items():
            self.combo_theme.addItem(label, key)
        idx = self.combo_theme.findData(self._theme)
        if idx >= 0:
            self.combo_theme.setCurrentIndex(idx)
        theme_row.addWidget(self.combo_theme)
        theme_row.addStretch(1)
        lay.addLayout(theme_row)

        lay.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(SPACE["sm"])
        btns.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        set_variant(ok, "primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    def _update_preview(self):
        try:
            img = Image.open(self._selected or self._current)
            img.thumbnail((120, 120), Image.LANCZOS)
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            self.preview.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            self.preview.setText("(无封面)")

    def _update_path_label(self):
        self.lbl_path.setText(f"当前：{os.path.basename(self._selected)}"
                              if self._selected else "当前：内置默认")

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
        # 色块按钮：底色是用户选的（业务值，不是主题色），边框走当前主题
        pal = current_palette()
        self.btn_color.setStyleSheet(
            f"QPushButton {{ background:{self._bg_color};"
            f" border:1px solid {pal['border_field']};"
            f" border-radius:6px; min-height:0; }}")
        self.btn_color.setToolTip(f"封面背景色 {self._bg_color}")

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

    def selected_anti_swallow(self) -> bool:
        return self._anti_swallow

    def selected_theme(self) -> str:
        return self.combo_theme.currentData() or "xiaodu"

