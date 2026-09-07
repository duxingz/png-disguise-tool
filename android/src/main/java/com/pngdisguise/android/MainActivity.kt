package com.pngdisguise.android

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.core.ImageKind
import com.pngdisguise.core.MaskBrushType
import com.pngdisguise.core.MosaicSession
import com.pngdisguise.core.RgbaFrame
import java.io.File
import java.io.FileOutputStream
import kotlin.math.min
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** 当前打开的图片会话。 */
class OpenImage(val file: File, val frame: RgbaFrame, val isGif: Boolean, val gifFrames: Int = 1)

class MainActivity : ComponentActivity() {

    private val workDir: File get() = File(filesDir, "work").apply { mkdirs() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                AppRoot()
            }
        }
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent) {
        if (intent.action == Intent.ACTION_SEND || intent.action == Intent.ACTION_VIEW) {
            val uri = if (intent.action == Intent.ACTION_SEND) {
                intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            } else intent.data
            uri?.let { importUri(it) }
        }
    }

    /** 把分享/打开的 uri 拷贝到私有目录并解析。 */
    private fun importUri(uri: Uri) {
        lifecycleScope.launch {
            runCatching {
                val target = File(workDir, "source_${System.currentTimeMillis()}.img")
                contentResolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(target).use { out -> input.copyTo(out) }
                } ?: error("无法打开所选图片")
                val decoder = AndroidImageDecoder(this@MainActivity)
                val kind = com.pngdisguise.core.ImageKind.detect(target, decoder)
                val frame = when (kind.kind) {
                    ImageKind.GIF -> decoder.decodeGifFrames(target).frames.first()
                    else -> decoder.decode(target)
                }
                openImage = OpenImage(target, frame, kind.kind == ImageKind.GIF, kind.frameCount)
                lastKind = kind
            }.onFailure { e ->
                Toast.makeText(this@MainActivity, "打开失败: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    // Compose 可见状态
    private var openImage by mutableStateOf<OpenImage?>(null)
    private var lastKind by mutableStateOf<com.pngdisguise.core.KindResult?>(null)
    private var lastOutput by mutableStateOf<File?>(null)
    private var lastOutputKind by mutableStateOf<com.pngdisguise.core.ProcessedImage?>(null)

    @Composable
    private fun AppRoot() {
        val context = LocalContext.current
        val scope = rememberCoroutineScope()
        var screen by remember { mutableStateOf("main") } // main / mosaic / settings
        val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            uri?.let { importUri(it) }
        }

        Column(Modifier.fillMaxSize().padding(12.dp)) {
            when (screen) {
                "mosaic" -> MosaicEditor(
                    context = context,
                    scope = scope,
                    image = openImage,
                    onOutput = { file -> lastOutput = file; lastOutputKind = null },
                    onDone = { screen = "main" }
                )
                "settings" -> SettingsScreen(context) { screen = "main" }
                else -> MainScreen(
                    context = context,
                    openImage = openImage,
                    lastKind = lastKind,
                    lastOutput = lastOutput,
                    onOpenFromGallery = { picker.launch("image/*") },
                    onDisguise = {
                        scope.launch {
                            val img = openImage ?: return@launch
                            runCatching {
                                val svc = DisguiseService(
                                    AndroidImageDecoder(context),
                                    workDir,
                                    AndroidCoverProvider(context, CoverPrefs(context))
                                )
                                val result = withContext(Dispatchers.IO) { svc.createDisguise(img.file) {} }
                                lastOutput = File(result.path)
                                lastOutputKind = result
                                Toast.makeText(context, "伪装已生成", Toast.LENGTH_SHORT).show()
                            }.onFailure { Toast.makeText(context, "伪装失败: ${it.message}", Toast.LENGTH_LONG).show() }
                        }
                    },
                    onRestore = {
                        scope.launch {
                            val img = openImage ?: return@launch
                            runCatching {
                                val svc = DisguiseService(
                                    AndroidImageDecoder(context),
                                    workDir,
                                    AndroidCoverProvider(context, CoverPrefs(context))
                                )
                                val result = withContext(Dispatchers.IO) { svc.restoreDisguise(img.file) {} }
                                lastOutput = File(result.path)
                                lastOutputKind = result
                                Toast.makeText(context, "还原完成", Toast.LENGTH_SHORT).show()
                            }.onFailure { Toast.makeText(context, "还原失败: ${it.message}", Toast.LENGTH_LONG).show() }
                        }
                    },
                    onSaveToGallery = { saveToGallery(context, lastOutput) },
                    onShare = { shareFile(context, lastOutput) },
                    onOpenMosaic = { screen = "mosaic" },
                    onOpenSettings = { screen = "settings" }
                )
            }
        }
    }

    private fun saveToGallery(context: Context, file: File?) {
        if (file == null) { Toast.makeText(context, "暂无输出", Toast.LENGTH_SHORT).show(); return }
        try {
            val values = android.content.ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, file.name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/png伪装工具")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            if (uri != null) {
                context.contentResolver.openOutputStream(uri)?.use { out ->
                    file.inputStream().use { it.copyTo(out) }
                }
                values.clear()
                values.put(MediaStore.Images.Media.IS_PENDING, 0)
                context.contentResolver.update(uri, values, null, null)
                Toast.makeText(context, "已保存到 Pictures/png伪装工具", Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            Toast.makeText(context, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun shareFile(context: Context, file: File?) {
        if (file == null) { Toast.makeText(context, "暂无输出", Toast.LENGTH_SHORT).show(); return }
        val uri = androidx.core.content.FileProvider.getUriForFile(
            context, "${context.packageName}.fileprovider", file
        )
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "分享"))
    }
}

// ============ 一级界面 ============

@Composable
private fun MainScreen(
    context: Context,
    openImage: OpenImage?,
    lastKind: com.pngdisguise.core.KindResult?,
    lastOutput: File?,
    onOpenFromGallery: () -> Unit,
    onDisguise: () -> Unit,
    onRestore: () -> Unit,
    onSaveToGallery: () -> Unit,
    onShare: () -> Unit,
    onOpenMosaic: () -> Unit,
    onOpenSettings: () -> Unit
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("png伪装工具", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            TextButton(onClick = onOpenSettings) { Text("设置") }
        }

        if (openImage == null) {
            Box(Modifier.fillMaxWidth().padding(vertical = 60.dp), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("从相册选图,或在聊天软件里\n选择图片→分享到 png伪装工具")
                    Button(onClick = onOpenFromGallery) { Text("从相册选择") }
                }
            }
        } else {
            val img = openImage
            // 预览
            Box(
                Modifier.fillMaxWidth().background(Color(0xFFEEEEEE)),
                contentAlignment = Alignment.Center
            ) {
                RgbaImage(img.frame, Modifier.fillMaxWidth().padding(4.dp))
            }
            val kindLabel = when (lastKind?.kind) {
                ImageKind.CHATBAR_DISGUISE_APNG -> "已识别的 APNG 伪装图"
                ImageKind.GIF -> "GIF 动图(${lastKind?.frameCount} 帧)"
                ImageKind.OTHER_APNG -> "普通 APNG(非伪装)"
                else -> "普通图片"
            }
            Text("${img.file.name} · ${img.frame.width}×${img.frame.height} · $kindLabel", style = MaterialTheme.typography.bodySmall)

            // 操作
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val isDisguise = lastKind?.kind != ImageKind.CHATBAR_DISGUISE_APNG && lastKind?.kind != ImageKind.OTHER_APNG
                Button(onClick = onDisguise, enabled = isDisguise) { Text("APNG伪装") }
                if (lastKind?.kind == ImageKind.CHATBAR_DISGUISE_APNG) {
                    Button(onClick = onRestore) { Text("还原真图") }
                }
            }
            OutlinedButton(onClick = onOpenGallery, modifier = Modifier.fillMaxWidth()) { Text("打开其他图片") }
            OutlinedButton(onClick = onOpenMosaic, modifier = Modifier.fillMaxWidth(), enabled = !img.isGif) { Text("打码编辑…") }
        }

        lastOutput?.let { out ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("输出: ${out.name}", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onSaveToGallery) { Text("保存到相册") }
                OutlinedButton(onClick = onShare) { Text("分享") }
            }
        }
    }
}

