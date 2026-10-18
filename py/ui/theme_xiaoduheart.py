# -*- coding: utf-8 -*-
"""小独爱心 Xiaodu Heart UI · PySide6 掉件主题 v2.1.0「完全体」（light + dark「小独夜」）。

与 unified_image_tool 的 ``app/ui/theme.py`` 保持同一 API 表面。v2.0.0 把 QSS
模板从紧凑档升级为**完全体**——web 端「软糖手感」设计语言整体落地桌面：

* 大圆角（卡片 16 / 控件胶囊 11 / 输入 10）、直角清零；
* 彩色填充上的文字按 tokens 的 on_action/on_danger 自动深暖墨（暗色规则）；
* 输入类聚焦 = 2px 天蓝环；输入选区 = 粉底暖墨（::selection 对应）；
* 分区标题保留小独夜同款克制度（马克笔高亮在 web 端为 h1 专属，桌面不滥用）。

色值全部来自 ``../tokens/tokens.json``（唯一事实源），改色先改 tokens
再同步这里。**只换皮不动布局**：本文件只提供 token 与 QSS，不改宿主
任何 widget 结构。宿主想拿到镜框卡片/爱心进度条（QSS 画不出的母题），
在自家 widget 上自绘并读 ``current_palette()``——unified_image_tool 的
SectionCard/HeartProgressBar 是参考实现。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------- design tokens

# 下拉箭头图片：与本文件同目录（套件 qt/ 或宿主 app/ui/，两处字节一致）。
_ARROW_DIR = Path(__file__).resolve().parent
ARROW_LIGHT = (_ARROW_DIR / "xdd_arrow_light.png").as_posix()
ARROW_DARK = (_ARROW_DIR / "xdd_arrow_dark.png").as_posix()
# 勾选图标（QSS 自绘指示器不会自带勾号，必须给图源；两枚 14×14 透明 PNG）
CHECK_LIGHT = (_ARROW_DIR / "xdd_check_light.png").as_posix()
CHECK_DARK = (_ARROW_DIR / "xdd_check_dark.png").as_posix()

# metric tokens (px) -- shared by the QSS below and by the widget components
# v2.0.0 完全体：半径对齐 web 档（卡片 16 / 控件胶囊），间距保持紧凑档
# （右栏 220px 可窄约束由 ToolPanel 的 Ignored 尺寸策略保底，实测可守）。
# v2.1.0：间距对齐 4pt 栅格（原 3/6/10/14/20），xl 保持 20 以守住右栏 220px 窄约束。
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20}
# v2.1.0：补 xs（下拉框技术角）与 pill（胶囊控件）/ input（输入框）；9px/10px 散值收回 token。
RADIUS = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "pill": 11, "input": 10}
TYPE = {"caption": 11, "body": 12, "body_lg": 13, "subtitle": 14, "title": 16}
CONTROL_PAD = "4px 10px"    # pill 手感的水平呼吸；垂直保持紧凑

# 小独爱心圆体字链：拉丁/数字落圆体（装了 M PLUS Rounded 1c 才生效），
# 中文回退微软雅黑；全部为 Windows 常见字体，缺省无害。
FONT_STACK = '"M PLUS Rounded 1c", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'

# light（亮色 · 暖白画布）—— 全部出自 tokens.json
LIGHT = {
    "canvas": "#FAF6EF",
    "surface": "#FFFFFF",
    "surface_alt": "#F5EFE4",
    "sunken": "#F0E9DC",
    "border": "#EBE4D8",
    "border_strong": "#D9CFC0",
    "border_field": "#96897A",   # v2.2.0 输入框/复选边界：白卡上 3.41:1（原 border_strong 仅 1.5:1）
    "text": "#453F36",
    "text_strong": "#3A342C",
    "text_muted": "#6C655B",
    "text_faint": "#756C60",
    "accent": "#2478A8",        # 天蓝 = 瞳色（主行动/成功态）
    "accent_hover": "#1E6A94",
    "accent_pressed": "#15506F",
    "accent_text": "#FFFFFF",
    "accent_soft": "#E9F2F8",
    "accent_on_soft": "#1E6A94",   # 软底上的蓝字档（tokens.action_text）
    "energy_text": "#A8471A",
    "energy_soft": "#FDEBDD",
    "energy_band": "rgba(240, 130, 76, 0.34)",
    "arrow_img": ARROW_LIGHT,
    "check_img": CHECK_LIGHT,
    "hover": "rgba(0, 0, 0, 0.05)",
    "pressed": "rgba(0, 0, 0, 0.09)",
    "disabled_bg": "#F3EEE5",   # 派生自 surface_alt 与 canvas 之间
    "disabled_text": "#A8A196",
    "sel_bg": "#2478A8",
    "sel_border": "#F27BAE",    # 选中环 = 心粉（爱心瞳）
    "track": "#F0E9DC",
    "handle": "#C9C0B2",
    "handle_hover": "#A79D8D",
    "tooltip_bg": "#3A342C",
    "tooltip_text": "#FAF6EF",
    "menu_bg": "#FFFFFF",
    "card_shadow": "rgba(93, 72, 42, 0.08)",
    "thumb_text": "#453F36",
    "thumb_hover": "rgba(0, 0, 0, 0.06)",
    "danger": "#B0562B",        # 深陶橙 = 危险态（v2.1.0 下移一档：白字 3.74→4.99）
    "danger_text": "#FFFFFF",   # 危险填充上的字
    "danger_soft_text": "#9A4A22",  # 危险色作文字 / 落在 danger_soft 上
    # 完全体新增（镜框卡片 / 选区 / 焦点 / 马克笔）——tokens.json 同名
    "frame": "#EFE7DA",
    "frame_hover": "#BFD9E8",
    "shadow": "rgba(93, 72, 42, 0.10)",
    "shadow_hover": "rgba(93, 72, 42, 0.14)",
    "heart_soft": "#FBE7EE",
    "heart_ring": "#F8D7E4",
    "selection_bg": "#F9C7DB",
    "selection_text": "#3A342C",
}

# dark（小独夜 · 暖黑画布，不发蓝）—— 全部出自 tokens.json
DARK = {
    "canvas": "#211E1A",
    "surface": "#322D28",       # v2.2.0 提亮一档：与 canvas 差 1.22:1（原 1.09 几乎同色）
    "surface_alt": "#262220",
    "sunken": "#1A1714",
    "border": "#4D463E",        # v2.2.0 同步提亮，卡片描边才立得住
    "border_strong": "#574F44",
    "border_field": "#837B6C",  # v2.2.0 暗色输入框边界：卡片底上 3.25:1
    "text": "#E5DFD5",
    "text_strong": "#F7F3EC",
    "text_muted": "#A79F92",
    "text_faint": "#8D857A",
    "accent": "#4E9CCB",
    "accent_hover": "#63ABD6",
    "accent_pressed": "#3B7FA8",
    "accent_text": "#10222E",   # 暗色规则：彩色填充配深暖墨字，不用白字
    "accent_soft": "#1E3442",
    "accent_on_soft": "#63ABD6",   # 软底上的蓝字档（tokens.action_text）
    "energy_text": "#F5A76B",
    "energy_soft": "#3A2A1E",
    "energy_band": "rgba(244, 155, 99, 0.38)",
    "arrow_img": ARROW_DARK,
    "check_img": CHECK_DARK,
    "hover": "rgba(255, 255, 255, 0.06)",
    "pressed": "rgba(0, 0, 0, 0.25)",
    "disabled_bg": "#2B2723",
    "disabled_text": "#6E675C",
    "sel_bg": "#4E9CCB",
    "sel_border": "#F591BD",
    "track": "#332E27",
    "handle": "#574F44",
    "handle_hover": "#6E675C",
    "tooltip_bg": "#141210",
    "tooltip_text": "#EFEAE2",
    "menu_bg": "#2B2723",
    "card_shadow": "rgba(0, 0, 0, 0.40)",
    "thumb_text": "#E5DFD5",
    "thumb_hover": "rgba(255, 255, 255, 0.06)",
    "danger": "#E08A5E",
    "danger_text": "#331507",   # 危险填充上的字（暗色规则：深暖墨）
    "danger_soft_text": "#E08A5E",  # 危险色作文字 / 落在 danger_soft 上
    # 完全体新增（镜框卡片 / 选区 / 焦点 / 马克笔）——tokens.json 同名
    "frame": "#565041",
    "frame_hover": "#3E6B87",
    "shadow": "rgba(0, 0, 0, 0.40)",
    "shadow_hover": "rgba(0, 0, 0, 0.50)",
    "heart_soft": "#3C2733",
    "heart_ring": "#4E3340",
    "selection_bg": "#5A3247",
    "selection_text": "#F7F3EC",
}


_QSS_TEMPLATE = """
/* ---------------------------------------------------------------- base */
* {{ outline: none; }}
QWidget {{
    background-color: {canvas};
    color: {text};
    font-family: {font_stack};
    font-size: {body_lg}px;
}}
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog {{
    background-color: {canvas};
}}
QLabel {{ background: transparent; }}

