package ai.chesscoach.app

import org.json.JSONObject

/**
 * Helpers for the offline /game/finish retry path.
 *
 * Lifecycle
 * ---------
 * When MainActivity.onGameOver hits a transient failure on
 * /game/finish — timeout, network error, or 5xx — the request payload
 * is JSON-serialised via [toJson] and persisted to
 * [PREF_PENDING_FINISH_PAYLOAD] in SharedPreferences.  On the next
 * MainActivity cold-start [fromJson] rehydrates it and the activity
 * tries the call again.  Success clears the slot; a still-transient
 * failure leaves it for the next attempt; a 4xx response (other than
 * 401, which is handled separately) clears the slot since the call
 * would just fail again.
 *
 * This closes a real silent-data-loss bug: an entire game's PGN +
 * weakness analysis used to be dropped on the floor when the network
 * hiccupped at exactly the wrong moment, and the user had no way to
 * recover the work.
 *
 * The slot is one-deep on purpose — chess games take 10–30 minutes,
 * so multiple pending finishes is a vanishingly rare edge.  A second
 * pending finish overwrites the first; the older one is gone.  Future
 * improvement: a queue, or fire-and-forget retry that doesn't block
 * the next finish attempt.
 */
object PendingGameFinish {

    const val PREF_PENDING_FINISH_PAYLOAD = "pending_game_finish_payload"

    /**
     * Should this [ApiResult] failure be retried later, or is it
     * permanent (4xx, success)?  We retry only on signals that
     * suggest "the request never reached a healthy server":
     *   - Timeout: server might be slow / unreachable, retry
     *   - NetworkError: connection refused / DNS / etc., retry
     *   - HttpError 5xx: server-side incident, retry
     *
     * 4xx (other than 401, handled by handleSessionExpired upstream)
     * indicates a payload the server actively rejected — retrying
     * with the same payload would just fail again, so we don't.
     */
    fun isTransient(result: ApiResult<*>): Boolean = when (result) {
        is ApiResult.Timeout       -> true
        is ApiResult.NetworkError  -> true
        is ApiResult.HttpError     -> result.code >= 500
        is ApiResult.Success       -> false
    }

    /**
     * Serialise a GameFinishRequest into a JSON blob suitable for
     * SharedPreferences.  Schema mirrors the wire format the
     * HttpGameApiClient sends so the round-trip is loss-free.
     */
    fun toJson(req: GameFinishRequest): String {
        val weaknesses = JSONObject()
        req.weaknesses.forEach { (k, v) -> weaknesses.put(k, v.toDouble()) }
        return JSONObject()
            .put("pgn", req.pgn)
            .put("result", req.result)
            .put("accuracy", req.accuracy.toDouble())
            .put("weaknesses", weaknesses)
            .apply { req.playerId?.let { put("player_id", it) } }
            .apply { req.gameId?.let { put("game_id", it) } }
            .toString()
    }

    /**
     * Inverse of [toJson] — returns null when the blob is malformed
     * (corrupted prefs, partial write, schema drift across upgrades)
     * so the caller can drop the slot and continue rather than crash.
     * Missing optional fields (player_id, game_id) round-trip to null.
     */
    fun fromJson(json: String): GameFinishRequest? = try {
        val root = JSONObject(json)
        val weakObj = root.optJSONObject("weaknesses") ?: JSONObject()
        val weaknesses = buildMap<String, Float> {
            weakObj.keys().forEach { k -> put(k, weakObj.optDouble(k, 0.0).toFloat()) }
        }
        GameFinishRequest(
            pgn = root.getString("pgn"),
            result = root.getString("result"),
            accuracy = root.getDouble("accuracy").toFloat(),
            weaknesses = weaknesses,
            playerId = root.optString("player_id").takeIf { it.isNotEmpty() },
            gameId   = root.optString("game_id").takeIf { it.isNotEmpty() },
        )
    } catch (_: Exception) {
        null
    }
}
