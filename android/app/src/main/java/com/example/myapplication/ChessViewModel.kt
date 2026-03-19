package com.example.myapplication

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Turn { HUMAN, AI }

class ChessViewModel(
    private val engineProvider: EngineProvider = NativeEngineProvider(),
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.Default,
) : ViewModel() {

    private var turn: Turn = Turn.HUMAN
    private var aiThinking = false

    private var stateId: Long = 0
    private var aiJob: Job? = null

    // ── Move history for PGN export ──────────────────────────────────────────
    private val moveHistory = mutableListOf<String>()

    /** Returns the game moves as a minimal coordinate-notation PGN string. */
    fun exportPGN(): String {
        if (moveHistory.isEmpty()) return "(no moves)"
        return moveHistory
            .mapIndexed { index, uci ->
                if (index % 2 == 0) "${index / 2 + 1}. $uci" else uci
            }
            .joinToString(" ")
    }

    private fun uciFromCoords(fr: Int, fc: Int, tr: Int, tc: Int): String {
        val files = "abcdefgh"
        return "${files[fc]}${8 - fr}${files[tc]}${8 - tr}"
    }

    private fun assertTurn(expected: Turn) {
        check(turn == expected) {
            "ILLEGAL MOVE: $expected expected, but was $turn"
        }
    }

    private fun invalidateState() {
        stateId++
        aiJob?.cancel()
        aiThinking = false
        turn = Turn.HUMAN
        moveHistory.clear()
        Log.d("STATE", "Game state invalidated. New ID: $stateId")
    }

    fun onHumanMove(
        fr: Int, fc: Int, tr: Int, tc: Int,
        applyHumanMove: () -> MoveResult,
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (turn != Turn.HUMAN) return
        
        val requestId = stateId 

        viewModelScope.launch(ioDispatcher) {
            val result = withContext(Dispatchers.Main) { applyHumanMove() }
            
            withContext(Dispatchers.Main) {
                if (stateId != requestId) return@withContext 

                when (result) {
                    MoveResult.SUCCESS -> {
                        moveHistory.add(uciFromCoords(fr, fc, tr, tc))
                        turn = Turn.AI
                        requestAIMove(exportFEN, applyAIMove)
                    }
                    MoveResult.PROMOTION -> {
                        Log.d("TURN", "Human promotion pending...")
                    }
                    MoveResult.FAILED -> {}
                }
            }
        }
    }

    fun onPromotionFinished(
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (turn != Turn.HUMAN) return
        turn = Turn.AI
        requestAIMove(exportFEN, applyAIMove)
    }

    private fun requestAIMove(
        exportFEN: () -> String,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (aiThinking || turn != Turn.AI) return
        aiThinking = true
        
        val requestId = stateId

        aiJob = viewModelScope.launch(ioDispatcher) {
            try {
                val fen = withContext(Dispatchers.Main) { exportFEN() }
                
                // 🛡️ Use engine provider instead of direct JNI
                val move = engineProvider.getBestMove(fen)

                withContext(Dispatchers.Main) {
                    if (stateId == requestId) {
                        processAIMoveResult(move, applyAIMove)
                    } else {
                        Log.w("AI_TEST", "Discarding AI move from stale state ($requestId vs $stateId)")
                    }
                }
            } finally {
                aiThinking = false
            }
        }
    }

    private fun processAIMoveResult(
        move: AIMove?,
        applyAIMove: (Int, Int, Int, Int) -> Unit
    ) {
        if (turn != Turn.AI) return
        
        if (move == null || !move.isValid()) {
            turn = Turn.HUMAN
            return
        }

        assertTurn(Turn.AI)
        turn = Turn.HUMAN
        applyAIMove(move.fr, move.fc, move.tr, move.tc)
        moveHistory.add(uciFromCoords(move.fr, move.fc, move.tr, move.tc))
    }

    fun reset() {
        invalidateState()
    }
}
