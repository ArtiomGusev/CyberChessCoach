package ai.chesscoach.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.max

/**
 * Cereveon · Atrium · Home / Library (handoff screen #5).
 *
 * Post-auth landing.  Replaces the old "register/login → MainActivity"
 * routing: LoginActivity now lands here (or routes via [OnboardingActivity]
 * for first-run users), and the user picks what they want to do next from
 * the four library rows or the bottom tab bar.
 *
 * Library routing
 * ---------------
 *   I   — New game     → MainActivity (no extras; existing flow takes over)
 *   II  — Lessons      → MainActivity + EXTRA_OPEN_SHEET=training
 *   III — Openings     → no-op (AtriumOpenings is not built yet — Toast)
 *   IV  — Past games   → MainActivity + EXTRA_OPEN_SHEET=history
 *
 * Bottom tab bar
 * --------------
 *   Home    — active, no-op
 *   Lessons → MainActivity + EXTRA_OPEN_SHEET=training
 *   Coach   → MainActivity + EXTRA_OPEN_SHEET=chat
 *   You     → MainActivity + EXTRA_OPEN_SHEET=profile
 *
 * Day counter
 * -----------
 * The date kicker reads "<Weekday> · Day <N>" where N is the number of
 * days since the user first opened Home.  We persist the epoch millis of
 * the first visit in [PREF_HOME_FIRST_SEEN_AT] and clamp the displayed
 * value at 1 so a fresh install always shows "Day 1".
 *
 * Resume card
 * -----------
 * Hidden for now.  When MainActivity grows a "current game in progress"
 * persistence hook (or the backend exposes an unfinished-game query),
 * the [updateResumeCard] helper can be wired to populate it; the layout
 * already includes the card markup behind a `gone` visibility flag.
 */
class HomeActivity : AppCompatActivity() {

    private lateinit var avatar: TextView
    private lateinit var dateKicker: TextView
    private lateinit var resumeBlock: View
    private lateinit var resumeTitle: TextView
    private lateinit var resumeSub: TextView

    private val authRepo: AuthRepository by lazy {
        AuthRepository(EncryptedTokenStorage(this))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Defensive: if the user's session expired between LoginActivity
        // and Home opening, kick them back to login rather than render a
        // half-authenticated surface.
        if (!authRepo.isLoggedIn()) {
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
            )
            finish()
            return
        }

        setContentView(R.layout.activity_home)

        avatar       = findViewById(R.id.homeAvatar)
        dateKicker   = findViewById(R.id.homeDateKicker)
        resumeBlock  = findViewById(R.id.homeResumeBlock)
        resumeTitle  = findViewById(R.id.homeResumeTitle)
        resumeSub    = findViewById(R.id.homeResumeSub)

        val playerId = (authRepo.authState() as? AuthState.Authenticated)?.playerId
        avatar.text = initialsFor(playerId)

        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val firstSeen = prefs.getLong(PREF_HOME_FIRST_SEEN_AT, -1L)
            .takeIf { it > 0L }
            ?: System.currentTimeMillis().also {
                prefs.edit().putLong(PREF_HOME_FIRST_SEEN_AT, it).apply()
            }
        dateKicker.text = formatDateKicker(System.currentTimeMillis(), firstSeen)

        // Resume card stays hidden until a downstream hook calls
        // updateResumeCard(); the markup is inflated regardless so the
        // wiring is a one-liner when the data lands.
        resumeBlock.visibility = View.GONE

