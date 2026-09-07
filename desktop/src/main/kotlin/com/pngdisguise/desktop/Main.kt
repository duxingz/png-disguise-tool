package com.pngdisguise.desktop

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.toComposeImageBitmap
import androidx.compose.ui.graphics.painter.BitmapPainter
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import com.pngdisguise.core.RgbaFrame
import org.jetbrains.skia.Image

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        title = "png伪装工具",
        icon = rememberWindowIconPainter()
    ) {
        // this: FrameWindowScope → window: ComposeWindow
        val appState = remember { AppState() }
        App(appState, window)
    }
}

/** 窗口/任务栏图标:内置默认封面(用户提供的图)。 */
@Composable
private fun rememberWindowIconPainter(): Painter? = remember {
    runCatching {
        val stream = AppState::class.java.classLoader.getResourceAsStream("default_cover.png")
            ?: return@runCatching null
        val skiaImage = Image.makeFromEncoded(stream.readBytes())
        BitmapPainter(skiaImage.toComposeImageBitmap())
    }.getOrNull()
}

@Composable
fun App(state: AppState, window: androidx.compose.ui.awt.ComposeWindow) {
    Box(Modifier.fillMaxSize()) {
        when (state.screen) {
            Screen.Main -> MainScreen(state, window)
            Screen.MosaicEditor -> MosaicEditorScreen(state)
            Screen.Settings -> SettingsScreen(state)
        }
    }
}

/** RgbaFrame → Compose ImageBitmap */
fun RgbaFrame.toImageBitmap(): ImageBitmap {
    val image = java.awt.image.BufferedImage(width, height, java.awt.image.BufferedImage.TYPE_INT_ARGB)
    image.setRGB(0, 0, width, height, pixels, 0, width)
    return image.toComposeImageBitmap()
}

@Composable
fun FitImage(frame: RgbaFrame?, modifier: Modifier = Modifier) {
    if (frame != null) {
        Image(
            bitmap = remember(frame) { frame.toImageBitmap() },
            contentDescription = null,
            modifier = modifier,
            contentScale = ContentScale.Fit
        )
    }
}
