package com.example.myapplication

interface EngineProvider {
    fun getBestMove(fen: String): AIMove?
}

/**
 * The real implementation that calls our JNI code.
 */
class NativeEngineProvider : EngineProvider {
    override fun getBestMove(fen: String): AIMove? {
        if (!ChessNative.isLibraryLoaded) return null
        val move = ChessNative.getBestMove(fen) ?: return null
        return JniMoveBridge.normalize(move, fen)
    }
}
