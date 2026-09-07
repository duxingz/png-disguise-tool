package com.pngdisguise.desktop

import java.io.File
import java.io.RandomAccessFile

/** 打印 PNG/APNG 的 chunk 序列(验证伪装结构用)。 */
object PngChunkDump {
    fun dump(file: File): List<String> {
        val chunks = mutableListOf<String>()
        RandomAccessFile(file, "r").use { input ->
            val sig = ByteArray(8)
            input.readFully(sig)
            chunks += "PNG_SIGNATURE"
            while (input.filePointer + 12 <= input.length()) {
                val length = input.readInt()
                val typeBytes = ByteArray(4).also(input::readFully)
                val type = typeBytes.toString(Charsets.US_ASCII)
                // 对 tEXt 解析关键内容
                var note = ""
                if (type == "tEXt" && length <= 200) {
                    val data = ByteArray(length).also(input::readFully)
                    note = " [" + data.toString(Charsets.ISO_8859_1).substringBefore(0.toChar()) + "]"
                } else {
                    input.skipBytes(length)
                }
                input.skipBytes(4) // crc
                chunks += "$type($length)$note"
                if (type == "IEND") break
            }
        }
        return chunks
    }
}
