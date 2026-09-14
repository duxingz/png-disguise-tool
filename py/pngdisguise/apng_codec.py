# -*- coding: utf-8 -*-
"""
APNG 伪装编解码核心(纯 Python,复刻 Kotlin 版已验证格式)。

伪装 = APNG 动画:默认帧(IDAT)= 封面(蓝底+完整图),动画帧(fcTL+fdAT)= 真图。
聊天软件只显示静态首帧(封面),支持动画的查看器才显示真图。

格式契约(与原 ChatChatBar 兼容):
    IHDR → acTL → tEXt("ChatBarApngDisguise\\0version;STATIC|ANIMATED;count")
    → IDAT×N(封面) → fcTL+fdAT(真图帧 nudged) → fcTL+fdAT(真图帧 clean,静态) → IEND
    静态双真图帧为 v4.0 手法:两帧强制差 1 像素防解码器判静态;原版 v1 的
    [真图, 1x1 保活帧] 结构同样兼容读取。
"""
import struct
import zlib
from pathlib import Path

MARKER_KEYWORD = b"ChatBarApngDisguise"
FORMAT_VERSION = 1
MAX_SUPPORTED_VERSION = 2
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
PNG_SIG = b"\x89PNG\r\n\x1a\n"

# 封面留白背景色(蓝底 #2563EB) —— 与 Kotlin 版一致
COVER_BG = (0x25, 0x63, 0xEB)


class CodecError(Exception):
    pass


# ---------------------------------------------------------------------------
# PNG chunk 读写
# ---------------------------------------------------------------------------

def _chunk_bytes(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc & 0xFFFFFFFF)


def _parse_chunks(data: bytes):
    """迭代 PNG chunks,产出 (type, payload)。"""
    if not data.startswith(PNG_SIG):
        raise CodecError("不是 PNG 文件")
    pos = len(PNG_SIG)
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if pos + 8 + length + 4 > len(data):
            raise CodecError("PNG chunk 越界")
        yield ctype, payload
        pos += 12 + length
        if ctype == b"IEND":
            break


# ---------------------------------------------------------------------------
# 像素编码(把 RGBA 行编码为 PNG 滤波行)
# ---------------------------------------------------------------------------

def sanitize_apng(data: bytes, marker_keyword: bytes) -> bytes:
    """白名单重组:仅保留伪装必需的块(IHDR/acTL/标记tEXt/IDAT/fcTL/fdAT/IEND),
    其余任何块(eXIf/iTXt/zTXt/其他 tEXt 等)全部剥离。keep_meta=False 时的强保证。"""
    if not data.startswith(bytes([0x89]) + b"PNG"):
        return data
    out = bytearray()
    out += data[:8]  # 签名
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos+4], "big")
        ctype = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        keep = ctype in (b"IHDR", b"acTL", b"fcTL", b"fdAT", b"IDAT", b"IEND")
        if ctype == b"tEXt":
            # 仅保留伪装标记本身
            keep = payload.startswith(marker_keyword + bytes([0])) if False else payload.startswith(marker_keyword + bytes([0]))
        if keep:
            crc = zlib.crc32(ctype)
            crc = zlib.crc32(payload, crc)
            out += data[pos:pos+8] + payload + (crc & 0xFFFFFFFF).to_bytes(4, "big")
        pos += 12 + length
        if ctype == b"IEND":
            break
    return bytes(out)


def _filter_rows(width, height, get_row_rgba):
    """None 滤波直写(每行前缀 0x00 + 原始 RGBA 字节)。

    滤波只影响 zlib 压缩率、不影响正确性;纯 Python 逐字节尝试 4 种滤波
    曾占伪装耗时 98%(600 万像素 ~43s),None 直写后 ~0.03s,且实测压缩率
    几乎无损(噪声最坏情况 0.9MB 持平)。html/JS 版不受影响(V8 JIT 快)。"""
    out = bytearray()
    zero = b"\x00"
    for y in range(height):
        out += zero
        out += get_row_rgba(y)
    return bytes(out)


# ---------------------------------------------------------------------------
# 伪装写入
# ---------------------------------------------------------------------------

