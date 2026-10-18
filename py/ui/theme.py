# -*- coding: utf-8 -*-
"""主题薄壳（小独爱心 / 小独夜）。

颜色与组件样式**一律**来自 `theme_xiaoduheart.py` —— 那是套件
`D:\\workwork\\UI设计规则\\xiaodu-heart-ui\\qt\\theme_xiaoduheart.py` 的**字节级掉件**
（v2.2.0）。改色只改套件的 `tokens/tokens.json`，跑一遍套件 `check_tokens.py`
全绿后重拷，**不要在本文件里写色值**。

本文件只做三件事：

1. 导出度量令牌 `SPACE` / `RADIUS` / `TYPE`（与套件 `metric_qt` 同值），
   供 widget 代码里的像素级布局使用；
2. 在套件 QSS 之后追加一层「站点层」——本程序特有的**尺寸与命名控件**约定
   （按钮 32px 高、标题/状态/提示的命名标签、卡片框、状态胶囊、预览框的
   空态虚线）。站点层引用的颜色全部是套件 palette 的键；
3. 提供 `apply_theme` / `current_palette` / `set_variant`。

**唯一的例外**：禁用态文字/描边。套件的 `disabled_text` 在 `disabled_bg` 上只有
2.22:1（WCAG 1.4.11 对 inactive 组件本可豁免），但本项目按用户要求做成 ≥3:1，
所以下面 `_DISABLED_TEXT` 是**按 disabled_bg 逐档算出来的派生值**，并写明实测值。
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from . import theme_xiaoduheart as _xh

# ------------------------------------------------------------------ metrics
SPACE = dict(_xh.SPACE)        # xs 4 / sm 8 / md 12 / lg 16 / xl 20
RADIUS = dict(_xh.RADIUS)      # xs 4 / sm 8 / md 12 / lg 16 / pill 11 / input 10
TYPE = dict(_xh.TYPE)          # caption 11 / body 12 / body_lg 13 / subtitle 14 / title 16
TYPE["display"] = 20           # 窗口标题用的一档（套件没有更大的档，站点层自持）
CONTROL_H = 32                 # 按钮总高 = 内容 22 + 上下内边距 8 + 边框 2
CONTROL_FONT = TYPE["body_lg"]  # 13

# 禁用态：light 3.13:1 / dark 3.54:1 —— 落在各自 disabled_bg 上
_DISABLED_TEXT = {"xiaodu": "#92856F", "xiaodunight": "#837B6C"}

_THEMES = {"xiaodu": _xh.LIGHT, "xiaodunight": _xh.DARK}
_LABELS = {"xiaodu": "小独爱心", "xiaodunight": "小独夜"}
_ALIASES = {"light": "xiaodu", "dark": "xiaodunight", "persona": "xiaodu"}
_ACTIVE = {"name": "xiaodu"}


def _resolve(name: str | None) -> str:
    name = _ALIASES.get(name or "", name or "")
    return name if name in _THEMES else "xiaodu"


def current_theme() -> str:
    return _ACTIVE["name"]


def current_palette() -> dict:
    return _THEMES[_ACTIVE["name"]]


def theme_labels() -> dict:
    return dict(_LABELS)


# ------------------------------------------------------------------ 站点层
# 只写尺寸与命名控件；颜色全部 {token} 代入。改这里等于改本程序的视觉约定。
_SITE_QSS = """
/* ---------- 尺寸约定 ---------- */
QPushButton {{
    min-height: {btn_content_h}px;      /* 32 总高 = 22 + 8 + 2 */
    font-size: {control_font}px;
}}

/* ---------- 禁用态：保形状、只降色（文字/描边都 ≥3:1）---------- */
QPushButton:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text_strong};
    border-color: {disabled_text_strong};
}}
/* 变体规则带 [variant=...] 属性选择器，特异性高于上面的 :disabled，
   所以每种变体都要单独再写一次禁用态，否则主/文字按钮禁用后仍是原色。 */
QPushButton[variant="primary"]:disabled,
QPushButton[variant="danger"]:disabled,
QPushButton[variant="ghost"]:disabled,
QPushButton[variant="quietDanger"]:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text_strong};
    border-color: {disabled_text_strong};
}}

