# -*- coding: utf-8 -*-
"""png伪装工具 — 入口。"""
import os
import sys

# 允许直接 `python app.py` 运行(把 py/ 加入 path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("png伪装工具")
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