// ============ RgbaFrame 显示 ============

@Composable
fun RgbaImage(frame: RgbaFrame, modifier: Modifier = Modifier) {
    val bmp = remember(frame) {
        val b = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.ARGB_8888)
        b.setPixels(frame.pixels, 0, frame.width, 0, 0, frame.width, frame.height)
        b.asImageBitmap()
    }
    Image(bitmap = bmp, contentDescription = null, modifier = modifier, contentScale = ContentScale.Fit)
}

// ============ 打码编辑(二级) ============

@Composable
private fun MosaicEditor(
    context: Context,
    scope: kotlinx.coroutines.CoroutineScope,
    image: OpenImage?,
    onOutput: (File) -> Unit,
    onDone: () -> Unit
) {
    if (image == null) { onDone(); return }
    val original = remember(image.file) { RgbaFrame(image.frame.width, image.frame.height, image.frame.pixels.copyOf()) }
    val session = remember(image.file) { MosaicSession(original) }
    var brushType by remember { mutableStateOf(MaskBrushType.Mosaic) }
    var brushSize by remember { mutableFloatStateOf(24f) }
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }
    var revision by remember { mutableStateOf(0) }
    var busy by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onDone) { Text("← 返回") }
            Text("打码编辑", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
        }
        Box(
            Modifier.weight(1f).fillMaxWidth().background(Color.Black).onSizeChanged { canvasSize = it },
            contentAlignment = Alignment.Center
        ) {
            androidx.compose.foundation.Canvas(
                Modifier.fillMaxSize().pointerInput(image.file, canvasSize, brushSize, brushType, session) {
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
                drawRgba(session.working)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
            MaskBrushType.entries.forEach { t ->
                OutlinedButton(onClick = { brushType = t }, modifier = Modifier.weight(1f)) {
                    Text(if (brushType == t) "● ${t.label}" else t.label)
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(horizontal = 8.dp)) {
            Text("笔刷 ${brushSize.toInt()}", style = MaterialTheme.typography.bodySmall)
            Slider(value = brushSize, onValueChange = { brushSize = it }, valueRange = 8f..80f, modifier = Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(horizontal = 8.dp)) {
            OutlinedButton(onClick = { if (session.undo()) revision++ }, modifier = Modifier.weight(1f)) { Text("撤销") }
            OutlinedButton(onClick = { session.reset(original); revision++ }, modifier = Modifier.weight(1f)) { Text("重置") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(horizontal = 8.dp)) {
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        try {
                            val f = withContext(Dispatchers.IO) {
                                val target = File(context.filesDir, "images").apply { mkdirs() }
                                val out = File(target, "mosaic_${System.currentTimeMillis()}.png")
                                writePng(session.working, out)
                                out
                            }
                            onOutput(f)
                            Toast.makeText(context, "打码图已保存", Toast.LENGTH_SHORT).show()
                            onDone()
                        } finally { busy = false }
                    }
                },
                enabled = !busy,
                modifier = Modifier.weight(1f)
            ) { Text("保存打码图") }
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        try {
                            val result = withContext(Dispatchers.IO) {
                                val svc = DisguiseService(
                                    AndroidImageDecoder(context),
                                    File(context.filesDir, "work").apply { mkdirs() },
                                    AndroidCoverProvider(context, CoverPrefs(context))
                                )
                                svc.createDisguise(session.working) {}
                            }
                            onOutput(File(result.path))
                            Toast.makeText(context, "伪装已生成(打码后)", Toast.LENGTH_SHORT).show()
                            onDone()
                        } finally { busy = false }
                    }
                },
                enabled = !busy,
                modifier = Modifier.weight(1f)
            ) { Text("打码后伪装") }
        }
    }
}

