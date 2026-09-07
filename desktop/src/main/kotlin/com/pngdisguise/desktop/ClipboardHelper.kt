package com.pngdisguise.desktop

import java.awt.Image
import java.awt.Toolkit
import java.awt.datatransfer.Clipboard
import java.awt.datatransfer.DataFlavor
import java.awt.datatransfer.StringSelection
import java.awt.datatransfer.Transferable
import java.awt.datatransfer.UnsupportedFlavorException
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO

/**
 * 剪贴板图片复制:把 PNG 文件作为图像对象放进系统剪贴板,
 * 聊天窗口(QQ/微信)Ctrl+V 可直接粘贴发送。
 * 多张时 QQ 粘贴只取一张,所以 >1 张时复制文件路径列表(资源管理器式粘贴)并返回 false 提示用"导出"。
 */
object ClipboardHelper {

    /** @return true=已作为图像复制;false=图片多于一张,已复制文件路径(建议改用导出)。 */
    fun copyImages(files: List<File>): Boolean {
        val clipboard = Toolkit.getDefaultToolkit().systemClipboard
        if (files.isEmpty()) return false
        if (files.size == 1) {
            val img = readImage(files[0])
            if (img != null) {
                clipboard.setContents(ImageSelection(img), null)
                return true
            }
        }
        // 多张:复制文件路径(以换行分隔),粘贴到支持文件的窗口
        val paths = files.joinToString("\n") { it.absolutePath }
        clipboard.setContents(StringSelection(paths), null)
        return false
    }

    private fun readImage(file: File): BufferedImage? = runCatching {
        ImageIO.read(file)
    }.getOrNull()

    private class ImageSelection(private val image: Image) : Transferable {
        override fun getTransferData(flavor: DataFlavor): Any {
            if (flavor == DataFlavor.imageFlavor) return image
            throw UnsupportedFlavorException(flavor)
        }

        override fun isDataFlavorSupported(flavor: DataFlavor): Boolean =
            flavor == DataFlavor.imageFlavor

        override fun getTransferDataFlavors(): Array<DataFlavor> = arrayOf(DataFlavor.imageFlavor)
    }
}
