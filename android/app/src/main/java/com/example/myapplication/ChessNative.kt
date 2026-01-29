package com.example.myapplication

import android.util.Log

/**
 * ✅ STEP 6 — JNI CONTRACT (ONE FUNCTION)
 * This is the SINGLE authority for Native calls.
 */
object ChessNative {
    var isLibraryLoaded = false
        private set

    init {
        try {
            System.loadLibrary("chessengine")
            isLibraryLoaded = true
            Log.e("AI_TEST", "✅ Native library loaded")
        } catch (e: Throwable) {
            Log.e("AI_TEST", "❌ Failed to load native library: ${e.message}")
        }
    }

    /**
     * Pure function: FEN -> ONE best move for Black.
     * No side effects in C++.
     */
    external fun getBestMove(fen: String): AIMove?

    external fun nativePing(): Int

    /** No-op in pure architecture, kept for build compatibility */
    fun reset() {}
}

/**
 * ✅ Kotlin AIMove model
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
