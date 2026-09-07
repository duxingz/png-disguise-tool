package com.pngdisguise.desktop

import com.pngdisguise.core.ApngDisguiseCodec
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.desktop.jvmimpl.JvmImageDecoder
import com.pngdisguise.desktop.jvmimpl.JvmImageIo
import com.pngdisguise.desktop.jvmimpl.ResourceCoverProvider
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * 互操作验证:Python 版(png-disguise-tool/py)生成的伪装文件,
 * 必须能被 Kotlin 核心识别并还原为正确真图。
 */
class CrossInteropTest {

    @Test
    fun kotlinRestoresPythonDisguise() = runBlocking {
        // Gradle 测试工作目录是 desktop/,文件在仓库根
        val root = File(System.getProperty("user.dir")).parentFile
        val disguise = File(root, "cross_python_disguise.png")
        val truth = File(root, "cross_truth.png")
        assertTrue(disguise.isFile, "Python 伪装文件不存在: ${disguise.absolutePath}")
        assertTrue(truth.isFile, "真图文件不存在")

        // 1) Kotlin 能识别为伪装
        val inspection = ApngDisguiseCodec.inspectDisguise(disguise)
        assertNotNull(inspection, "Kotlin 应识别 Python 伪装文件")
        assertEquals(ApngDisguiseCodec.ApngDisguiseContentKind.STATIC, inspection.metadata.contentKind)
        assertEquals(80, inspection.width)
        assertEquals(60, inspection.height)

        // 2) Kotlin 还原,应与真图逐像素一致
        val workDir = File("build/interop-work").apply { mkdirs() }
        val svc = DisguiseService(JvmImageDecoder(), workDir, ResourceCoverProvider())
        val restored = svc.restoreDisguise(disguise) {}
        val restoredFrame = JvmImageIo.read(File(restored.path))
        val truthFrame = JvmImageIo.read(truth)
        assertEquals(truthFrame.width, restoredFrame.width)
        assertEquals(truthFrame.height, restoredFrame.height)
        for (y in 0 until truthFrame.height step 3) {
            for (x in 0 until truthFrame.width step 3) {
                assertEquals(truthFrame.getPixel(x, y), restoredFrame.getPixel(x, y), "pixel($x,$y)")
            }
        }
        println("CROSS-INTEROP OK: Kotlin 还原 Python 伪装成功,像素一致")
    }
}
