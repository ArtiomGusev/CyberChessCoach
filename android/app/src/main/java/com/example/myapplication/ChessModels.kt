package com.example.myapplication

/**
 * Result of a move attempt.
 * Extracted from View to allow JVM testing without Android View dependencies.
 */
enum class MoveResult { SUCCESS, PROMOTION, FAILED }

/**
 * Kotlin AIMove model
 * Used by JNI to return coordinates.
 */
data class AIMove(
    val fr: Int,
    val fc: Int,
    val tr: Int,
    val tc: Int
) {
    fun isValid() = fr >= 0
}

/**
 * Mistake severity for the Quick Coach dock.
 * Derived purely from captured material — no inference, no RL.
 */
enum class MistakeClassification {
    GOOD, INACCURACY, MISTAKE, BLUNDER;
    fun label(): String = name
}

/**
 * Structured update emitted after each AI move for the Quick Coach dock.
 *
 * [scoreText]      Formatted score shown in the dock (e.g. "+1.52", "Equal", "?").
 *                  When built from the engine, this is the centipawn evaluation
 *                  formatted by [QuickCoachLogic.formatCentipawns]; when built
 *                  from local material balance it uses [QuickCoachLogic.formatScore].
 * [classification] Severity of the human's last move.
 * [explanation]    One-line coaching hint; null when position is solid.
 * [bestMove]       Engine's preferred response in UCI notation (e.g. "e2e4");
 *                  null when no engine call was made or engine unavailable.
 */
data class QuickCoachUpdate(
    val scoreText: String,
    val classification: MistakeClassification,
    /** null when position is solid — dock shows fallback text. */
    val explanation: String?,
    /** null when built from local heuristic or when engine is unavailable. */
    val bestMove: String? = null,
)