private fun DrawScope.drawRgba(frame: RgbaFrame) {
    val scale = min(size.width / frame.width, size.height / frame.height)
    val w = frame.width * scale
    val h = frame.height * scale
    val x = (size.width - w) / 2f
    val y = (size.height - h) / 2f
    val bmp = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.ARGB_8888).apply {
        setPixels(frame.pixels, 0, frame.width, 0, 0, frame.width, frame.height)
    }
    drawImage(bmp.asImageBitmap(), dstOffset = IntOffset(x.toInt(), y.toInt()), dstSize = IntSize(w.toInt(), h.toInt()))
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

private fun writePng(frame: RgbaFrame, target: File) {
    val bmp = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.ARGB_8888)
    bmp.setPixels(frame.pixels, 0, frame.width, 0, 0, frame.width, frame.height)
    FileOutputStream(target).use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    bmp.recycle()
}

// ============ 设置(封面) ============

@Composable
private fun SettingsScreen(context: Context, onDone: () -> Unit) {
    val prefs = remember { CoverPrefs(context) }
    val coverPath = remember { prefs.coverPath }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let {
            runCatching { prefs.importCover(context, it) }
                .onSuccess { Toast.makeText(context, "封面已更新", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(context, "设置失败: ${it.message}", Toast.LENGTH_LONG).show() }
        }
    }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onDone) { Text("← 返回") }
            Text("设置", style = MaterialTheme.typography.headlineSmall)
        }
        Text("伪装首帧封面", style = MaterialTheme.typography.titleMedium)
        Text("生成伪装图时,默认展示这张封面;按图片尺寸等比缩放居中。", style = MaterialTheme.typography.bodySmall)
        Box(Modifier.size(160.dp).background(Color(0xFFEEEEEE)), contentAlignment = Alignment.Center) {
            val provider = AndroidCoverProvider(context, prefs)
            val cover = remember { provider.cover() }
            RgbaImage(cover, Modifier.size(140.dp))
        }
        Button(onClick = { picker.launch("image/*") }) { Text("选择封面图片…") }
        if (coverPath != null) {
            OutlinedButton(onClick = { prefs.coverPath = null; Toast.makeText(context, "已恢复内置默认", Toast.LENGTH_SHORT).show() }) {
                Text("恢复内置默认")
            }
        }
    }
}