/* ---------------------------------------------------------------- cards */
/* QFrame#card 保留通用兜底样式（任意宿主直接用）；unified_image_tool 的
   SectionCard 在自家 paintEvent 里画镜框（暖影+白圈+浅暖环），会整体
   接管绘制，这里的背景不参与。 */
QFrame#card {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius_lg}px;
}}
QFrame#cardHeader {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {border};
}}
QLabel#cardTitle {{
    color: {text_strong};
    font-size: {title}px;
    font-weight: 700;
    background: transparent;
}}
QLabel#sectionTitle {{
    color: {text_muted};
    font-size: {caption}px;
    font-weight: 600;
    background: transparent;
}}
QLabel#hint {{
    color: {text_muted};
    font-size: {caption}px;
    background: transparent;
}}
QLabel#thumbStats {{ color: {text_muted}; padding: 2px 4px; background: transparent; }}
QFrame#statsBar {{ background: transparent; border-top: 1px solid {border}; }}
QLabel#dropZone {{
    background-color: {sunken};
    color: {text_muted};
    border: 2px dashed {border_strong};
    border-radius: {radius_lg}px;
    padding: 24px;
    font-size: {subtitle}px;
}}

/* ---------------------------------------------------------------- buttons */
/* 胶囊：radius 11 在 22px 控件上即为全胶囊；直角清零。 */
QPushButton {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: {radius_pill}px;
    padding: {control_pad};
    min-height: 14px;
}}
QPushButton:hover {{ background-color: {hover}; }}
QPushButton:pressed {{ background-color: {pressed}; }}
QPushButton:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text};
    border-color: {border};
}}
QPushButton:checked {{
    background-color: {accent_soft};
    border-color: {accent};
    color: {accent_on_soft};   /* 4.5:1；直接用 accent 只有 4.28 */
    font-weight: 600;
}}
QPushButton[variant="primary"] {{
    background-color: {accent};
    color: {accent_text};
    border-color: {accent};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background-color: {accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background-color: {accent_pressed}; }}
QPushButton[variant="primary"]:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text};
    border-color: {border};
}}
QPushButton[variant="danger"] {{
    background-color: {danger};
    color: {danger_text};
    border-color: {danger};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border-color: transparent;
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {hover};
    border-color: {border};
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {radius_pill}px;
    padding: 2px 8px;
}}
QToolButton:hover {{ background-color: {hover}; border-color: {border}; }}
QToolButton:checked {{ background-color: {accent_soft}; border-color: {accent}; }}

