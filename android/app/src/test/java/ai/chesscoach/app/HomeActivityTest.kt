package ai.chesscoach.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

/**
 * Pure-Kotlin unit tests for the static helpers on
 * [HomeActivity.Companion].  Like the Onboarding tests these run on
 * the host JVM without instrumentation since the helpers do not touch
 * the Android framework.
 *
 * Invariants pinned
 * -----------------
 *  1. initialsFor returns "—" for null/blank/"demo" so the avatar
 *     never displays a misleading default.
 *  2. initialsFor returns the first two alphanumeric chars uppercased
 *     for any other identifier.
 *  3. initialsFor pads to two chars by repeating the first when the
 *     id has only one alphanumeric char.
 *  4. formatDateKicker renders "<Weekday> · Day <NNN>" with N floored
 *     at 1 (same-day visit reads as "Day 001", not "Day 000").
 *  5. formatDateKicker advances by exactly one day per 24h delta.
 */
class HomeActivityTest {

    @Test
    fun `initialsFor returns dash for null blank or demo`() {
        assertEquals("—", HomeActivity.initialsFor(null))
        assertEquals("—", HomeActivity.initialsFor(""))
        assertEquals("—", HomeActivity.initialsFor("   "))
        assertEquals("—", HomeActivity.initialsFor("demo"))
        assertEquals("—", HomeActivity.initialsFor("DEMO"))
    }

    @Test
    fun `initialsFor returns first two alphanumeric chars uppercased`() {
        assertEquals("AG", HomeActivity.initialsFor("ag"))
        // Hyphens / non-alnum are stripped first, so "artiom-gusev"
        // collapses to "artiomgusev" and the leading two letters are
        // 'a' and 'r' — NOT 'a' and the leading char of the second
        // hyphen segment.
        assertEquals("AR", HomeActivity.initialsFor("artiom-gusev"))
        assertEquals("12", HomeActivity.initialsFor("12345-uuid-tail"))
    }

    @Test
    fun `initialsFor doubles a single alphanumeric char`() {
        assertEquals("AA", HomeActivity.initialsFor("a"))
        assertEquals("XX", HomeActivity.initialsFor("x---"))
    }

    @Test
    fun `initialsFor returns dash when there are no alphanumerics`() {
        assertEquals("—", HomeActivity.initialsFor("---"))
        assertEquals("—", HomeActivity.initialsFor("   "))
    }

    @Test
    fun `formatDateKicker shows Day 001 on the first visit`() {
        // Use UTC + a parsed date string so the assertion is independent
        // of the runner's TZ and the test author isn't responsible for
        // a magic millis literal.
        withUtc {
            val tueMillis = parseUtcDate("2026-04-21")  // Tuesday
            val kicker = HomeActivity.formatDateKicker(tueMillis, tueMillis)
            assertEquals("Tuesday · Day 001", kicker)
        }
    }

    @Test
    fun `formatDateKicker advances by one day per 24h`() {
        withUtc {
            val firstSeen = parseUtcDate("2026-04-21")  // Tuesday
            val sevenDaysLater = firstSeen + TimeUnit.DAYS.toMillis(7)
            val kicker = HomeActivity.formatDateKicker(sevenDaysLater, firstSeen)
            // 7 calendar days after a Tuesday is the next Tuesday.
            assertEquals("Tuesday · Day 008", kicker)
        }
    }

    @Test
    fun `formatDateKicker pads three digits even at high day counts`() {
        withUtc {
            val firstSeen = parseUtcDate("2026-04-21")
            val day47 = firstSeen + TimeUnit.DAYS.toMillis(46)  // 47th day inclusive
            val kicker = HomeActivity.formatDateKicker(day47, firstSeen)
            assertTrue(
                "expected kicker to end in Day 047, got $kicker",
                kicker.endsWith("Day 047"),
            )
        }
    }

    @Test
    fun `formatDateKicker floors at Day 001 even with clock skew`() {
        withUtc {
            val firstSeen = parseUtcDate("2026-04-21")
            // Now is BEFORE firstSeen (clock-skew or device-time-set
            // backwards); we never want the kicker to read "Day 000"
            // or "Day -005" — floor at 1.
            val skewed = firstSeen - TimeUnit.DAYS.toMillis(5)
            val kicker = HomeActivity.formatDateKicker(skewed, firstSeen)
            assertTrue(
                "expected kicker to end in Day 001 even with skew, got $kicker",
                kicker.endsWith("Day 001"),
            )
        }
    }

    // ── helpers ──────────────────────────────────────────────────────

    private fun parseUtcDate(iso: String): Long {
        val fmt = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        return fmt.parse(iso)!!.time
    }

    private inline fun withUtc(block: () -> Unit) {
        val tz = TimeZone.getDefault()
        TimeZone.setDefault(TimeZone.getTimeZone("UTC"))
        try {
            block()
        } finally {
            TimeZone.setDefault(tz)
        }
    }
}
