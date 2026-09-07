package com.pngdisguise.core

import com.pngdisguise.core.ApngDisguiseCodec.ApngDisguiseContentKind
import java.io.File
import java.util.UUID
import kotlin.math.max
import kotlin.math.min

enum class ProcessedImageOperation {
    APNG_DISGUISE,
    APNG_RESTORE
}

data class ImportedProcessImage(
    val path: String,
    val displayName: String,
    val mimeType: String,
    val width: Int,
    val height: Int,
    val frameCount: Int,
    val kind: ImageKind,
    val canRestoreApng: Boolean,
    val playCount: Int = 1
) {
    val isAnimatedGif: Boolean get() = kind == ImageKind.GIF
    val isApng: Boolean get() = kind == ImageKind.CHATBAR_DISGUISE_APNG || kind == ImageKind.OTHER_APNG
}

data class ProcessedImage(
    val path: String,
    val mimeType: String,
    val width: Int,
    val height: Int,
    val frameCount: Int,
    val isAnimated: Boolean = frameCount > 1,
    val operation: ProcessedImageOperation = ProcessedImageOperation.APNG_DISGUISE
)

/**
 * 伪装/还原服务(平台无关)。
 *
 * - 静态图 → 伪装(封面默认帧 + 真图帧 + 保活帧)
 * - GIF → 动态伪装(封面默认帧 + 逐帧真图)
 * - 伪装 APNG → 还原(静态→PNG,动态→无标记 APNG)
 */
