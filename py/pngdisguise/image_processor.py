# -*- coding: utf-8 -*-
"""
图像处理层:用 Pillow 读写图片,把静态图/GIF 伪装成 APNG,还原伪装。
封面 = 蓝底 + 完整图等比缩放居中(contain,类似 CCB 大象封面)。
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from PIL import Image

from . import apng_codec

# 内置默认封面路径(运行时由 main 注入;None = 用纯蓝底占位)
DEFAULT_COVER_PATH: str | None = None


def resources_dir() -> str:
    """内置资源目录:PyInstaller 打包 → sys._MEIPASS/assets;源码运行 → py/assets。"""
    import sys
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "assets")
    # 源码:本文件在 py/pngdisguise/,上级=py/
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets")


def user_data_dir() -> str:
    """用户可写数据目录(存自定义封面等):%APPDATA%/png伪装工具。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "png伪装工具")
    os.makedirs(d, exist_ok=True)
    return d

COVER_BG = (0x25, 0x63, 0xEB)  # #2563EB
MAX_FRAME_PIXELS = 8_000_000
MAX_TOTAL_PIXELS = 300_000_000
MAX_INPUT_BYTES = 100 * 1024 * 1024

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif"}


class ImageError(Exception):
    pass


# ---------------------------------------------------------------------------
# Pillow 帧 → codec 需要的行访问器
# ---------------------------------------------------------------------------

class _PillowFrame:
    """把 RGBA Pillow Image 包成 (width,height,get_row_rgba)。"""

    def __init__(self, img: Image.Image):
        self.img = img.convert("RGBA")
        self.width, self.height = self.img.size
        # 整图 RGBA bytes(行优先),get_row_rgba 直接切片
        self._buf = self.img.tobytes()
        self._stride = self.width * 4

    def get_row_rgba(self, y):
        s = y * self._stride
        return self._buf[s:s + self._stride]


def _load_image(path: str) -> Image.Image:
    try:
        return Image.open(path)
    except Exception as e:
        raise ImageError(f"无法打开图片: {e}")


# ---------------------------------------------------------------------------
# 封面适配(蓝底 contain)
# ---------------------------------------------------------------------------

