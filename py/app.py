# -*- coding: utf-8 -*-
"""png伪装工具 — 入口。"""
import os
import sys

# 允许直接 `python app.py` 运行(把 py/ 加入 path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("png伪装工具")
    # Qt 内置对话框(QColorDialog 等)中文化
    translator = QTranslator(app)
    tr_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if translator.load(QLocale(QLocale.Chinese, QLocale.China), "qtbase", "_", tr_path):
        app.installTranslator(translator)
    # 窗口/任务栏图标 = logo(内置封面转制)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.ico")
    if not os.path.isfile(icon_path):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "default_cover.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
