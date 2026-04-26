package ai.chesscoach.app

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.max
import kotlin.math.roundToInt

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
 *   III — Openings     → OpeningsActivity (static scaffold; no backend yet)
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
 * MainActivity persists a lightweight snapshot
 * ([MainActivity.PREF_LAST_GAME_*]) after every move, clears it on
 * game-over, and bumps the game number on every new session.  We
 * read those keys in [maybeShowResumeCard] and render the card iff
 * a game is in progress with at least one half-move played.
 *
 * The Resume tap launches MainActivity with [MainActivity.EXTRA_RESUME]
 * set; MainActivity.tryRestoreInProgressGame loads the saved FEN +
 * UCI history into ChessBoardView / ChessViewModel so the user picks
 * up the position they left.  Server-side session resumption is out
 * of scope — the next /game/finish creates a fresh row if the prior
 * server session has timed out.
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

        maybeShowResumeCard(prefs)

        // ── Library rows ─────────────────────────────────────────────
        findViewById<LinearLayout>(R.id.homeRowNewGame).setOnClickListener {
            launchMain(sheet = null)
        }
        findViewById<LinearLayout>(R.id.homeRowLessons).setOnClickListener {
            launchMain(sheet = MainActivity.OPEN_SHEET_TRAINING)
        }
        findViewById<LinearLayout>(R.id.homeRowOpenings).setOnClickListener {
            startActivity(Intent(this, OpeningsActivity::class.java))
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
     * Read MainActivity's in-progress snapshot from [prefs] and either
     * populate + reveal the Resume card or hide it entirely.  Hidden
     * when (a) the in-progress flag is false, (b) move count is 0, or
     * (c) the snapshot is older than [RESUME_TTL_MILLIS] (a stale
     * snapshot from days ago shouldn't claim there's an active game).
     */
    private fun maybeShowResumeCard(prefs: SharedPreferences) {
        val inProgress = prefs.getBoolean(MainActivity.PREF_LAST_GAME_IN_PROGRESS, false)
        val moveCount = prefs.getInt(MainActivity.PREF_LAST_GAME_MOVE_COUNT, 0)
        val timestamp = prefs.getLong(MainActivity.PREF_LAST_GAME_TIMESTAMP, 0L)
        val gameNumber = prefs.getInt(MainActivity.PREF_LAST_GAME_NUMBER, 0)
        val now = System.currentTimeMillis()

        if (!inProgress || moveCount <= 0 || timestamp <= 0L ||
            (now - timestamp) > RESUME_TTL_MILLIS
        ) {
            resumeBlock.visibility = View.GONE
            return
        }

        val playerRating = prefs.getFloat(MainActivity.PREF_RATING, -1f)
            .takeIf { it >= 0f }
        resumeTitle.text = formatResumeTitle(gameNumber, moveCount)
        resumeSub.text   = formatResumeSub(playerRating, timestamp)
        resumeBlock.visibility = View.VISIBLE
        findViewById<View>(R.id.homeResumeCard).setOnClickListener {
            // EXTRA_RESUME tells MainActivity.onCreate to skip
            // startNewGameSession() and apply the saved FEN / UCI
            // list from PREF_LAST_GAME_FEN / PREF_LAST_GAME_UCI_HISTORY
            // — see MainActivity.tryRestoreInProgressGame().
            startActivity(
                Intent(this, MainActivity::class.java)
                    .putExtra(MainActivity.EXTRA_RESUME, true),
            )
        }
    }

    companion object {
        const val PREFS_NAME = MainActivity.PREFS_NAME
        const val PREF_HOME_FIRST_SEEN_AT = "home_first_seen_at"

        /**
         * A Resume snapshot older than this gets treated as stale
         * (e.g. the user backgrounded mid-game and didn't return for
         * days; the AI side and server session have long since timed
         * out).  6h matches the rough "session" semantics the rest of
         * the app uses.
         */
        const val RESUME_TTL_MILLIS = 6L * 60L * 60L * 1000L

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

        /**
         * "Game NNN · move M" — three-digit game number to match the
         * design ("Game 047 · move 14").  [gameNumber] is the value
         * MainActivity bumps in startNewGameSession; [moveCount] is
         * half-moves played so far.
         */
        fun formatResumeTitle(gameNumber: Int, moveCount: Int): String =
            "Game ${"%03d".format(max(1, gameNumber))} · move $moveCount"

        /**
         * "vs. ~XXXX · HH:mm" — opponent rating biased ~40 below the
         * player's (matches the Onboarding handoff intent).  When no
         * cached rating is available we fall back to "vs. adaptive".
         * Time renders in the device's local timezone since the kicker
         * itself is a wall-clock display.
         */
        fun formatResumeSub(playerRating: Float?, timestampMillis: Long): String {
            val opponent = playerRating
                ?.let { (it - 40f).coerceAtLeast(800f).roundToInt() }
                ?.let { "vs. ~$it" }
                ?: "vs. adaptive"
            val time = SimpleDateFormat("HH:mm", Locale.US).format(Date(timestampMillis))
            return "$opponent · $time"
        }
    }
}
