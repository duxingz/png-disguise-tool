package com.pngdisguise.desktop

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.Button
import androidx.compose.material.LinearProgressIndicator
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import java.awt.FileDialog
import java.awt.Frame
import java.awt.datatransfer.DataFlavor
import java.awt.dnd.DnDConstants
import java.awt.dnd.DropTarget
import java.awt.dnd.DropTargetDragEvent
import java.awt.dnd.DropTargetDropEvent
import java.awt.dnd.DropTargetEvent
import java.awt.dnd.DropTargetListener
import java.io.File
import kotlinx.coroutines.launch

@Composable
fun MainScreen(state: AppState, window: androidx.compose.ui.awt.ComposeWindow?) {
    val scope = rememberCoroutineScope()
    var dragHover by remember { mutableStateOf(false) }

    // 拖放导入:直接挂 AWT DropTarget 到 Compose 窗口(跨 compose 版本稳定)
    DisposableEffect(window) {
        val dropTarget: DropTarget? = window?.let { win ->
            val listener = object : DropTargetListener {
                override fun dragEnter(e: DropTargetDragEvent) { dragHover = true }
                override fun dragOver(e: DropTargetDragEvent) { dragHover = true }
                override fun dropActionChanged(e: DropTargetDragEvent) {}
                override fun dragExit(e: DropTargetEvent) { dragHover = false }
                override fun drop(e: DropTargetDropEvent) {
                    dragHover = false
                    val paths = extractDropPaths(e)
                    if (paths.isEmpty()) {
                        e.dropComplete(false)
                        state.showStatus("拖入的内容不是图片文件")
                        return
                    }
                    val (added, rejected) = state.addPaths(paths)
                    e.dropComplete(true)
                    state.showStatus(
                        buildString {
                            append("已导入 $added 张")
                            if (rejected > 0) append(",超出上限 ${AppState.MAX_BATCH} 拒绝 $rejected 张")
                        }
                    )
                    if (added > 0 && state.preview == null) {
                        state.queue.firstOrNull()?.let { state.previewItem(it) }
                    }
                }
            }
            DropTarget(win, listener).also { win.dropTarget = it }
        }
        onDispose {
            dropTarget?.let { window?.dropTarget = null }
        }
    }

    Column(
        Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // 顶栏
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("png伪装工具", style = MaterialTheme.typography.h5, modifier = Modifier.weight(1f))
            TextButton(onClick = { state.navigate(Screen.Settings) }) { Text("设置") }
        }

        // 中部:左预览 + 右队列
        Row(Modifier.weight(1f).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            // 预览区(结果替换)
            Column(Modifier.weight(1.4f).fillMaxHeight()) {
                val preview = state.preview
                Box(
                    Modifier.fillMaxWidth().weight(1f)
                        .background(if (dragHover) Color(0xFFDCE9FF) else Color(0xFFF0F0F0)),
                    contentAlignment = Alignment.Center
                ) {
                    if (preview != null && preview.frame != null) {
                        FitImage(preview.frame, Modifier.fillMaxSize().padding(8.dp))
                    } else {
                        Text(
                            if (dragHover) "松开以导入" else "把图片或文件夹拖到这里\n(也可点下方\"选择图片\")",
                            color = if (dragHover) Color(0xFF2563EB) else Color.Gray,
                            style = MaterialTheme.typography.body2
                        )
                    }
                }
                // 预览下方操作:伪装(单个)/复制/导出
                val previewSource = preview?.sourceItem
                val isResult = preview?.resultFile != null
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    Button(
                        onClick = { previewSource?.let { item -> scope.launch { state.disguiseOne(item) } } },
                        enabled = !state.busy && previewSource != null && !isResult &&
                            previewSource.status != QueueStatus.DONE
                    ) { Text("APNG伪装") }

                    Button(
                        onClick = {
                            val target = preview?.resultFile ?: previewSource?.file
                            if (target != null) {
                                val asImage = ClipboardHelper.copyImages(listOf(target))
                                state.showStatus(if (asImage) "已复制到剪贴板,去聊天窗口 Ctrl+V 粘贴" else "已复制文件路径")
                            }
                        },
                        enabled = !state.busy && (previewSource != null)
                    ) { Text("复制") }

                    OutlinedButton(
                        onClick = {
                            val source = preview?.resultFile ?: previewSource?.file
                            if (source != null) exportCopyTo(source, state)
                        },
                        enabled = !state.busy && previewSource != null
                    ) { Text("导出到…") }

                    if (isResult) {
                        TextButton(
                            onClick = { previewSource?.let { state.previewItem(it) } },
                            enabled = !state.busy
                        ) { Text("← 回原图") }
                    }
                }
                state.statusMessage?.let {
                    Text(it, color = Color(0xFF777777), style = MaterialTheme.typography.caption, modifier = Modifier.padding(top = 4.dp))
                }
            }

            // 队列列表
            Column(Modifier.weight(1f).fillMaxHeight()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "队列 (${state.queue.size}/${AppState.MAX_BATCH})",
                        style = MaterialTheme.typography.subtitle1,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = { state.clearQueue() }, enabled = !state.busy && state.queue.isNotEmpty()) { Text("清空") }
                }
                if (state.queue.isEmpty()) {
                    Box(Modifier.fillMaxSize().background(Color(0xFFFAFAFA)), contentAlignment = Alignment.Center) {
                        Text("暂无图片", color = Color.LightGray)
                    }
                } else {
                    LazyColumn(Modifier.fillMaxSize().background(Color(0xFFFAFAFA))) {
                        items(state.queue.size) { idx -> QueueRow(state, state.queue[idx]) }
                    }
                }
            }
        }

        // 批量操作区
        state.batchProgress?.let { p ->
            LinearProgressIndicator(progress = p, modifier = Modifier.fillMaxWidth())
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = { scope.launch { state.disguiseAll() } },
                enabled = !state.busy && state.queue.any { it.status == QueueStatus.PENDING || it.status == QueueStatus.FAILED }
            ) { Text("全部伪装") }
            OutlinedButton(
                onClick = { pickFiles()?.let { paths ->
                    val (added, rejected) = state.addPaths(paths)
                    state.showStatus(if (rejected > 0) "已导入 $added 张(超限拒绝 $rejected)" else "已导入 $added 张")
                } },
                enabled = !state.busy
            ) { Text("选择图片…") }
            val doneCount = state.queue.count { it.status == QueueStatus.DONE }
            Button(
                onClick = {
                    val outputs = state.queue.mapNotNull { it.output }
                    if (outputs.size == 1) {
                        val asImage = ClipboardHelper.copyImages(outputs)
                        state.showStatus(if (asImage) "已复制到剪贴板" else "已复制文件路径")
                    } else if (outputs.isNotEmpty()) {
                        exportAllTo(outputs, state)
                    }
                },
                enabled = !state.busy && doneCount > 0
            ) { Text("复制/导出全部结果 ($doneCount)") }
        }
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun QueueRow(state: AppState, item: QueueItem) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        val statusLabel = when (item.status) {
            QueueStatus.PENDING -> "待处理"
            QueueStatus.PROCESSING -> "处理中…"
            QueueStatus.DONE -> "✓"
            QueueStatus.FAILED -> "✗ ${item.error?.take(24) ?: "失败"}"
        }
        val statusColor = when (item.status) {
            QueueStatus.DONE -> Color(0xFF2E7D32)
            QueueStatus.FAILED -> Color(0xFFC62828)
            QueueStatus.PROCESSING -> Color(0xFF1565C0)
            QueueStatus.PENDING -> Color.Gray
        }
        Text(
            text = statusLabel,
            color = statusColor,
            style = MaterialTheme.typography.caption,
            modifier = Modifier.width(120.dp)
        )
        Text(
            text = item.displayName,
            style = MaterialTheme.typography.caption,
            modifier = Modifier.weight(1f),
            maxLines = 1
        )
        TextButton(onClick = { state.previewItem(item) }) { Text("预览") }
        TextButton(onClick = { state.removeItem(item) }, enabled = !state.busy) { Text("移除") }
    }
}

