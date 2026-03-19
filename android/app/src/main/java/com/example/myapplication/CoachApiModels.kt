package com.example.myapplication

/**
 * Typed request/response models for the coach backend API.
 *
 * Pure Kotlin — no Android or org.json dependencies; fully JVM-testable.
 * All JSON serialisation/deserialisation is handled in [HttpCoachApiClient].
 */

/**
 * A single message in the conversation history, matching the backend schema.
 *
 * [role]    must be "user" or "assistant".
 * [content] is the message text (backend field name is "content", not "text").
 */
data class ChatMessageDto(val role: String, val content: String)

/**
 * Request body for POST /chat.
 *
 * [fen]      current board position in Forsyth-Edwards Notation.
 * [messages] conversation history (most-recent last).
 */
data class ChatRequestBody(
    val fen: String,
    val messages: List<ChatMessageDto>,
)

/**
 * Centipawn evaluation band returned by the engine for display in the context header.
 * Null fields indicate the server omitted the field.
 */
data class EvaluationDto(val band: String?, val side: String?)

/**
 * Engine context signal attached to each /chat response.
 * Null fields indicate the server omitted the field.
 */
data class EngineSignalDto(val evaluation: EvaluationDto?, val phase: String?)

/**
 * Typed response from POST /chat.
 *
 * [reply]        the coaching text to display in the chat UI.
 * [engineSignal] optional engine context for the context header; null when omitted.
 */
data class ChatResponseBody(val reply: String, val engineSignal: EngineSignalDto?)

/**
 * Discriminated union for all possible outcomes of a [CoachApiClient] call.
 *
 * Callers should handle all four variants; use `when` with exhaustive branches.
 *
 *  - [Success]      HTTP 200 with a valid parsed body.
 *  - [HttpError]    Server returned a non-200 status code.
 *  - [NetworkError] Transport-level failure (DNS, refused connection, etc.).
 *  - [Timeout]      Connect or read deadline exceeded.
 */
sealed class ApiResult<out T> {
    data class Success<out T>(val data: T) : ApiResult<T>()
    data class HttpError(val code: Int) : ApiResult<Nothing>()
    data class NetworkError(val cause: Throwable) : ApiResult<Nothing>()
    object Timeout : ApiResult<Nothing>()
}
