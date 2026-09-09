// PNG/APNG 伪装核心(浏览器环境,纯 JS,无依赖)
// 契约与 Kotlin/Python 版一致(与原 ChatChatBar 兼容):
//   IHDR→acTL→tEXt("ChatBarApngDisguise\0ver;STATIC|ANIMATED;count")→IDAT(封面)→fcTL+fdAT(真图 nudged)→fcTL+fdAT(真图 clean,静态)→IEND
// 像素行:RGBA,滤波 0/1/2/4(启发式最小和)。封面=蓝底 + 完整图等比缩小居中(contain)。
'use strict';

const MARKER_KEYWORD = 'ChatBarApngDisguise';
const COVER_BG = [0x25, 0x63, 0xEB]; // #2563EB

// ---------- CRC32 ----------
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c;
  }
  return t;
})();
function crc32(bytes) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

// ---------- 二进制工具 ----------
function chunk(type, data) {
  const out = new Uint8Array(12 + data.length);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, data.length);
  out.set(typeBytes(type), 4);
  out.set(data, 8);
  dv.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)));
  return out;
}
function typeBytes(t) { return [t.charCodeAt(0), t.charCodeAt(1), t.charCodeAt(2), t.charCodeAt(3)]; }
const PNG_SIG = new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

function concatBytes(arrays) {
  let len = 0;
  for (const a of arrays) len += a.length;
  const out = new Uint8Array(len);
  let o = 0;
  for (const a of arrays) { out.set(a, o); o += a.length; }
  return out;
}

// ---------- PNG 像素行滤波(启发式:None/Sub/Up/Paeth 取绝对和最小) ----------
function filterRows(width, height, getRow) {
  // getRow(y) -> Uint8Array(width*4) RGBA
  const stride = width * 4;
  const out = [];
  let prev = new Uint8Array(stride);
  for (let y = 0; y < height; y++) {
    const raw = getRow(y);
    let best = null, bestScore = Infinity;
    for (const f of [0, 1, 2, 4]) {
      const row = new Uint8Array(stride + 1);
      row[0] = f;
      let score = 0;
      for (let i = 0; i < stride; i++) {
        const cur = raw[i];
        const left = i >= 4 ? raw[i - 4] : 0;
        const up = prev[i];
        let v;
        if (f === 0) v = cur;
        else if (f === 1) v = cur - left;
        else if (f === 2) v = cur - up;
        else {
          const ul = i >= 4 ? prev[i - 4] : 0;
          const p = left + up - ul;
          const pa = Math.abs(p - left), pb = Math.abs(p - up), pc = Math.abs(p - ul);
          const pred = (pa <= pb && pa <= pc) ? left : (pb <= pc ? up : ul);
          v = cur - pred;
        }
        row[i + 1] = v & 0xFF;
        score += Math.abs(v);
      }
      if (score < bestScore) { bestScore = score; best = row; }
    }
    out.push(best);
    prev = raw;
  }
  return concatBytes(out);
}

// ---------- 像素级元数据/隐写清理(与 Python strip_metadata_img 一致,幂等) ----------
// NovelAI V3 把提示词隐写在 alpha 通道低位,且恰好写在 255↔254 这类不透明像素上
// (bit=1→255、bit=0→254),必须对**全部**像素清 alpha LSB(255→254、半透明取偶);
// 只清非 255 像素会原样保留隐写位型,NovelAI 照读。全透明像素 RGB→透明白。
function stripRGBAInPlace(px) {
  for (let i = 0; i < px.length; i += 4) {
    const a = px[i + 3] & 0xFE;
    px[i + 3] = a;
    if (a === 0) { px[i] = 255; px[i + 1] = 255; px[i + 2] = 255; }
  }
}
// frame 的 getRowRGBA 返回底层缓冲视图(canvas 帧均为 subarray),就地清理即生效
function stripFrame(fr) {
  if (fr._data) { stripRGBAInPlace(fr._data); return fr; }
  for (let y = 0; y < fr.height; y++) stripRGBAInPlace(fr.getRowRGBA(y));
  return fr;
}
function cloneFrame(fr) {
  const rows = [];
  for (let y = 0; y < fr.height; y++) rows.push(new Uint8Array(fr.getRowRGBA(y)));
  return { width: fr.width, height: fr.height, _rows: rows,
    getRowRGBA(y) { return this._rows[y]; } };
}