/* ---------------------------------------------------------------- inputs */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border_field};
    border-radius: {radius_input}px;
    padding: {control_pad};
    selection-background-color: {selection_bg};
    selection-color: {selection_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {accent};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text};
}}
QLineEdit[readOnly="true"] {{ background-color: {surface_alt}; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border_field};
    /* 右侧两个角收窄到 4px：原生下拉按钮区是方形子控件，胶囊圆角会让它
       压线裁切（v1.20 实测：6px 仍有 ~5px 残留，4px 与历史紧凑档一致、
       从未有投诉）。数字框无下拉按钮，右侧 6px 已验证干净。 */
    border-radius: {radius_input}px {radius_xs}px {radius_xs}px {radius_input}px;
    padding: {control_pad};
    min-height: 14px;
    selection-background-color: {selection_bg};
    selection-color: {selection_text};
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {accent}; }}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {accent};
}}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text};
}}
/* QComboBox::drop-down 与 QSpinBox 上下按钮刻意不样式化：不配图源样式化
   会让 Qt 停画默认箭头（在 unified_image_tool 上实测过），留给原生样式。 */
/* 下拉按钮收边 + border-trick 三角箭头：原生方盒自带深色边框会压掉
   框体右侧圆角（v1.20 实测），藏不掉就只能自己画。箭头颜色走令牌。 */
