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


def strip_metadata_img(img: Image.Image) -> Image.Image:
    """清除元数据与隐写(对齐 v4.0 strip_metadata):
    - NovelAI V3 把提示词隐写在 alpha 通道低位,且恰好写在 255↔254 这类
      不透明像素上(bit=1→255、bit=0→254),所以必须对**全部**像素清 alpha LSB
      (255→254、半透明取偶)。只清非 255 像素会原样保留隐写位型,NovelAI 照读。
    - 完全透明像素的 RGB 改"透明白",避免被看成黑底;半透明/不透明像素 RGB 不动
    - 清空 info 字典 → EXIF/ICC/提示词 tEXt 全部丢弃
    幂等设计:对本函数输出重复处理结果不变(伪装↔还原循环零漂移)。"""
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    a = a.point(lambda v: v & 0xFE)              # 全部像素清 LSB(隐写位)
    # 仅全透明像素 RGB→白;不透明/半透明 RGB 不动 → 幂等,循环零漂移
    mask = a.point(lambda v: 255 if v == 0 else 0)
    white = Image.new("L", rgba.size, 255)
    r = Image.composite(white, r, mask)
    g = Image.composite(white, g, mask)
    b = Image.composite(white, b, mask)
    clean = Image.merge("RGBA", (r, g, b, a))
    clean.info = {}
    return clean


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


def _pillow_frame_compress(width: int, height: int, get_row_rgba) -> bytes:
    """用 Pillow 的 C 编码器压缩一帧,返回 IDAT/fdAT 需要的 zlib 流。

    fdAT 里放任何合法滤波的 zlib 流都可被解码器还原,格式契约不变。
    实测:比原来的 None 直写小 ~20% 且更快(6MP 帧 1519KB/142ms → 1210KB/95ms)。
    曾试过自己用 Pillow 算子做逐行自适应滤波(None/Sub/Up),但实测真实图片反而
    比 Pillow 默认大 0~3%(Pillow 内部还会用 Paeth/Average),故不采用。"""
    rows = bytearray()
    for y in range(height):
        rows += get_row_rgba(y)
    img = Image.frombytes("RGBA", (width, height), bytes(rows))
    buf = io.BytesIO()
    img.save(buf, "PNG")  # 默认档:自适应滤波(含 Paeth) + zlib6
    return b"".join(p for t, p in apng_codec._parse_chunks(buf.getvalue())
                    if t == b"IDAT")


def _load_image(path: str) -> Image.Image:
    try:
        return Image.open(path)
    except Exception as e:
        raise ImageError(f"无法打开图片: {e}")


# ---------------------------------------------------------------------------
def extract_png_meta_chunks(png_bytes: bytes) -> list[tuple[str, bytes]]:
    import struct as _s
    out = []
    sig = bytes([0x89]) + b"PNG"
    if not png_bytes.startswith(sig):
        return out
    pos = 8
    META = {b"tEXt", b"iTXt", b"zTXt", b"eXIf"}
    while pos + 8 <= len(png_bytes):
        length = _s.unpack(">I", png_bytes[pos:pos+4])[0]
        ctype = png_bytes[pos+4:pos+8]
        payload = png_bytes[pos+8:pos+8+length]
        if ctype in META:
            out.append((ctype.decode("latin-1"), payload))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return out


def extract_jpeg_exif(jpeg_bytes: bytes) -> bytes | None:
    if not jpeg_bytes.startswith(bytes([0xFF, 0xD8])):
        return None
    pos = 2
    while pos + 4 <= len(jpeg_bytes):
        marker = jpeg_bytes[pos:pos+2]
        length = int.from_bytes(jpeg_bytes[pos+2:pos+4], "big")
        seg = jpeg_bytes[pos+4:pos+2+length]
        if marker == bytes([0xFF, 0xE1]) and seg.startswith(b"Exif" + bytes([0, 0])):
            return seg
        pos += 2 + length
        if marker == bytes([0xFF, 0xDA]):
            break
    return None


def build_meta_chunks_png(src_path: str) -> list[tuple[str, bytes]]:
    try:
        raw = Path(src_path).read_bytes()
    except Exception:
        return []
    if raw.startswith(bytes([0x89]) + b"PNG"):
        return extract_png_meta_chunks(raw)
    if raw.startswith(bytes([0xFF, 0xD8])):
        exif = extract_jpeg_exif(raw)
        return [("eXIf", exif)] if exif else []
    return []


def meta_chunks_bytes(chunks: list[tuple[str, bytes]]) -> list[tuple[bytes, bytes]]:
    return [(t.encode("latin-1"), d) for t, d in chunks]


# ---------------------------------------------------------------------------
# 封面适配(蓝底 contain)
# ---------------------------------------------------------------------------

