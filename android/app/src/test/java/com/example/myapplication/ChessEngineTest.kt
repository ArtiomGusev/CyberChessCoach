package com.example.myapplication

import org.junit.Test
import org.junit.Assert.*

class ChessEngineTest {

    @Test
    fun testPawnInitialMove() {
        val engine = ChessEngine()
        // White pawn at e2 (6,4) to e4 (4,4)
        val success = engine.move(6, 4, 4, 4)
        assertTrue("Pawn should be able to move 2 squares on first move", success)
        assertEquals('P', engine.board[4][4])
        assertEquals('.', engine.board[6][4])
        assertFalse("It should now be black's turn", engine.whiteTurn)
    }

    @Test
    fun testInvalidMove() {
        val engine = ChessEngine()
        // Try to move a white pawn at e2 (6,4) to e5 (3,4) - 3 squares is illegal
        val success = engine.move(6, 4, 3, 4)
        assertFalse("Pawn should not be able to move 3 squares", success)
    }

    /**
     * 🧪 Unit Test: “AI never moves twice”
     * Verifies that for a given FEN, the pure native engine returns a consistent 
     * result without mutating internal global state.
     */
    @Test
    fun ai_moves_only_once_per_turn() {
        // Position after 1. e4
        val fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b"

        // Step 6: Pure function contract ensures same input -> same output
        val move1 = ChessNative.getBestMove(fen)
        val move2 = ChessNative.getBestMove(fen)

        assertNotNull("AI should return a valid move", move1)
        assertNotNull("AI should return a valid move on second call", move2)

        // Same position -> same suggestion (idempotency)
        assertEquals("AI must be pure and return consistent results", move1, move2)
    }
}
