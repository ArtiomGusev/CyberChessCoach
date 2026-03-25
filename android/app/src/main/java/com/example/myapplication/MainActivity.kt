package com.example.myapplication

import android.app.AlertDialog
import android.app.Dialog
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.util.Log
import android.view.GestureDetector
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.animation.AlphaAnimation
import android.view.animation.Animation
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.viewModels
import androidx.core.view.GravityCompat
import androidx.appcompat.app.AppCompatActivity
import androidx.drawerlayout.widget.DrawerLayout
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private val viewModel: ChessViewModel by viewModels()

    private lateinit var chessBoard: ChessBoardView
    private lateinit var drawerLayout: DrawerLayout
    private lateinit var coachText: TextView
    private lateinit var coachDock: LinearLayout
    private lateinit var statusPulse: View
    private lateinit var scoreRow: LinearLayout
    private lateinit var txtEngineScore: TextView
    private lateinit var txtMistakeCategory: TextView

    // ── Game session state ───────────────────────────────────────────────────
    private lateinit var gameApiClient: GameApiClient
    private lateinit var authApiClient: AuthApiClient
    private lateinit var authRepo: AuthRepository
    private lateinit var txtRatingHeader: TextView
    private lateinit var txtWeaknessTags: TextView
    private lateinit var txtNextTrainingChip: TextView
    private var currentPlayerId: String = "demo"
    private val moveClassifications = mutableListOf<MistakeClassification>()

    /**
     * Cached result from the most recent /game/finish call.
     * Provides [PlayerProfileDto] (rating + confidence) and weakness categories for
     * the next chat session opened via [openChat].  Null before the first game ends.
     */
    private var lastGameFinishResponse: GameFinishResponse? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Redirect unauthenticated users to the login screen before showing
        // the board. EncryptedTokenStorage is lazily initialised; no Keystore
        // operation occurs if the token is already in the prefs cache.
        authRepo = AuthRepository(EncryptedTokenStorage(this))
        if (!authRepo.isLoggedIn()) {
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
            )
            finish()
            return
        }

        currentPlayerId = (authRepo.authState() as? AuthState.Authenticated)?.playerId ?: "demo"
        gameApiClient =
            HttpGameApiClient(
                baseUrl = BuildConfig.COACH_API_BASE,
                apiKey = BuildConfig.COACH_API_KEY,
                tokenProvider = { authRepo.getToken() },
            )
        authApiClient = HttpAuthApiClient(baseUrl = BuildConfig.COACH_API_BASE)

        // Verify SECA safe_mode at cold-start — fire-and-forget, no UI update.
        lifecycleScope.launch {
            when (val r = gameApiClient.getSecaStatus()) {
                is ApiResult.Success -> {
                    Log.d("SECA", "seca/status: safe_mode=${r.data.safeModeEnabled} bandit_enabled=${r.data.banditEnabled} version=${r.data.version}")
                    if (!r.data.safeModeEnabled) {
                        Log.w("SECA", "WARNING: backend reports safe_mode=false — bandit training may be active")
                    }
                }
                else -> Log.d("SECA", "seca/status unavailable (${r::class.simpleName})")
            }
        }

        setContentView(R.layout.activity_main)

        Log.d("AI_TEST", "MainActivity started")

        // -------- FIND VIEWS --------
        chessBoard = findViewById(R.id.chessBoard)
        drawerLayout = findViewById(R.id.drawerLayout)
        coachText = findViewById(R.id.txtCoach)
        coachDock = findViewById(R.id.txtCoachContainer)
        statusPulse = findViewById(R.id.statusPulse)
        scoreRow = findViewById(R.id.scoreRow)
        txtEngineScore = findViewById(R.id.txtEngineScore)
        txtMistakeCategory = findViewById(R.id.txtMistakeCategory)

        txtRatingHeader = findViewById(R.id.txtRatingHeader)
        txtWeaknessTags = findViewById(R.id.txtWeaknessTags)
        txtNextTrainingChip = findViewById(R.id.txtNextTrainingChip)
        val btnReset = findViewById<Button>(R.id.btnReset)
        val btnUndo = findViewById<Button>(R.id.btnUndo)
        val btnChat = findViewById<Button>(R.id.btnChat)
        val btnGameHistory = findViewById<Button>(R.id.btnGameHistory)
        val btnTraining = findViewById<Button>(R.id.btnTraining)
        val btnChangePassword = findViewById<Button>(R.id.btnChangePassword)
        val btnLogout = findViewById<Button>(R.id.btnLogout)

        // START PULSE ANIMATION
        startPulseAnimation()

        // 🛡️ SAFETY CHECK
        if (!ChessNative.isLibraryLoaded) {
            Toast.makeText(this, "Native engine failed to load!", Toast.LENGTH_LONG).show()
            coachText.text = "❌ Engine Error"
        } else {
            Log.d("AI_TEST", "Engine loaded. Ready to play.")
        }

        // 3️⃣ Wire move callback
        chessBoard.onMovePlayed = { fr, fc, tr, tc ->
            if (ChessNative.isLibraryLoaded) {
                viewModel.onHumanMove(
                    fr, fc, tr, tc,
                    applyHumanMove = { 
                        chessBoard.applyMove(fr, fc, tr, tc) 
                    },
                    exportFEN = {
                        chessBoard.exportFEN()
                    },
                    applyAIMove = { afr, afc, atr, atc ->
                        chessBoard.applyAIMove(afr, afc, atr, atc)
                    }
                )
            } else {
                Toast.makeText(this, "Engine not available", Toast.LENGTH_SHORT).show()
            }
        }

        // -------- SIDEBAR BUTTONS --------
        btnReset.setOnClickListener {
            if (ChessNative.isLibraryLoaded) {
                viewModel.reset()
                chessBoard.resetBoard()
            }
            moveClassifications.clear()
            coachText.text = "♟ New game. Control the center!"
            scoreRow.visibility = View.GONE
            txtEngineScore.text = ""
            txtMistakeCategory.text = ""
            drawerLayout.closeDrawer(GravityCompat.END)
            startNewGameSession()
        }

        btnUndo.setOnClickListener {
            chessBoard.undoBoth()
            viewModel.reset()
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        btnChat.setOnClickListener {
            openChat()
        }

        btnGameHistory.setOnClickListener {
            drawerLayout.closeDrawer(GravityCompat.END)
            val sheet = GameHistoryBottomSheet()
            sheet.gameApiClient = gameApiClient
            sheet.show(supportFragmentManager, "GameHistoryBottomSheet")
        }

        btnTraining.setOnClickListener {
            drawerLayout.closeDrawer(GravityCompat.END)
            lifecycleScope.launch {
                when (val r = gameApiClient.getNextCurriculum(currentPlayerId)) {
                    is ApiResult.Success -> {
                        if (!supportFragmentManager.isStateSaved) {
                            TrainingSessionBottomSheet
                                .newInstance(r.data)
                                .show(supportFragmentManager, "TrainingSessionBottomSheet")
                        }
                    }
                    else -> Toast.makeText(
                        this@MainActivity,
                        "Training unavailable — try again later",
                        Toast.LENGTH_SHORT,
                    ).show()
                }
            }
        }

        btnChangePassword.setOnClickListener {
            drawerLayout.closeDrawer(GravityCompat.END)
            showChangePasswordDialog()
        }

        btnLogout.setOnClickListener {
            performLogout()
        }

        // Show persisted rating and cached curriculum chip if available.
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val storedRating = prefs.getFloat(PREF_RATING, -1f)
        if (storedRating >= 0f) {
            txtRatingHeader.text = "Rating: %.0f".format(storedRating)
        }
        val cachedTopic = prefs.getString(PREF_CURRICULUM_TOPIC, null)
        val cachedExType = prefs.getString(PREF_CURRICULUM_EXERCISE_TYPE, null)
        if (cachedTopic != null) {
            txtNextTrainingChip.text = formatCurriculumChip(cachedTopic, cachedExType)
            txtNextTrainingChip.visibility = View.VISIBLE
        }

        // Sync full profile from server at cold-start (rating + skill_vector for weakness tags).
        val authToken = authRepo.getToken()
        if (authToken != null) {
            lifecycleScope.launch {
                when (val r = authApiClient.me(authToken)) {
                    is ApiResult.Success -> {
                        txtRatingHeader.text = "Rating: %.0f".format(r.data.rating)
                        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
                            .putFloat(PREF_RATING, r.data.rating)
                            .putFloat(PREF_CONFIDENCE, r.data.confidence)
                            .apply()
                        val tags = formatWeaknessTags(r.data.skillVector)
                        if (tags.isNotEmpty()) {
                            txtWeaknessTags.text = tags
                            txtWeaknessTags.visibility = View.VISIBLE
                        }
                    }
                    is ApiResult.HttpError -> Log.d("AUTH", "me() HTTP ${r.code}")
                    is ApiResult.NetworkError -> Log.d("AUTH", "me() network error", r.cause)
                    ApiResult.Timeout -> Log.d("AUTH", "me() timed out")
                }
            }
        }

        // -------- ROBUST GESTURE FOR THE WHOLE DOCK --------
        val swipeDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent): Boolean = true

            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vX: Float, vY: Float): Boolean {
                if (e1 != null && (e1.y - e2.y > 50)) {
                    coachDock.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    openChat()
                    return true
                }
                return false
            }

            override fun onSingleTapUp(e: MotionEvent): Boolean {
                coachDock.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                openChat()
                return true
            }
        })

        coachDock.isClickable = true
        coachDock.setOnTouchListener { v, event ->
            if (swipeDetector.onTouchEvent(event)) return@setOnTouchListener true
            if (event.action == MotionEvent.ACTION_UP) v.performClick()
            true
        }

        chessBoard.coachListener = { comment -> coachText.text = comment }
        chessBoard.promotionListener = { r, c -> showPromotionDialog(r, c) }

        chessBoard.onGameOver = { result ->
            val pgn = viewModel.exportPGN()
            val resultStr =
                when (result) {
                    GameResult.WHITE_WINS -> "win"
                    GameResult.BLACK_WINS -> "loss"
                    GameResult.DRAW -> "draw"
                }
            val accuracy = computeAccuracy()
            val weaknesses = computeWeaknesses(moveClassifications)
            moveClassifications.clear()
            lifecycleScope.launch {
                when (val r = gameApiClient.finishGame(GameFinishRequest(pgn, resultStr, accuracy, weaknesses, currentPlayerId))) {
                    is ApiResult.Success -> {
                        lastGameFinishResponse = r.data
                        showCoachingResult(r.data)
                    }
                    is ApiResult.HttpError -> {
                        if (r.code == 401) {
                            handleSessionExpired()
                        } else {
                            Log.w("GAME", "finishGame HTTP ${r.code}")
                        }
                    }
                    is ApiResult.NetworkError -> Log.w("GAME", "finishGame network error", r.cause)
                    ApiResult.Timeout -> Log.w("GAME", "finishGame timed out")
                }
            }
        }

        // Start initial game session
        startNewGameSession()

        // Wire real Stockfish evaluation: after each AI move, ChessViewModel calls
        // POST /engine/eval and optionally POST /live/move, then emits the result here.
        viewModel.engineEvalClient = HttpEngineEvalClient(
            baseUrl = BuildConfig.COACH_API_BASE,
            apiKey = BuildConfig.COACH_API_KEY,
        )
        viewModel.liveCoachClient = HttpLiveMoveClient(
            baseUrl = BuildConfig.COACH_API_BASE,
            apiKey = BuildConfig.COACH_API_KEY,
        )
        viewModel.onQuickCoachUpdate = { update ->
            // Track for end-of-game accuracy computation
            moveClassifications.add(update.classification)

            // Show engine score badge; degrade gracefully when engine is unavailable
            txtEngineScore.text = if (update.engineAvailable) {
                update.scoreText
            } else {
                "⚠ Eval N/A"
            }

            // Show mistake category badge with severity colour
            txtMistakeCategory.text = update.classification.label()
            val categoryColor = when (update.classification) {
                MistakeClassification.BLUNDER    -> 0xFFFF4444.toInt()
                MistakeClassification.MISTAKE    -> 0xFFFF8800.toInt()
                MistakeClassification.INACCURACY -> 0xFFFFDD00.toInt()
                MistakeClassification.GOOD       -> 0xFF00FFFF.toInt()
            }
            txtMistakeCategory.setTextColor(categoryColor)
            scoreRow.visibility = View.VISIBLE

            // Show explanation or fallback when position is solid
            coachText.text = update.explanation
                ?: "Solid move — tap for deeper analysis"
        }
    }

    companion object {
        const val PREFS_NAME = "chesscoach_prefs"
        const val PREF_RATING = "last_rating"
        const val PREF_CONFIDENCE = "last_confidence"
        const val PREF_CURRICULUM_TOPIC = "curriculum_topic"
        const val PREF_CURRICULUM_DIFFICULTY = "curriculum_difficulty"
        const val PREF_CURRICULUM_EXERCISE_TYPE = "curriculum_exercise_type"

        /**
         * Format top [maxTags] skill-vector entries as weakness tag labels.
         *
         * Entries are sorted by descending weakness score. Tags with a score ≥ 0.5
         * are marked "↑" (high weakness); those below 0.5 are marked "↓".
         * Returns an empty string when [skillVector] is empty.
         */
        fun formatWeaknessTags(skillVector: Map<String, Float>, maxTags: Int = 3): String {
            val sorted = skillVector.entries.sortedByDescending { it.value }.take(maxTags)
            if (sorted.isEmpty()) return ""
            return sorted.joinToString(" · ") { (k, v) ->
                val arrow = if (v >= 0.5f) "↑" else "↓"
                "$arrow ${k.replace('_', ' ')}"
            }
        }

        /**
         * Format the cached curriculum recommendation as a training chip label.
         *
         * Example: "↳ DRILL: endgame technique"
         */
        fun formatCurriculumChip(topic: String, exerciseType: String?): String {
            val type = exerciseType?.uppercase() ?: "TRAIN"
            return "↳ $type: ${topic.replace('_', ' ')}"
        }

        /**
         * Compute weakness rates from the accumulated move classifications.
         *
         * Returned map keys match the backend SECA schema:
         *  - "blunder_rate"    — fraction of moves classified as BLUNDER
         *  - "mistake_rate"    — fraction classified as MISTAKE
         *  - "inaccuracy_rate" — fraction classified as INACCURACY
         *
         * Returns emptyMap() when [classifications] is empty (avoids division
         * by zero and matches the previous safe fallback).
         */
        fun computeWeaknesses(classifications: List<MistakeClassification>): Map<String, Float> {
            val total = classifications.size.toFloat()
            if (total == 0f) return emptyMap()
            return mapOf(
                "blunder_rate"    to classifications.count { it == MistakeClassification.BLUNDER }    / total,
                "mistake_rate"    to classifications.count { it == MistakeClassification.MISTAKE }    / total,
                "inaccuracy_rate" to classifications.count { it == MistakeClassification.INACCURACY } / total,
            )
        }
    }

    private fun performLogout() {
        val token = authRepo.getToken()
        lifecycleScope.launch {
            if (token != null) {
                authApiClient.logout(token)   // best-effort; ignore result
            }
            authRepo.clearToken()
            startActivity(
                Intent(this@MainActivity, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
            )
            finish()
        }
    }

    private fun startPulseAnimation() {
        val pulse = AlphaAnimation(1.0f, 0.3f).apply {
            duration = 1000
            repeatMode = Animation.REVERSE
            repeatCount = Animation.INFINITE
        }
        statusPulse.startAnimation(pulse)
    }

    private fun openChat() {
        if (supportFragmentManager.isStateSaved) return
        if (drawerLayout.isDrawerOpen(GravityCompat.END)) {
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        val boardSnapshot = chessBoard.exportFEN()
        val currentMoveCount = viewModel.moveCount

        // Build player context: prefer live game result, fall back to cached prefs.
        val profile: PlayerProfileDto? = lastGameFinishResponse?.let {
            PlayerProfileDto(rating = it.newRating, confidence = it.confidence)
        } ?: run {
            val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            val cachedRating = prefs.getFloat(PREF_RATING, -1f)
            if (cachedRating >= 0f) {
                PlayerProfileDto(
                    rating = cachedRating,
                    confidence = prefs.getFloat(PREF_CONFIDENCE, 0f).coerceAtLeast(0f),
                )
            } else null
        }
        val mistakes = lastGameFinishResponse?.coachAction?.weakness?.let { listOf(it) }

        ChatBottomSheet
            .newInstance(boardSnapshot, profile, mistakes, currentMoveCount)
            .show(supportFragmentManager, "ChatBottomSheet")
    }

    /**
     * Called when the backend returns HTTP 401 during an active game session.
     * Shows a non-disruptive dialog instead of silently breaking the game flow.
     * The user can choose to re-authenticate or dismiss and continue offline.
     */
    private fun handleSessionExpired() {
        if (isFinishing || isDestroyed) return
        AlertDialog.Builder(this)
            .setTitle("Session expired")
            .setMessage("Your session has expired. Log in again to save your game progress.")
            .setPositiveButton("Log in") { _, _ ->
                authRepo.clearToken()
                startActivity(
                    Intent(this, LoginActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
                )
                finish()
            }
            .setNegativeButton("Dismiss", null)
            .show()
    }

    private fun showChangePasswordDialog() {
        if (isFinishing || isDestroyed) return
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(64, 32, 64, 16)
        }
        val etCurrent = EditText(this).apply {
            hint = "Current password"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val etNew = EditText(this).apply {
            hint = "New password (min 8 characters)"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        layout.addView(etCurrent)
        layout.addView(etNew)

        AlertDialog.Builder(this)
            .setTitle("Change Password")
            .setView(layout)
            .setPositiveButton("Save") { _, _ ->
                val current = etCurrent.text.toString()
                val new = etNew.text.toString()
                if (current.isBlank() || new.isBlank()) {
                    Toast.makeText(this, "Fields must not be empty.", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                if (new.length < 8) {
                    Toast.makeText(this, "New password must be at least 8 characters.", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                val token = authRepo.getToken() ?: return@setPositiveButton
                lifecycleScope.launch {
                    when (authApiClient.changePassword(current, new, token)) {
                        is ApiResult.Success ->
                            Toast.makeText(this@MainActivity, "Password updated.", Toast.LENGTH_SHORT).show()
                        is ApiResult.HttpError ->
                            Toast.makeText(this@MainActivity, "Incorrect current password.", Toast.LENGTH_SHORT).show()
                        else ->
                            Toast.makeText(this@MainActivity, "Network error. Please try again.", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun startNewGameSession() {
        lifecycleScope.launch {
            when (val r = gameApiClient.startGame(currentPlayerId)) {
                is ApiResult.Success -> Log.d("GAME", "Session started: ${r.data.gameId}")
                is ApiResult.HttpError -> Log.w("GAME", "startGame HTTP ${r.code}")
                is ApiResult.NetworkError -> Log.w("GAME", "startGame network error", r.cause)
                ApiResult.Timeout -> Log.w("GAME", "startGame timed out")
            }
        }
    }

    private fun computeAccuracy(): Float {
        if (moveClassifications.isEmpty()) return 0.5f
        val score =
            moveClassifications.sumOf { c ->
                when (c) {
                    MistakeClassification.GOOD -> 1.0
                    MistakeClassification.INACCURACY -> 0.75
                    MistakeClassification.MISTAKE -> 0.5
                    MistakeClassification.BLUNDER -> 0.0
                }
            }
        return (score / moveClassifications.size).toFloat()
    }

    private fun showCoachingResult(response: GameFinishResponse) {
        coachText.text = response.coachContent.title

        // Update rating header immediately so it's visible when the drawer is open
        txtRatingHeader.text = "Rating: %.0f".format(response.newRating)

        if (supportFragmentManager.isStateSaved) return
        val sheet = GameSummaryBottomSheet.newInstance(response, currentPlayerId)
        sheet.gameApiClient = gameApiClient
        sheet.show(supportFragmentManager, "GameSummaryBottomSheet")
    }

    private fun showPromotionDialog(r: Int, c: Int) {
        val dialog = Dialog(this)
        dialog.setContentView(R.layout.dialog_promotion)
        dialog.window?.setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
        dialog.setCancelable(false)

        fun onSelected(piece: Char) {
            chessBoard.promotePawn(r, c, piece)
            viewModel.onPromotionFinished(
                exportFEN = { chessBoard.exportFEN() },
                applyAIMove = { afr, afc, atr, atc -> chessBoard.applyAIMove(afr, afc, atr, atc) }
            )
            dialog.dismiss()
        }

        dialog.findViewById<Button>(R.id.btnQueen).setOnClickListener { onSelected('Q') }
        dialog.findViewById<Button>(R.id.btnRook).setOnClickListener { onSelected('R') }
        dialog.findViewById<Button>(R.id.btnBishop).setOnClickListener { onSelected('B') }
        dialog.findViewById<Button>(R.id.btnKnight).setOnClickListener { onSelected('N') }
        dialog.show()
    }
}