def make_cover(canvas_w: int, canvas_h: int, cover_path: str | None = None,
               cover_image: Image.Image | None = None, badge: int | None = None,
               bg_color: tuple | None = None, transparent: bool = False) -> Image.Image:
    """生成与画布同尺寸的封面:背景 + 封面图等比缩小完整居中(不裁剪)。
    bg_color: 背景色 (r,g,b);transparent: 背景透明(封面图本身带透明区域时保持透明)。
    badge:批量伪装时画进封面左上角的导入序号(黑底白字圆角块,像素级)。"""
    if transparent:
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    else:
        bg = bg_color or COVER_BG
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (bg[0], bg[1], bg[2], 255))
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
                    cover_image: Image.Image | None = None,
                    bg_color: tuple | None = None, transparent: bool = False,
                    keep_meta: bool = False) -> bytes:
    img = _load_image(src_path)
    w, h = img.size
    _validate(w, h, 1)
    cover = cover_image if cover_image is not None else make_cover(
        w, h, cover_path, bg_color=bg_color, transparent=transparent)
    cover = strip_metadata_img(cover)  # 封面同样清隐写(透明封面直接用原图像素)

    writer = apng_codec.ApngWriter(w, h, animation_frames=2, play_count=0,
                                   content_kind="STATIC", content_frame_count=1,
                                   compress=_pillow_frame_compress)
    writer.write_default(_PillowFrame(cover))
    # 真图只存一份(清元数据/隐写后),第二帧用 1×1 全透明保活帧(blend=1,合成时
    # 画面不变)。两帧内容不同 → 解码器按动画处理,而真图不再存两份(原版结构,
    # 比双真帧小 ~35%)。
    writer.write_frame(_PillowFrame(strip_metadata_img(img)), delay_num=10, delay_den=100)
    hb = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    writer.write_frame(_PillowFrame(hb), delay_num=10, delay_den=100, blend=1)
    if keep_meta:
        writer.write_extra_chunks(meta_chunks_bytes(build_meta_chunks_png(src_path)))
    result = writer.finish()
    # 强保证:未开启保留时,白名单重组剥离任何非必需块(元数据绝不出现在输出)
    if not keep_meta:
        result = apng_codec.sanitize_apng(result, apng_codec.MARKER_KEYWORD)
    return result


# ---------------------------------------------------------------------------
# GIF 动态伪装
# ---------------------------------------------------------------------------

def disguise_gif(src_path: str, cover_path: str | None = None,
                 cover_image: Image.Image | None = None,
                 bg_color: tuple | None = None, transparent: bool = False,
                 keep_meta: bool = False) -> bytes:
    img = _load_image(src_path)
    w, h = img.size
    n_frames = getattr(img, "n_frames", 1)
    if n_frames <= 1:
        return disguise_static(src_path, cover_path, cover_image,
                               bg_color, transparent, keep_meta)
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
                                   content_kind="ANIMATED", content_frame_count=len(frames),
                                   compress=_pillow_frame_compress)
    cover = cover_image if cover_image is not None else make_cover(
        w, h, cover_path, bg_color=bg_color, transparent=transparent)
    cover = strip_metadata_img(cover)  # 封面同样清隐写(透明封面直接用原图像素)
    writer.write_default(_PillowFrame(cover))
    # GIF 帧不清隐写:GIF 无 8 位 alpha 通道,不可能携带 NovelAI alpha 隐写
    for i, fr in enumerate(frames):
        writer.write_frame(_PillowFrame(fr), delay_num=delays[i], delay_den=100)
    if keep_meta:
        writer.write_extra_chunks(meta_chunks_bytes(build_meta_chunks_png(src_path)))
    result = writer.finish()
    if not keep_meta:
        result = apng_codec.sanitize_apng(result, apng_codec.MARKER_KEYWORD)
    return result


# ---------------------------------------------------------------------------
# 伪装/还原 入口
# ---------------------------------------------------------------------------

def process_file(src_path: str, cover_path: str | None = None,
                 cover_image: Image.Image | None = None,
                 bg_color: tuple | None = None, transparent: bool = False,
                 keep_meta: bool = False) -> bytes:
    """按类型伪装:静态/GIF。cover_image 优先于 cover_path。返回伪装 APNG bytes。"""
    # 防御:伪装 APNG 输入会把封面默认帧当原图(错误),必须拒绝
    with Path(src_path).open("rb") as fh:
        head = fh.read(8)
    if head.startswith(bytes([0x89]) + b"PNG"):
        with Path(src_path).open("rb") as fh:
            fh.seek(8)
            while True:
                hdr = fh.read(8)
                if len(hdr) < 8:
                    break
                length = int.from_bytes(hdr[:4], "big")
                ctype = hdr[4:8]
                if ctype == b"acTL":
                    raise ImageError("该文件已是伪装图/APNG 动画,请先还原再重新伪装")
                if ctype == b"IDAT":
                    break
                fh.seek(length + 4, 1)
    ext = Path(src_path).suffix.lower()
    if ext == ".gif" or _is_gif(src_path):
        return disguise_gif(src_path, cover_path, cover_image, bg_color, transparent,
                            keep_meta)
    return disguise_static(src_path, cover_path, cover_image, bg_color, transparent,
                           keep_meta)


def restore_file(src_path: str) -> bytes:
    """还原伪装 APNG → 普通 PNG/APNG bytes。
    静态还原额外做像素级清理(对齐 v4.0 restore_real 的 strip_metadata(real)):
    清 alpha LSB 隐写 + 全透明像素透白 —— 别人工具伪装的文件,真图帧像素里
    可能带着 NovelAI alpha 隐写,不做这步还原后 NovelAI 仍能读出提示词。"""
    data = Path(src_path).read_bytes()
    out = apng_codec.restore_disguise(data)
    info = apng_codec.inspect_disguise(data)
    if info and info["meta"]["kind"] == "STATIC":
        try:
            im = Image.open(io.BytesIO(out))
            buf = io.BytesIO()
            strip_metadata_img(im).save(buf, "PNG")
            out = buf.getvalue()
        except Exception:
            pass  # 清理失败(异常结构)时退回纯字节重组结果
    return out


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
