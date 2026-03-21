package com.example.myapplication

// ── /curriculum/next ─────────────────────────────────────────────────────────

/**
 * Training recommendation returned by POST /curriculum/next.
 *
 * Driven by the SECA brain using real per-player history — more accurate than
 * [TrainingRecommendation] from /next-training which uses hardcoded demo weights.
 *
 * **Schema note:** field names differ from [TrainingRecommendation]:
 *  - [exerciseType] (not `format`) — exercise type string
 *  - [payload] (not `expectedGain`) — type-specific parameters dict
 *
 * Clients MUST NOT conflate this type with [TrainingRecommendation].
 *
 * Backend contract: docs/API_CONTRACTS.md §2 (schema conflict note).
 */
data class CurriculumRecommendation(
    val topic: String,
    val difficulty: Float,
    val exerciseType: String,
    val payload: Map<String, String> = emptyMap(),
)

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

// ── /game/history ─────────────────────────────────────────────────────────────

/**
 * Summary of a single completed game returned by GET /game/history.
 *
 * [result]      One of "win", "loss", "draw".
 * [accuracy]    Move accuracy 0.0–1.0 as recorded at the time of /game/finish.
 * [ratingAfter] Player rating after this game; null when no rating update was stored.
 * [createdAt]   ISO-8601 datetime string (e.g. "2026-03-21T14:05:00").
 */
data class GameHistoryItem(
    val id: String,
    val result: String,
    val accuracy: Float,
    val ratingAfter: Float?,
    val createdAt: String,
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
    /**
     * Status string from the `learning` object in the /game/finish response
     * (e.g. "stored", "updated").  Null when the backend omitted the field.
     */
    val learningStatus: String? = null,
)