def _default_compress(width: int, height: int, get_row_rgba) -> bytes:
    """默认帧压缩:None 滤波直写 + zlib6(纯 Python,不依赖 Pillow)。"""
    return zlib.compress(bytes(_filter_rows(width, height, get_row_rgba)), 6)


class ApngWriter:
    """流式写伪装 APNG。frame 提供 (width,height,get_row_rgba(y))。

    compress: 可选的帧压缩函数 (w, h, get_row_rgba) -> zlib 流。默认 None 滤波直写;
    调用方可传入 C 实现(如 Pillow)以取得自适应滤波的更小体积。
    """

    def __init__(self, width: int, height: int, animation_frames: int,
                 play_count: int, content_kind: str, content_frame_count: int,
                 compress=None):
        self.w = width
        self.h = height
        self._compress = compress or _default_compress
        self.declared = animation_frames
        self.written = 0
        self.chunks = bytearray()
        self.chunks += PNG_SIG
        # IHDR: 8bit RGBA 非隔行
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        self.chunks += _chunk_bytes(b"IHDR", ihdr)
        self.chunks += _chunk_bytes(b"acTL", struct.pack(">II", animation_frames, play_count))
        marker = b"%d;%s;%d" % (FORMAT_VERSION, content_kind.encode(), content_frame_count)
        self.chunks += _chunk_bytes(b"tEXt", MARKER_KEYWORD + b"\x00" + marker)
        self.seq = 0

    def _write_image_data(self, frame, is_default: bool):
        fw, fh = frame.width, frame.height
        comp = self._compress(fw, fh, frame.get_row_rgba)
        # 分块写(64KB)
        DATA = 64 * 1024
        for i in range(0, len(comp), DATA):
            piece = comp[i:i + DATA]
            if is_default:
                self.chunks += _chunk_bytes(b"IDAT", piece)
            else:
                self.chunks += _chunk_bytes(b"fdAT", struct.pack(">I", self.seq) + piece)
                self.seq += 1

    def write_default(self, frame):
        self._write_image_data(frame, is_default=True)

    def write_frame(self, frame, delay_num=10, delay_den=100, dispose=0, blend=0,
                    x=0, y=0):
        if self.written >= self.declared:
            raise CodecError("帧数超过声明")
        # fcTL: seq(I) w(I) h(I) x(I) y(I) delay_num(H) delay_den(H) dispose(B) blend(B)
        fcTL = struct.pack(">IIIIIHHBB", self.seq, frame.width, frame.height, x, y,
                           delay_num, delay_den, dispose, blend)
        self.seq += 1
        self.chunks += _chunk_bytes(b"fcTL", fcTL)
        self._write_image_data(frame, is_default=False)
        self.written += 1

    def write_extra_chunks(self, chunks: list[tuple[bytes, bytes]]):
        """在 IEND 前追加自定义块(如 eXIf/tEXt 元数据,可选保留元数据用)。"""
        for ctype, data in chunks:
            self.chunks += _chunk_bytes(ctype, data)

    def finish(self) -> bytes:
        if self.written != self.declared:
            raise CodecError("帧数与声明不一致")
        self.chunks += _chunk_bytes(b"IEND", b"")
        return bytes(self.chunks)


# ---------------------------------------------------------------------------
# 伪装检测/还原
# ---------------------------------------------------------------------------

def inspect_disguise(data: bytes):
    """识别伪装 APNG;是则返回信息 dict,否则 None。"""
    try:
        chunks = list(_parse_chunks(data))
    except Exception:
        return None
    ctypes = [c[0] for c in chunks]
    if b"acTL" not in ctypes:
        return None
    # 找标记 tEXt
    meta = None
    for ct, payload in chunks:
        if ct == b"tEXt" and payload.startswith(MARKER_KEYWORD + b"\x00"):
            val = payload[len(MARKER_KEYWORD) + 1:].decode("ascii", "replace")
            parts = val.split(";")
            if len(parts) == 3 and parts[0].isdigit():
                meta = {"version": int(parts[0]), "kind": parts[1], "count": int(parts[2])}
            break
    if not meta:
        return None
    # 解析 IHDR
    w = h = 0
    for ct, payload in chunks:
        if ct == b"IHDR":
            w, h = struct.unpack(">II", payload[:8])
            break
    return {"width": w, "height": h, "meta": meta, "chunks": chunks}


