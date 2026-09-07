package com.pngdisguise.desktop.jvmimpl
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.core.DecodedGif
import com.pngdisguise.core.ImageDecoder
import com.pngdisguise.core.RgbaFrame
import com.pngdisguise.core.hasGifSignature

import java.awt.image.BufferedImage
import java.io.File
import java.io.InputStream
import javax.imageio.ImageIO

/**
 * JVM 侧 RgbaFrame ↔ 图片文件互转(桌面端与测试共用)。
 */
object JvmImageIo {
    /** RgbaFrame → PNG 文件(用于"保存打码图")。 */
    fun writePng(frame: RgbaFrame, target: File) {
        val image = BufferedImage(frame.width, frame.height, BufferedImage.TYPE_INT_ARGB)
        val pixels = frame.pixels
        image.setRGB(0, 0, frame.width, frame.height, pixels, 0, frame.width)
        ImageIO.write(image, "png", target)
    }

    /** 读取图片文件为 RgbaFrame(静态图;GIF 取首帧)。 */
    fun read(file: File): RgbaFrame {
        val image = ImageIO.read(file) ?: throw IllegalArgumentException("无法解码图片: ${file.name}")
        val frame = RgbaFrame(image.width, image.height)
        val pixels = IntArray(image.width * image.height)
        image.getRGB(0, 0, image.width, image.height, pixels, 0, image.width)
        pixels.copyInto(frame.pixels)
        return frame
    }
}

/**
 * 从 classpath 资源读取默认封面(内置 default_cover.png)。
 */
class ResourceCoverProvider(
    private val resourcePath: String = "/default_cover.png"
) : DisguiseService.CoverProvider {
    override fun cover(): RgbaFrame {
        val stream: InputStream = requireNotNull(javaClass.getResourceAsStream(resourcePath)) {
            "找不到内置封面资源 $resourcePath"
        }
        stream.use { input ->
            val image = ImageIO.read(input) ?: error("内置封面解析失败")
            val frame = RgbaFrame(image.width, image.height)
            val pixels = IntArray(image.width * image.height)
            image.getRGB(0, 0, image.width, image.height, pixels, 0, image.width)
            pixels.copyInto(frame.pixels)
            return frame
        }
    }
}

/** 固定封面(用户在设置里选择的自定义封面文件)。 */
class FileCoverProvider(private val file: File) : DisguiseService.CoverProvider {
    override fun cover(): RgbaFrame = JvmImageIo.read(file)
}