// ---------- PNG 反滤波(还原清理用;支持全部 5 种滤波) ----------
function unfilterRGBA(raw, width, height) {
  const stride = width * 4, bpp = 4, rowLen = stride + 1;
  const out = new Uint8Array(height * stride);
  for (let y = 0; y < height; y++) {
    const f = raw[y * rowLen];
    const src = y * rowLen + 1, dst = y * stride;
    const row = out.subarray(dst, dst + stride);
    const up = y > 0 ? out.subarray(dst - stride, dst) : null;
    for (let i = 0; i < stride; i++) {
      const x = raw[src + i];
      const a = i >= bpp ? row[i - bpp] : 0;
      const b = up ? up[i] : 0;
      const c = (i >= bpp && up) ? up[i - bpp] : 0;
      let v;
      if (f === 0) v = x;
      else if (f === 1) v = x + a;
      else if (f === 2) v = x + b;
      else if (f === 3) v = x + ((a + b) >> 1);
      else { // Paeth
        const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        v = x + ((pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c));
      }
      row[i] = v & 0xFF;
    }
  }
  return out;
}

// ---------- Deflate(zlib 包装,流式;fallback 同步) ----------// PNG 的 IDAT/fdAT 需要 zlib 流(头 + deflate + adler32)。CompressionStream 的
// 'deflate' 格式即 zlib 包装,直接可用;'deflate-raw' 是裸 deflate(无头),勿用。
async function deflateRaw(bytes) {
  if (typeof CompressionStream !== 'undefined') {
    const cs = new CompressionStream('deflate');
    const writer = cs.writable.getWriter();
    writer.write(bytes);
    writer.close();
    const reader = cs.readable.getReader();
    const parts = [];
    for (;;) { const { done, value } = await reader.read(); if (done) break; parts.push(value); }
    const total = parts.reduce((s, p) => s + p.length, 0);
    const out = new Uint8Array(total);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }
  // 同步 fallback:最小 zlib(存储块,无压缩)
  return syncDeflateStored(bytes);
}
function syncDeflateStored(bytes) {
  // zlib header: 0x78 0x01(无压缩)
  const head = new Uint8Array([0x78, 0x01]);
  const parts = [head];
  const len = bytes.length;
  let pos = 0;
  let final = false;
  while (!final) {
    const remain = len - pos;
    const chunkLen = Math.min(remain, 65535);
    final = pos + chunkLen >= len;
    const bh = new Uint8Array(5);
    bh[0] = final ? 1 : 0; // BFINAL=1,BTYPE=00(存储)
    bh[1] = chunkLen & 0xFF; bh[2] = (chunkLen >> 8) & 0xFF;
    bh[3] = (~chunkLen) & 0xFF; bh[4] = ((~chunkLen) >> 8) & 0xFF;
    parts.push(bh);
    parts.push(bytes.subarray(pos, pos + chunkLen));
    pos += chunkLen;
  }
  // adler32
  let a = 1, b = 0;
  for (let i = 0; i < bytes.length; i++) { a = (a + bytes[i]) % 65521; b = (b + a) % 65521; }
  const adler = new Uint8Array(4);
  const ad = ((b << 16) | a) >>> 0;
  adler[0] = (ad >>> 24) & 0xFF; adler[1] = (ad >>> 16) & 0xFF; adler[2] = (ad >>> 8) & 0xFF; adler[3] = ad & 0xFF;
  parts.push(adler);
  return concatBytes(parts);
}

