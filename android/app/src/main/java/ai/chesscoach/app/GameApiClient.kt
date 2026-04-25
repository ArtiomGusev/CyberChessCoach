package ai.chesscoach.app

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

    /**
     * GET /game/history.
     *
     * Returns the 20 most recent games for the authenticated player, ordered
     * newest-first. Requires Bearer token authentication.
     *
     * Default implementation returns [ApiResult.HttpError(501)] so test fakes
     * do not need to override this method.
     */
    suspend fun getGameHistory(): ApiResult<List<GameHistoryItem>> = ApiResult.HttpError(501)

    /**
     * GET /seca/status — open endpoint, no auth required.
     *
     * Returns SECA runtime safety flags. Called at cold-start to confirm that
     * [SecaStatusDto.safeModeEnabled] is true before sending coaching requests.
     * Logs a warning if the backend reports safe_mode=false.
     *
     * Default implementation returns [ApiResult.HttpError(501)] so test fakes
     * do not need to override this method.
     */
    suspend fun getSecaStatus(): ApiResult<SecaStatusDto> = ApiResult.HttpError(501)

    /**
     * GET /player/progress — requires Bearer token authentication.
     *
     * Returns the full progress dashboard snapshot: current world-model state,
     * last 20 games with per-game weaknesses, and HistoricalAnalysisPipeline output.
     *
     * Default implementation returns [ApiResult.HttpError(501)] so test fakes
     * do not need to override this method.
     */
    suspend fun getPlayerProgress(): ApiResult<PlayerProgressResponse> = ApiResult.HttpError(501)
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
                // T3: /game/start now requires a JWT-authenticated session.
                // The server derives player_id from the token; the body
                // player_id is accepted for back-compat but ignored.
                tokenProvider?.invoke()?.let { token ->
                    conn.setRequestProperty("Authorization", "Bearer $token")
                }

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
        withRetry(maxAttempts = 3) {
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

    override suspend fun getGameHistory(): ApiResult<List<GameHistoryItem>> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openGetConnection("$baseUrl/game/history")
                tokenProvider?.invoke()?.let { token ->
                    conn.setRequestProperty("Authorization", "Bearer $token")
                }
                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseHistoryResponse(text))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    override suspend fun getPlayerProgress(): ApiResult<PlayerProgressResponse> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openGetConnection("$baseUrl/player/progress")
                tokenProvider?.invoke()?.let { token ->
                    conn.setRequestProperty("Authorization", "Bearer $token")
                }
                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseProgressResponse(text))
                } else {
                    ApiResult.HttpError(code)
                }
            } catch (e: SocketTimeoutException) {
                ApiResult.Timeout
            } catch (e: Exception) {
                ApiResult.NetworkError(e)
            }
        }

    override suspend fun getSecaStatus(): ApiResult<SecaStatusDto> =
        withContext(Dispatchers.IO) {
            try {
                val conn = openGetConnection("$baseUrl/seca/status")
                val code = conn.responseCode
                if (code == 200) {
                    val text = conn.inputStream.bufferedReader().readText()
                    ApiResult.Success(parseSecaStatusResponse(text))
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

    private fun parseHistoryResponse(text: String): List<GameHistoryItem> {
        val json = JSONObject(text)
        val arr = json.optJSONArray("games") ?: return emptyList()
        return (0 until arr.length()).map { i ->
            val g = arr.getJSONObject(i)
            GameHistoryItem(
                id = g.optString("id", ""),
                result = g.optString("result", ""),
                accuracy = g.optDouble("accuracy", 0.0).toFloat(),
                ratingAfter = if (g.isNull("rating_after")) null
                              else g.optDouble("rating_after").toFloat(),
                createdAt = g.optString("created_at", ""),
            )
        }
    }

    private fun parseSecaStatusResponse(text: String): SecaStatusDto {
        val json = JSONObject(text)
        return SecaStatusDto(
            safeModeEnabled = json.optBoolean("safe_mode", true),
            banditEnabled   = json.optBoolean("bandit_enabled", false),
            version         = json.optString("version", ""),
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

    private fun parseProgressResponse(text: String): PlayerProgressResponse {
        val json = JSONObject(text)

        // current
        val cur = json.optJSONObject("current") ?: JSONObject()
        val svJson = cur.optJSONObject("skill_vector") ?: JSONObject()
        val skillVector = buildMap<String, Float> {
            svJson.keys().forEach { k -> put(k, svJson.optDouble(k, 0.0).toFloat()) }
        }
        val current = ProgressCurrentDto(
            rating           = cur.optDouble("rating", 0.0).toFloat(),
            confidence       = cur.optDouble("confidence", 0.0).toFloat(),
            skillVector      = skillVector,
            tier             = cur.optString("tier", "intermediate"),
            teachingStyle    = cur.optString("teaching_style", "intermediate"),
            opponentElo      = cur.optInt("opponent_elo", 1200),
            explanationDepth = cur.optDouble("explanation_depth", 0.5).toFloat(),
            conceptComplexity = cur.optDouble("concept_complexity", 0.5).toFloat(),
        )

        // history
        val histArr = json.optJSONArray("history") ?: org.json.JSONArray()
        val history = (0 until histArr.length()).map { i ->
            val h = histArr.getJSONObject(i)
            val wJson = h.optJSONObject("weaknesses") ?: JSONObject()
            val weaknesses = buildMap<String, Float> {
                wJson.keys().forEach { k -> put(k, wJson.optDouble(k, 0.0).toFloat()) }
            }
            ProgressHistoryItem(
                gameId          = h.optString("game_id", ""),
                result          = h.optString("result", ""),
                accuracy        = h.optDouble("accuracy", 0.0).toFloat(),
                ratingAfter     = if (h.isNull("rating_after")) null
                                  else h.optDouble("rating_after").toFloat(),
                confidenceAfter = if (h.isNull("confidence_after")) null
                                  else h.optDouble("confidence_after").toFloat(),
                weaknesses      = weaknesses,
                createdAt       = h.optString("created_at", ""),
            )
        }

        // analysis
        val ana = json.optJSONObject("analysis") ?: JSONObject()
        val csJson = ana.optJSONObject("category_scores") ?: JSONObject()
        val categoryScores = buildMap<String, Float> {
            csJson.keys().forEach { k -> put(k, csJson.optDouble(k, 0.0).toFloat()) }
        }
        val prJson = ana.optJSONObject("phase_rates") ?: JSONObject()
        val phaseRates = buildMap<String, Float> {
            prJson.keys().forEach { k -> put(k, prJson.optDouble(k, 0.0).toFloat()) }
        }
        val recsArr = ana.optJSONArray("recommendations") ?: org.json.JSONArray()
        val recommendations = (0 until recsArr.length()).map { i ->
            val r = recsArr.getJSONObject(i)
            ProgressRecommendation(
                category  = r.optString("category", ""),
                priority  = r.optString("priority", "low"),
                rationale = r.optString("rationale", ""),
            )
        }
        val analysis = ProgressAnalysisDto(
            dominantCategory = ana.optString("dominant_category").ifEmpty { null },
            gamesAnalyzed    = ana.optInt("games_analyzed", 0),
            categoryScores   = categoryScores,
            phaseRates       = phaseRates,
            recommendations  = recommendations,
        )

        return PlayerProgressResponse(current = current, history = history, analysis = analysis)
    }
}
