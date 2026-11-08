package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerAttachmentsTest {
    @Test fun supportedEvidenceAndLimitBoundariesAreAccepted() {
        listOf("bill.PDF", "photo.jpg", "photo.jpeg", "photo.png", "photo.webp", "map.gif", "note.txt", "data.csv", "plan.docx", "work.xlsx").forEach {
            validateTrackerAttachment(it, 1)
            validateTrackerAttachment(it, TRACKER_ATTACHMENT_LIMIT.toLong())
        }
    }
    @Test fun emptyOversizeAndUnsupportedSelectionsAreRejectedBeforeUpload() {
        listOf("" to 1L, "a.exe" to 1L, "no-extension" to 1L, "proof.txt" to 0L, "proof.txt" to TRACKER_ATTACHMENT_LIMIT + 1L,
            ("a".repeat(180) + ".txt") to 1L).forEach { (name, size) ->
            try {validateTrackerAttachment(name, size); fail("Expected rejection for $name / $size")}
            catch (_: IllegalArgumentException) { }
        }
    }
    @Test fun fileSizeLabelsAreCompactAndStable() {
        assertEquals("12 B", trackerAttachmentSize(12))
        assertEquals("2 KB", trackerAttachmentSize(1025))
        assertEquals("1.5 MB", trackerAttachmentSize(1572864))
    }
}
