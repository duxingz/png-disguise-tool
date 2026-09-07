package com.pngdisguise.android

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.bumptech.glide.gifdecoder.GifDecoder
import com.bumptech.glide.gifdecoder.GifHeaderParser
import com.bumptech.glide.gifdecoder.StandardGifDecoder
import com.pngdisguise.core.DecodedGif
import com.pngdisguise.core.ImageDecoder
import com.pngdisguise.core.RgbaFrame
import com.pngdisguise.core.hasGifSignature
import java.io.File
import java.nio.ByteBuffer

/**
 * Android 端解码器。
 * - 静态图/PNG/JPEG:BitmapFactory
 * - GIF:Glide gifdecoder(与桌面 animated-gif-lib 同源 fmsware,帧合成语义一致)
 * 统一转成 core 的 RgbaFrame。
 */
class AndroidImageDecoder(private val context: Context) : ImageDecoder {

    override fun decode(file: File): RgbaFrame {
        if (hasGifSignature(file)) {
            return decodeGifFrames(file).frames.first()
        }
        val bmp = BitmapFactory.decodeFile(file.absolutePath)
            ?: throw IllegalArgumentException("无法解码图片;暂不支持此格式")
        return bmp.toRgbaFrame().also { if (!it.isRecycled) it.recycle() }
    }

    override fun decodeBounds(file: File): Pair<Int, Int> {
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, opts)
        require(opts.outWidth > 0 && opts.outHeight > 0) { "无法识别图片格式" }
        return opts.outWidth to opts.outHeight
    }

    override fun isSupported(file: File): Boolean = runCatching {
        if (hasGifSignature(file)) return@runCatching true
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, opts)
        opts.outWidth > 0 && opts.outHeight > 0
    }.getOrDefault(false)

    override fun gifFrameCount(file: File): Int {
        if (!hasGifSignature(file)) return 1
        return runCatching { decodeGifFrames(file).frames.size }.getOrDefault(1)
    }

    override fun decodeGifFrames(file: File): DecodedGif {
        require(hasGifSignature(file)) { "不是 GIF 文件" }
        val bytes = file.readBytes()
        val header = GifHeaderParser().setData(bytes).parseHeader()
        require(header.status == GifDecoder.STATUS_OK && header.frameCount > 0) { "GIF 文件损坏或无法解析" }
        val decoder = StandardGifDecoder(BitmapProvider(), header, ByteBuffer.wrap(bytes))
        try {
            val count = decoder.frameCount
            val frames = mutableListOf<RgbaFrame>()
            val delays = mutableListOf<Int>()
            repeat(count) { i ->
                decoder.advance()
                val frame = decoder.nextFrame ?: error("GIF 第 ${i + 1} 帧解码失败")
                frames += frame.toRgbaFrame()
                frame.recycle()
                delays += decoder.nextDelay.coerceAtLeast(0)
            }
            // netscapeLoopCount: 0=无限; -1=无(单次); N=N 次 —— Glide 同语义
            return DecodedGif(
                width = header.width,
                height = header.height,
                frames = frames,
                delays = delays,
                netscapeLoopCount = decoder.netscapeLoopCount
            )
        } finally {
            decoder.clear()
        }
    }

    private class BitmapProvider : GifDecoder.BitmapProvider {
        override fun obtain(width: Int, height: Int, config: Bitmap.Config?): Bitmap =
            Bitmap.createBitmap(width, height, config ?: Bitmap.Config.ARGB_8888)

        override fun release(bitmap: Bitmap) {
            if (!bitmap.isRecycled) bitmap.recycle()
        }

        override fun obtainByteArray(size: Int): ByteArray = ByteArray(size)
        override fun release(bytes: ByteArray) = Unit
        override fun obtainIntArray(size: Int): IntArray = IntArray(size)
        override fun release(array: IntArray) = Unit
    }
}

/** Bitmap(ARGB_8888)→ RgbaFrame(0xAARRGGBB)。 */
internal fun Bitmap.toRgbaFrame(): RgbaFrame {
    val frame = RgbaFrame(width, height)
    val pixels = IntArray(width * height)
    getPixels(pixels, 0, width, 0, 0, width, height)
    pixels.copyInto(frame.pixels)
    return frame
}
