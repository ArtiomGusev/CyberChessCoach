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
