package com.example.myapplication

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Turn { HUMAN, AI }

class ChessViewModel : ViewModel() {

    private var turn: Turn = Turn.HUMAN
    private var aiThinking = false

    /**
     * 🧪 STEP 8 — ADD A KILL-SWITCH ASSERT
     */
    private fun assertTurn(expected: Turn) {
        check(turn == expected) {
            "ILLEGAL MOVE: $expected expected, but was $turn"
        }
    }

    /**
     * 🧍 STEP 2 — HUMAN MOVE (ONLY IF ALLOWED)
     */
    fun onHumanMove(
        fr: Int, fc: Int, tr: Int, tc: Int,
        applyHumanMove: () -> ChessBoardView.MoveResult,
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        // 🔒 HARD TURN LOCK
        if (turn != Turn.HUMAN) return

        viewModelScope.launch(Dispatchers.Default) {
            // 1️⃣ Apply human move to the board (rules handled by View)
            val result = withContext(Dispatchers.Main) { applyHumanMove() }
            
            when (result) {
                ChessBoardView.MoveResult.SUCCESS -> {
                    Log.d("TURN", "Human move SUCCESS. Switching to AI.")
                    turn = Turn.AI
                    requestAIMove(exportFEN, applyAIMove)
                }
                ChessBoardView.MoveResult.PROMOTION -> {
                    // Pawn reached edge. Turn stays HUMAN until piece is picked.
                    // The UI will call onPromotionFinished() later.
                    Log.d("TURN", "Human promotion pending piece selection...")
                }
                ChessBoardView.MoveResult.FAILED -> {
                    // Stay in HUMAN turn
                }
            }
        }
    }

    /**
     * Called by UI when the user finishes selecting a promotion piece.
     */
    fun onPromotionFinished(
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (turn != Turn.HUMAN) return
        
        Log.d("TURN", "Promotion finished. Switching to AI.")
        turn = Turn.AI
        requestAIMove(exportFEN, applyAIMove)
    }

    /**
     * 🤖 STEP 3 — AI MOVE (SINGLE ENTRY POINT)
     */
    private fun requestAIMove(
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (aiThinking || turn != Turn.AI) return
        aiThinking = true

        viewModelScope.launch(Dispatchers.Default) {
            try {
                // Engine is PURE: we must give it the full state
                val fen = withContext(Dispatchers.Main) { exportFEN() }
                Log.d("AI_TEST", "AI Thinking with FEN: $fen")
                
                // STEP 6: JNI Contract
                val move = ChessNative.getBestMove(fen)

                withContext(Dispatchers.Main) {
                    processAIMoveResult(move, applyAIMove)
                }
            } finally {
                aiThinking = false
            }
        }
    }

    /**
     * ♟️ STEP 4 — APPLY AI MOVE (NO ENGINE CALLS HERE)
     */
    private fun processAIMoveResult(
        move: AIMove?,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (turn != Turn.AI) return
        
        if (move == null || !move.isValid()) {
            Log.e("AI_TEST", "AI returned no valid moves")
            turn = Turn.HUMAN
            return
        }

        assertTurn(Turn.AI)

        // Switch turn back BEFORE applying to board to allow human input again
        turn = Turn.HUMAN
        
        // Final rule execution is done by the board
        applyAIMove(move.fr, move.fc, move.tr, move.tc)
        
        Log.d("TURN", "AI move applied. Back to HUMAN.")
    }

    fun reset() {
        turn = Turn.HUMAN
        aiThinking = false
    }
}
