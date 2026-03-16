package com.example.myapplication

import org.junit.Assert.*
import org.junit.Test

/**
 * JVM unit tests for the Quick Coach dock logic.
 *
 * Invariants pinned
 * -----------------
 *  1. CLASSIFICATION_QUEEN:       queen capture → BLUNDER
 *  2. CLASSIFICATION_ROOK:        rook capture  → MISTAKE
 *  3. CLASSIFICATION_BISHOP:      bishop capture → MISTAKE
 *  4. CLASSIFICATION_KNIGHT:      knight capture → MISTAKE
 *  5. CLASSIFICATION_PAWN:        pawn capture   → INACCURACY
 *  6. CLASSIFICATION_EMPTY:       empty square   → GOOD
 *  7. CLASSIFICATION_UNKNOWN:     unknown char   → GOOD
 *  8. FORMAT_SCORE_EQUAL:         near-zero balance → "Equal"
 *  9. FORMAT_SCORE_POSITIVE:      positive balance  → "+N.N"
 * 10. FORMAT_SCORE_NEGATIVE:      negative balance  → "-N.N" (no plus sign)
 * 11. FORMAT_SCORE_BOUNDARY:      ±0.05 edge cases
 * 12. EXPLANATION_NULL_FOR_GOOD:  GOOD → null explanation
 * 13. EXPLANATION_NONNULL_BLUNDER: BLUNDER → non-null explanation
 * 14. EXPLANATION_NONNULL_MISTAKE: MISTAKE → non-null explanation
 * 15. EXPLANATION_NONNULL_INACCURACY: INACCURACY → non-null explanation
 * 16. LABEL_NONEMPTY:             all MistakeClassification labels are non-empty
 * 17. MATERIAL_BALANCE_EQUAL:     starting position has equal material
 * 18. MATERIAL_BALANCE_WHITE_ADV: removing a black piece increases white advantage
 * 19. MATERIAL_BALANCE_BLACK_ADV: removing a white piece produces negative balance
 * 20. BUILD_UPDATE_FIELDS:        buildUpdate sets all fields consistently
 * 21. BUILD_UPDATE_FALLBACK_EXPLANATION: GOOD capture → null explanation in update
 * 22. DETERMINISM: identical inputs → identical QuickCoachUpdate
 */
class QuickCoachDockTest {

    // ---------------------------------------------------------------------------
    // 1–7  classifyCapture
    // ---------------------------------------------------------------------------

    @Test fun `queen capture is BLUNDER`() {
        assertEquals(MistakeClassification.BLUNDER, QuickCoachLogic.classifyCapture('Q'))
        assertEquals(MistakeClassification.BLUNDER, QuickCoachLogic.classifyCapture('q'))
    }

