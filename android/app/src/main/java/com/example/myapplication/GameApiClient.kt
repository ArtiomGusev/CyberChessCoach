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

    private fun openConnection(urlStr: String): HttpURLConnection =
        (URL(urlStr).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
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

        return GameFinishResponse(
            status = json.optString("status", "stored"),
            newRating = json.optDouble("new_rating", 0.0).toFloat(),
            confidence = json.optDouble("confidence", 0.0).toFloat(),
            coachAction = coachAction,
            coachContent = coachContent,
        )
    }
}
