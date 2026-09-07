package com.pngdisguise.desktop.jvmimpl
import com.pngdisguise.core.DecodedGif
import com.pngdisguise.core.ImageDecoder
import com.pngdisguise.core.RgbaFrame
import com.pngdisguise.core.hasGifSignature

import com.madgag.gif.fmsware.GifDecoder
import java.awt.image.BufferedImage
import java.io.File
import java.io.FileInputStream
import javax.imageio.ImageIO


/**
 * JVM 端解码器。
 *
 * - 静态图(PNG/JPEG/BMP 等):ImageIO
 * - GIF:com.madgag:animated-gif-lib(fmsware GifDecoder),逐帧已合成全画布;
 *   与 Android gifdecoder(原 ChatChatBar 所用)同源,帧语义一致。
 */
class JvmImageDecoder : ImageDecoder {
    override fun decode(file: File): RgbaFrame {
        if (hasGifSignature(file)) {
            return decodeGifFrames(file).frames.first()
        }
        val image = ImageIO.read(file) ?: throw IllegalArgumentException("无法解码图片;暂不支持此格式")
        return image.toRgbaFrame()
    }

    override fun decodeBounds(file: File): Pair<Int, Int> {
        val image = ImageIO.read(file) ?: throw IllegalArgumentException("无法识别图片格式")
        return image.width to image.height
    }

    override fun isSupported(file: File): Boolean = runCatching {
        if (hasGifSignature(file)) return@runCatching true
        ImageIO.read(file) != null
    }.getOrDefault(false)

    override fun gifFrameCount(file: File): Int {
        if (!hasGifSignature(file)) return 1
        val decoder = GifDecoder()
        val status = decoder.read(FileInputStream(file))
        return if (status == GifDecoder.STATUS_OK) decoder.frameCount else 1
    }

    override fun decodeGifFrames(file: File): DecodedGif {
        require(hasGifSignature(file)) { "不是 GIF 文件" }
        val decoder = GifDecoder()
        val status = decoder.read(FileInputStream(file))
        require(status == GifDecoder.STATUS_OK) { "GIF 文件损坏或无法解析 (status=$status)" }
        val count = decoder.frameCount
        require(count > 0) { "GIF 无有效帧" }
        val frames = (0 until count).map { i -> decoder.getFrame(i).toRgbaFrame() }
        val delays = (0 until count).map { i -> decoder.getDelay(i).coerceAtLeast(0) }
        // loopCount:0=无限;1=无扩展(单次);N=N 次
        val loopCount = decoder.loopCount
        return DecodedGif(
            width = decoder.frameSize.width,
            height = decoder.frameSize.height,
            frames = frames,
            delays = delays,
            netscapeLoopCount = if (loopCount == 1) -1 else loopCount
        )
    }
}

private fun BufferedImage.toRgbaFrame(): RgbaFrame {
    val frame = RgbaFrame(width, height)
    val pixels = IntArray(width * height)
    getRGB(0, 0, width, height, pixels, 0, width)
    var i = 0
    for (y in 0 until height) {
        for (x in 0 until width) {
            frame.setPixel(x, y, pixels[i])
            i++
        }
    }
    return frame
}