// ---------- 伪装写入 ----------
// frame: { width, height, getRowRGBA(y) -> Uint8Array }
async function buildDisguise(width, height, coverFrame, truthFrames, opts) {
  // opts: { playCount, contentKind: 'STATIC'|'ANIMATED', contentFrameCount }
  // 封面先清隐写(透明封面直接用原图像素);静态真图同样清理
  stripFrame(coverFrame);
  const chunks = [PNG_SIG];
  const ihdr = new Uint8Array(13);
  const dv = new DataView(ihdr.buffer);
  dv.setUint32(0, width); dv.setUint32(4, height);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  chunks.push(chunk('IHDR', ihdr));

  const frameCount = opts.contentKind === 'STATIC' ? 2 : opts.contentFrameCount;
  const acTL = new Uint8Array(8);
  const adv = new DataView(acTL.buffer);
  adv.setUint32(0, frameCount); adv.setUint32(4, opts.playCount || 0);
  chunks.push(chunk('acTL', acTL));

  const marker = new TextEncoder().encode(`${MARKER_KEYWORD}\0${1};${opts.contentKind};${opts.contentFrameCount}`);
  chunks.push(chunk('tEXt', marker));

  // 封面默认帧(IDAT)
  const coverRaw = filterRows(width, height, y => coverFrame.getRowRGBA(y));
  const coverComp = await deflateRaw(coverRaw);
  chunks.push(chunk('IDAT', coverComp));

  // 真图帧(fcTL+fdAT),sequence 从 fcTL 起共享递增
  let seq = 0;
  const writeFrameData = async (fr, delayNum, delayDen, dispose, blend, w, h) => {
    const fcTL = new Uint8Array(26);
    const fdv = new DataView(fcTL.buffer);
    fdv.setUint32(0, seq++); fdv.setUint32(4, w); fdv.setUint32(8, h);
    fdv.setUint32(12, 0); fdv.setUint32(16, 0);
    fdv.setUint16(20, delayNum); fdv.setUint16(22, delayDen);
    fcTL[24] = dispose; fcTL[25] = blend;
    chunks.push(chunk('fcTL', fcTL));
    const raw = filterRows(w, h, y => fr.getRowRGBA(y));
    const comp = await deflateRaw(raw);
    // 分块 64KB
    for (let i = 0; i < comp.length; i += 65536) {
      const piece = comp.subarray(i, i + 65536);
      const fd = new Uint8Array(4 + piece.length);
      new DataView(fd.buffer).setUint32(0, seq++);
      fd.set(piece, 4);
      chunks.push(chunk('fdAT', fd));
    }
  };

  if (opts.contentKind === 'STATIC') {
    // 真图清隐写后写双真图帧 [nudged, clean](v4.0 手法:两帧强制差 1 像素,
    // 防解码器判静态;还原取 clean 帧),取代 1x1 保活帧
    const clean = stripFrame(truthFrames[0]);
    const nudge = cloneFrame(clean);
    nudge.getRowRGBA(0)[0] = (nudge.getRowRGBA(0)[0] + 1) & 0xFF;
    await writeFrameData(nudge, 10, 100, 0, 0, width, height);
    await writeFrameData(clean, 10, 100, 0, 0, width, height);
  } else {
    for (let i = 0; i < truthFrames.length; i++) {
      const f = truthFrames[i];
      await writeFrameData(f, f.delayNum || 10, 100, 0, 0, width, height);
    }
  }
  // 可选:保留原图元数据块(eXIf/tEXt/iTXt/zTXt,由调用方提取传入)
  for (const mc of (opts.extraChunks || [])) {
    chunks.push(chunk(mc.type, mc.data));
  }
  // 保留元数据模式:直接输出(含伪装必需块 + 有意保留的元数据块)
  if (opts.keepMeta) {
    chunks.push(chunk('IEND', new Uint8Array(0)));
    return concatBytes(chunks);
  }
  // 强保证:剥离任何非白名单块(元数据等),仅保留伪装必需块
  const ALLOW = new Set(['IHDR', 'acTL', 'IDAT', 'fcTL', 'fdAT', 'IEND']);
  const kept = chunks.filter((c, i) => {
    if (i === 0) return true;              // PNG 签名块始终保留
    const t = String.fromCharCode(c[4], c[5], c[6], c[7]);
    if (t === 'IEND') return false;        // 末尾统一重加
    if (t === 'tEXt') {
      return new TextDecoder().decode(c.slice(8, -4)).startsWith(MARKER_KEYWORD);
    }
    return ALLOW.has(t);
  });
  kept.push(chunk('IEND', new Uint8Array(0)));
  return concatBytes(kept);
}