// ---------- 拖放数据提取 ----------

/** 从 AWT 拖放事件提取文件路径列表(文件/文件夹)。 */
private fun extractDropPaths(e: DropTargetDropEvent): List<String> {
    e.acceptDrop(DnDConstants.ACTION_COPY)
    val transferable = e.transferable
    return runCatching {
        if (transferable.isDataFlavorSupported(DataFlavor.javaFileListFlavor)) {
            @Suppress("UNCHECKED_CAST")
            val files = transferable.getTransferData(DataFlavor.javaFileListFlavor) as List<File>
            files.map { it.absolutePath }
        } else {
            emptyList()
        }
    }.getOrDefault(emptyList())
}

// ---------- 文件选择 / 导出 ----------

/** 多选图片文件。 */
fun pickFiles(): List<String>? {
    val dialog = FileDialog(null as Frame?, "选择图片(可多选)", FileDialog.LOAD)
    dialog.setMultipleMode(true)
    dialog.file = null
    dialog.isVisible = true
    val files = dialog.files ?: return null
    if (files.isEmpty()) return null
    return files.map { it.absolutePath }
}

/** 导出单个文件到用户选择的位置。 */
fun exportCopyTo(source: File, state: AppState) {
    val dialog = FileDialog(null as Frame?, "导出到", FileDialog.SAVE)
    dialog.file = source.name
    dialog.isVisible = true
    val dir = dialog.directory
    val file = dialog.file
    if (dir != null && file != null) {
        val target = File(dir, if (file.endsWith(".png") || file.contains('.')) file else "$file.png")
        source.copyTo(target, overwrite = true)
        state.showStatus("已导出: ${target.absolutePath}")
    }
}

/** 批量导出全部结果到用户选择的文件夹。 */
fun exportAllTo(outputs: List<File>, state: AppState) {
    val dialog = FileDialog(null as Frame?, "选择导出文件夹(任选一个位置即可)", FileDialog.SAVE)
    dialog.file = "placeholder.png"
    dialog.isVisible = true
    val dir = dialog.directory ?: return
    var count = 0
    for (out in outputs) {
        val target = File(dir, out.name)
        runCatching { out.copyTo(target, overwrite = true) }.onSuccess { count++ }
    }
    state.showStatus("已导出 $count 张到 $dir")
}