    @Test fun `rook capture is MISTAKE`() {
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('R'))
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('r'))
    }

    @Test fun `bishop capture is MISTAKE`() {
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('B'))
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('b'))
    }

    @Test fun `knight capture is MISTAKE`() {
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('N'))
        assertEquals(MistakeClassification.MISTAKE, QuickCoachLogic.classifyCapture('n'))
    }

    @Test fun `pawn capture is INACCURACY`() {
        assertEquals(MistakeClassification.INACCURACY, QuickCoachLogic.classifyCapture('P'))
        assertEquals(MistakeClassification.INACCURACY, QuickCoachLogic.classifyCapture('p'))
    }

    @Test fun `empty square capture is GOOD`() {
        assertEquals(MistakeClassification.GOOD, QuickCoachLogic.classifyCapture('.'))
    }

    @Test fun `unknown char capture is GOOD`() {
        assertEquals(MistakeClassification.GOOD, QuickCoachLogic.classifyCapture('?'))
        assertEquals(MistakeClassification.GOOD, QuickCoachLogic.classifyCapture(' '))
    }

    // ---------------------------------------------------------------------------
    // 8–11  formatScore
    // ---------------------------------------------------------------------------

    @Test fun `zero balance formats as Equal`() {
        assertEquals("Equal", QuickCoachLogic.formatScore(0.0f))
    }

    @Test fun `positive balance starts with plus sign`() {
        val result = QuickCoachLogic.formatScore(3.0f)
        assertTrue("Expected '+' prefix for positive balance: $result", result.startsWith("+"))
        assertEquals("+3.0", result)
    }

    @Test fun `negative balance has no plus sign`() {
        val result = QuickCoachLogic.formatScore(-3.0f)
        assertFalse("Unexpected '+' in negative score: $result", result.startsWith("+"))
        assertEquals("-3.0", result)
    }

    @Test fun `values within boundary treated as Equal`() {
        assertEquals("Equal", QuickCoachLogic.formatScore(0.04f))
        assertEquals("Equal", QuickCoachLogic.formatScore(-0.04f))
    }

    // ---------------------------------------------------------------------------
    // 12–15  deriveExplanation
    // ---------------------------------------------------------------------------

    @Test fun `GOOD classification produces null explanation`() {
        assertNull(QuickCoachLogic.deriveExplanation(MistakeClassification.GOOD))
    }

    @Test fun `BLUNDER classification produces non-null explanation`() {
        val text = QuickCoachLogic.deriveExplanation(MistakeClassification.BLUNDER)
        assertNotNull(text)
        assertTrue(text!!.isNotBlank())
    }

    @Test fun `MISTAKE classification produces non-null explanation`() {
        val text = QuickCoachLogic.deriveExplanation(MistakeClassification.MISTAKE)
        assertNotNull(text)
        assertTrue(text!!.isNotBlank())
    }

    @Test fun `INACCURACY classification produces non-null explanation`() {
        val text = QuickCoachLogic.deriveExplanation(MistakeClassification.INACCURACY)
        assertNotNull(text)
        assertTrue(text!!.isNotBlank())
    }

    // ---------------------------------------------------------------------------
    // 16  MistakeClassification.label()
    // ---------------------------------------------------------------------------

    @Test fun `all classification labels are non-empty strings`() {
        for (c in MistakeClassification.values()) {
            assertTrue("Empty label for $c", c.label().isNotBlank())
        }
    }

    // ---------------------------------------------------------------------------
    // 17–19  materialBalance
    // ---------------------------------------------------------------------------

    private fun startingBoard(): Array<CharArray> {
        val start = arrayOf(
            "rnbqkbnr",
            "pppppppp",
            "........",
            "........",
            "........",
            "........",
            "PPPPPPPP",
            "RNBQKBNR"
        )
        return Array(8) { r -> CharArray(8) { c -> start[r][c] } }
    }

    @Test fun `starting position has balanced material`() {
        val board = startingBoard()
        assertEquals(0.0f, QuickCoachLogic.materialBalance(board), 0.01f)
    }

    @Test fun `removing a black piece increases white advantage`() {
        val board = startingBoard()
        board[0][3] = '.'  // remove black queen
        val balance = QuickCoachLogic.materialBalance(board)
        assertTrue("Expected white advantage after removing black queen, got $balance", balance > 0)
    }

    @Test fun `removing a white piece produces negative balance`() {
        val board = startingBoard()
        board[7][3] = '.'  // remove white queen
        val balance = QuickCoachLogic.materialBalance(board)
        assertTrue("Expected black advantage after removing white queen, got $balance", balance < 0)
    }

    // ---------------------------------------------------------------------------
    // 20–22  buildUpdate
    // ---------------------------------------------------------------------------

    @Test fun `buildUpdate sets all fields`() {
        val board = startingBoard()
        val update = QuickCoachLogic.buildUpdate('q', board)
        assertNotNull(update.scoreText)
        assertTrue(update.scoreText.isNotBlank())
        assertEquals(MistakeClassification.BLUNDER, update.classification)
        assertNotNull(update.explanation)
    }

    @Test fun `buildUpdate with empty capture gives null explanation`() {
        val board = startingBoard()
        val update = QuickCoachLogic.buildUpdate('.', board)
        assertEquals(MistakeClassification.GOOD, update.classification)
        assertNull(update.explanation)
    }

    @Test fun `identical inputs produce identical QuickCoachUpdate`() {
        val board = startingBoard()
        val u1 = QuickCoachLogic.buildUpdate('r', board)
        val u2 = QuickCoachLogic.buildUpdate('r', board)
        assertEquals(u1, u2)
    }
}
