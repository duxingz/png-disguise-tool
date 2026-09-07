package com.pngdisguise.core

import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.hypot

enum class MaskBrushType(val label: String) {
    Mosaic("马赛克"),
    Black("黑色"),
    White("白色")
}

/** 马赛克打码编辑(直接改 [RgbaFrame] 像素,纯逻辑无 UI)。 */
object MosaicEditor {

    /** 在 (x,y) 处画一个笔刷圆点(bitmap 坐标)。 */
    fun applyBrush(frame: RgbaFrame, x: Float, y: Float, radius: Float, type: MaskBrushType) {
        if (x !in 0f..frame.width.toFloat() || y !in 0f..frame.height.toFloat()) return
        if (type != MaskBrushType.Mosaic) {
            val color = when (type) {
                MaskBrushType.Black -> 0xFF000000.toInt()
                MaskBrushType.White -> 0xFFFFFFFF.toInt()
                else -> return
            }
            drawCircle(frame, x, y, radius, color)
            return
        }
        // 马赛克:以块为单位采样平均色填充圆形覆盖区域
        val block = (radius / 3f).toInt().coerceAtLeast(6)
        val left = floor((x - radius) / block).toInt() * block
        val top = floor((y - radius) / block).toInt() * block
        val right = ceil((x + radius) / block).toInt() * block
        val bottom = ceil((y + radius) / block).toInt() * block
        var by = top
        while (by < bottom) {
            var bx = left
            while (bx < right) {
                val cx = bx + block / 2f
                val cy = by + block / 2f
                val dx = cx - x
                val dy = cy - y
                if (dx * dx + dy * dy <= radius * radius) {
                    fillBlock(frame, bx, by, block)
                }
                bx += block
            }
            by += block
        }
    }

    /** 拖动路径:在 from→to 之间按步长补点画连续笔刷。 */
    fun applyBrushStroke(frame: RgbaFrame, fromX: Float, fromY: Float, toX: Float, toY: Float, radius: Float, type: MaskBrushType) {
        val distance = hypot(toX - fromX, toY - fromY)
        val steps = ceil(distance / (radius * 0.35f).coerceAtLeast(1f)).toInt().coerceAtLeast(1)
        for (index in 1..steps) {
            val fraction = index.toFloat() / steps
            applyBrush(
                frame,
                fromX + (toX - fromX) * fraction,
                fromY + (toY - fromY) * fraction,
                radius,
                type
            )
        }
    }

    /** 纯色实心圆(非马赛克)。 */
    private fun drawCircle(frame: RgbaFrame, cx: Float, cy: Float, radius: Float, color: Int) {
        val r2 = radius * radius
        val xMin = floor(cx - radius).toInt().coerceAtLeast(0)
        val xMax = ceil(cx + radius).toInt().coerceAtMost(frame.width - 1)
        val yMin = floor(cy - radius).toInt().coerceAtLeast(0)
        val yMax = ceil(cy + radius).toInt().coerceAtMost(frame.height - 1)
        for (y in yMin..yMax) {
            for (x in xMin..xMax) {
                val dx = x + 0.5f - cx
                val dy = y + 0.5f - cy
                if (dx * dx + dy * dy <= r2) frame.setPixel(x, y, color)
            }
        }
    }

    /** 马赛克块:以块内中心像素色填充整块(与原版一致,块内同色)。 */
    private fun fillBlock(frame: RgbaFrame, bx: Int, by: Int, block: Int) {
        val sampleX = (bx + block / 2).coerceIn(0, frame.width - 1)
        val sampleY = (by + block / 2).coerceIn(0, frame.height - 1)
        val color = frame.getPixel(sampleX, sampleY)
        val xEnd = (bx + block).coerceAtMost(frame.width)
        val yEnd = (by + block).coerceAtMost(frame.height)
        for (y in by.coerceAtLeast(0) until yEnd) {
            for (x in bx.coerceAtLeast(0) until xEnd) {
                frame.setPixel(x, y, color)
            }
        }
    }

    /** 顺时针旋转 90°,返回新帧。 */
    fun rotate90(frame: RgbaFrame): RgbaFrame {
        val out = RgbaFrame(frame.height, frame.width)
        for (y in 0 until frame.height) {
            for (x in 0 until frame.width) {
                out.setPixel(frame.height - 1 - y, x, frame.getPixel(x, y))
            }
        }
        return out
    }
}

/** 计算两点间距/距离的工具(供 UI 调用)。 */
fun distance(x1: Float, y1: Float, x2: Float, y2: Float): Float = hypot(x2 - x1, y2 - y1)
