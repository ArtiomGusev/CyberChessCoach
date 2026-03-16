package com.example.myapplication

import kotlin.math.abs

/**
 * Pure-Kotlin logic for the Quick Coach dock.
 *
 * All computation is deterministic:
 *  - Material balance from board state (piece-count heuristic)
 *  - Score formatted as "+1.5", "Equal", "-2.0"
 *  - Capture classification: captured piece value → severity tier
 *  - One-line explanation derived from classification tier
 *
 * No model inference, no RL, no backend calls.
 */
object QuickCoachLogic {

    private val PIECE_VALUE = mapOf(
        'p' to 1, 'n' to 3, 'b' to 3, 'r' to 5, 'q' to 9
    )

    /**
     * Compute material balance (white minus black, in pawn units).
     * Positive = white advantage; negative = black advantage.
     */
    fun materialBalance(board: Array<CharArray>): Float {
        var white = 0f
        var black = 0f
        for (row in board) {
            for (ch in row) {
                val value = PIECE_VALUE[ch.lowercaseChar()]?.toFloat() ?: continue
                if (ch.isUpperCase()) white += value else black += value
            }
        }
        return white - black
    }

    /**
     * Format a material balance float as "+1.5", "Equal", or "-2.0".
     * Values within ±0.05 are considered equal.
     */
    fun formatScore(balance: Float): String = when {
        abs(balance) < 0.05f -> "Equal"
        balance > 0f         -> "+%.1f".format(balance)
        else                 -> "%.1f".format(balance)
    }

    /**
     * Classify the human's last move based on what the AI captured.
     * '.' or any unmapped char → GOOD (AI took nothing).
     */
    fun classifyCapture(capturedPiece: Char): MistakeClassification {
        return when (PIECE_VALUE[capturedPiece.lowercaseChar()] ?: 0) {
            9    -> MistakeClassification.BLUNDER     // queen hung
            5    -> MistakeClassification.MISTAKE     // rook hung
            3    -> MistakeClassification.MISTAKE     // bishop or knight hung
            1    -> MistakeClassification.INACCURACY  // pawn dropped
            else -> MistakeClassification.GOOD
        }
    }

    /**
     * Derive a one-line coaching explanation from the classification.
     * Returns null for GOOD moves — the dock shows a generic fallback instead.
     */
    fun deriveExplanation(classification: MistakeClassification): String? = when (classification) {
        MistakeClassification.BLUNDER    -> "Piece left undefended — engine capitalised."
        MistakeClassification.MISTAKE    -> "Material lost. Protect pieces before advancing."
        MistakeClassification.INACCURACY -> "A pawn dropped. Keep all pieces covered."
        MistakeClassification.GOOD       -> null
    }

    /**
     * Build a [QuickCoachUpdate] from the AI's captured piece and the
     * board state after the AI's move has been applied.
     */
    fun buildUpdate(capturedPiece: Char, board: Array<CharArray>): QuickCoachUpdate {
        val classification = classifyCapture(capturedPiece)
        val balance = materialBalance(board)
        return QuickCoachUpdate(
            scoreText = formatScore(balance),
            classification = classification,
            explanation = deriveExplanation(classification)
        )
    }
}
