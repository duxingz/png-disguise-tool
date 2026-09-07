package com.pngdisguise.core

/**
 * 打码编辑会话(平台无关):持有工作副本,管理撤销栈与"是否有改动"。
 * UI 层把拖动手势换算成位图像素坐标后调用 [applyBrushStrokeAt]。
 */
class MosaicSession(
    original: RgbaFrame,
    private val maxUndo: Int = 10
) {
    val width: Int get() = working.width
    val height: Int get() = working.height

    var working: RgbaFrame = copyFrame(original)
        private set

    var hasVisualChanges: Boolean = false
        private set

    private val undoStack = ArrayDeque<RgbaFrame>()

    /** 快照当前帧(用于撤销)。由 UI 在每次"开始一笔"时调用。 */
    fun pushUndoSnapshot() {
        if (undoStack.size >= maxUndo) undoStack.removeFirst()
        undoStack.addLast(copyFrame(working))
    }

    fun undo(): Boolean {
        if (undoStack.isEmpty()) return false
        working = undoStack.removeLast()
        hasVisualChanges = true
        return true
    }

    fun reset(original: RgbaFrame) {
        undoStack.clear()
        working = copyFrame(original)
        hasVisualChanges = false
    }

    /** 在画布坐标处画一笔(起点)。 */
    fun applyBrushAt(x: Float, y: Float, radius: Float, type: MaskBrushType) {
        MosaicEditor.applyBrush(working, x, y, radius, type)
        hasVisualChanges = true
    }

    /** 拖动画一笔(from→to 连续)。 */
    fun applyBrushStrokeAt(fromX: Float, fromY: Float, toX: Float, toY: Float, radius: Float, type: MaskBrushType) {
        MosaicEditor.applyBrushStroke(working, fromX, fromY, toX, toY, radius, type)
        hasVisualChanges = true
    }

    fun rotate90() {
        pushUndoSnapshot()
        working = MosaicEditor.rotate90(working)
        hasVisualChanges = true
    }

    private companion object {
        fun copyFrame(src: RgbaFrame): RgbaFrame = RgbaFrame(src.width, src.height, src.pixels.copyOf())
    }
}
