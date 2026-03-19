package com.example.myapplication

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
