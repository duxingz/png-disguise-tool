# -*- coding: utf-8 -*-
"""
png伪装工具 — 主窗口(PySide6)

交互(按用户要求):
- 第一版 UI:单图预览 + 伪装/还原/打码按钮(导入单张时)
- 导入多张(拖多文件/文件夹)→ 自动切换为队列模式(列表 + 全部伪装 + 导出)
- 拖放:文件/文件夹递归(参考 pyside6-drag-import skill 模板)
- 点伪装必定生效;成功后预览区直接显示伪装的封面
- 结果不落隐藏路径:预览下按钮 = 复制到剪贴板 / 导出到…
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal, QThread, QRect, QTimer, QEvent, QPoint, QSize
from PySide6.QtGui import QAction, QImage, QPixmap, QGuiApplication, QClipboard, QPainter, QColor, QDrag, QFontMetrics, QShortcut, QKeySequence
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import (
    QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
    QListWidget, QListWidgetItem, QWidget, QMessageBox, QProgressBar,
    QButtonGroup, QAbstractButton, QScrollArea, QFrame, QSizePolicy,
    QListView, QAbstractItemView,
)

from pngdisguise import image_processor as ip

MAX_BATCH = 150
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif"}


def _default_cover_path() -> str:
    """内置封面路径:资源目录 + default_cover.png。"""
    return os.path.join(ip.resources_dir(), "default_cover.png")


# ---------------------------------------------------------------------------
# 后台处理线程(不卡 UI)
# ---------------------------------------------------------------------------

class WorkThread(QThread):
    finished_ok = Signal(str, str)     # (source_path, result_path)
    failed = Signal(str, str)          # (source_path, error)
    progressed = Signal(int, int)      # (done, total) 批量

    def __init__(self, sources: list[str], mode: str, badges: dict | None = None,
                 cover_path: str | None = None, bg_color: str | None = None,
                 transparent: bool = False, keep_meta: bool = False, parent=None):
        super().__init__(parent)
        self.sources = sources
        self.mode = mode  # "disguise" | "restore"
        self.badges = badges or {}     # source_path -> 导入序号(批量时画进封面)
        self.cover_path = cover_path
        self.bg_color = bg_color
        self.transparent = transparent
        self.keep_meta = keep_meta

    def run(self):
        total = len(self.sources)
        for i, src in enumerate(self.sources):
            try:
                if self.mode == "disguise":
                    cover_image = None
                    badge = self.badges.get(src)
                    if badge:
                        # 先解码真图尺寸,构建带序号的封面
                        from PIL import Image as _Img
                        probe = _Img.open(src)
                        w, h = probe.size
                        bg = None
                        if not self.transparent and self.bg_color:
                            bg = tuple(int(self.bg_color[i:i+2], 16) for i in (1, 3, 5))
                        cover_image = ip.make_cover(w, h, self.cover_path, badge=badge,
                                                    bg_color=bg, transparent=self.transparent)
                    data = ip.process_file(src, cover_image=cover_image,
                                           bg_color=None if cover_image else None,
                                           transparent=self.transparent and not cover_image,
                                           keep_meta=self.keep_meta)
                else:
                    data = ip.restore_file(src)
                out = ip.save_temp(data)
                self.finished_ok.emit(src, out)
            except Exception as e:
                self.failed.emit(src, str(e))
            self.progressed.emit(i + 1, total)


class ScaledLabel(QLabel):
    """pixmap 等比缩放适应控件大小显示,且不反向撑大布局。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._source: QPixmap | None = None

    def setPixmap(self, pm):
        self._source = pm
        self.update()

    def pixmap(self):
        return self._source

    def paintEvent(self, event):
        pm = self._source
        if pm is not None and not pm.isNull() and pm.width() > 0 and pm.height() > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            s = min(self.width() / pm.width(), self.height() / pm.height())
            dw, dh = max(1, int(pm.width() * s)), max(1, int(pm.height() * s))
            # 目标矩形重载:整图等比缩放到 (dw,dh) 完整绘制(此前误用原尺寸重载导致裁剪)
            painter.drawPixmap((self.width() - dw) // 2, (self.height() - dh) // 2, dw, dh, pm)
            painter.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# APNG 动画播放器(QTimer 帧轮换;帧来自 Pillow 解码,跳过默认帧/封面)
# ---------------------------------------------------------------------------

class ApngAnimPlayer(ScaledLabel):
    """按 APNG 语义播放:画布累积 + dispose/blend 合成。
    (简化播放器直接 setPixmap 每帧,会把 1×1 透明保活帧显示成空白画面。)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:transparent;")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._frames: list[QPixmap] = []
        self._delays: list[int] = []
        self._idx = 0

    def set_apng(self, path: str):
        self.stop()
        try:
            img = Image.open(path)
            n = getattr(img, "n_frames", 1)
            if n < 2 or img.size[0] <= 0:
                return
            W, H = img.size
            canvas = QImage(W, H, QImage.Format_RGBA8888)
            canvas.fill(0)  # 动画画布初始透明
            frames, delays = [], []
            for i in range(1, n):  # 跳过 seek(0) 默认帧(封面)
                img.seek(i)
                fr = img.convert("RGBA")
                dur = img.info.get("duration", 100) or 100
                disposal = img.info.get("disposal", 0)
                blend = img.info.get("blend", 0)
                fr_data = fr.tobytes("raw", "RGBA")
                frame_img = QImage(fr_data, fr.width, fr.height, QImage.Format_RGBA8888)
                painter = QPainter(canvas)
                if blend == 1:
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                else:
                    painter.setCompositionMode(QPainter.CompositionMode_Source)
                painter.drawImage(0, 0, frame_img)
                painter.end()
                if disposal == 2:  # APNG_DISPOSE_OP_PREVIOUS: 播完恢复上一画布
                    prev = canvas.copy()
                else:
                    prev = None
                frames.append(QPixmap.fromImage(canvas.copy()))
                delays.append(max(30, dur))
                if prev is not None:
                    canvas = prev
            if not frames:
                return
            self._frames, self._delays = frames, delays
            self._idx = 0
            self.setPixmap(frames[0])
            self._timer.start(delays[0])
        except Exception:
            import traceback
            traceback.print_exc()

    def stop(self):
        self._timer.stop()
        self._frames = []
        self._delays = []
        self.clear()

    def _tick(self):
        if not self._frames:
            self._timer.stop()
            return
        self._idx = (self._idx + 1) % len(self._frames)
        self.setPixmap(self._frames[self._idx])
        self._timer.start(self._delays[self._idx])


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("png伪装工具")
        self.setAcceptDrops(True)
        # 恢复上次窗口大小(记忆)
        saved_size = self._win_settings().value("windowSize")
        self.resize(saved_size if saved_size and saved_size.isValid() else __import__('PySide6.QtCore').QtCore.QSize(1000, 680))

        # 封面(用户可在设置换);兼容源码运行与 PyInstaller 打包
        self.cover_path = _default_cover_path()
        ip.DEFAULT_COVER_PATH = self.cover_path

        # 设置记忆:背景色/透明/保留元数据/笔刷(大小+类型)
        self.cover_bg = self._win_settings().value("coverBg") or "#2563EB"
        self.cover_transparent = self._win_settings().value("coverTransparent", "0") == "1"
        self.keep_meta = self._win_settings().value("keepMeta", "0") == "1"
        self.brush_size = int(self._win_settings().value("brushSize", "24"))
        self.brush_type = self._win_settings().value("brushType", "mosaic")

        # 状态
        self.queue: list[str] = []            # 待处理/处理中源图
        self.results: dict[str, str] = {}     # 源图路径 -> 结果路径
        self.status: dict[str, str] = {}      # 源图路径 -> "pending"/"done"/"failed"
        self.current_source: str | None = None  # 当前队列源(原始图)
        self._current_path: str | None = None   # 预览显示的实际文件(源/伪装结果/还原结果)
        self._current_is_result: bool = False   # 当前显示的是伪装结果(可原地还原)
        self.worker: WorkThread | None = None

        self._build_ui()
        QShortcut(QKeySequence.Paste, self, activated=self._paste_from_clipboard)

    def _win_settings(self):
        from PySide6.QtCore import QSettings
        return QSettings("pngDisguiseTool", "pngDisguiseTool")

    def closeEvent(self, event):
        # 记住窗口大小,下次启动恢复
        try:
            self._win_settings().setValue("windowSize", self.size())
        except Exception:
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 顶栏:标题 + 设置
        top = QHBoxLayout()
        title = QLabel("png伪装工具")
        title.setStyleSheet("font-size:20px;font-weight:600;")
        top.addWidget(title)
        top.addStretch(1)
        btn_settings = QPushButton("设置")
        btn_settings.clicked.connect(self._open_settings)
        top.addWidget(btn_settings)
        root.addLayout(top)

        # 预览区(大图,结果/封面显示于此;支持拖动导出与双视角)
        self.preview_stack = QFrame()
        self.preview_stack.setObjectName("previewStack")
        self.preview_stack.setStyleSheet(
            "#previewStack { background:#f2f4f9; border:2px dashed #c3c9d6; border-radius:8px; }"
            ".duo-title { font-size:12px; color:#556; background:#e8ebf3; border-radius:10px; padding:2px 12px; }"
        )
        stack_lay = QHBoxLayout(self.preview_stack)
        stack_lay.setContentsMargins(8, 8, 8, 8)

        # 单图视图
        self.preview = QLabel("把图片或文件夹拖到这里\n\n也可以点下方「选择图片」\n伪装后按住图片可拖到 QQ 发送")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("font-size:14px;color:#888;background:transparent;")
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stack_lay.addWidget(self.preview)

        # 双视角:左=对方视角(封面) / 右=点开效果(动画播放)
        self.dual = QWidget()
        self.dual.setStyleSheet("background:transparent;")
        dl = QHBoxLayout(self.dual)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(14)

        def _duo_cell(title, anim=False):
            cell = QWidget()
            cell.setStyleSheet("background:transparent;")
            v = QVBoxLayout(cell)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(6)
            t = QLabel(title)
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet("font-size:12px;color:#556;background:#e8ebf3;border-radius:10px;padding:2px 12px;")
            # 标题固定为小胶囊,不被拉伸;图片占据剩余全部空间
            t.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            if anim:
                img = ApngAnimPlayer()  # 右格 = 动画播放器本体(必须在布局内才可见)
            else:
                img = ScaledLabel()
            img.setAlignment(Qt.AlignCenter)
            img.setStyleSheet("background:transparent;")
            v.addWidget(t, 0)
            v.addWidget(img, 1)
            return cell, img

        cell_l, self.cover_view = _duo_cell("对方视角 · 不点开时")
        cell_r, self.anim_player = _duo_cell("点开效果 · 播放动画", anim=True)
        dl.addWidget(cell_l)
        dl.addWidget(cell_r)
        stack_lay.addWidget(self.dual)
        self.dual.hide()

        # 拖动导出:按住预览区拖动 → 把当前文件拖到 QQ/资源管理器
        self._drag_press_pos = None
        self.preview_stack.installEventFilter(self)
        root.addWidget(self.preview_stack, 1)

        # 单图模式操作区(第一版 UI)
        self.single_bar = QWidget()
        sb = QHBoxLayout(self.single_bar)
        sb.setContentsMargins(0, 0, 0, 0)
        self.btn_disguise = QPushButton("APNG伪装")
        self.btn_disguise.setStyleSheet("font-size:15px;padding:8px 18px;")
        self.btn_disguise.clicked.connect(self._disguise_current)
        self.btn_restore = QPushButton("还原真图")
        self.btn_restore.setStyleSheet("font-size:15px;padding:8px 18px;")
        self.btn_restore.clicked.connect(self._restore_current)
        self.btn_restore.hide()  # 仅当前是伪装文件时出现
        self.btn_mosaic = QPushButton("打码编辑…")
        self.btn_mosaic.clicked.connect(self._open_mosaic)
        self.btn_copy = QPushButton("复制")
        self.btn_copy.clicked.connect(self._copy_current)
        self.btn_export = QPushButton("导出到…")
        self.btn_export.clicked.connect(self._export_current)
        self.btn_remove_one = QPushButton("移除图片")
        self.btn_remove_one.setStyleSheet("font-size:15px;padding:8px 18px;")
        self.btn_remove_one.clicked.connect(self._remove_current)
        sb.addWidget(self.btn_disguise)
        sb.addWidget(self.btn_restore)
        sb.addWidget(self.btn_mosaic)
        sb.addWidget(self.btn_remove_one)
        sb.addStretch(1)
        sb.addWidget(self.btn_copy)
        sb.addWidget(self.btn_export)
        root.addWidget(self.single_bar)

        # 队列模式区(多图时显示)
        self.queue_panel = QWidget()
        qp = QVBoxLayout(self.queue_panel)
        qp.setContentsMargins(0, 0, 0, 0)
        qhead = QHBoxLayout()
        self.lbl_queue = QLabel("队列 (0/150)")
        self.lbl_queue.setStyleSheet("font-size:14px;font-weight:600;")
        qhead.addWidget(self.lbl_queue)
        qhead.addStretch(1)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear_queue)
        qhead.addWidget(btn_clear)
        qp.addLayout(qhead)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(False)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setSpacing(10)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setDragEnabled(False)
        self.list.setMinimumHeight(150)
        self.list.setStyleSheet("QListWidget { background:transparent; border:none; }")
        self.list.itemSelectionChanged.connect(self._sync_card_highlight)
        self.list.itemClicked.connect(self._on_queue_clicked)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._queue_context_menu)
        qp.addWidget(self.list)

        qbar = QHBoxLayout()
        self.btn_all = QPushButton("全部伪装")
        self.btn_all.setStyleSheet("font-size:15px;padding:6px 16px;")
        self.btn_all.clicked.connect(self._disguise_all)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.btn_export_all = QPushButton("导出全部结果")
        self.btn_export_all.clicked.connect(self._export_all)
        qbar.addWidget(self.btn_all)
        qbar.addWidget(self.progress, 1)
        qbar.addWidget(self.btn_export_all)
        qp.addLayout(qbar)
        root.addWidget(self.queue_panel)

        # 底部工具:选择图片 / 提示
        bottom = QHBoxLayout()
        btn_open = QPushButton("选择图片…")
        btn_open.clicked.connect(self._pick_files)
        bottom.addWidget(btn_open)
        bottom.addStretch(1)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#777;")
        bottom.addWidget(self.lbl_status)
        root.addLayout(bottom)

        self.single_bar.show()
        self.queue_panel.hide()
        self._update_buttons()

        # 防子控件拦截拖放(拖放统一由主窗口接收)
        for w in self.findChildren(QWidget):
            w.setAcceptDrops(False)
            if hasattr(w, "viewport"):
                w.viewport().setAcceptDrops(False)

    # ------------------------------------------------------------ 队列操作
    def add_images(self, paths: list[str]):
        """加图片(去重,上限)。返回 (added, rejected)。"""
        added = 0
        rejected = 0
        for p in paths:
            if p in self.queue:
                continue
            if len(self.queue) >= MAX_BATCH:
                rejected += 1
                continue
            self.queue.append(p)
            self.status[p] = "pending"
            added += 1
        self._refresh_queue_list()
        # 单张→单图 UI;多张→队列 UI
        if len(self.queue) == 1 and self.current_source is None:
            self._show_single(self.queue[0])
        elif len(self.queue) > 1:
            self._show_queue_mode()
        if added:
            self.lbl_status.setText(f"已导入 {added} 张" + (f",超限拒绝 {rejected} 张" if rejected else ""))
        return added, rejected

    def _sync_card_highlight(self):
        """选中项的卡片加蓝框,未选中去蓝框(卡片自绘边框,需显式刷新)。"""
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if w is None:
                continue
            sel = self.list.item(i).isSelected()
            cur = (self.queue[i] == self.current_source if i < len(self.queue) else False)
            border = "2px solid #2563EB" if (sel or cur) else "2px solid transparent"
            w.setStyleSheet(f"background:#fff;border:{border};border-radius:8px;")

    def _refresh_queue_list(self):
        self.list.clear()
        for i, p in enumerate(self.queue):
            st = self.status.get(p, "pending")
            is_disguise = st == "pending" and self._looks_like_disguise(p)
            if is_disguise:
                label = "伪装图·可还原"
            else:
                label = {"pending": "待处理", "processing": "处理中…", "done": "✓ 完成", "failed": "✗ 失败"}.get(st, "待处理")
            item = QListWidgetItem()
            item.setData(Qt.UserRole, p)
            item.setSizeHint(QSize(126, 138))
            self.list.addItem(item)
            card = self._build_card(p, i, label, st, cur=False)
            self.list.setItemWidget(item, card)
        self.lbl_queue.setText(f"队列 ({len(self.queue)}/{MAX_BATCH})")
        # 重建后恢复选中(当前项)并滚动到可见
        if self.current_source in self.queue:
            idx = self.queue.index(self.current_source)
            it = self.list.item(idx)
            self.list.setCurrentItem(it)
            it.setSelected(True)
            self.list.scrollToItem(it)
        self._update_buttons()

    def _build_card(self, path: str, idx: int, label: str, st: str, cur: bool) -> QWidget:
        """队列缩略图卡片:缩略图(带序号角标) + 文件名 + 状态,当前项蓝框高亮。"""
        card = QWidget()
        card.setStyleSheet(
            "background:#fff; border-radius:8px;" +
            (f"border:2px solid #2563EB;" if cur else "border:2px solid transparent;")
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(3)

        # 缩略图:伪装结果显示封面(带序号),其余显示原图
        thumb_src = self.results.get(path) if (st == "done" and path in self.results) else path
        pix = QPixmap(104, 78)
        pix.fill(QColor(238, 240, 245))
        try:
            img = Image.open(thumb_src)
            img.seek(0)
            img = img.convert("RGBA")
            img.thumbnail((104, 78), Image.LANCZOS)
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            pix = QPixmap.fromImage(qimg)
        except Exception:
            pass
        # 序号角标(左上角,黑底白字) — 与封面角标同风格
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        text = str(idx + 1)
        fm = p.fontMetrics()
        bw, bh = fm.horizontalAdvance(text) + 12, fm.height() + 4
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 158))
        p.drawRoundedRect(3, 3, bw, bh, 9, 9)
        p.setPen(QColor("white"))
        p.drawText(QRect(3, 3, bw, bh), Qt.AlignCenter, text)
        p.end()
        # 缩略图容器(叠加右上角 × 删除按钮)
        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        img_label = QLabel()
        img_label.setPixmap(pix)
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setStyleSheet("background:transparent;")
        hl.addWidget(img_label)
        btn_x = QPushButton("✕")
        btn_x.setFixedSize(20, 20)
        btn_x.setCursor(Qt.PointingHandCursor)
        btn_x.setToolTip("删除这张")
        btn_x.setStyleSheet(
            "QPushButton { background:rgba(0,0,0,140); color:white; border:none;"
            "border-radius:10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#c62828; }")
        btn_x.clicked.connect(lambda _=False, pp=path: self._remove_queue_paths([pp]))
        hl.addWidget(btn_x, 0, Qt.AlignTop)
        v.addWidget(holder)

        # 文件名(截断)
        fm = QFontMetrics(card.font())
        name = fm.elidedText(os.path.basename(path), Qt.ElideRight, 108)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size:11px;color:#555;background:transparent;")
        v.addWidget(name_label)

        # 状态
        color = {"done": "#2e7d32", "failed": "#c62828", "processing": "#1565c0"}.get(st, "#888888")
        st_label = QLabel(label)
        st_label.setStyleSheet(f"font-size:11px;color:{color};background:transparent;")
        v.addWidget(st_label)
        return card

    def _show_single(self, source: str):
        """单图模式(第一版 UI)。"""
        self.current_source = source
        # 初始:显示源图;识别若是伪装则进入"可还原"态
        self._current_path = source
        self._current_is_result = False
        self.single_bar.show()
        self.queue_panel.hide()
        self._refresh_preview_from_current()
        self._update_buttons()

    def _show_queue_mode(self):
        self.current_source = None
        self._current_path = None
        self._current_is_result = False
        self.single_bar.hide()
        self.queue_panel.show()
        # 预览区仍可显示单张(点击队列项)
        self.preview.setText("已进入批量模式\n点击左侧队列项可预览\n点「全部伪装」批量处理")
        self._update_buttons()

    def _queue_context_menu(self, pos):
        """右键:删除单项或删除多选。"""
        from PySide6.QtWidgets import QMenu
        item = self.list.itemAt(pos)
        sel = self.list.selectedItems()
        if item is None and not sel:
            return
        # 若右键点在未选中的项上 → 只选中它;否则保留当前多选
        if item is not None and item not in sel:
            self.list.clearSelection()
            item.setSelected(True)
            sel = [item]
        menu = QMenu(self)
        n = len(sel)
        act_del = menu.addAction(f"删除选中 ({n})" if n > 1 else "删除该项")
        act_clear = menu.addAction("清空队列") if n == 1 else None
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen == act_del:
            paths = [it.data(Qt.UserRole) for it in sel if it.data(Qt.UserRole)]
            self._remove_queue_paths(paths)
        elif act_clear is not None and chosen == act_clear:
            self._clear_queue()

    def canvas_brush_size(self, dlg):
        try:
            return int(dlg.canvas.brush)
        except Exception:
            return 24

    def canvas_brush_type(self, dlg):
        return {0: "mosaic", 1: "black", 2: "white"}.get(dlg.canvas.mode, "mosaic")

    def _remove_current(self):
        """单图模式:移除当前图片(等同清空当前项)。"""
        if self.current_source:
            self._remove_queue_paths([self.current_source])

    def _remove_queue_paths(self, paths):
        """从队列删除指定路径(含结果/状态/当前项处理)。"""
        if not paths:
            return
        was_current = self.current_source in paths
        for p in paths:
            if p in self.queue:
                self.queue.remove(p)
            self.results.pop(p, None)
            self.status.pop(p, None)
        if was_current or self.current_source not in self.queue:
            # 当前项被删 → 切到队列剩余最后一个(或空状态)
            if self.queue:
                self.current_source = self.queue[-1]
                self._current_path = self.results.get(self.current_source, self.current_source)
                self._current_is_result = self.current_source in self.results and self.status.get(self.current_source) == "done"
                self._refresh_preview_from_current()
            else:
                self.current_source = None
                self._current_path = None
                self._current_is_result = False
                self.anim_player.stop()
                self.dual.hide()
                self.preview.show()
                self.preview.setPixmap(QPixmap())
                self.preview.setText("把图片或文件夹拖到这里 / 点击选择 / Ctrl+V 粘贴" + chr(10) + chr(10) + "伪装后按住图片可拖到 QQ 发送")
                self.preview.setStyleSheet("font-size:14px;color:#888;background:transparent;")
        self._refresh_queue_list()
        self.lbl_status.setText(f"已删除 {len(paths)} 项")

    def _on_queue_clicked(self, item):
        from PySide6.QtCore import Qt as _Qt
        mods = QGuiApplication.keyboardModifiers()
        p = item.data(Qt.UserRole)
        if p:
            # Ctrl/Shift 点击 → 交给系统多选(itemClicked 前 Qt 已处理选择);仍预览该项
            if mods & (_Qt.ControlModifier | _Qt.ShiftModifier):
                self.current_source = p
                self._show_queue_item(p)
                self._sync_card_highlight()
                return
            # 无修饰单击 → 单选该项并预览
            self.list.clearSelection()
            item.setSelected(True)
            self.current_source = p
            self._show_queue_item(p)
            self._sync_card_highlight()

    def _show_queue_item(self, p):
        """按队列项状态预览:完成→结果(伪装双视角/还原单图);否则原图。"""
        if self.status.get(p) == "done" and p in self.results:
            self._current_path = self.results[p]
            self._current_is_result = True
        else:
            self._current_path = p
            self._current_is_result = False
        self.single_bar.show()
        if self._current_is_result:
            self._show_disguise_result(self._current_path)
        else:
            self._show_image(self._current_path)
        self._update_buttons()

    # ------------------------------------------------------------ 粘贴
    def _paste_from_clipboard(self):
        """Ctrl+V:粘贴剪贴板里的图片/文件到队列。"""
        cb = QGuiApplication.clipboard()
        mime = cb.mimeData()
        paths = []
        if mime.hasUrls():
            for u in mime.urls():
                local = u.toLocalFile()
                if local and local.lower().endswith(tuple(_IMG_EXTS)):
                    paths.append(local)
        if not paths and mime.imageData() is not None and not mime.imageData().isNull():
            # 剪贴板是位图(截图等) → 存临时 PNG 再导入
            try:
                img = mime.imageData()
                buf_dir = os.path.join(tempfile.gettempdir(), "png-disguise-paste")
                os.makedirs(buf_dir, exist_ok=True)
                path = os.path.join(buf_dir, f"粘贴图片_{int(time.time() * 1000)}.png")
                if not img.save(path, "PNG"):
                    raise RuntimeError("保存剪贴板图片失败")
                paths.append(path)
            except Exception as e:
                QMessageBox.warning(self, "粘贴失败", str(e))
                return
        if paths:
            self.add_images(paths)
        else:
            self.lbl_status.setText("剪贴板里没有图片")

    # ------------------------------------------------------------ 显示
    def _refresh_preview_from_current(self):
        """预览当前路径;若当前是伪装结果,预览封面并可原地还原。"""
        path = self._current_path
        if not path:
            return
        # 识别当前文件类型
        try:
            info = ip.inspect_file(path)
            if info["kind"] == "DISGUISE":
                self._current_is_result = True
            elif info["kind"] in ("STATIC", "GIF"):
                self._current_is_result = False
        except Exception:
            pass
        self._show_image(path)

    def _show_image(self, path: str, max_h=360):
        # 单图视图(原图/还原结果/打码图)
        self.dual.hide()
        self.preview.show()
        try:
            img = Image.open(path)
            # 若是伪装 APNG,显示其封面(首帧,批量时左上角已带导入序号角标)
            img.seek(0)
            img = img.convert("RGBA")
            # 等比缩放到预览
            img.thumbnail((900, max_h), Image.LANCZOS)
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            pm = QPixmap.fromImage(qimg)
            self.preview.setPixmap(pm)
            self.preview.setAlignment(Qt.AlignCenter)
            self.preview.setStyleSheet("font-size:14px;color:#888;background:transparent;")
        except Exception as e:
            self.preview.setText(f"无法预览: {e}")

    def _show_disguise_result(self, path: str):
        """双视角:左=对方视角(封面静态) 右=点开效果(APNG 动画播放)。"""
        self.preview.hide()
        self.dual.show()
        try:
            img = Image.open(path)
            img.seek(0)  # 封面(默认帧)
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            self.cover_view.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            pass
        self.anim_player.set_apng(path)

    def eventFilter(self, obj, event):
        # 预览区拖动导出:按住拖动 → 把当前文件拖到 QQ/资源管理器
        if obj is self.preview_stack:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_press_pos = event.position().toPoint()
            elif event.type() == QEvent.MouseMove and self._drag_press_pos is not None:
                if (event.position().toPoint() - self._drag_press_pos).manhattanLength() > 12:
                    self._drag_press_pos = None
                    self._start_drag()
            elif event.type() == QEvent.MouseButtonRelease:
                self._drag_press_pos = None
        return super().eventFilter(obj, event)

    def _start_drag(self):
        path = getattr(self, "_current_path", None)
        if not path or not os.path.isfile(path):
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def _update_buttons(self):
        has = self.current_source is not None
        done = has and self.status.get(self.current_source) == "done"
        # 当前是伪装文件 → 主按钮=还原;否则 → APNG伪装
        is_disguise = bool(getattr(self, "_current_is_result", False)) or (
            has and self._looks_like_disguise(self._current_path))
        # 伪装:普通图才可伪装;伪装文件不可再伪装
        self.btn_disguise.setEnabled(has and not is_disguise)
        self.btn_disguise.setText("APNG伪装")
        # 还原按钮:仅当前是伪装文件时显示
        self.btn_restore.setVisible(has and is_disguise)
        self.btn_restore.setEnabled(has and is_disguise)
        self.btn_mosaic.setEnabled(has and not is_disguise)
        self.btn_copy.setEnabled(has and done)
        self.btn_export.setEnabled(has and done)

    def _looks_like_disguise(self, path):
        if not path:
            return False
        try:
            return ip.inspect_file(path)["kind"] == "DISGUISE"
        except Exception:
            return False

    # ------------------------------------------------------------ 动作
    def _disguise_current(self):
        # 所见即所得:伪装的永远是当前预览显示的图(还原后的真图/打码图/原件)
        target = self._current_path or self.current_source
        if not target or not os.path.isfile(target):
            return
        if self._looks_like_disguise(target):
            self.lbl_status.setText("当前是伪装文件,请先「还原真图」再伪装")
            return
        # 结果归属到队列源(缩略图/状态跟随)
        self._run_worker([target], "disguise", single=True, result_owner=self.current_source)

    def _restore_current(self):
        if not self.current_source:
            return
        # 还原对象 = 当前显示的伪装文件
        target = self._current_path if (getattr(self, "_current_is_result", False) or
                                        self._looks_like_disguise(self._current_path)) else self.current_source
        if not self._looks_like_disguise(target):
            self.lbl_status.setText("当前不是伪装文件,无法还原")
            return
        # 还原结果归属到源(current_source),成功后按钮态复原
        self._run_worker([target], "restore", single=True, result_owner=self.current_source)

    def _disguise_all(self):
        pending = [p for p in self.queue if self.status.get(p) != "done"]
        if not pending:
            return
        self._run_worker(pending, "disguise", single=False)

    def _run_worker(self, sources, mode, single: bool, result_owner: str | None = None):
        if self.worker and self.worker.isRunning():
            return
        self._worker_owner = result_owner  # None=按 src 归属(批量);非None=单张还原归属
        self.lbl_status.setText(f"处理中… 0/{len(sources)}")
        if not single:
            self.progress.setVisible(True)
            self.progress.setMaximum(len(sources))
            self.progress.setValue(0)
        # 批量(队列>1)时给每张分配导入序号,画进封面左上角
        badges = {}
        if mode == "disguise" and len(self.queue) > 1:
            badges = {p: self.queue.index(p) + 1 for p in sources if p in self.queue}
        self.worker = WorkThread(sources, mode, badges=badges, cover_path=self.cover_path,
                                 bg_color=self.cover_bg if isinstance(self.cover_bg, str) else None,
                                 transparent=self.cover_transparent,
                                 keep_meta=self.keep_meta)
        self.worker.finished_ok.connect(lambda src, out, m=mode: self._on_one_done(src, out, m))
        self.worker.failed.connect(self._on_one_failed)
        self.worker.progressed.connect(self._on_progress)
        self.worker.finished.connect(lambda: self._on_all_done(single))
        self.worker.start()

    def _on_one_done(self, src, out, mode):
        owner = self._worker_owner if self._worker_owner is not None else src
        self.results[owner] = out
        self.status[owner] = "done"
        # 伪装成功 → 双视角预览(封面/动画),当前对象=伪装文件(可原地还原)
        # 还原成功 → 预览=真图,当前对象=普通图
        if owner == self.current_source:
            self._current_path = out
            self._current_is_result = (mode == "disguise")
            if mode == "disguise":
                self._show_disguise_result(out)
            else:
                self._show_image(out)
        self._refresh_queue_list()

    def _on_one_failed(self, src, err):
        self.status[src] = "failed"
        if src == self.current_source:
            self.lbl_status.setText(f"处理失败: {err}")
        self._refresh_queue_list()

    def _on_progress(self, done, total):
        self.lbl_status.setText(f"处理中… {done}/{total}")
        self.progress.setValue(done)

    def _on_all_done(self, single):
        self.progress.setVisible(False)
        if single and self.current_source:
            st = self.status.get(self.current_source)
            self.lbl_status.setText("已完成,可复制或导出" if st == "done" else "处理失败")
        else:
            n = sum(1 for v in self.status.values() if v == "done")
            self.lbl_status.setText(f"批量完成:{n} 张成功")
            # 对齐 html:批量完成后自动把最后完成的设为当前,双视角展示成果
            done_items = [p for p in self.queue if self.status.get(p) == "done"]
            if done_items:
                last = done_items[-1]
                self.current_source = last
                self._current_path = self.results[last]
                self._current_is_result = True
                self.single_bar.show()
                self.queue_panel.show()
                self._show_disguise_result(self._current_path)
        self._refresh_queue_list()
        self._update_buttons()

    # ------------------------------------------------------------ 复制/导出
    def _copy_current(self):
        # 复制当前显示的实际文件
        path = getattr(self, "_current_path", None)
        if not path or not os.path.isfile(path):
            return
        # 伪装 APNG → 作为文件复制(QQ 可粘贴文件,保留完整动画);普通图 → 图像复制
        if self._current_is_result or self._looks_like_disguise(path):
            self._copy_file_to_clipboard(path)
        else:
            self._copy_to_clipboard(path)

    def _copy_file_to_clipboard(self, path: str):
        """把文件(伪装 APNG)以文件形式放进剪贴板:QQ/微信粘贴=发送原文件。"""
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtGui import QGuiApplication
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(path)])
        QGuiApplication.clipboard().setMimeData(md)
        self.lbl_status.setText("伪装文件已复制,去 QQ 粘贴(发送的是文件,对方可保存原图)")

    def _copy_to_clipboard(self, path: str):
        """把普通图放进剪贴板,聊天窗口 Ctrl+V 可粘贴。"""
        try:
            img = Image.open(path)
            data = img.convert("RGBA").tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
            QGuiApplication.clipboard().setImage(qimg)
            self.lbl_status.setText("已复制到剪贴板,去聊天窗口 Ctrl+V 粘贴")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", str(e))

    def _export_current(self):
        path = getattr(self, "_current_path", None)
        if not path or not os.path.isfile(path):
            return
        suffix = "_伪装.png" if self._current_is_result else ".png"
        default_name = Path(path).stem + suffix
        target, _ = QFileDialog.getSaveFileName(self, "导出到", default_name, "PNG 图片 (*.png)")
        if target:
            import shutil
            shutil.copyfile(path, target)
            self.lbl_status.setText(f"已导出:{target}")

    def _export_all(self):
        outs = [v for k, v in self.results.items() if os.path.isfile(v)]
        if not outs:
            return
        d = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if not d:
            return
        import shutil
        count = 0
        for k, v in self.results.items():
            if os.path.isfile(v):
                try:
                    # 文件名带导入序号(与 html 版一致),解包后不会混淆
                    idx = self.queue.index(k) + 1 if k in self.queue else 0
                    name = f"{idx:03d}_{Path(k).stem}_伪装.png"
                    shutil.copyfile(v, os.path.join(d, name))
                    count += 1
                except Exception:
                    pass
        self.lbl_status.setText(f"已导出 {count} 张到 {d}")

    # ------------------------------------------------------------ 选择
    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片(可多选)", "",
            "图片 (*.png *.jpg *.jpeg *.gif)")
        if files:
            self.add_images(files)

    # ------------------------------------------------------------ 打码/设置
    def _open_mosaic(self):
        if not self.current_source:
            return
        from .mosaic_dialog import MosaicDialog
        badge = self.queue.index(self.current_source) + 1 if len(self.queue) > 1 and self.current_source in self.queue else None
        dlg = MosaicDialog(self, self.current_source, self.cover_path, badge=badge,
                           brush_size=self.brush_size, brush_type=self.brush_type,
                           bg_color=self.cover_bg if not self.cover_transparent else None)
        if dlg.exec() and dlg.result_path:
            self.brush_size = self.canvas_brush_size(dlg)
            self.brush_type = self.canvas_brush_type(dlg)
            self._win_settings().setValue("brushSize", str(self.brush_size))
            self._win_settings().setValue("brushType", self.brush_type)
            # 打码完成 → 结果作为当前图结果,预览替换
            out = dlg.result_path
            self.results[self.current_source] = out
            self.status[self.current_source] = "done"
            self._show_image(out)
            self.lbl_status.setText("打码完成,可复制或导出")
            self._refresh_queue_list()
            self._update_buttons()

    def _open_settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, self.cover_path,
                             bg_color=(self.cover_bg if isinstance(self.cover_bg, str) else "#2563EB"),
                             transparent=self.cover_transparent,
                             keep_meta=self.keep_meta)
        if dlg.exec():
            self.cover_path = dlg.selected_cover()
            self.cover_bg = dlg.selected_bg()
            self.cover_transparent = dlg.selected_transparent()
            self.keep_meta = dlg.selected_keep_meta()
            # 全部持久化
            st = self._win_settings()
            st.setValue("coverBg", self.cover_bg)
            st.setValue("coverTransparent", "1" if self.cover_transparent else "0")
            st.setValue("keepMeta", "1" if self.keep_meta else "0")
            st.setValue("appVersion", "1.0.0")  # 版本号记录在设置存储里
            ip.DEFAULT_COVER_PATH = self.cover_path

    # ------------------------------------------------------------ 清空
    def _clear_queue(self):
        self.queue.clear()
        self.results.clear()
        self.status.clear()
        self.current_source = None
        self._current_path = None
        self._current_is_result = False
        # 关闭双视角并停止动画,回到空状态单图占位(否则界面停留在旧图上像"没清空")
        self.anim_player.stop()
        self.dual.hide()
        self.preview.show()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("把图片或文件夹拖到这里 / 点击选择 / Ctrl+V 粘贴" + "\n\n" + "伪装后按住图片可拖到 QQ 发送")
        self.preview.setStyleSheet("font-size:14px;color:#888;background:transparent;")
        self.cover_view.setPixmap(QPixmap())
        self.single_bar.show()
        self.queue_panel.hide()
        self._refresh_queue_list()
        self.lbl_status.setText("已清空")


    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        local_files = []
        if md.hasUrls():
            for u in md.urls():
                local = u.toLocalFile()
                if local:
                    local_files.append(local)
        if local_files:
            files = []
            for p in local_files:
                pp = Path(p)
                if pp.is_dir():
                    files.extend(
                        str(x) for x in pp.rglob("*")
                        if x.suffix.lower() in _IMG_EXTS and x.is_file()
                    )
                elif pp.suffix.lower() in _IMG_EXTS:
                    files.append(p)
            # 自然排序
            files.sort(key=lambda x: _natural_key(Path(x).stem))
            if files:
                self.add_images(files)
        event.acceptProposedAction()


def _natural_key(name: str):
    import re
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in re.split(r"(\d+)", name)]