QComboBox::drop-down {{
    background: {surface};
    border: none;
    border-radius: {radius_xs}px;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: url({arrow_img});
    width: 12px; height: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {menu_bg};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: {radius_md}px;
    padding: 3px;
    /* 不写 selection-color：非聚焦弹层的"当前行"会拿 selection 背景却跳过
       selection 文字（Qt 怪癖），白字白底直接隐身。状态在下面显式画。 */
    selection-background-color: {accent};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    color: {text};
    padding: 4px 8px;
    min-height: 16px;
    border-radius: {radius_sm}px;
}}
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:hover {{
    background-color: {accent};
    color: {accent_text};
}}

/* 复选/单选指示器必须在这里显式画：全局 QSS 生效后 checked 态会丢框丢填充
   （实测：checked 的墨水反而比 unchecked 少）。checked = accent 实心。 */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {border_field};
    background-color: {surface};
}}
QCheckBox::indicator {{ border-radius: {radius_xs}px; }}   /* 圆角方块：与单选的圆点区分 */
QRadioButton::indicator {{ border-radius: {radius_sm}px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {accent};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
/* 自绘指示器不会自动画勾（QSS 接管后 Qt 停画原生勾），必须给图源 */
QCheckBox::indicator:checked {{ image: url({check_img}); }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {disabled_bg};
    border-color: {border};
}}
QCheckBox::indicator:checked:disabled, QRadioButton::indicator:checked:disabled {{
    background-color: {disabled_text};
    border-color: {disabled_text};
}}
QCheckBox {{ spacing: {space_sm}px; background: transparent; }}
QRadioButton {{ spacing: {space_sm}px; background: transparent; }}

/* ---------------------------------------------------------------- tabs */
/* 选中 tab = 柔和胶囊（accent_soft 底 + accent 字），非选中只有文字。 */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: {radius_md}px;
    background: transparent;
    top: -1px;
}}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {text_muted};
    border: 1px solid transparent;
    border-radius: {radius_sm}px;
    padding: 5px 12px;
    margin-right: 2px;
}}
QTabBar::tab:hover:!selected {{ color: {text}; background: {hover}; }}
QTabBar::tab:selected {{
    color: {accent_on_soft};
    background: {accent_soft};
    font-weight: 600;
}}
QTabBar::tab:disabled {{ color: {disabled_text}; }}

/* ---------------------------------------------------------------- lists */
QListWidget, QListView, QTreeView, QTableView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {radius_md}px;
    outline: none;
}}
QListWidget::item, QListView::item {{ border-radius: {radius_sm}px; padding: 2px; }}
QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
    background: {hover};
}}
QTableView::item:selected, QTreeView::item:selected {{
    background: {accent};
    color: {accent_text};
}}
QHeaderView::section {{
    background-color: {surface_alt};
    color: {text_muted};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 4px 6px;
    font-weight: 600;
}}
QScrollArea {{ border: none; background: transparent; }}

{thumb_select}

/* ---------------- 宿主命名控件（unified_image_tool 专用钩子） ---------------- */
/* 贴纸墙 chip：白底素材在白卡片上需要 1px 暖边 + 米底才可见 */
QListWidget#stickerWall::item {{
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: {radius_input}px;
}}
QListWidget#stickerWall::item:selected {{
    background: {accent_soft};
    border: 2px solid {sel_border};
    color: {text};
}}
/* 批量子页签：比主 tab 高一档（实心胶囊），拉开两级层级 */
QTabWidget#subTabs QTabBar::tab:selected {{
    background-color: {accent};
    color: {accent_text};
    font-weight: 600;
}}

