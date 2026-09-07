package com.pngdisguise.desktop

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Slider
import androidx.compose.material.Text
import androidx.compose.material.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.pngdisguise.core.MaskBrushType
import com.pngdisguise.core.MosaicSession
import com.pngdisguise.core.RgbaFrame
import java.io.File
import kotlin.math.min
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun MosaicEditorScreen(state: AppState) {
    val source = state.preview?.sourceItem
    val sourceFile = source?.file
    val sourceFrame = state.preview?.frame
    if (source == null || sourceFile == null || sourceFrame == null) {
        state.navigate(Screen.Main)
        return
    }
    val original = remember(sourceFile) { copyOf(sourceFrame) }
    val session = remember(sourceFile) { MosaicSession(original) }
    val scope = rememberCoroutineScope()

    var brushType by remember { mutableStateOf(MaskBrushType.Mosaic) }
    var brushSize by remember { mutableFloatStateOf(24f) }
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }
    var revision by remember { mutableStateOf(0) }
    var busy by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { state.navigate(Screen.Main) }) { Text("← 返回") }
            Text("打码编辑", style = MaterialTheme.typography.h6, modifier = Modifier.weight(1f))
            if (session.hasVisualChanges) Text("有改动", color = Color(0xFF4CAF50), style = MaterialTheme.typography.caption)
        }

        // 画布
        Box(
            Modifier.weight(1f).fillMaxWidth().background(Color.Black).onSizeChanged { canvasSize = it },
            contentAlignment = Alignment.Center
        ) {
            Canvas(
                Modifier.fillMaxSize().pointerInput(sourceFile, canvasSize, brushSize, brushType, session) {
                    var previous: Offset? = null
                    detectDragGestures(
                        onDragStart = { pos ->
                            session.pushUndoSnapshot()
                            val p = mapToFrame(pos, canvasSize, session.working)
                            session.applyBrushAt(p.x, p.y, brushRadius(session.working, canvasSize, brushSize), brushType)
                            previous = p
                            revision++
                        },
                        onDrag = { change, _ ->
                            change.consume()
                            val p = mapToFrame(change.position, canvasSize, session.working)
                            val prev = previous ?: p
                            session.applyBrushStrokeAt(prev.x, prev.y, p.x, p.y, brushRadius(session.working, canvasSize, brushSize), brushType)
                            previous = p
                            revision++
                        },
                        onDragEnd = { previous = null },
                        onDragCancel = { previous = null }
                    )
                }
            ) {
                revision
                drawFrame(session.working)
            }
        }

        // 笔刷选择
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MaskBrushType.entries.forEach { type ->
                OutlinedButton(
                    onClick = { brushType = type },
                    modifier = Modifier.weight(1f)
                ) {
                    Text(if (brushType == type) "● ${type.label}" else type.label)
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("笔刷 ${brushSize.toInt()}", style = MaterialTheme.typography.caption)
            Slider(value = brushSize, onValueChange = { brushSize = it }, valueRange = 4f..80f, modifier = Modifier.weight(1f))
        }

        // 操作
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { if (session.undo()) revision++ }, enabled = !busy) { Text("撤销") }
            OutlinedButton(onClick = { session.reset(original); revision++ }, enabled = !busy) { Text("重置") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        try {
                            // 打码结果直接替换预览(另存到工作目录),复制/导出在主界面操作
                            val target = withContext(Dispatchers.IO) {
                                val f = File.createTempFile("mosaic_", ".png", state.workDirectory())
                                com.pngdisguise.desktop.jvmimpl.JvmImageIo.writePng(session.working, f)
                                f
                            }
                            source.output = target
                            source.status = QueueStatus.DONE
                            state.previewResult(target, source)
                            state.showStatus("打码完成,可复制或导出")
                        } finally { busy = false }
                    }
                },
                enabled = !busy
            ) { Text("完成打码") }
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        try {
                            val result = withContext(Dispatchers.IO) {
                                state.disguiseService().createDisguise(session.working) { }
                            }
                            source.output = File(result.path)
                            source.status = QueueStatus.DONE
                            state.previewResult(File(result.path), source)
                            state.showStatus("伪装已生成(打码后)")
                        } catch (e: Exception) {
                            state.showStatus("伪装失败: ${e.message}")
                        } finally { busy = false }
                    }
                },
                enabled = !busy
            ) { Text("打码后伪装") }
        }
    }
}

private fun copyOf(frame: RgbaFrame): RgbaFrame = RgbaFrame(frame.width, frame.height, frame.pixels.copyOf())

private fun DrawScope.drawFrame(frame: RgbaFrame) {
    // 等比缩放绘制
    val scale = min(size.width / frame.width, size.height / frame.height)
    val w = frame.width * scale
    val h = frame.height * scale
    val x = (size.width - w) / 2f
    val y = (size.height - h) / 2f
    // 用 ImageBitmap 绘制
    drawImage(frame.toImageBitmap(), dstOffset = IntOffset(x.toInt(), y.toInt()), dstSize = IntSize(w.toInt(), h.toInt()))
}

private fun mapToFrame(point: Offset, canvas: IntSize, frame: RgbaFrame): Offset {
    if (canvas.width == 0 || canvas.height == 0) return Offset.Zero
    val scale = min(canvas.width.toFloat() / frame.width, canvas.height.toFloat() / frame.height)
    val w = frame.width * scale
    val h = frame.height * scale
    val x = (canvas.width - w) / 2f
    val y = (canvas.height - h) / 2f
    return Offset((point.x - x) / scale, (point.y - y) / scale)
}

private fun brushRadius(frame: RgbaFrame, canvas: IntSize, brushSize: Float): Float {
    if (canvas.width == 0 || canvas.height == 0) return 1f
    val scale = min(canvas.width.toFloat() / frame.width, canvas.height.toFloat() / frame.height)
    return brushSize / 2f / scale
}
