package com.example.myapplication

interface EngineProvider {
    fun getBestMove(fen: String): AIMove?
}

/**
 * The real implementation that calls our JNI code.
 */
class NativeEngineProvider : EngineProvider {
    override fun getBestMove(fen: String): AIMove? {
        return ChessNative.getBestMove(fen)
    }
}