class DisguiseService(
    private val decoder: ImageDecoder,
    private val workDirectory: File,
    private val coverProvider: CoverProvider
) {
    private companion object {
        const val MAX_INPUT_BYTES = 100L * 1024 * 1024
        const val MAX_FRAME_PIXELS = 8_000_000L
        const val MAX_TOTAL_FRAME_PIXELS = 300_000_000L

        /** 封面留白背景色(蓝底,#2563EB)。 */
        const val COVER_BACKGROUND_COLOR = 0xFF2563EB.toInt()
    }

    fun interface CoverProvider {
        /** 返回封面图(尺寸任意,会被缩放居中到目标画布)。失败抛异常。 */
        fun cover(): RgbaFrame
    }

    fun inspect(file: File): ImportedProcessImage {
        require(file.isFile && file.length() in 1..MAX_INPUT_BYTES) { "图片为空或超过 100 MB" }
        val result = ImageKind.detect(file, decoder)
        return ImportedProcessImage(
            path = file.absolutePath,
            displayName = file.name,
            mimeType = if (result.kind == ImageKind.GIF) "image/gif" else "image/png",
            width = result.width,
            height = result.height,
            frameCount = result.frameCount,
            kind = result.kind,
            canRestoreApng = result.canRestore
        )
    }

    /**
     * 生成伪装。source 是静态图或 GIF。
     * @param coverOverride 非空时用本次封面,否则用 coverProvider 全局默认。
     */
    suspend fun createDisguise(
        source: File,
        coverOverride: RgbaFrame? = null,
        onProgress: (Float) -> Unit = {}
    ): ProcessedImage {
        require(source.isFile && source.length() in 1..MAX_INPUT_BYTES) { "原图文件不存在或超过 100 MB" }
        return if (hasGifSignature(source)) {
            createGifDisguise(source, coverOverride, onProgress)
        } else {
            require(!ApngDisguiseCodec.containsAnimationControl(source)) { "APNG 不能再次伪装" }
            val frame = decoder.decode(source)
            try {
                createStaticDisguise(frame, coverOverride, onProgress)
            } finally {
                frameRecycle(frame)
            }
        }
    }

    suspend fun createDisguise(frame: RgbaFrame, coverOverride: RgbaFrame? = null, onProgress: (Float) -> Unit = {}): ProcessedImage =
        createStaticDisguise(frame, coverOverride, onProgress)

    suspend fun restoreDisguise(source: File, onProgress: (Float) -> Unit = {}): ProcessedImage {
        require(source.isFile && source.length() in 1..MAX_INPUT_BYTES) { "APNG 文件不存在或超过 100 MB" }
        val inspection = ApngDisguiseCodec.inspectDisguise(source)
            ?: error("不是可还原的 ChatBar APNG 伪装图")
        onProgress(0.1f)
        val animated = inspection.metadata.contentKind == ApngDisguiseContentKind.ANIMATED
        val target = outputFile("restored", "png")
        try {
            ApngDisguiseCodec.restoreDisguise(source, target) { codecProgress ->
                onProgress(0.1f + codecProgress * 0.85f)
            }
            onProgress(1f)
            return ProcessedImage(
                path = target.absolutePath,
                mimeType = "image/png",
                width = inspection.width,
                height = inspection.height,
                frameCount = inspection.animationFrameCount,
                isAnimated = animated,
                operation = ProcessedImageOperation.APNG_RESTORE
            )
        } catch (error: Throwable) {
            target.delete()
            throw error
        }
    }

    // ---------- 静态伪装 ----------

    private suspend fun createStaticDisguise(
        frame: RgbaFrame,
        coverOverride: RgbaFrame?,
        onProgress: (Float) -> Unit
    ): ProcessedImage {
        validateFrame(frame)
        val target = outputFile("disguise", "png")
        val temporary = File(target.parentFile, "${target.name}.tmp")
        val cover = coverOverride ?: loadCover(frame.width, frame.height)
        try {
            ApngDisguiseCodec.limitedFileOutput(temporary).use { output ->
                val writer = ApngDisguiseCodec.Writer(
                    output = output,
                    width = frame.width,
                    height = frame.height,
                    animationFrameCount = 2,
                    playCount = 0,
                    contentKind = ApngDisguiseContentKind.STATIC,
                    contentFrameCount = 1
                )
                writer.writeDefaultImage(cover)
                onProgress(0.3f)
                writer.writeFrame(frame, delayNumerator = 10, delayDenominator = 100)
                onProgress(0.85f)
                writer.writeStaticHeartbeatFrame()
                writer.finish()
            }
            require(ApngDisguiseCodec.inspectDisguise(temporary) != null) { "APNG 伪装结构校验失败" }
            replaceTemporaryFile(temporary, target)
            onProgress(1f)
            return ProcessedImage(
                path = target.absolutePath,
                mimeType = "image/png",
                width = frame.width,
                height = frame.height,
                frameCount = 1,
                isAnimated = false,
                operation = ProcessedImageOperation.APNG_DISGUISE
            )
        } catch (error: Throwable) {
            target.delete()
            throw error
        } finally {
            temporary.delete()
        }
    }

    // ---------- GIF 动态伪装 ----------

    private suspend fun createGifDisguise(
        source: File,
        coverOverride: RgbaFrame?,
        onProgress: (Float) -> Unit
    ): ProcessedImage {
        // 交给平台实现逐帧解码(Android 用 gifdecoder,JVM 用 gif-decoder),统一产出帧序列
        val decoded = decoder.decodeGifFrames(source)
        require(decoded.frames.isNotEmpty()) { "GIF 无有效帧" }
        if (decoded.frames.size == 1) {
            // 单帧 GIF → 按静态处理
            return createStaticDisguise(decoded.frames[0], coverOverride, onProgress)
        }
        val width = decoded.width
        val height = decoded.height
        validateGif(width, height, decoded.frames.size)
        val target = outputFile("disguise", "png")
        val temporary = File(target.parentFile, "${target.name}.tmp")
        val cover = coverOverride ?: loadCover(width, height)
        try {
            ApngDisguiseCodec.limitedFileOutput(temporary).use { output ->
                val writer = ApngDisguiseCodec.Writer(
                    output = output,
                    width = width,
                    height = height,
                    animationFrameCount = decoded.frames.size,
                    playCount = ApngDisguiseCodec.gifLoopCountToApngPlayCount(decoded.netscapeLoopCount),
                    contentKind = ApngDisguiseContentKind.ANIMATED,
                    contentFrameCount = decoded.frames.size
                )
                writer.writeDefaultImage(cover)
                onProgress(0.15f)
                decoded.frames.forEachIndexed { index, f ->
                    writer.writeFrame(f, delayNumerator = decoded.delays[index], delayDenominator = 100)
                    onProgress(0.15f + 0.8f * (index + 1f) / decoded.frames.size)
                }
                writer.finish()
            }
            require(ApngDisguiseCodec.inspectDisguise(temporary) != null) { "APNG 伪装结构校验失败" }
            replaceTemporaryFile(temporary, target)
            onProgress(1f)
            return ProcessedImage(
                path = target.absolutePath,
                mimeType = "image/png",
                width = width,
                height = height,
                frameCount = decoded.frames.size,
                isAnimated = true,
                operation = ProcessedImageOperation.APNG_DISGUISE
            )
        } catch (error: Throwable) {
            target.delete()
            throw error
        } finally {
            temporary.delete()
        }
    }

    // ---------- 封面 ----------

    /**
     * 封面适配(类似 CCB 大象封面效果):封面图等比缩小到**完整容纳**在画布内、居中摆放,
     * 四周留白用背景色(蓝底)填满;不裁剪、不变形。
     */
    private fun loadCover(canvasWidth: Int, canvasHeight: Int): RgbaFrame {
        val cover = coverProvider.cover()
        require(cover.width > 0 && cover.height > 0) { "封面图无效" }
        return fitCoverContain(cover, canvasWidth, canvasHeight)
    }

    internal fun fitCoverContain(cover: RgbaFrame, targetWidth: Int, targetHeight: Int): RgbaFrame {
        val out = RgbaFrame(targetWidth, targetHeight)
        // 1) 背景全部填蓝底
        for (i in 0 until targetWidth * targetHeight) out.pixels[i] = COVER_BACKGROUND_COLOR
        // 2) 等比缩小封面到画布内完整容纳
        val scale = minOf(
            targetWidth.toDouble() / cover.width,
            targetHeight.toDouble() / cover.height
        )
        val scaledW = (cover.width * scale).toInt().coerceIn(1, targetWidth)
        val scaledH = (cover.height * scale).toInt().coerceIn(1, targetHeight)
        val offsetX = (targetWidth - scaledW) / 2
        val offsetY = (targetHeight - scaledH) / 2
        // 3) 双线性采样缩放绘制到中央
        for (y in 0 until scaledH) {
            for (x in 0 until scaledW) {
                val sx = (x + 0.5) / scale - 0.5
                val sy = (y + 0.5) / scale - 0.5
                val sampled = bilinearSample(cover, sx, sy)
                out.setPixel(offsetX + x, offsetY + y, sampled)
            }
        }
        return out
    }

    private fun bilinearSample(img: RgbaFrame, x: Double, y: Double): Int {
        val x0 = x.toInt().coerceIn(0, img.width - 1)
        val y0 = y.toInt().coerceIn(0, img.height - 1)
        val x1 = (x0 + 1).coerceAtMost(img.width - 1)
        val y1 = (y0 + 1).coerceAtMost(img.height - 1)
        val fx = (x - x0).toFloat()
        val fy = (y - y0).toFloat()
        val c00 = img.getPixel(x0, y0)
        val c10 = img.getPixel(x1, y0)
        val c01 = img.getPixel(x0, y1)
        val c11 = img.getPixel(x1, y1)
        fun mix(a: Int, b: Int, t: Float): Int = (a + (b - a) * t).toInt()
        return (0xFF shl 24) or
            (mix(mix(c00 ushr 16 and 0xFF, c10 ushr 16 and 0xFF, fx), mix(c01 ushr 16 and 0xFF, c11 ushr 16 and 0xFF, fx), fy) shl 16) or
            (mix(mix(c00 ushr 8 and 0xFF, c10 ushr 8 and 0xFF, fx), mix(c01 ushr 8 and 0xFF, c11 ushr 8 and 0xFF, fx), fy) shl 8) or
            mix(mix(c00 and 0xFF, c10 and 0xFF, fx), mix(c01 and 0xFF, c11 and 0xFF, fx), fy)
    }

    // ---------- 校验与工具 ----------

    private fun validateFrame(frame: RgbaFrame) {
        require(frame.width > 0 && frame.height > 0) { "图片尺寸无效" }
        require(frame.width.toLong() * frame.height <= MAX_FRAME_PIXELS) { "图片尺寸过大;单帧最多约 800 万像素" }
    }

    private fun validateGif(width: Int, height: Int, frameCount: Int) {
        require(width > 0 && height > 0 && frameCount > 0) { "GIF 尺寸或帧数无效" }
        require(width.toLong() * height <= MAX_FRAME_PIXELS) { "图片尺寸过大;单帧最多约 800 万像素" }
        require(width.toLong() * height * frameCount <= MAX_TOTAL_FRAME_PIXELS) { "图片总像素量过大;请减少尺寸或帧数" }
    }

    private fun outputFile(prefix: String, extension: String): File {
        workDirectory.mkdirs()
        return File(workDirectory, "${prefix}_${UUID.randomUUID()}.$extension")
    }

    private fun replaceTemporaryFile(temporary: File, target: File) {
        check(temporary.isFile && temporary.length() in 1..ApngDisguiseCodec.MAX_OUTPUT_BYTES) {
            "处理结果为空或超过 100 MB"
        }
        check(temporary.renameTo(target)) { "无法保存处理结果" }
    }

    /** 解码器产出的帧需要平台回收(Android Bitmap)时由平台实现释放 */
    private fun frameRecycle(frame: RgbaFrame) {
        // RgbaFrame 为普通对象,JVM 无需回收;Android 端若持有 Bitmap 需另行处理
    }
}
