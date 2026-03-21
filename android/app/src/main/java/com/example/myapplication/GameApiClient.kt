package com.example.myapplication

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

// ── Interface ─────────────────────────────────────────────────────────────────

interface GameApiClient {
    suspend fun startGame(playerId: String): ApiResult<GameStartResponse>
    suspend fun finishGame(req: GameFinishRequest): ApiResult<GameFinishResponse>

    /**
     * Fetch the next training recommendation for [playerId] from
     * GET /next-training/{player_id}.
     *
     * Returns [ApiResult.Success] with a [TrainingRecommendation] on HTTP 200;
     * [ApiResult.HttpError] on any non-200 response; [ApiResult.Timeout] when
     * the connect or read deadline is exceeded; [ApiResult.NetworkError]
     * for all other transport failures.
     */
    suspend fun getNextTraining(playerId: String): ApiResult<TrainingRecommendation>

    /**
     * Fetch the SECA curriculum recommendation from POST /curriculum/next.
     *
     * Requires Bearer token authentication (uses the configured [tokenProvider]).
     * Returns a [CurriculumRecommendation] driven by real per-player history
     * — the authoritative training recommendation engine.
     *
     * Schema differs from [getNextTraining]; do not conflate the two responses.
     *
     * Default implementation returns [ApiResult.HttpError(501)] so that test
     * fakes implementing only the other methods do not need to override this.
     */
    suspend fun getNextCurriculum(playerId: String): ApiResult<CurriculumRecommendation> =
        ApiResult.HttpError(501)
}

// ── HTTP implementation ───────────────────────────────────────────────────────

class HttpGameApiClient(
    val baseUrl: String,
    val apiKey: String,
    val connectTimeoutMs: Int = 8_000,
    val readTimeoutMs: Int = 30_000,
    val tokenProvider: (() -> String?)? = null,
) : GameApiClient {

    override suspend fun startGame(playerId: String): ApiResult<GameStartResponse> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openConnection("$baseUrl/game/start")
                conn.setRequestProperty("X-Api-Key", apiKey)
                // /game/start uses X-Api-Key only (no Bearer required)

                val body = JSONObject().put("player_id", playerId).toString()
                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    val json = JSONObject(text)
                    val gameId = json.opt("game_id")?.toString() ?: ""
                    ApiResult.Success(GameStartResponse(gameId))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    override suspend fun finishGame(req: GameFinishRequest): ApiResult<GameFinishResponse> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openConnection("$baseUrl/game/finish")
                conn.setRequestProperty("X-Api-Key", apiKey)
                tokenProvider?.invoke()?.let { token ->
                    conn.setRequestProperty("Authorization", "Bearer $token")
                }

                val weaknessesJson = JSONObject()
                req.weaknesses.forEach { (k, v) -> weaknessesJson.put(k, v) }

                val body =
                    JSONObject()
                        .put("pgn", req.pgn)
                        .put("result", req.result)
                        .put("accuracy", req.accuracy)
                        .put("weaknesses", weaknessesJson)
                        .apply { req.playerId?.let { put("player_id", it) } }
                        .toString()

                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseFinishResponse(text))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    override suspend fun getNextTraining(playerId: String): ApiResult<TrainingRecommendation> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openGetConnection("$baseUrl/next-training/$playerId")
                conn.setRequestProperty("X-Api-Key", apiKey)
                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseTrainingResponse(text))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    override suspend fun getNextCurriculum(playerId: String): ApiResult<CurriculumRecommendation> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openConnection("$baseUrl/curriculum/next")
                tokenProvider?.invoke()?.let { token ->
                    conn.setRequestProperty("Authorization", "Bearer $token")
                }
                val body = JSONObject().put("player_id", playerId).toString()
                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseCurriculumResponse(text))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    private fun openConnection(urlStr: String): HttpURLConnection =
        (URL(urlStr).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }

    private fun openGetConnection(urlStr: String): HttpURLConnection =
        (URL(urlStr).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            setRequestProperty("Content-Type", "application/json")
        }

    private fun parseTrainingResponse(text: String): TrainingRecommendation {
        val json = JSONObject(text)
        return TrainingRecommendation(
            topic = json.optString("topic", ""),
            difficulty = json.optDouble("difficulty", 0.5).toFloat(),
            format = json.optString("format", ""),
            expectedGain = json.optDouble("expected_gain", 0.0).toFloat(),
        )
    }

    private fun parseCurriculumResponse(text: String): CurriculumRecommendation {
        val json = JSONObject(text)
        val payloadJson = json.optJSONObject("payload") ?: JSONObject()
        val payload = buildMap<String, String> {
            payloadJson.keys().forEach { key -> put(key, payloadJson.opt(key)?.toString() ?: "") }
        }
        return CurriculumRecommendation(
            topic = json.optString("topic", ""),
            difficulty = json.optDouble("difficulty", 0.5).toFloat(),
            exerciseType = json.optString("exercise_type", ""),
            payload = payload,
        )
    }

    private fun parseFinishResponse(text: String): GameFinishResponse {
        val json = JSONObject(text)

        val actionJson = json.optJSONObject("coach_action") ?: JSONObject()
        val coachAction =
            CoachActionDto(
                type = actionJson.optString("type", "NONE"),
                weakness = actionJson.optString("weakness").ifEmpty { null },
                reason = actionJson.optString("reason").ifEmpty { null },
            )

        val contentJson = json.optJSONObject("coach_content") ?: JSONObject()
        val payloadJson = contentJson.optJSONObject("payload") ?: JSONObject()
        val payload =
            buildMap<String, String> {
                payloadJson.keys().forEach { key -> put(key, payloadJson.opt(key)?.toString() ?: "") }
            }
        val coachContent =
            CoachContentDto(
                title = contentJson.optString("title", "Keep playing"),
                description = contentJson.optString("description", ""),
                payload = payload,
            )

        // Parse learning.status for P3-B surface
        val learningStatus = json.optJSONObject("learning")?.optString("status")?.ifEmpty { null }

        return GameFinishResponse(
            status = json.optString("status", "stored"),
            newRating = json.optDouble("new_rating", 0.0).toFloat(),
            confidence = json.optDouble("confidence", 0.0).toFloat(),
            coachAction = coachAction,
            coachContent = coachContent,
            learningStatus = learningStatus,
        )
    }
}
