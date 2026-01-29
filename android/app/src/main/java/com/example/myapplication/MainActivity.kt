package com.example.myapplication

import android.app.Dialog
import android.graphics.Color
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.util.Log
import android.widget.Button
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        Log.e("AI_TEST", "🔥 MAIN ACTIVITY STARTED 🔥")

        // -------- FIND VIEWS --------
        chessBoard = findViewById(R.id.chessBoard)
        drawerLayout = findViewById(R.id.drawerLayout)
        coachText = findViewById(R.id.txtCoach)

        val btnReset = findViewById<Button>(R.id.btnReset)
        val btnUndo = findViewById<Button>(R.id.btnUndo)
        val btnChat = findViewById<Button>(R.id.btnChat)

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
                // ✅ Connect Human Move to the Hard Lock architecture
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

        // -------- BUTTONS --------
        btnReset.setOnClickListener {
            if (ChessNative.isLibraryLoaded) {
                viewModel.reset()
                chessBoard.resetBoard()
            }
            coachText.text = "🧠 New game. Control the center!"
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        btnUndo.setOnClickListener {
            // ✅ Reverts both AI and Human moves in one click
            chessBoard.undoBoth()
            viewModel.reset() // Ensure turn returns to HUMAN
            drawerLayout.closeDrawer(GravityCompat.END)
        }

        btnChat.setOnClickListener {
            if (supportFragmentManager.isStateSaved) return@setOnClickListener
            drawerLayout.closeDrawer(GravityCompat.END)

            val boardSnapshot = chessBoard.exportFEN()
            ChatBottomSheet
                .newInstance(boardSnapshot)
                .show(supportFragmentManager, "ChatBottomSheet")
        }

        chessBoard.coachListener = { comment -> coachText.text = comment }
        chessBoard.promotionListener = { r, c -> showPromotionDialog(r, c) }
    }

    private fun showPromotionDialog(r: Int, c: Int) {
        val dialog = Dialog(this)
        dialog.setContentView(R.layout.dialog_promotion)
        dialog.window?.setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
        dialog.setCancelable(false)

        fun onSelected(piece: Char) {
            chessBoard.promotePawn(r, c, piece)
            // ✅ Triggers AI turn only AFTER human selection is complete
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
