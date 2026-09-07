package com.pngdisguise.desktop

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.material.Text
import androidx.compose.material.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun SettingsScreen(state: AppState) {
    var coverPath by remember { mutableStateOf(state.customCoverPath) }
    var preview by remember { mutableStateOf(state.currentCoverPreview()) }

    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { state.navigate(Screen.Main) }) { Text("← 返回") }
            Text("设置", style = MaterialTheme.typography.h5)
        }

        // 封面设置
        Text("伪装首帧封面", style = MaterialTheme.typography.h6)
        Text("生成的伪装图,默认展示这张封面。生成时会按图片尺寸等比缩放居中。", style = MaterialTheme.typography.caption)
        Box(
            Modifier.size(180.dp).background(Color(0xFFF0F0F0)),
            contentAlignment = Alignment.Center
        ) {
            preview?.let { FitImage(it, Modifier.fillMaxSize().padding(4.dp)) }
                ?: Text("无封面", color = Color.Gray)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                pickFiles()?.firstOrNull()?.let { path ->
                    state.customCoverPath = path
                    coverPath = path
                    preview = state.currentCoverPreview()
                }
            }) { Text("选择封面图片…") }
            OutlinedButton(onClick = {
                state.customCoverPath = null
                coverPath = null
                preview = state.currentCoverPreview()
            }) { Text("恢复内置默认") }
        }
        if (coverPath != null) {
            Text("当前: $coverPath", style = MaterialTheme.typography.caption, color = Color.Gray)
        } else {
            Text("当前: 内置默认", style = MaterialTheme.typography.caption, color = Color.Gray)
        }
    }
}