def restore_disguise(data: bytes):
    """还原伪装 APNG → 普通 PNG/APNG(静态出 PNG,动态出无标记 APNG)。"""
    info = inspect_disguise(data)
    if not info or info["meta"]["kind"] not in ("STATIC", "ANIMATED"):
        raise CodecError("不是可还原的伪装 APNG")
    chunks = info["chunks"]
    # 需要帧数据(真图)的 IDAT/fdAT 位置
    # 结构: IHDR, acTL, tEXt, IDAT*(封面), fcTL, fdAT*(真图帧1), fcTL, fdAT*(真图帧2)... IEND
    # 真图帧 = 去掉第一个 IDAT 组之后的所有帧数据
    out = bytearray()
    out += PNG_SIG
    # IHDR 原样
    seen_idat_group = False
    # 重组: IHDR + (动态时 acTL) + 帧数据(静态: 第一组 fdAT→IDAT;动态: 全部)
    ihdr = None
    for ct, payload in chunks:
        if ct == b"IHDR":
            ihdr = payload
            break
    out += _chunk_bytes(b"IHDR", ihdr)
    frame_groups = _extract_frame_groups(chunks)
    if info["meta"]["kind"] == "ANIMATED":
        # 输出为普通 APNG:acTL + 每帧 fcTL(seq 重排)+ IDAT/fdAT
        acTL = None
        for ct, payload in chunks:
            if ct == b"acTL":
                acTL = payload
                break
        frame_count = len(frame_groups)
        # play count 保留
        play_count = struct.unpack(">II", acTL)[1]
        out += _chunk_bytes(b"acTL", struct.pack(">II", frame_count, play_count))
        seq = 0
        for i, (fcTL, fdat_pieces) in enumerate(frame_groups):
            # 重写 fcTL sequence
            fcTL_data = bytearray(fcTL)
            struct.pack_into(">I", fcTL_data, 0, seq)
            seq += 1
            out += _chunk_bytes(b"fcTL", bytes(fcTL_data))
            for j, piece in enumerate(fdat_pieces):
                if i == 0:
                    out += _chunk_bytes(b"IDAT", piece)
                else:
                    out += _chunk_bytes(b"fdAT", struct.pack(">I", seq) + piece)
                    seq += 1
        out += _chunk_bytes(b"IEND", b"")
    else:
        # 静态:取"与画布同尺寸"的最后一组真图帧。
        # 双真图帧结构 [nudged, clean](本工具/v4.0)→ 取 clean,避免还原出
        # 角像素 +1 的 nudged 帧;原版结构 [真图, 1x1 保活帧] → 过滤保活帧。
        w, h = struct.unpack(">II", ihdr[:8])
        cand = [g for g in frame_groups
                if struct.unpack(">II", g[0][4:12]) == (w, h)]
        if not cand:
            cand = [frame_groups[-1]]
        _fctl, fdat_pieces = cand[-1]
        for piece in fdat_pieces:
            out += _chunk_bytes(b"IDAT", piece)
        out += _chunk_bytes(b"IEND", b"")
    return bytes(out)


def _extract_frame_groups(chunks):
    """把 fcTL 开头的一组帧数据切出来:返回 [(fcTL_payload, [fdAT_payloads...]), ...]"""
    groups = []
    cur = None
    seen_first_idat = False
    for ct, payload in chunks:
        if ct == b"IDAT":
            if cur is None:
                # 封面默认帧数据,跳过
                continue
            else:
                # 第一组真图帧若走 IDAT? 不可能,伪装里真图都是 fdAT
                pass
        elif ct == b"fcTL":
            cur = [payload, []]
            groups.append(cur)
        elif ct == b"fdAT":
            if cur is None:
                continue
            # 去掉 4 字节 sequence
            cur[1].append(payload[4:])
    return groups
