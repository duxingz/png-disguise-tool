package com.pngdisguise.android

import android.app.Application
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import com.pngdisguise.core.DisguiseService
import com.pngdisguise.core.RgbaFrame
import java.io.File
import java.io.FileOutputStream

class PngDisguiseApp : Application() {
    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    companion object {
        lateinit var instance: PngDisguiseApp
            private set
    }
}

/** Android 端封面 Provider:优先用户设置(文件),否则内置资源。 */
class AndroidCoverProvider(context: Context, private val prefs: CoverPrefs) : DisguiseService.CoverProvider {
    private val appContext = context.applicationContext

    override fun cover(): RgbaFrame {
        val customPath = prefs.coverPath
        if (customPath != null) {
            val f = File(customPath)
            if (f.isFile) {
                val bmp = BitmapFactory.decodeFile(f.absolutePath)
                if (bmp != null) return bmp.toRgbaFrame().also { bmp.recycle() }
            }
        }
        // 内置默认封面(用户提供的图,打包进 drawable-nodpi)
        val res = appContext.resources
        val id = res.getIdentifier("default_cover", "drawable", appContext.packageName)
        val bmp = BitmapFactory.decodeResource(res, id)
            ?: Bitmap.createBitmap(64, 64, Bitmap.Config.ARGB_8888).apply {
                eraseColor(0xFF2F8E7B.toInt())
            }
        return bmp.toRgbaFrame().also { bmp.recycle() }
    }
}

/** 封面偏好(存文件路径;App 私有目录内拷贝,避免相册 URI 权限问题)。 */
class CoverPrefs(context: Context) {
    private val prefs = context.getSharedPreferences("cover", Context.MODE_PRIVATE)

    var coverPath: String?
        get() = prefs.getString("path", null)
        set(value) {
            prefs.edit().putString("path", value).apply()
        }

    /** 把用户选的图拷贝到私有目录,返回新路径(持久可用)。 */
    fun importCover(context: Context, uri: Uri): String {
        val dir = File(context.filesDir, "cover").apply { mkdirs() }
        val target = File(dir, "custom_cover_${System.currentTimeMillis()}.png")
        context.contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(target).use { out -> input.copyTo(out) }
        } ?: error("无法读取所选图片")
        coverPath = target.absolutePath
        return target.absolutePath
    }
}

/** 内置封面资源也放一份到 drawable(供 AndroidCoverProvider 读)。 */
internal fun saveCoverToDrawable(context: Context, bitmap: Bitmap) {
    // 封面资源在打包时已放 drawable-nodpi;此处仅为兼容
}