/* ---------- 变体：文字按钮 / 安静的危险按钮 ---------- */
QPushButton[variant="ghost"] {{
    background: transparent;
    border-color: transparent;
    color: {text_muted};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {hover};
    border-color: {border};
    color: {text_strong};
}}
QPushButton[variant="quietDanger"] {{
    background: transparent;
    border-color: transparent;
    color: {text_muted};
}}
QPushButton[variant="quietDanger"]:hover {{
    background-color: {hover};
    border-color: {border};
    color: {danger_soft_text};
}}
/* 次级描边按钮 = 套件允许的蜜橙用法之一（"次级描边按钮"）。
   用在"可做但不急"的动作上，让橙色有一个常驻位。 */
QPushButton[variant="outlineEnergy"] {{
    background-color: {surface};
    color: {energy_text};
    /* 1px 而不是 1.5px：边框也算进控件总高，1.5 会让它比同行按钮高 2px（实测 34 vs 32） */
    border: 1px solid {energy_text};
}}
QPushButton[variant="outlineEnergy"]:hover {{
    background-color: {energy_soft};
    border-color: {energy_text};
}}
QPushButton[variant="outlineEnergy"]:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text_strong};
    border-color: {disabled_text_strong};
}}

/* ---------- 命名标签 ---------- */
/* 套件的 QWidget 底色是 canvas；放在预览框(深一档 sunken)里的容器要透明，
   否则会露出一块块 canvas 色。 */
QWidget#pane {{ background: transparent; }}
QLabel#appTitle {{
    font-size: {display}px;
    font-weight: 700;
    color: {text_strong};
    background: transparent;
}}
QLabel#previewHint {{
    font-size: {body_lg}px;
    color: {text_muted};
    background: transparent;
}}
/* 空态里那枚心粉爱心（QPixmap 现画，见 main_window._heart_pixmap）——尺寸由代码定 */
QLabel#emptyMark {{ background: transparent; }}
QLabel#statusLine {{
    font-size: {body}px;
    color: {text_muted};
    background: transparent;
}}
QLabel#duoChip {{
    font-size: {body}px;      /* 12px：双视角的唯一语义标记，别比正文还小 */
    font-weight: 600;
    /* 蜜橙 = 能量色。这两枚胶囊是"常驻橙色位"——否则橙色只在报错时才露面 */
    color: {energy_text};
    background-color: {energy_soft};
    border-radius: {radius_pill}px;
    padding: 3px 10px;
}}
QLabel#cardName {{
    font-size: {caption}px;
    color: {text_muted};
    background: transparent;
}}
QLabel#sectionTitle {{
    font-size: {subtitle}px;
    font-weight: 700;
    color: {text_strong};
    background: transparent;
}}
QLabel#hint {{
    font-size: {caption}px;
    color: {text_muted};
    background: transparent;
}}
QLabel#warnBox {{
    background-color: {energy_soft};
    border-left: 4px solid {energy_text};
    border-radius: {radius_sm}px;
    padding: 8px 10px;
    color: {energy_text};
    font-size: {body}px;
}}
QLabel#coverPreview {{
    background-color: {sunken};
    border: 1px solid {border};
    border-radius: {radius_md}px;
}}
QCheckBox {{
    font-size: {body_lg}px;
    color: {text};
    background: transparent;
}}

/* ---------- 预览框：空态虚线，有图转实线浅底 ---------- */
QFrame#previewBox {{
    background-color: {sunken};
    /* 有图时也要看得出边界：border_strong 只有 1.4:1，这里用 field 档(白卡上 3.4:1) */
    border: 2px solid {border_field};
    border-radius: {radius_lg}px;
}}
QFrame#previewBox[empty="1"] {{
    background-color: {sunken};
    border: 2px dashed {border_field};
}}
QFrame#previewBox[dragging="1"] {{
    border: 2px dashed {accent};
    background-color: {accent_soft};
}}