def make_cover(canvas_w: int, canvas_h: int, cover_path: str | None = None,
               cover_image: Image.Image | None = None, badge: int | None = None) -> Image.Image:
    """生成与画布同尺寸的封面:蓝底 + 封面图等比缩小完整居中(不裁剪)。
    badge:批量伪装时画进封面左上角的导入序号(黑底白字圆角块,像素级)。"""
    canvas = Image.new("RGBA", (canvas_w, canvas_h), COVER_BG + (255,))
    src = cover_image
    if src is None:
        src_path = cover_path or DEFAULT_COVER_PATH
        if src_path and os.path.isfile(src_path):
            try:
                src = Image.open(src_path).convert("RGBA")
            except Exception:
                src = None
    if src is not None:
        try:
            src = src.convert("RGBA")
            scale = min(canvas_w / src.width, canvas_h / src.height)
            dw = max(1, int(src.width * scale))
            dh = max(1, int(src.height * scale))
            src = src.resize((dw, dh), Image.LANCZOS)
            canvas.alpha_composite(src, ((canvas_w - dw) // 2, (canvas_h - dh) // 2))
        except Exception:
            pass  # 封面合成失败就纯蓝底
    if badge:
        _draw_badge(canvas, badge)
    return canvas


def _draw_badge(canvas: Image.Image, badge: int):
    """左上角画序号角标:半透明黑圆角块 + 白色粗体数字。"""
    from PIL import ImageDraw, ImageFont
    w, h = canvas.size
    fs = max(24, round(min(w, h) * 0.09))
    font = _load_font_bold(fs)
    text = str(badge)
    try:
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        off_x, off_y = bbox[0], bbox[1]
    except Exception:
        tw, th, off_x, off_y = fs * len(text) * 0.6, fs, 0, 0
    pad_x, pad_y = int(fs * 0.5), int(fs * 0.32)
    bx, by = int(fs * 0.45), int(fs * 0.45)
    bw, bh = int(tw + pad_x * 2), int(th + pad_y * 2)
    overlay = Image.new("RGBA", (bw + 4, bh + 4), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([2, 2, 2 + bw, 2 + bh], radius=bh // 2, fill=(0, 0, 0, 158))
    od.text((2 + pad_x - off_x, 2 + pad_y - off_y), text, font=font, fill=(255, 255, 255, 255))
    canvas.alpha_composite(overlay, (bx, by))


def _load_font_bold(size: int):
    import PIL.ImageFont as ImageFont
    for p in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "C:/Windows/Fonts/msyhbd.ttc", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 静态图伪装
# ---------------------------------------------------------------------------

def disguise_static(src_path: str, cover_path: str | None = None,
                    cover_image: Image.Image | None = None) -> bytes:
    img = _load_image(src_path)
    w, h = img.size
    _validate(w, h, 1)
    cover = cover_image if cover_image is not None else make_cover(w, h, cover_path)

    writer = apng_codec.ApngWriter(w, h, animation_frames=2, play_count=0,
                                   content_kind="STATIC", content_frame_count=1)
    writer.write_default(_PillowFrame(cover))
    writer.write_frame(_PillowFrame(img), delay_num=10, delay_den=100)
    # 保活帧 1x1(与 Kotlin/原版 v1 一致: blend=1)
    hb = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    writer.write_frame(_PillowFrame(hb), delay_num=10, delay_den=100, blend=1)
    return writer.finish()


# ---------------------------------------------------------------------------
# GIF 动态伪装
# ---------------------------------------------------------------------------

def disguise_gif(src_path: str, cover_path: str | None = None,
                 cover_image: Image.Image | None = None) -> bytes:
    img = _load_image(src_path)
    w, h = img.size
    n_frames = getattr(img, "n_frames", 1)
    if n_frames <= 1:
        return disguise_static(src_path, cover_path, cover_image)
    _validate(w, h, n_frames)

    # 逐帧提取(合成为全画布 RGBA;Pillow 的 seek 会保留 dispose,逐帧 seek 即合成)
    frames = []
    delays = []
    try:
        for i in range(n_frames):
            img.seek(i)
            frames.append(img.convert("RGBA").copy())
            dur = img.info.get("duration", 100) or 100
            delays.append(max(1, min(0xFFFF, round(dur / 10))))
    except EOFError:
        pass
    # Pillow 合成:seek 不自动做 dispose,但对全画布 GIF 通常没问题;稳妥起见逐帧独立
    # 若 GIF 是局部帧,需手动合成——这里对"完整帧"GIF 足够
    loop = img.info.get("loop", 0)  # Pillow: 0=无限? 实际可能 None

    writer = apng_codec.ApngWriter(w, h, animation_frames=len(frames), play_count=loop,
                                   content_kind="ANIMATED", content_frame_count=len(frames))
    writer.write_default(_PillowFrame(cover_image if cover_image is not None else make_cover(w, h, cover_path)))
    for i, fr in enumerate(frames):
        writer.write_frame(_PillowFrame(fr), delay_num=delays[i], delay_den=100)
    return writer.finish()


# ---------------------------------------------------------------------------
# 伪装/还原 入口
# ---------------------------------------------------------------------------

def process_file(src_path: str, cover_path: str | None = None,
                 cover_image: Image.Image | None = None) -> bytes:
    """按类型伪装:静态/GIF。cover_image 优先于 cover_path。返回伪装 APNG bytes。"""
    ext = Path(src_path).suffix.lower()
    if ext == ".gif" or _is_gif(src_path):
        return disguise_gif(src_path, cover_path, cover_image)
    return disguise_static(src_path, cover_path, cover_image)


def restore_file(src_path: str) -> bytes:
    """还原伪装 APNG → 普通 PNG/APNG bytes。"""
    data = Path(src_path).read_bytes()
    return apng_codec.restore_disguise(data)


def inspect_file(src_path: str) -> dict:
    """检测类型。返回 {kind, width, height, frame_count, can_restore}"""
    data = Path(src_path).read_bytes()
    if data.startswith(apng_codec.PNG_SIG):
        info = apng_codec.inspect_disguise(data)
        if info:
            return {"kind": "DISGUISE", "width": info["width"], "height": info["height"],
                    "frame_count": info["meta"]["count"], "can_restore": True}
        if b"acTL" in data:
            return {"kind": "OTHER_APNG", "width": 0, "height": 0, "frame_count": 1, "can_restore": False}
        im = Image.open(io.BytesIO(data))
        return {"kind": "STATIC", "width": im.width, "height": im.height, "frame_count": 1, "can_restore": False}
    if _is_gif_path(src_path):
        im = Image.open(src_path)
        return {"kind": "GIF", "width": im.width, "height": im.height,
                "frame_count": getattr(im, "n_frames", 1), "can_restore": False}
    raise ImageError("不支持的图片格式")


def _is_gif(src_path: str) -> bool:
    try:
        with open(src_path, "rb") as f:
            head = f.read(6)
        return head in (b"GIF87a", b"GIF89a")
    except Exception:
        return False


def _is_gif_path(src_path: str) -> bool:
    return _is_gif(src_path)


def _validate(w: int, h: int, frames: int):
    if w <= 0 or h <= 0 or frames <= 0:
        raise ImageError("图片尺寸或帧数无效")
    if w * h > MAX_FRAME_PIXELS:
        raise ImageError("图片尺寸过大;单帧最多约 800 万像素")
    if w * h * frames > MAX_TOTAL_PIXELS:
        raise ImageError("图片总像素量过大")


def save_temp(data: bytes, suffix=".png") -> str:
    """把处理结果写到临时目录(结果由 UI 复制/导出,不直接暴露)。"""
    fd, path = tempfile.mkstemp(prefix="pngdisguise_", suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path
