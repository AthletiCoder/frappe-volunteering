package org.sevamrita.mobile.ui

import androidx.compose.ui.text.AnnotatedString
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalTime
import org.sevamrita.mobile.data.inQuietHours
import kotlin.math.pow

class ExtraFeaturesTest {
    private fun luminance(c:Long):Double {
        fun v(shift:Int):Double {val s=(c shr shift and 255)/255.0;return if(s<=.04045)s/12.92 else ((s+.055)/1.055).pow(2.4)}
        return .2126*v(16)+.7152*v(8)+.0722*v(0)
    }
    private fun contrast(a:Long,b:Long):Double{val x=luminance(a);val y=luminance(b);return (maxOf(x,y)+.05)/(minOf(x,y)+.05)}
    @Test fun darkTextAndSemanticColoursMeetReadableContrast(){
        for(bg in listOf(0xFF111A20,0xFF1B262D,0xFF202D34,0xFF3A2630,0xFF243349,0xFF19382F)){
            assertTrue("Body contrast $bg",contrast(0xFFE7EFF3,bg)>=7)
            for(fg in listOf(0xFFB6C6CF,0xFFFFAFBA,0xFFA7C8FF,0xFF75DFC1))assertTrue("Semantic contrast $fg/$bg",contrast(fg,bg)>=4.5)
        }
        assertTrue(contrast(0xFF092D23,0xFF75DFC1)>=7)
    }
    @Test fun legacyChatColoursMapToDistinctReadableDarkRoles(){
        assertEquals(0xFF1B262D,darkArgb(0xFFFFFFFF))
        assertNotEquals(darkArgb(0xFFFCF5E7),darkArgb(0xFFEAF2FD))
        assertNotEquals(darkArgb(0xFFEAF2FD),darkArgb(0xFFE4F4EA))
    }
    @Test fun overnightQuietHoursIncludeStartExcludeEnd(){
        val start=LocalTime.of(22,0);val end=LocalTime.of(7,0)
        assertTrue(inQuietHours(LocalTime.of(22,0),start,end));assertTrue(inQuietHours(LocalTime.of(1,0),start,end))
        assertFalse(inQuietHours(LocalTime.of(7,0),start,end));assertFalse(inQuietHours(LocalTime.NOON,start,end))
        assertFalse(inQuietHours(start,start,start))
    }
    @Test fun daytimeQuietHoursDoNotMuteWholeDay(){
        assertTrue(inQuietHours(LocalTime.NOON,LocalTime.of(11,0),LocalTime.of(13,0)))
        assertFalse(inQuietHours(LocalTime.of(14,0),LocalTime.of(11,0),LocalTime.of(13,0)))
    }
    @Test fun mentionsDisplayNamesAndKeepStableEditableOffsets(){
        val original="Hello @[Ravi Menon](ravi@example.com), ask @[Dev Patil](dev@example.com)."
        val transformed=MentionVisualTransformation().filter(AnnotatedString(original))
        assertEquals("Hello @Ravi Menon, ask @Dev Patil.",transformed.text.text)
        assertEquals(transformed.text.text,mentionLabel(original))
        val mapped=(0..original.length).map{transformed.offsetMapping.originalToTransformed(it)}
        assertEquals(mapped.sorted(),mapped)
        assertTrue(mapped.all{it in 0..transformed.text.length})
        assertEquals(original.length,transformed.offsetMapping.transformedToOriginal(transformed.text.length))
        assertEquals("email@example.com",mentionLabel("email@example.com"))
    }
    @Test fun utilityScreensHaveBackHistoryAndCannotTakePrivateRoomArguments(){
        for(view in listOf(ChatView.SEARCH,ChatView.MENTIONS,ChatView.OUTBOX,ChatView.SETTINGS)){
            val nav=ChatNavigation().navigate(ChatRoute(view));assertEquals(ChatRoute(),nav.back().current)
            assertThrows(IllegalArgumentException::class.java){ChatRoute(view,"private")}
        }
    }
    @Test fun choosingMentionPlacesCursorAfterTagButOrdinaryEditingPreservesSelection() {
        val editing = androidx.compose.ui.text.input.TextFieldValue("@Arjun", androidx.compose.ui.text.TextRange(6))
        val tag = "@[Arjun Sharma](arjun@example.com) "
        val selected = syncMentionValue(editing, tag)
        assertEquals(tag.length, selected.selection.end)
        val middle = androidx.compose.ui.text.input.TextFieldValue(tag, androidx.compose.ui.text.TextRange(3))
        assertEquals(middle, syncMentionValue(middle, tag))
        assertEquals(0, syncMentionValue(selected, "").selection.end)
    }
    @Test fun cachedOfflineReadStaysQuietButAccessAndSessionErrorsAreNotHidden() {
        assertTrue(canReadCachedChat(true, java.net.ConnectException("Disconnected")))
        assertFalse(canReadCachedChat(false, java.net.ConnectException("Disconnected")))
        assertFalse(canReadCachedChat(true, org.sevamrita.mobile.data.PortalApiException("Denied", 403)))
        assertFalse(canReadCachedChat(true, org.sevamrita.mobile.data.PortalSessionRequiredException()))
    }
}
