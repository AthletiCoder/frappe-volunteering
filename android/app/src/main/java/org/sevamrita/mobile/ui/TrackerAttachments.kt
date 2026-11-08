package org.sevamrita.mobile.ui

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import org.sevamrita.mobile.data.text
import java.io.ByteArrayOutputStream
import java.util.Locale

internal const val TRACKER_ATTACHMENT_LIMIT = 10 * 1024 * 1024
internal val TRACKER_ATTACHMENT_MIME_TYPES = arrayOf("application/pdf", "image/*", "text/*", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

internal fun validateTrackerAttachment(filename: String, size: Long) {
    require(filename.isNotBlank() && filename.length <= 180) { "Choose a file with a name up to 180 characters." }
    require(filename.substringAfterLast('.', "").lowercase(Locale.ROOT) in setOf("pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv", "docx", "xlsx")) {
        "Choose a PDF, image, text, Word or Excel file."
    }
    require(size in 1..TRACKER_ATTACHMENT_LIMIT.toLong()) { "Choose a non-empty file up to 10 MB." }
}

internal fun trackerAttachmentSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> String.format(Locale.ROOT, "%.1f MB", bytes / 1048576.0)
    bytes >= 1024 -> "${(bytes + 1023) / 1024} KB"
    else -> "$bytes B"
}

internal fun readTrackerAttachment(context: Context, uri: Uri): JSONObject {
    val filename = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(cursor.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else null
    } ?: error("The selected file has no name. Choose it again.")
    val bytes = context.contentResolver.openInputStream(uri)?.use { input ->
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (output.size() <= TRACKER_ATTACHMENT_LIMIT) {
            val count = input.read(buffer, 0, minOf(buffer.size, TRACKER_ATTACHMENT_LIMIT + 1 - output.size()))
            if (count < 0) break
            output.write(buffer, 0, count)
        }
        output.toByteArray()
    } ?: error("Unable to read the selected file. Choose it again.")
    validateTrackerAttachment(filename, bytes.size.toLong())
    return JSONObject().put("filename", filename).put("size", bytes.size).put("content", Base64.encodeToString(bytes, Base64.NO_WRAP))
}

@Composable
internal fun TrackerAttachmentSelection(files: List<JSONObject>, reading: Boolean, error: String, enabled: Boolean,
    choose: () -> Unit, remove: (Int) -> Unit) {
    EditorSection("Attachments${if (files.isEmpty()) "" else " (${files.size}/5)"}") {
        Text("PDF, images, text, Word or Excel · up to five files · 10 MB each. Files are private to conversation members.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        files.forEachIndexed { index, file ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Description, null)
                Column(Modifier.weight(1f)) {
                    Text(file.text("filename"), maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(trackerAttachmentSize(file.optLong("size")), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { remove(index) }, enabled = enabled && !reading) { Icon(Icons.Default.Close, "Remove ${file.text("filename")}") }
            }
        }
        if (reading) Text("Reading selected files…", style = MaterialTheme.typography.bodySmall)
        if (error.isNotBlank()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = choose, enabled = enabled && !reading && files.size < 5, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.AttachFile, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Choose files")
        }
    }
}
