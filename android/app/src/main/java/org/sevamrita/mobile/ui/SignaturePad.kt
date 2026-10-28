package org.sevamrita.mobile.ui

import android.graphics.Bitmap
import android.graphics.Paint
import android.util.Base64
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import java.io.ByteArrayOutputStream

internal class SignatureState {
    val strokes = mutableStateListOf<List<Offset>>()
    var size by mutableStateOf(IntSize.Zero)
    fun clear() = strokes.clear()
    fun imageData(): String? {
        if (strokes.isEmpty() || size.width <= 0 || size.height <= 0) return null
        val bitmap = Bitmap.createBitmap(600, 220, Bitmap.Config.ARGB_8888)
        val canvas = android.graphics.Canvas(bitmap)
        canvas.drawColor(android.graphics.Color.WHITE)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.BLACK
            strokeWidth = 4f
            style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND
            strokeJoin = Paint.Join.ROUND
        }
        val sx = 600f / size.width
        val sy = 220f / size.height
        for (stroke in strokes) {
            if (stroke.isEmpty()) continue
            val path = android.graphics.Path().apply {
                moveTo(stroke[0].x * sx, stroke[0].y * sy)
                if (stroke.size == 1) lineTo(stroke[0].x * sx + 1f, stroke[0].y * sy)
                else stroke.drop(1).forEach { lineTo(it.x * sx, it.y * sy) }
            }
            canvas.drawPath(path, paint)
        }
        val output = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
        bitmap.recycle()
        return "data:image/png;base64," + Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)
    }
}

@Composable
internal fun SignaturePad(label: String, state: SignatureState, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(label)
        Canvas(Modifier.fillMaxWidth().height(170.dp).background(Color.White)
            .border(1.dp, Color(0xFFB4C7C2)).onSizeChanged { state.size = it }
            .pointerInput(state) {
                detectDragGestures(onDragStart = { state.strokes.add(listOf(it)) }, onDrag = { change, _ ->
                    if (state.strokes.isNotEmpty()) {
                        val last = state.strokes.lastIndex
                        state.strokes[last] = state.strokes[last] + change.position
                    }
                    change.consume()
                })
            }) {
            state.strokes.forEach { stroke ->
                if (stroke.isEmpty()) return@forEach
                val path = Path().apply {
                    moveTo(stroke[0].x, stroke[0].y)
                    if (stroke.size == 1) lineTo(stroke[0].x + 1f, stroke[0].y)
                    else stroke.drop(1).forEach { lineTo(it.x, it.y) }
                }
                drawPath(path, Color.Black, style = Stroke(width = 3.dp.toPx()))
            }
        }
        OutlinedButton(onClick = state::clear, enabled = state.strokes.isNotEmpty()) { Text("Clear signature") }
    }
}
