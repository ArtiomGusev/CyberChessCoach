package com.example.myapplication

// ── /next-training/{player_id} ───────────────────────────────────────────────

/**
 * Training recommendation returned by GET /next-training/{player_id}.
 *
 * Schema matches the backend contract documented in docs/API_CONTRACTS.md §2.
 * Fields correspond 1-to-1 with the JSON keys: topic, difficulty, format,
 * expected_gain.
 *
 * [topic]       Training topic (e.g. "tactics", "endgame", "general_play").
 * [difficulty]  Difficulty in the range 0.0–1.0.
 * [format]      Training format ("puzzle", "drill", "game", "explanation").
 * [expectedGain] Estimated rating gain from completing the recommended task.
 */
data class TrainingRecommendation(
    val topic: String,
    val difficulty: Float,
    val format: String,
    val expectedGain: Float,
)

// ── /game/start ──────────────────────────────────────────────────────────────

data class GameStartRequest(val playerId: String)

data class GameStartResponse(val gameId: String)

// ── /game/finish ─────────────────────────────────────────────────────────────

data class GameFinishRequest(
    val pgn: String,
    val result: String, // "win" | "loss" | "draw"
    val accuracy: Float, // 0..1
    val weaknesses: Map<String, Float> = emptyMap(),
    val playerId: String? = null,
)

data class CoachActionDto(
    val type: String,
    val weakness: String?,
    val reason: String?,
)

data class CoachContentDto(
    val title: String,
    val description: String,
    val payload: Map<String, String> = emptyMap(),
)

data class GameFinishResponse(
    val status: String,
    val newRating: Float,
    val confidence: Float,
    val coachAction: CoachActionDto,
    val coachContent: CoachContentDto,
)
