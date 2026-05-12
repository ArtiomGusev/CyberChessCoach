package ai.chesscoach.app

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Request/response models for POST /live/move (server.py).
 *
 * The endpoint requires X-Api-Key authentication.
 * Sprint 4.3.C migrated these off hand-rolled ``org.json.JSONObject``
 * parsing onto kotlinx-serialization — see [HttpLiveMoveClient].
 *
 * Schema documented in docs/API_CONTRACTS.md §5.
 */

/**
 * Request body for POST /live/move.
 *
 * [fen]       Board position after the move in FEN notation or "startpos".
 * [uci]       The move just played in UCI notation (e.g. "e2e4", "e7e8q").
 * [playerId]  Player identifier; reserved for future profile enrichment.
 */
@Serializable
data class LiveMoveRequest(
    val fen: String,
    val uci: String,
    @SerialName("player_id") val playerId: String = "demo",
)

/**
 * Response from POST /live/move.
 *
 * [status]       Always "ok" on success.
 * [hint]         Coaching hint referencing engine evaluation, phase, and move quality.
 * [moveQuality]  last_move_quality from the engine signal ("best", "blunder", etc.).
 * [mode]         Always "LIVE_V1" for this pipeline version.
 * [engineSignal] Structured evaluation context from the backend engine signal;
 *                null when absent or unparseable.  Matches [EngineSignalDto] from
 *                the /chat response so the same display logic can be reused.
 */
@Serializable
data class LiveMoveResponse(
    val status: String = "ok",
    val hint: String = "",
    @SerialName("move_quality") val moveQuality: String = "unknown",
    val mode: String = "LIVE_V1",
    @SerialName("engine_signal") val engineSignal: EngineSignalDto? = null,
)