/* ---------- 队列卡：白底 + 1px 边；选中/当前靠边框与浅底 ---------- */
/* 列表自身的 item:selected（套件里是蓝底 + 心粉 2px 边）在这里必须关掉：
   选中态由卡片自己的 [sel="1"] 画，否则会出现"粉环 + 蓝环"两层同心框。 */
QListWidget#queueList::item:selected,
QListWidget#queueList::item:hover:!selected {{
    background: transparent;
    border: none;
}}
QFrame#queueCard {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius_md}px;
}}
/* 两种状态用两种颜色分开（套件原意：选中环 = 心粉 sel_border，当前项 = 天蓝）：
   - selected：你在列表里勾了它（心粉环，底色不动，一次可多个）
   - current ：预览窗正在显示它（天蓝环 + 浅蓝底，只有一个）
   两者同时成立时按 current 画（"正在看的那张"语义更强）。 */
QFrame#queueCard[state="selected"] {{
    border: 2px solid {sel_border};
}}
QFrame#queueCard[state="current"] {{
    border: 2px solid {accent};
    background-color: {accent_soft};
}}
QFrame#queueCard[state="none"]:hover {{
    border: 1px solid {border_field};
}}

/* ---------- 状态胶囊（成功=天蓝，四色纪律见套件）---------- */
QLabel#pillPending, QLabel#pillRunning, QLabel#pillDone, QLabel#pillFailed {{
    font-size: {caption}px;
    font-weight: 600;
    border-radius: {radius_sm}px;
    padding: 1px 7px;
    background: transparent;
}}
QLabel#pillPending {{ background-color: {surface_alt}; color: {text_muted}; }}
QLabel#pillRunning {{ background-color: {energy_soft}; color: {energy_text}; }}
QLabel#pillDone    {{ background-color: {accent_soft}; color: {accent_on_soft}; }}
/* 失败态用「描边危险橙」而不是填充：套件 palette 里没有 danger_soft 的填充档，
   而描边版在三套底色上都清楚（danger 在画布 4.9:1）。 */
QLabel#pillFailed {{
    background: transparent;
    border: 1px solid {danger};
    color: {danger_soft_text};
}}

/* ---------- 队列里的删除按钮：小、透明、hover 才红 ---------- */
QPushButton#cardDelete {{
    background: transparent;
    border: none;
    color: {text_muted};
    font-size: {title}px;
    padding: 0;
    min-height: 0;
}}
QPushButton#cardDelete:hover {{
    background-color: {hover};
    color: {danger_soft_text};
}}
"""


def _site_qss(name: str) -> str:
    pal = dict(_THEMES[name])
    pal.update(TYPE)          # caption / body / body_lg / subtitle / title / display
    for k, v in RADIUS.items():
        pal[f"radius_{k}"] = v
    for k, v in SPACE.items():
        pal[f"space_{k}"] = v
    pal["disabled_text_strong"] = _DISABLED_TEXT[name]
    pal["btn_content_h"] = CONTROL_H - 8 - 2
    pal["control_font"] = CONTROL_FONT
    return _SITE_QSS.format(**pal)


def theme_qss(name: str) -> str:
    name = _resolve(name)
    base = _xh.DARK_QSS if name == "xiaodunight" else _xh.LIGHT_QSS
    return base + _site_qss(name)


def apply_theme(app: QApplication, name: str | None) -> str:
    """套用皮肤并记住它；返回实际生效的键（xiaodu / xiaodunight）。"""
    name = _resolve(name)
    _ACTIVE["name"] = name
    app.setStyleSheet(theme_qss(name))
    return name


# ------------------------------------------------------------------ helpers
def set_variant(widget, variant: str):
    """打上 QSS 变体标签（primary / ghost / quietDanger / danger）。

    动态属性改完必须 unpolish → polish，否则已经画过的控件不会重算样式。"""
    widget.setProperty("variant", variant)
    try:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    except Exception:
        pass
    return widget


def load_theme() -> str:
    return _resolve(QSettings("pngDisguiseTool", "pngDisguiseTool").value("theme", "xiaodu"))


def save_theme(name: str) -> None:
    QSettings("pngDisguiseTool", "pngDisguiseTool").setValue("theme", _resolve(name))
