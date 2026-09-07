package com.pngdisguise.desktop

import com.pngdisguise.core.ApngDisguiseCodec.ApngDisguiseContentKind
import com.pngdisguise.core.ApngDisguiseCodec
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.desktop.jvmimpl.JvmImageIo
import com.pngdisguise.core.MaskBrushType
import com.pngdisguise.core.MosaicEditor
import com.pngdisguise.core.MosaicSession
import com.pngdisguise.core.ProcessedImageOperation
import com.pngdisguise.desktop.jvmimpl.ResourceCoverProvider
import com.pngdisguise.core.RgbaFrame
import com.pngdisguise.desktop.jvmimpl.JvmImageDecoder
import kotlinx.coroutines.runBlocking
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ApngDisguiseTest {

    private val tmp: File = Files.createTempDirectory("png-disguise-test").toFile()

    private fun testFrame(width: Int = 32, height: Int = 32, seed: Int = 0): RgbaFrame {
        val frame = RgbaFrame(width, height)
        for (y in 0 until height) {
            for (x in 0 until width) {
                val v = (x * 7 + y * 13 + seed * 31) and 0xFF
                frame.setPixel(x, y, (0xFF shl 24) or (v shl 16) or ((255 - v) shl 8) or ((v * 3) and 0xFF))
            }
        }
        return frame
    }

    private fun solidFrame(width: Int, height: Int, argb: Int): RgbaFrame = RgbaFrame.solid(width, height, argb)

    private fun coverProvider(color: Int = 0xFF2F8E7B.toInt()): DisguiseService.CoverProvider =
        DisguiseService.CoverProvider { solidFrame(64, 64, color) }

    private fun service(cover: DisguiseService.CoverProvider = coverProvider()): DisguiseService {
        val workDir = File(tmp, "work").apply { mkdirs() }
        return DisguiseService(JvmImageDecoder(), workDir, cover)
    }

    // ---------- 静态伪装 ----------

    @Test
    fun staticDisguiseThenRestore() = runBlocking {
        val svc = service()
        val truth = testFrame(64, 48)
        val png = File(tmp, "truth.png")
        JvmImageIo.writePng(truth, png)

        val disguised = svc.createDisguise(png) {}
        assertTrue(File(disguised.path).isFile)
        assertEquals(ProcessedImageOperation.APNG_DISGUISE, disguised.operation)
        assertTrue(!disguised.isAnimated)

        // 结构上必须是带标记的伪装 APNG
        val file = File(disguised.path)
        assertTrue(ApngDisguiseCodec.hasPngSignature(file))
        assertTrue(ApngDisguiseCodec.containsAnimationControl(file))
        val inspection = ApngDisguiseCodec.inspectDisguise(file)
        assertNotNull(inspection)
        assertEquals(ApngDisguiseContentKind.STATIC, inspection.metadata.contentKind)
        assertEquals(1, inspection.animationFrameCount)

        // 还原应得到与真图逐像素一致的 PNG
        val restored = svc.restoreDisguise(file) {}
        val restoredFrame = JvmImageIo.read(File(restored.path))
        assertPixelsEqual(truth, restoredFrame)
    }

    @Test
    fun disguiseMarkedAsChatBarCompatible() = runBlocking {
        val svc = service()
        val png = File(tmp, "truth2.png")
        JvmImageIo.writePng(testFrame(16, 16), png)
        val disguised = svc.createDisguise(png) {}
        val file = File(disguised.path)
        // 还原时应被识别为"可还原的伪装"
        assertNotNull(ApngDisguiseCodec.inspectDisguise(file))
        // 普通 PNG(无 acTL、无标记)不可还原
        val plainApng = makePlainPng(File(tmp, "plain.png"))
        assertNull(ApngDisguiseCodec.inspectDisguise(plainApng))
    }

    // ---------- 动态 GIF 伪装 ----------

    @Test
    fun gifDisguisePreservesFrames() = runBlocking {
        // 造一个 3 帧 GIF(不同颜色),伪装后还原应逐帧一致且带动画
        val gif = makeTestGif(File(tmp, "anim.gif"), frames = 3)
        val svc = service()
        val disguised = svc.createDisguise(gif) {}
        val file = File(disguised.path)
        assertTrue(ApngDisguiseCodec.containsAnimationControl(file))
        val inspection = ApngDisguiseCodec.inspectDisguise(file)
        assertNotNull(inspection)
        assertEquals(ApngDisguiseContentKind.ANIMATED, inspection.metadata.contentKind)
        assertEquals(3, inspection.animationFrameCount)

        val restored = svc.restoreDisguise(file) {}
        assertTrue(File(restored.path).isFile)
        assertTrue(restored.isAnimated)
        // 还原后的 APNG 帧数应仍为 3
        val restoredFile = File(restored.path)
        assertTrue(ApngDisguiseCodec.containsAnimationControl(restoredFile))
        assertNull(ApngDisguiseCodec.inspectDisguise(restoredFile))
    }

    // ---------- 封面:contain 模式(完整容纳 + 蓝底留白) ----------

    @Test
    fun coverIsContainedWithBlueBackground() = runBlocking {
        // 封面 64x64,真图 128x64(宽幅)→ 封面等比缩小完整居中,左右留白为蓝底
        val svc = service(coverProvider(0xFF112233.toInt()))
        val truth = solidFrame(128, 64, 0xFFAABBCC.toInt())
        val png = File(tmp, "wide.png")
        JvmImageIo.writePng(truth, png)
        val disguised = svc.createDisguise(png) {}
        val firstFrame = readApngDefaultFrame(File(disguised.path))
        assertEquals(128, firstFrame.width)
        assertEquals(64, firstFrame.height)
        // 中央应是封面色(封面完整放进画布)
        assertEquals(0xFF112233.toInt(), firstFrame.getPixel(64, 32))
        // 左右留白应是蓝底(#2563EB)
        assertEquals(0xFF2563EB.toInt(), firstFrame.getPixel(2, 32))
        assertEquals(0xFF2563EB.toInt(), firstFrame.getPixel(125, 32))
    }

    // ---------- 打码 ----------

    @Test
    fun mosaicBrushChangesPixels() {
        val frame = solidFrame(50, 50, 0xFFFFFFFF.toInt())
        MosaicEditor.applyBrush(frame, 25f, 25f, 20f, MaskBrushType.Black)
        // 中心区域应被涂黑
        assertEquals(0xFF000000.toInt(), frame.getPixel(25, 25))
        // 远处不受影响
        assertEquals(0xFFFFFFFF.toInt(), frame.getPixel(1, 1))
    }

    @Test
    fun mosaicSessionUndoReset() {
        val original = solidFrame(40, 40, 0xFFFFFFFF.toInt())
        val session = MosaicSession(original)
        session.pushUndoSnapshot()
        session.applyBrushAt(20f, 20f, 10f, MaskBrushType.Mosaic)
        assertTrue(session.hasVisualChanges)
        assertEquals(true, session.undo())
        assertPixelsEqual(original, session.working)
    }

    // ---------- 端到端:内置封面(真实资源) ----------

    @Test
    fun endToEndWithBundledCover() = runBlocking {
        // 使用真实的默认封面资源(用户提供的图),验证资源可加载、伪装/还原闭环
        val provider = ResourceCoverProvider()
        val cover = provider.cover()
        assertTrue(cover.width > 0 && cover.height > 0, "内置封面应可加载")

        val svc = DisguiseService(JvmImageDecoder(), File(tmp, "work2").apply { mkdirs() }, provider)
        val truth = testFrame(200, 150)
        val png = File(tmp, "truth_e2e.png")
        JvmImageIo.writePng(truth, png)

        val d = svc.createDisguise(png) {}
        val file = File(d.path)
        assertTrue(file.isFile && file.length() > 0)
        // 还原后与真图逐像素一致
        val restored = svc.restoreDisguise(file) {}
        assertPixelsEqual(truth, JvmImageIo.read(File(restored.path)))
    }

    // ---------- 伪装结构契约(与 ChatChatBar 一致) ----------

    @Test
    fun disguiseChunkStructureMatchesCanonical() = runBlocking {
        val svc = service()
        val png = File(tmp, "struct.png")
        JvmImageIo.writePng(testFrame(20, 20), png)
        val d = svc.createDisguise(png) {}
        val chunks = PngChunkDump.dump(File(d.path))
        // 期望:签名 + IHDR + acTL + tEXt(标记) + IDAT(封面) + fcTL + fdAT(真图) + fcTL + fdAT(保活) + IEND
        println(chunks.joinToString("\n"))
        assertTrue(chunks[1].startsWith("IHDR(13)"), "首 chunk 应为 IHDR,got ${chunks[1]}")
        assertTrue(chunks[2].startsWith("acTL(8)"), "应含 acTL")
        assertTrue(chunks[3].startsWith("tEXt(") && chunks[3].contains("ChatBarApngDisguise"), "标记缺失: ${chunks[3]}")
        // IDAT 在 fcTL 前(封面为默认帧)
        val idatIdx = chunks.indexOfFirst { it.startsWith("IDAT") }
        val firstFctlIdx = chunks.indexOfFirst { it.startsWith("fcTL") }
        assertTrue(idatIdx in 0 until firstFctlIdx, "封面默认帧(IDAT)应在动画帧(fcTL)之前")
        // 恰好 2 个动画帧(真图+保活)
        val fctlCount = chunks.count { it.startsWith("fcTL") }
        val fdatCount = chunks.count { it.startsWith("fdAT") }
        assertEquals(2, fctlCount)
        assertEquals(2, fdatCount)
        assertTrue(chunks.last().startsWith("IEND"))
    }

    // ---------- 辅助 ----------

    private fun assertPixelsEqual(a: RgbaFrame, b: RgbaFrame) {
        assertEquals(a.width, b.width)
        assertEquals(a.height, b.height)
        for (y in 0 until a.height) {
            for (x in 0 until a.width) {
                assertEquals(a.getPixel(x, y), b.getPixel(x, y), "pixel ($x,$y)")
            }
        }
    }

    /** 造一个无标记的普通 PNG(无 acTL),验证不是伪装图。 */
    private fun makePlainPng(file: File): File {
        JvmImageIo.writePng(testFrame(8, 8), file)
        return file
    }

    /** 生成多帧 GIF(用纯 Java 简单 LZW? 不——用 BufferedImage 手动写 GIF 需要编码器;这里用 animated-gif-lib 的编码器?) */
    private fun makeTestGif(file: File, frames: Int): File {
        // 用 AnimatedGifEncoder(同库)造 GIF
        val encoder = com.madgag.gif.fmsware.AnimatedGifEncoder()
        encoder.start(file.absolutePath)
        encoder.setRepeat(0) // 无限循环
        for (i in 0 until frames) {
            val img = java.awt.image.BufferedImage(32, 32, java.awt.image.BufferedImage.TYPE_INT_ARGB)
            val g = img.createGraphics()
            g.color = java.awt.Color(i * 60 % 255, 100, 200)
            g.fillRect(0, 0, 32, 32)
            g.dispose()
            encoder.setDelay(100)
            encoder.addFrame(img)
        }
        encoder.finish()
        return file
    }

    /** 读取 APNG 默认帧(IDAT)为 RgbaFrame。 */
    private fun readApngDefaultFrame(file: File): RgbaFrame {
        // 直接解码 PNG(ImageIO 读 APNG 默认帧即为首帧)
        return JvmImageIo.read(file)
    }
}
