package com.pngdisguise.desktop

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.core.RgbaFrame
import com.pngdisguise.core.hasGifSignature
import com.pngdisguise.desktop.jvmimpl.FileCoverProvider
import com.pngdisguise.desktop.jvmimpl.JvmImageDecoder
import com.pngdisguise.desktop.jvmimpl.JvmImageIo
import com.pngdisguise.desktop.jvmimpl.ResourceCoverProvider
import java.io.File
import java.util.prefs.Preferences

/** 应用内导航。 */
enum class Screen { Main, MosaicEditor, Settings }

/** 队列状态。 */
enum class QueueStatus { PENDING, PROCESSING, DONE, FAILED }

/** 队列里的一项(导入的待处理图)。 */
class QueueItem(val file: File) {
    val displayName: String = file.name
    var status by mutableStateOf(QueueStatus.PENDING)
    var output: File? by mutableStateOf(null)
    var error: String? by mutableStateOf(null)
}

/** 预览区内容(伪装完成后 frame/resultFile 替换为结果)。 */
class PreviewItem(
    val frame: RgbaFrame?,
    val resultFile: File? = null,
    val sourceItem: QueueItem? = null
)

/**
 * 桌面端应用状态与业务编排(批量模型,上限 [AppState.MAX_BATCH] 张)。
 */
class AppState {
    private val prefs = Preferences.userNodeForPackage(AppState::class.java)
    private val workDir = File(System.getProperty("java.io.tmpdir"), "png-disguise-work").apply { mkdirs() }

    companion object {
        const val MAX_BATCH = 150
        val IMAGE_EXTENSIONS = setOf("png", "jpg", "jpeg", "gif")
    }

    var screen by mutableStateOf(Screen.Main)
        private set

    /** 批量队列 */
    val queue = mutableListOf<QueueItem>()

    /** 队列修订号(UI 观察刷新用) */
    var queueRevision by mutableStateOf(0)
        private set

    /** 当前预览(中间大图)。伪装完成后替换为结果图。 */
    var preview by mutableStateOf<PreviewItem?>(null)

    var busy by mutableStateOf(false)
        private set

    /** 批量进度(0..1) */
    var batchProgress by mutableStateOf<Float?>(null)
        private set

    var statusMessage by mutableStateOf<String?>(null)

    /** 设置:自定义封面文件路径(null = 用内置默认) */
    var customCoverPath: String?
        get() = prefs.get("coverPath", null)
        set(value) {
            if (value == null) prefs.remove("coverPath") else prefs.put("coverPath", value)
        }

    fun navigate(target: Screen) {
        screen = target
    }

    fun showStatus(msg: String) {
        statusMessage = msg
    }

    // ---------- 导入 ----------

    /** 添加文件/文件夹(文件夹递归展开);上限 MAX_BATCH。返回(新增数, 拒绝数)。 */
    fun addPaths(paths: List<String>): Pair<Int, Int> {
        val files = expandToImageFiles(paths)
        var added = 0
        var rejected = 0
        for (f in files) {
            if (queue.size >= MAX_BATCH) {
                rejected++
                continue
            }
            queue.add(QueueItem(f))
            added++
        }
        queueRevision++
        return added to rejected
    }

    fun clearQueue() {
        queue.clear()
        queueRevision++
        preview = null
    }

    fun removeItem(item: QueueItem) {
        queue.remove(item)
        if (preview?.sourceItem == item) preview = null
        queueRevision++
    }

    /** 展开路径:文件直接收,文件夹递归收集图片扩展名(排序保证顺序稳定)。 */
    private fun expandToImageFiles(paths: List<String>): List<File> {
        val out = LinkedHashSet<File>()
        for (raw in paths) {
            val f = File(raw)
            when {
                f.isDirectory -> f.walkTopDown()
                    .filter { it.isFile && it.extension.lowercase() in IMAGE_EXTENSIONS }
                    .toSortedSet(compareBy { it.absolutePath })
                    .forEach { if (out.size < MAX_BATCH) out.add(it) }
                f.isFile && f.extension.lowercase() in IMAGE_EXTENSIONS -> out.add(f)
            }
        }
        return out.toList()
    }

    // ---------- 预览 ----------

    /** 预览某队列项(解码首帧显示)。 */
    fun previewItem(item: QueueItem) {
        preview = PreviewItem(loadFrame(item.file), sourceItem = item)
    }

    /** 预览输出结果文件(伪装完成后调用,中间大图直接替换成结果)。 */
    fun previewResult(outputFile: File, fromItem: QueueItem?) {
        preview = PreviewItem(loadFrame(outputFile), resultFile = outputFile, sourceItem = fromItem)
    }

    private fun loadFrame(file: File): RgbaFrame? = runCatching {
        if (hasGifSignature(file)) {
            JvmImageDecoder().decodeGifFrames(file).frames.first()
        } else {
            JvmImageIo.read(file)
        }
    }.getOrNull()

    // ---------- 伪装 ----------

    /** 单张伪装指定项(完成后预览直接替换为结果)。 */
    suspend fun disguiseOne(item: QueueItem) {
        item.status = QueueStatus.PROCESSING
        queueRevision++
        try {
            val result = disguiseService().createDisguise(item.file) {}
            item.output = File(result.path)
            item.status = QueueStatus.DONE
            previewResult(File(result.path), item)
        } catch (e: Exception) {
            item.error = e.message ?: "未知错误"
            item.status = QueueStatus.FAILED
        }
        queueRevision++
    }

    /** 批量伪装整个队列(含重试失败项)。 */
    suspend fun disguiseAll() {
        busy = true
        try {
            val items = queue.filter { it.status == QueueStatus.PENDING || it.status == QueueStatus.FAILED }
            var index = 0
            for (item in items) {
                item.status = QueueStatus.PROCESSING
                queueRevision++
                try {
                    val result = disguiseService().createDisguise(item.file) {}
                    item.output = File(result.path)
                    item.status = QueueStatus.DONE
                } catch (e: Exception) {
                    item.error = e.message ?: "未知错误"
                    item.status = QueueStatus.FAILED
                }
                index++
                batchProgress = index.toFloat() / items.size
            }
            batchProgress = null
            queueRevision++
        } finally {
            busy = false
        }
    }

    // ---------- 其他 ----------

    /** 当前封面 Provider(用户设置优先,否则内置默认)。 */
    fun coverProvider(): DisguiseService.CoverProvider {
        val custom = customCoverPath?.let { File(it) }
        return if (custom != null && custom.isFile) {
            FileCoverProvider(custom)
        } else {
            ResourceCoverProvider()
        }
    }

    /** 返回封面预览帧(供设置页显示)。 */
    fun currentCoverPreview(): RgbaFrame? = runCatching {
        val custom = customCoverPath?.let { File(it) }
        if (custom != null && custom.isFile) JvmImageIo.read(custom) else ResourceCoverProvider().cover()
    }.getOrNull()

    fun disguiseService(): DisguiseService = DisguiseService(JvmImageDecoder(), workDir, coverProvider())

    /** 打码等工作产物目录。 */
    fun workDirectory(): File = workDir
}
