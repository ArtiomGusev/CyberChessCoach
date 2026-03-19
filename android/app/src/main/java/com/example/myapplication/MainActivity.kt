package com.example.myapplication

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
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.viewModels
import androidx.core.view.GravityCompat
import androidx.appcompat.app.AppCompatActivity
import androidx.drawerlayout.widget.DrawerLayout

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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Redirect unauthenticated users to the login screen before showing
        // the board. EncryptedTokenStorage is lazily initialised; no Keystore
        // operation occurs if the token is already in the prefs cache.
        val authRepository = AuthRepository(EncryptedTokenStorage(this))
        if (!authRepository.isLoggedIn()) {
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
            )
            finish()
            return
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

        val btnReset = findViewById<Button>(R.id.btnReset)
        val btnUndo = findViewById<Button>(R.id.btnUndo)
        val btnChat = findViewById<Button>(R.id.btnChat)

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
            coachText.text = "♟ New game. Control the center!"
            scoreRow.visibility = View.GONE
            txtEngineScore.text = ""
            txtMistakeCategory.text = ""
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        btnUndo.setOnClickListener {
            chessBoard.undoBoth()
            viewModel.reset()
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        btnChat.setOnClickListener {
            openChat()
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

        chessBoard.quickCoachListener = { update ->
            // Show engine score badge
            txtEngineScore.text = update.scoreText

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
        ChatBottomSheet
            .newInstance(boardSnapshot)
            .show(supportFragmentManager, "ChatBottomSheet")
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
