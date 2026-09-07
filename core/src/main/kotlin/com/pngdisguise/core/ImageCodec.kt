package com.pngdisguise.core

import java.io.File

/**
 * 平台图片解码抽象。
 *
 * Android 端用 BitmapFactory 实现;JVM 端用 ImageIO 实现。
 * 两端统一产出 [RgbaFrame],供伪装/编码与界面使用。
 */
interface ImageDecoder {
    /** 解码为 RGBA(0xAARRGGBB)帧。失败抛异常。 */
    fun decode(file: File): RgbaFrame

    /** 仅探测尺寸,不解码像素。 */
    fun decodeBounds(file: File): Pair<Int, Int>

    /** 是否可识别该格式(能解码或至少能读尺寸)。 */
    fun isSupported(file: File): Boolean

    /** GIF 帧数(平台解码器探测)。默认 1。 */
    fun gifFrameCount(file: File): Int = 1

    /**
     * 解码 GIF 全部帧(已合成,全画布 RGBA),含延迟与循环计数。
     * 仅当 [gifFrameCount] > 1 时调用。
     */
    fun decodeGifFrames(file: File): DecodedGif = throw UnsupportedOperationException("GIF 解码未实现")
}

/** 平台无关的图片类型识别(魔数优先)。 */
enum class ImageKind {
    STATIC, GIF, CHATBAR_DISGUISE_APNG, OTHER_APNG;

    companion object {
        fun detect(file: File, decoder: ImageDecoder): KindResult {
            // 先按魔数/APNG 结构判断
            if (ApngDisguiseCodec.hasPngSignature(file)) {
                if (ApngDisguiseCodec.containsAnimationControl(file)) {
                    val disguise = ApngDisguiseCodec.inspectDisguise(file)
                    if (disguise != null) {
                        return KindResult(
                            kind = CHATBAR_DISGUISE_APNG,
                            width = disguise.width,
                            height = disguise.height,
                            frameCount = disguise.animationFrameCount,
                            playCount = disguise.playCount,
                            canRestore = true
                        )
                    }
                    val bounds = decoder.decodeBounds(file)
                    return KindResult(OTHER_APNG, bounds.first, bounds.second, 1, 1, false)
                }
                // 无 acTL 的普通 PNG
                val bounds = decoder.decodeBounds(file)
                return KindResult(STATIC, bounds.first, bounds.second, 1, 1, false)
            }
    if (hasGifSignature(file)) {
                // GIF 交给具体实现探测帧数(GIF 有头部帧数信息,无需完整解码)
                val frames = decoder.gifFrameCount(file)
                val bounds = decoder.decodeBounds(file)
                return KindResult(GIF, bounds.first, bounds.second, frames, 1, false)
            }
            // JPEG/WebP 等静态
            val bounds = decoder.decodeBounds(file)
            return KindResult(STATIC, bounds.first, bounds.second, 1, 1, false)
        }
    }
}

data class KindResult(
    val kind: ImageKind,
    val width: Int,
    val height: Int,
    val frameCount: Int,
    val playCount: Int,
    val canRestore: Boolean
)

/** GIF 解码结果(平台解码器产出) */
data class DecodedGif(
    val width: Int,
    val height: Int,
    val frames: List<RgbaFrame>,
    /** 每帧延迟(毫秒) */
    val delays: List<Int>,
    /** NETSCAPE 循环计数,0=无限,<0=无扩展(单次) */
    val netscapeLoopCount: Int = -1
)

/** 共享:GIF 魔数检测。 */
fun hasGifSignature(file: File): Boolean = runCatching {
    file.inputStream().buffered().use { input ->
        val signature = ByteArray(6)
        input.read(signature) == signature.size &&
            (signature.contentEquals("GIF87a".toByteArray()) || signature.contentEquals("GIF89a".toByteArray()))
    }
}.getOrDefault(false)
