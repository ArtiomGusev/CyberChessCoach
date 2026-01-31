#include <jni.h>
#include <string>
#include <mutex>
#include <chrono>
#include <android/log.h>

#include "SachmatuLenta.h"   // <-- your engine header

// ------------------------------------------------------------------
// Global engine instance (single-threaded access via coroutine usage)
// ------------------------------------------------------------------
static SachmatuLenta engine;

// Optional mutex (SAFE even if later you add parallel calls)
static std::mutex engineMutex;

extern "C" {

// ================================================================
// Load board position from FEN
// Kotlin: ChessNative.loadPosition(fen: String)
// ================================================================
JNIEXPORT void JNICALL
Java_com_example_myapplication_ChessNative_loadPosition(
        JNIEnv* env,
        jobject /* this */,
        jstring fen
) {
    if (!fen) return;

    const char* fenStr = env->GetStringUTFChars(fen, nullptr);
    if (!fenStr) return;

    std::lock_guard<std::mutex> lock(engineMutex);

    // Parse side to move from FEN
    // Example: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    bool whiteTurn = true;
    const char* space = strchr(fenStr, ' ');
    if (space && *(space + 1) == 'b') {
        whiteTurn = false;
    }

    engine.loadFromBoard64(fenStr, whiteTurn);

    env->ReleaseStringUTFChars(fen, fenStr);
}

// ================================================================
// Compute best move (blocking, call from background thread only)
// Kotlin: ChessNative.computeBestMove(): String
// Returns: "e2e4" or "" if no move
// ================================================================
JNIEXPORT jstring JNICALL
Java_com_example_myapplication_ChessNative_computeBestMove(
        JNIEnv* env,
        jobject /* this */
) {
    std::lock_guard<std::mutex> lock(engineMutex);

    auto start = std::chrono::steady_clock::now();

    Move bestMove = engine.getBestMove(engine.getCurrentTurn());

    auto end = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    __android_log_print(ANDROID_LOG_ERROR, "AI_TEST",
                        "AI thinking time: %lld ms", (long long)ms);

    if (!bestMove.isValid()) {
        return env->NewStringUTF("");
    }

    // Convert to "e2e4" format
    std::string move;
    move += char('a' + bestMove.fromY);
    move += std::to_string(8 - bestMove.fromX);
    move += char('a' + bestMove.toY);
    move += std::to_string(8 - bestMove.toX);

    return env->NewStringUTF(move.c_str());
}

// ================================================================
// Make AI Move
// Kotlin: ChessNative.makeAIMove(aiIsWhite: Boolean): Boolean
// ================================================================
JNIEXPORT jboolean JNICALL
Java_com_example_myapplication_ChessNative_makeAIMove(
        JNIEnv* env,
        jobject /* this */,
        jboolean aiIsWhite
) {
    std::lock_guard<std::mutex> lock(engineMutex);
    
    int side = aiIsWhite ? BALTA : JUODA;
    
    Move bestMove = engine.getBestMove(side);
    if (bestMove.isValid()) {
        engine.makeMove(bestMove);
        return JNI_TRUE;
    }
    return JNI_FALSE;
}

// ================================================================
// Make Human Move
// Kotlin: ChessNative.makeHumanMove(fromRow, fromCol, toRow, toCol): Boolean
// ================================================================
JNIEXPORT jboolean JNICALL
Java_com_example_myapplication_ChessNative_makeHumanMove(
        JNIEnv* env,
        jobject /* this */,
        jint fromRow, jint fromCol,
        jint toRow, jint toCol
) {
    std::lock_guard<std::mutex> lock(engineMutex);
    
    Move humanMove(fromRow, fromCol, toRow, toCol);
    if (engine.isLegal(humanMove, engine.getCurrentTurn())) {
        engine.makeMove(humanMove);
        return JNI_TRUE;
    }
    return JNI_FALSE;
}

// ================================================================
// Is White Turn
// Kotlin: ChessNative.isWhiteTurn(): Boolean
// ================================================================
JNIEXPORT jboolean JNICALL
Java_com_example_myapplication_ChessNative_isWhiteTurn(
        JNIEnv* env,
        jobject /* this */
) {
    std::lock_guard<std::mutex> lock(engineMutex);
    return (engine.getCurrentTurn() == BALTA) ? JNI_TRUE : JNI_FALSE;
}

// ================================================================
// Get Board 64
// Kotlin: ChessNative.getBoard64(): String
// ================================================================
JNIEXPORT jstring JNICALL
Java_com_example_myapplication_ChessNative_getBoard64(
        JNIEnv* env,
        jobject /* this */
) {
    std::lock_guard<std::mutex> lock(engineMutex);
    std::string board = engine.toBoard64String(); 
    return env->NewStringUTF(board.c_str());
}

// ================================================================
// Reset engine to initial position
// Kotlin: ChessNative.reset()
// ================================================================
JNIEXPORT void JNICALL
Java_com_example_myapplication_ChessNative_reset(
        JNIEnv* env,
        jobject /* this */
) {
    std::lock_guard<std::mutex> lock(engineMutex);
    engine.reset();
}

// ================================================================
// Hidden Self-Test (No UI)
// Kotlin: ChessNative.selfTest(): Boolean
// ================================================================
JNIEXPORT jboolean JNICALL
Java_com_example_myapplication_ChessNative_selfTest(
        JNIEnv* env,
        jobject /* this */
) {
    SachmatuLenta b;
    b.reset();
    Move m = b.getBestMove(BALTA); 
    return (jboolean)m.isValid();
}

} // extern "C"
