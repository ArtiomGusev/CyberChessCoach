package com.example.myapplication

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test for JNI contract: requires a running Android device or emulator
 * so that libchessengine.so is available via System.loadLibrary.
 *
 * Verifies that ChessNative.getBestMove is a pure function: same FEN in -> same move out.
 */
@RunWith(AndroidJUnit4::class)
class ChessNativeInstrumentedTest {

    @Test
    fun ai_moves_only_once_per_turn() {
        // Position after 1. e4
        val fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b"

        val move1 = ChessNative.getBestMove(fen)
        val move2 = ChessNative.getBestMove(fen)

        assertNotNull("AI should return a valid move", move1)
        assertNotNull("AI should return a valid move on second call", move2)

        // Same position -> same suggestion (idempotency / no global state mutation)
        assertEquals("AI must be pure and return consistent results", move1, move2)
    }
}
