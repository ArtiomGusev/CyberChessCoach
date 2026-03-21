package com.example.myapplication

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

/**
 * Shared HTTP client interface for all coach backend endpoints.
 *
 * Each call returns an [ApiResult]; callers never see raw exceptions.
 * Implementations are safe to call from any coroutine context — I/O
 * dispatch is handled internally.
 */
interface CoachApiClient {

    /**
     * Send the current position, conversation history, and optional player context
     * to POST /chat.
     *
     * @param fen           Board position in FEN notation.
     * @param messages      Conversation history (most-recent last).
     * @param playerProfile Optional player context (rating, confidence) for personalised
     *                      coaching; omitted from the request when null.
     * @param pastMistakes  Optional list of weakness categories from the last game; omitted
     *                      from the request when null.
     * @param moveCount     Number of half-moves played so far; gives the backend context
     *                      about game phase during mid-game chat (null omits the field).
     * @return              [ApiResult.Success] on HTTP 200 with a valid body;
     *                      [ApiResult.HttpError] on non-200; [ApiResult.Timeout]
     *                      on deadline exceeded; [ApiResult.NetworkError] otherwise.
     */
    suspend fun chat(
        fen: String,
        messages: List<ChatMessageDto>,
        playerProfile: PlayerProfileDto? = null,
        pastMistakes: List<String>? = null,
        moveCount: Int? = null,
    ): ApiResult<ChatResponseBody>

    /**
     * POST /game/coach-feedback.
     *
     * Records whether the coaching reply for a given position was helpful.
     * Fire-and-forget: callers should not block the UI on this result.
     * Returns [ApiResult.HttpError(501)] by default so test fakes don't need
     * to override this method.
     */
    suspend fun submitFeedback(
        fen: String,
        isHelpful: Boolean,
        token: String?,
    ): ApiResult<Unit> = ApiResult.HttpError(501)
}

/**
 * Production implementation of [CoachApiClient] backed by [HttpURLConnection].
 *
 * All I/O is dispatched to [Dispatchers.IO] — the caller needs no special
 * dispatcher. Constructed once and shared; the instance is thread-safe because
 * each [chat] call opens its own connection.
 *
 * @param baseUrl          Scheme + host + optional port, no trailing slash
 *                         (e.g. "http://10.0.2.2:8000").
 * @param apiKey           Sent as the X-Api-Key request header.
 * @param connectTimeoutMs TCP connect deadline in milliseconds.
 * @param readTimeoutMs    Read deadline in milliseconds.
 * @param tokenProvider    Optional supplier of a JWT Bearer token. When
 *                         non-null and returns a non-null string, the token
 *                         is sent as `Authorization: Bearer <token>` alongside
 *                         the X-Api-Key header. Required for endpoints that
 *                         enforce user-level auth (/game/finish, /next-training,
 *                         /curriculum/next).
 */
class HttpCoachApiClient(
    val baseUrl: String,
    val apiKey: String,
    val connectTimeoutMs: Int = DEFAULT_CONNECT_TIMEOUT_MS,
    val readTimeoutMs: Int = DEFAULT_READ_TIMEOUT_MS,
    val tokenProvider: (() -> String?)? = null,
) : CoachApiClient {

    companion object {
        const val DEFAULT_CONNECT_TIMEOUT_MS = 8_000
        const val DEFAULT_READ_TIMEOUT_MS = 15_000
        private const val CHAT_PATH = "/chat"
        private const val FEEDBACK_PATH = "/game/coach-feedback"
    }

    override suspend fun chat(
        fen: String,
        messages: List<ChatMessageDto>,
        playerProfile: PlayerProfileDto?,
        pastMistakes: List<String>?,
        moveCount: Int?,
    ): ApiResult<ChatResponseBody> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl$CHAT_PATH")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("X-Api-Key", apiKey)
            // Inject JWT Bearer token when the caller has a logged-in session.
            tokenProvider?.invoke()?.let { token ->
                conn.setRequestProperty("Authorization", "Bearer $token")
            }
            conn.doOutput = true
            conn.connectTimeout = connectTimeoutMs
            conn.readTimeout = readTimeoutMs

            conn.outputStream.bufferedWriter(Charsets.UTF_8).use {
                it.write(buildJson(fen, messages, playerProfile, pastMistakes, moveCount))
            }

            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) {
                val body = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                ApiResult.Success(parseResponse(body))
            } else {
                ApiResult.HttpError(code)
            }
        } catch (_: SocketTimeoutException) {
            ApiResult.Timeout
        } catch (e: Exception) {
            ApiResult.NetworkError(e)
        }
    }

    override suspend fun submitFeedback(
        fen: String,
        isHelpful: Boolean,
        token: String?,
    ): ApiResult<Unit> = withContext(Dispatchers.IO) {
        try {
            val body = JSONObject().apply {
                put("session_fen", fen)
                put("is_helpful", isHelpful)
            }.toString()
            val url = URL("$baseUrl$FEEDBACK_PATH")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("X-Api-Key", apiKey)
            token?.let { conn.setRequestProperty("Authorization", "Bearer $it") }
            conn.doOutput = true
            conn.connectTimeout = connectTimeoutMs
            conn.readTimeout = readTimeoutMs
            conn.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body) }
            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) ApiResult.Success(Unit)
            else ApiResult.HttpError(code)
        } catch (_: SocketTimeoutException) {
            ApiResult.Timeout
        } catch (e: Exception) {
            ApiResult.NetworkError(e)
        }
    }

    // -----------------------------------------------------------------------
    // JSON serialisation / deserialisation (private — not unit tested directly)
    // -----------------------------------------------------------------------

    private fun buildJson(
        fen: String,
        messages: List<ChatMessageDto>,
        playerProfile: PlayerProfileDto?,
        pastMistakes: List<String>?,
        moveCount: Int?,
    ): String {
        val arr = JSONArray()
        for (msg in messages) {
            arr.put(
                JSONObject().apply {
                    put("role", msg.role)
                    put("content", msg.content)
                },
            )
        }
        return JSONObject()
            .apply {
                put("fen", fen)
                put("messages", arr)
                // Omit player_profile when null so the server uses its own defaults.
                playerProfile?.let {
                    put(
                        "player_profile",
                        JSONObject().apply {
                            put("rating", it.rating.toDouble())
                            put("confidence", it.confidence.toDouble())
                        },
                    )
                }
                // Omit past_mistakes when null; empty list is sent as [] (valid).
                pastMistakes?.let {
                    val arr2 = JSONArray()
                    for (mistake in it) arr2.put(mistake)
                    put("past_mistakes", arr2)
                }
                // Move count gives the backend phase context during mid-game chat.
                moveCount?.let { put("move_count", it) }
            }
            .toString()
    }

    private fun parseResponse(body: String): ChatResponseBody {
        val root = JSONObject(body)
        val reply = root.optString("reply", "")
        val signalObj = root.optJSONObject("engine_signal")
        val engineSignal =
            signalObj?.let { sig ->
                val evalObj = sig.optJSONObject("evaluation")
                val evaluation =
                    evalObj?.let { ev ->
                        EvaluationDto(
                            band = ev.optString("band", "").takeIf { it.isNotEmpty() },
                            side = ev.optString("side", "").takeIf { it.isNotEmpty() },
                        )
                    }
                EngineSignalDto(
                    evaluation = evaluation,
                    phase = sig.optString("phase", "").takeIf { it.isNotEmpty() },
                )
            }
        return ChatResponseBody(reply = reply, engineSignal = engineSignal)
    }
}
