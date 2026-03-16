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
 */
data class QuickCoachUpdate(
    val scoreText: String,
    val classification: MistakeClassification,
    /** null when position is solid — dock shows fallback text. */
    val explanation: String?
)