        // ── Library rows ─────────────────────────────────────────────
        findViewById<LinearLayout>(R.id.homeRowNewGame).setOnClickListener {
            launchMain(sheet = null)
        }
        findViewById<LinearLayout>(R.id.homeRowLessons).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_TRAINING)
        }
        findViewById<LinearLayout>(R.id.homeRowOpenings).setOnClickListener {
            // No AtriumOpenings screen yet; a Toast is honest about it
            // (a chevron row that does nothing on tap is a worse signal).
            Toast.makeText(this, "Openings — coming soon", Toast.LENGTH_SHORT).show()
        }
        findViewById<LinearLayout>(R.id.homeRowPastGames).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_HISTORY)
        }

        // ── Bottom tab bar ───────────────────────────────────────────
        findViewById<LinearLayout>(R.id.homeTabHome).setOnClickListener { /* already here */ }
        findViewById<LinearLayout>(R.id.homeTabLessons).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_TRAINING)
        }
        findViewById<LinearLayout>(R.id.homeTabCoach).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_CHAT)
        }
        findViewById<LinearLayout>(R.id.homeTabYou).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_PROFILE)
        }

        // Mirror the cached rating into the "I — New game" sub so it
        // reflects the player's current calibration without waiting for
        // a network round-trip.  The opponent rating is biased ~40
        // below per the Onboarding handoff.
        val cachedRating = prefs.getFloat(MainActivity.PREF_RATING, -1f)
        if (cachedRating >= 0f) {
            val opponent = OnboardingActivity.formatFirstOpponent(cachedRating)
            findViewById<TextView>(R.id.homeRowNewGameSub).text =
                "Adaptive opponent · $opponent"
        }
    }

    /**
     * Build a MainActivity intent that optionally asks the activity to
     * open a specific bottom sheet on startup.  Passing [sheet] = null
     * just launches MainActivity in its default state ("New game").
     */
    private fun launchMain(sheet: String?) {
        val intent = Intent(this, MainActivity::class.java)
        if (sheet != null) {
            intent.putExtra(MainActivity.EXTRA_OPEN_SHEET, sheet)
        }
        startActivity(intent)
    }

    /**
     * Wired but currently unused: when a "last game in progress" hook
     * lands (either MainActivity persisting `last_game_id` + move count
     * to prefs, or the backend exposing an unfinished-game query), call
     * this to populate and reveal the Resume card.
     */
    @Suppress("unused")
    fun updateResumeCard(title: String?, sub: String?) {
        if (title.isNullOrBlank()) {
            resumeBlock.visibility = View.GONE
            return
        }
        resumeTitle.text = title
        resumeSub.text = sub.orEmpty()
        resumeBlock.visibility = View.VISIBLE
    }

    companion object {
        const val PREFS_NAME = MainActivity.PREFS_NAME
        const val PREF_HOME_FIRST_SEEN_AT = "home_first_seen_at"

        /**
         * Compute up-to-2-letter initials from a player identifier.
         * The auth layer currently surfaces only `playerId` (no email /
         * display name), so we derive initials from whatever it gives
         * us.  Returns "—" for null/blank/"demo" so the avatar reads as
         * "no identity yet" rather than a misleading "DE".
         */
        fun initialsFor(playerId: String?): String {
            if (playerId.isNullOrBlank()) return "—"
            val cleaned = playerId.trim()
            if (cleaned.equals("demo", ignoreCase = true)) return "—"
            // Take the first two alphanumeric chars; if the id is short
            // (e.g. a single-char username), pad with the same char.
            val alnum = cleaned.filter { it.isLetterOrDigit() }
            if (alnum.isEmpty()) return "—"
            val a = alnum[0].uppercaseChar()
            val b = if (alnum.length >= 2) alnum[1].uppercaseChar() else a
            return "$a$b"
        }

        /**
         * "<Weekday> · Day <N>" — N = days between [firstSeenAtMillis]
         * and [nowMillis], floored at 1 so a same-day visit reads as
         * "Day 1" rather than "Day 0".
         *
         * Locale.US / TimeZone.getDefault() — weekday name is rendered
         * in the locale the design ships with (English) but the day
         * arithmetic uses the device's local time so "today" lines up
         * with the user's calendar.
         */
        fun formatDateKicker(nowMillis: Long, firstSeenAtMillis: Long): String {
            val weekday = SimpleDateFormat("EEEE", Locale.US).format(Date(nowMillis))
            val deltaDays = TimeUnit.MILLISECONDS.toDays(nowMillis - firstSeenAtMillis)
            val dayN = max(1L, deltaDays + 1L)
            return "$weekday · Day ${"%03d".format(dayN)}"
        }
    }
}