// ---------- 伪装检测/还原 ----------
function parseChunks(data) {
  if (data.length < 8 || data[0] !== 0x89 || data[1] !== 0x50) return null;
  const out = [];
  let pos = 8;
  const dv = new DataView(data.buffer, data.byteOffset);
  while (pos + 8 <= data.length) {
    const len = dv.getUint32(pos);
    const type = String.fromCharCode(data[pos + 4], data[pos + 5], data[pos + 6], data[pos + 7]);
    const payload = data.subarray(pos + 8, pos + 8 + len);
    out.push({ type, payload });
    pos += 12 + len;
    if (type === 'IEND') break;
  }
  return out;
}

function inspectDisguise(data) {
  const chunks = parseChunks(data);
  if (!chunks) return null;
  const types = chunks.map(c => c.type);
  if (!types.includes('acTL')) return null;
  let meta = null, w = 0, h = 0;
  for (const c of chunks) {
    if (c.type === 'IHDR' && c.payload.length >= 8) {
      w = new DataView(c.payload.buffer, c.payload.byteOffset).getUint32(0);
      h = new DataView(c.payload.buffer, c.payload.byteOffset).getUint32(4);
    }
    if (c.type === 'tEXt') {
      const s = new TextDecoder().decode(c.payload);
      if (s.startsWith(MARKER_KEYWORD + '\0')) {
        const val = s.slice(MARKER_KEYWORD.length + 1).split(';');
        if (val.length === 3 && /^\d+$/.test(val[0])) {
          meta = { version: +val[0], kind: val[1], count: +val[2] };
        }
      }
    }
  }
  if (!meta) return null;
  return { width: w, height: h, meta, chunks };
}

async function inflateRaw(bytes) {
  // PNG 的 IDAT/fdAT 载荷是 zlib 包装流(RFC1950,头+deflate+adler32),与
  // deflateRaw 对应也用 'deflate' 格式;'deflate-raw' 是裸 deflate(RFC1951),勿用
  if (typeof DecompressionStream !== 'undefined') {
    const ds = new DecompressionStream('deflate');
    const stream = new Blob([bytes]).stream().pipeThrough(ds);
    const buf = await new Response(stream).arrayBuffer();
    return new Uint8Array(buf);
  }
  throw new Error('当前环境不支持解压');
}

