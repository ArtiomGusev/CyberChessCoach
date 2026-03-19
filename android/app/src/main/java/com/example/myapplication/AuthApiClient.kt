package com.example.myapplication

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

/**
 * Shared client interface for the backend authentication endpoints.
 *
 * Returns [ApiResult] on every call — callers never see raw exceptions.
 * Implementations are safe to call from any coroutine context.
 */
interface AuthApiClient {

    /**
     * POST /auth/login.
     *
     * @return [ApiResult.Success] with [LoginResponse] on HTTP 200.
     *         [ApiResult.HttpError(401)] for invalid credentials.
     *         [ApiResult.Timeout] or [ApiResult.NetworkError] on transport failures.
     */
    suspend fun login(email: String, password: String): ApiResult<LoginResponse>

    /**
     * POST /auth/logout.
     *
     * Sends [token] in the Authorization header; invalidates the server-side
     * session so the token can no longer be used.
     *
     * @return [ApiResult.Success(Unit)] on HTTP 200; error variants otherwise.
     */
    suspend fun logout(token: String): ApiResult<Unit>
}

/**
 * Production [AuthApiClient] backed by [HttpURLConnection].
 *
 * All I/O is dispatched to [Dispatchers.IO] — safe to call from any coroutine.
 *
 * @param baseUrl          Scheme + host + optional port, no trailing slash
 *                         (e.g. "http://10.0.2.2:8000").
 * @param connectTimeoutMs TCP connect deadline in milliseconds.
 * @param readTimeoutMs    Read deadline in milliseconds.
 */
class HttpAuthApiClient(
    val baseUrl: String,
    val connectTimeoutMs: Int = DEFAULT_CONNECT_TIMEOUT_MS,
    val readTimeoutMs: Int = DEFAULT_READ_TIMEOUT_MS,
) : AuthApiClient {

    companion object {
        const val DEFAULT_CONNECT_TIMEOUT_MS = 8_000
        const val DEFAULT_READ_TIMEOUT_MS = 15_000
        private const val LOGIN_PATH = "/auth/login"
        private const val LOGOUT_PATH = "/auth/logout"
    }

    override suspend fun login(
        email: String,
        password: String,
    ): ApiResult<LoginResponse> = withContext(Dispatchers.IO) {
        try {
            val body =
                JSONObject().apply {
                    put("email", email)
                    put("password", password)
                    put("device_info", "android")
                }.toString()

            val url = URL("$baseUrl$LOGIN_PATH")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = connectTimeoutMs
            conn.readTimeout = readTimeoutMs

            conn.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body) }

            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) {
                val raw = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                ApiResult.Success(parseLoginResponse(raw))
            } else {
                ApiResult.HttpError(code)
            }
        } catch (_: SocketTimeoutException) {
            ApiResult.Timeout
        } catch (e: Exception) {
            ApiResult.NetworkError(e)
        }
    }

    override suspend fun logout(
        token: String,
    ): ApiResult<Unit> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl$LOGOUT_PATH")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.connectTimeout = connectTimeoutMs
            conn.readTimeout = readTimeoutMs

            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) {
                ApiResult.Success(Unit)
            } else {
                ApiResult.HttpError(code)
            }
        } catch (_: SocketTimeoutException) {
            ApiResult.Timeout
        } catch (e: Exception) {
            ApiResult.NetworkError(e)
        }
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    private fun parseLoginResponse(body: String): LoginResponse {
        val root = JSONObject(body)
        return LoginResponse(
            accessToken = root.getString("access_token"),
            playerId = root.optString("player_id", ""),
            tokenType = root.optString("token_type", "bearer"),
        )
    }
}
