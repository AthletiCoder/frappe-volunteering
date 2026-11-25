package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class ExpenseSubmissionGuardTest {
    private class InvalidDetails : IOException()
    private class Fixture {
        var saved: ExpenseAttempt<String>? = null
        var result: String? = null
        var checkFails = false
        var sendFails = false
        var reject = false
        val sentKeys = mutableListOf<String>()
        var onSend: (() -> Unit)? = null
        fun guard() = ExpenseSubmissionGuard<String>(
            read = { saved }, write = { saved = it }, remove = { saved = null },
            send = { _, _, key -> sentKeys += key; onSend?.invoke(); if (reject) throw InvalidDetails(); if (sendFails) throw IOException(); result = "CLAIM-1"; "CLAIM-1" },
            recover = { if (checkFails) throw IOException(); result }, rejected = { it is InvalidDetails },
            same = { a, b -> a == b }, newKey = { "key-${sentKeys.size}" }, status = {})
    }
    @Test fun lostResponseRecoversSavedClaimWithoutResending() {
        val f = Fixture(); f.sendFails = true; f.onSend = { f.result = "CLAIM-1" }
        assertEquals("CLAIM-1", f.guard().submit("single", "private receipt"))
        assertEquals(1, f.sentKeys.size); assertNull(f.saved!!.args)
        assertEquals("CLAIM-1", f.guard().submit("single", "private receipt"))
        assertEquals(1, f.sentKeys.size)
    }
    @Test fun unknownOutcomeKeepsReceiptAndReferenceAcrossRestart() {
        val f = Fixture(); f.sendFails = true; f.checkFails = true
        assertThrows(IllegalStateException::class.java) { f.guard().submit("single", "private receipt") }
        val original = f.saved!!
        assertThrows(IOException::class.java) { f.guard().submit("single", "changed amount") }
        assertEquals(original, f.saved); assertEquals(1, f.sentKeys.size)
        f.checkFails = false; f.sendFails = false
        assertEquals("CLAIM-1", f.guard().submit("single", "private receipt"))
        assertEquals(f.sentKeys[0], f.sentKeys[1])
    }
    @Test fun validationFailureClearsAttemptButDoesNotHideTheError() {
        val f = Fixture(); f.reject = true
        assertThrows(InvalidDetails::class.java) { f.guard().submit("single", "invalid") }
        assertNull(f.saved); f.reject = false
        assertEquals("CLAIM-1", f.guard().submit("single", "corrected"))
    }
    @Test fun unresolvedAttemptCannotBeSentAgainWhileResultCheckFails() {
        val f = Fixture(); f.sendFails = true
        assertThrows(IllegalStateException::class.java) { f.guard().submit("multiple", "two receipts") }
        f.checkFails = true
        assertThrows(IOException::class.java) { f.guard().submit("multiple", "two receipts") }
        assertEquals(1, f.sentKeys.size)
    }
    @Test fun reentrantUiSubmissionIsSuppressed() {
        val f = Fixture(); val guard = f.guard()
        f.onSend = { assertThrows(IllegalStateException::class.java) { guard.submit("single", "receipt") } }
        assertEquals("CLAIM-1", guard.submit("single", "receipt")); assertEquals(1, f.sentKeys.size)
    }
}