async function restoreDisguise(data) {
  const info = inspectDisguise(data);
  if (!info || (info.meta.kind !== 'STATIC' && info.meta.kind !== 'ANIMATED')) {
    throw new Error('不是可还原的伪装 APNG');
  }
  const chunks = info.chunks;
  const width = info.width, height = info.height;
  const out = [PNG_SIG];
  let ihdr = null;
  for (const c of chunks) if (c.type === 'IHDR') { ihdr = c.payload; break; }
  out.push(chunk('IHDR', ihdr));

  // 提取帧组:fcTL 开头,收集后续 fdAT 数据
  const groups = [];
  let cur = null;
  for (const c of chunks) {
    if (c.type === 'fcTL') { cur = { fctl: c.payload, datas: [] }; groups.push(cur); }
    else if (c.type === 'fdAT' && cur) cur.datas.push(c.payload.subarray(4));
  }
  if (groups.length === 0) throw new Error('伪装文件缺少动画帧');

  if (info.meta.kind === 'ANIMATED') {
    // 还原为无标记 APNG:acTL + 帧(fcTL seq 重排;首帧数据→IDAT,其余 fdAT)
    const acTL = chunks.find(c => c.type === 'acTL').payload;
    out.push(chunk('acTL', acTL));
    let seq = 0;
    for (let gi = 0; gi < groups.length; gi++) {
      const g = groups[gi];
      const fctl = g.fctl.slice();
      new DataView(fctl.buffer, fctl.byteOffset).setUint32(0, seq++);
      out.push(chunk('fcTL', fctl));
      const comp = concatBytes(g.datas);
      if (gi === 0) {
        out.push(chunk('IDAT', comp));
      } else {
        const fd = new Uint8Array(4 + comp.length);
        new DataView(fd.buffer).setUint32(0, seq++);
        fd.set(comp, 4);
        out.push(chunk('fdAT', fd));
      }
    }
  } else {
    // 静态:取"与画布同尺寸"的最后一组真图帧。
    // 双真图帧 [nudged, clean](本工具/v4.0)→ 取 clean;原版结构 [真图, 1x1 保活] → 过滤保活帧
    let sel = groups.filter(g => {
      const fv = new DataView(g.fctl.buffer, g.fctl.byteOffset);
      return fv.getUint32(4) === width && fv.getUint32(8) === height;
    });
    if (sel.length === 0) sel = [groups[groups.length - 1]];
    const comp = concatBytes(sel[sel.length - 1].datas);
    // 像素级隐写清理(与 Python restore_file 一致):8bit RGBA 非隔行才解压
    // 清理(alpha LSB 全清 + 全透明透白);异常结构原样字节输出
    if (ihdr.length >= 13 && ihdr[8] === 8 && ihdr[9] === 6 && ihdr[12] === 0) {
      const raw = await inflateRaw(comp);
      const rgba = unfilterRGBA(raw, width, height);
      stripRGBAInPlace(rgba);
      const filtered = filterRows(width, height,
        y => rgba.subarray(y * width * 4, (y + 1) * width * 4));
      out.push(chunk('IDAT', await deflateRaw(filtered)));
    } else {
      out.push(chunk('IDAT', comp));
    }
  }
  out.push(chunk('IEND', new Uint8Array(0)));
  return concatBytes(out);
}

// 供浏览器 UI 使用的解码辅助
function rgbaFrameFromImage(img) {
  const c = document.createElement('canvas');
  c.width = img.naturalWidth || img.width;
  c.height = img.naturalHeight || img.height;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const id = ctx.getImageData(0, 0, c.width, c.height);
  return {
    width: c.width,
    height: c.height,
    _data: id.data,
    getRowRGBA(y) {
      return this._data.subarray(y * this.width * 4, (y + 1) * this.width * 4);
    }
  };
}

// 封面 contain:蓝底 + 源图等比缩小完整居中(类似 CCB 大象封面)
function makeCoverFrame(coverFrame, canvasW, canvasH) {
  const scale = Math.min(canvasW / coverFrame.width, canvasH / coverFrame.height);
  const dw = Math.max(1, Math.floor(coverFrame.width * scale));
  const dh = Math.max(1, Math.floor(coverFrame.height * scale));
  const ox = Math.floor((canvasW - dw) / 2);
  const oy = Math.floor((canvasH - dh) / 2);
  const canvas = document.createElement('canvas');
  canvas.width = canvasW; canvas.height = canvasH;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.fillStyle = `rgb(${COVER_BG[0]},${COVER_BG[1]},${COVER_BG[2]})`;
  ctx.fillRect(0, 0, canvasW, canvasH);
  const srcC = document.createElement('canvas');
  srcC.width = coverFrame.width; srcC.height = coverFrame.height;
  srcC.getContext('2d').putImageData(new ImageData(coverFrame._data.slice(), coverFrame.width, coverFrame.height), 0, 0);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(srcC, ox, oy, dw, dh);
  const id = ctx.getImageData(0, 0, canvasW, canvasH);
  return {
    width: canvasW, height: canvasH, _data: id.data,
    getRowRGBA(y) { return this._data.subarray(y * canvasW * 4, (y + 1) * canvasW * 4); }
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { buildDisguise, restoreDisguise, inspectDisguise, makeCoverFrame, filterRows, deflateRaw, unfilterRGBA, stripRGBAInPlace, stripFrame, cloneFrame, PNG_SIG, chunk, parseChunks, MARKER_KEYWORD };
}