/* ---------------------------------------------------------------- menus */
QMenu {{
    background-color: {menu_bg};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: {radius_md}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 22px 5px 12px;
    border-radius: {radius_sm}px;
}}
QMenu::item:selected {{ background-color: {accent}; color: {accent_text}; }}
QMenu::item:disabled {{ color: {disabled_text}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 6px; }}
QMenuBar {{ background: {canvas}; }}
QMenuBar::item:selected {{ background: {hover}; border-radius: {radius_sm}px; }}

/* ---------------------------------------------------------------- chrome */
QStatusBar {{
    background-color: {canvas};
    color: {text_muted};
    border-top: 1px solid {border};
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {text_muted}; }}

/* 进度条全胶囊；unified_image_tool 的 HeartProgressBar 在自家 paintEvent
   里追加"尽头爱心瞳"，这里的规则是通用宿主的兜底。 */
QProgressBar {{
    background-color: {track};
    border: none;
    border-radius: {radius_sm}px;
    text-align: center;
    /* 文字居中画在 fill 上：跟填充走 accent_text（亮=白 / 暗=深暖墨）。
       进度很低（<50%）时文字会落到轨道上，宿主应把百分比放到外部标签。 */
    color: {accent_text};
    min-height: 14px;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: {radius_sm}px; }}

QSplitter {{ background: transparent; }}
QSplitter::handle {{ background-color: {border}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QSplitter::handle:hover {{ background-color: {accent}; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {handle};
    border-radius: 5px;   /* 5 = 11px 宽度的一半（圆头把手），非散值 */
    min-height: 24px;
    min-width: 24px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {handle_hover};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{
    background: {track};
    height: 5px;
    border-radius: 3px;   /* 3 ≈ 5px 槽高的一半（圆头），非散值 */
}}
QSlider::handle:horizontal {{
    background: {accent};
    width: 16px;
    margin: -6px 0;
    border-radius: {radius_sm}px;
}}
QGroupBox {{
    border: 1px solid {border};
    border-radius: {radius_md}px;
    margin-top: 10px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {text_muted};
}}

QToolTip {{
    background-color: {tooltip_bg};
    color: {tooltip_text};
    border: 1px solid {border_strong};
    border-radius: {radius_sm}px;
    padding: 4px 6px;
}}

EditorCanvas, QGraphicsView {{ background-color: {sunken}; }}
"""

_THUMB_SELECT = """
QListWidget::item {{
    border-radius: {radius_sm}px;
    padding: 2px;
    color: {thumb_text};
}}
QListWidget::item:hover:!selected {{ background: {thumb_hover}; }}
QListWidget::item:selected {{
    background: {sel_bg};
    color: {accent_text};
    border: 2px solid {sel_border};
}}
"""


def _qss(t: dict) -> str:
    """Render the shared template with one palette (plus metric tokens)."""
    values = dict(t)
    for key, val in SPACE.items():
        values[f"space_{key}"] = val
    for key, val in RADIUS.items():
        values[f"radius_{key}"] = val
    for key, val in TYPE.items():
        values[key] = val
    values["control_pad"] = CONTROL_PAD
    values["font_stack"] = FONT_STACK
    values["thumb_select"] = _THUMB_SELECT.format(**values)
    return _QSS_TEMPLATE.format(**values)


LIGHT_QSS = _qss(LIGHT)
DARK_QSS = _qss(DARK)

# Which palette is live, for widgets that paint themselves (QSS cannot reach
# inside a custom paintEvent).
_ACTIVE = {"name": "light"}

_THEMES = {"light": LIGHT, "dark": DARK}


def current_palette() -> dict:
    """The active token dict (light or dark)."""
    return _THEMES.get(_ACTIVE["name"], LIGHT)


def current_theme() -> str:
    return _ACTIVE["name"]


def theme_qss(name: str) -> str:
    if name == "dark":
        return DARK_QSS
    return LIGHT_QSS


def apply_theme(app: QApplication, name: str) -> None:
    """Apply a theme app-wide. ``name`` is 'light' or 'dark'."""
    _ACTIVE["name"] = name if name in _THEMES else "light"
    app.setStyleSheet(theme_qss(_ACTIVE["name"]))
