package com.example.myapplication

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Long-form chat coaching bottom sheet.
 *
 * Displays a GPT-style chess conversation that:
 *  - Sends full conversation context (FEN + history) to the backend /chat endpoint.
 *  - Displays a structured response that always references engine evaluation.
 *  - Shows an engine context header (evaluation band + game phase).
 *  - Falls back gracefully when the backend is unavailable or returns no reply.
 *
 * No RL adaptation. All coaching logic lives server-side in chat_pipeline.py.
 */
class ChatBottomSheet : BottomSheetDialogFragment() {

    // ---------------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------------

    private lateinit var recyclerMessages: RecyclerView
    private lateinit var input: EditText
    private lateinit var sendBtn: Button
    private lateinit var miniBoard: ChessBoardView
    private lateinit var engineContextHeader: LinearLayout
    private lateinit var txtEngineContext: TextView

    // ---------------------------------------------------------------------------
    // State
    // ---------------------------------------------------------------------------

    private var currentFen: String? = null
    private var isStreaming = false

    private val sessionStore = ChatSessionStore(maxMessages = 50)
    private val chatAdapter = ChatAdapter()

    companion object {
        private const val ARG_FEN = "arg_fen"
        private const val STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

        /**
         * Backend base URL.
         * 10.0.2.2 routes to the host machine from the Android emulator.
         * Override via a build-config constant in production.
         */
        private const val COACH_API_BASE = "http://10.0.2.2:8000"

        /**
         * Dev API key (matches SECA_API_KEY=dev-key in .env).
         * Replace with BuildConfig.COACH_API_KEY in a production build.
         */
        private const val DEV_API_KEY = "dev-key"

        private const val FALLBACK_REPLY =
            "Coach is offline. Review the position and consider piece activity, " +
            "centre control, and king safety."

        fun newInstance(fen: String): ChatBottomSheet {
            val fragment = ChatBottomSheet()
            val args = Bundle()
            args.putString(ARG_FEN, fen)
            fragment.arguments = args
            return fragment
        }
    }

    // ---------------------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------------------

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        currentFen = arguments?.getString(ARG_FEN)
        isCancelable = true
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View = inflater.inflate(R.layout.sheet_chat, container, false)

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Bind views
        recyclerMessages = view.findViewById(R.id.recyclerMessages)
        input = view.findViewById(R.id.inputMessage)
        sendBtn = view.findViewById(R.id.btnSend)
        miniBoard = view.findViewById(R.id.miniBoard)
        engineContextHeader = view.findViewById(R.id.engineContextHeader)
        txtEngineContext = view.findViewById(R.id.txtEngineContext)

        // Mini board — non-interactive position preview
        miniBoard.isInteractive = false
        currentFen?.let { miniBoard.setFEN(it) }

        // RecyclerView — stable message rendering
        val layoutManager = LinearLayoutManager(requireContext()).apply {
            stackFromEnd = true
        }
        recyclerMessages.layoutManager = layoutManager
        recyclerMessages.adapter = chatAdapter

        // Expand bottom sheet fully
        (dialog as? BottomSheetDialog)?.behavior?.apply {
            state = BottomSheetBehavior.STATE_EXPANDED
            skipCollapsed = true
            peekHeight = resources.displayMetrics.heightPixels
        }

        // Initial greeting
        appendAssistant("Hi! Ask me about the current position, strategy, or your recent mistakes.")

        sendBtn.setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isNotEmpty() && !isStreaming) {
                input.setText("")
                appendUser(text)
                sendToBackend(text)
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Message helpers
    // ---------------------------------------------------------------------------

    private fun appendUser(text: String) {
        sessionStore.addMessage("user", text)
        chatAdapter.addMessage(ChatMessage(role = "user", text = text))
        scrollToBottom()
    }

    private fun appendAssistant(text: String) {
        sessionStore.addMessage("assistant", text)
        chatAdapter.addMessage(ChatMessage(role = "assistant", text = text))
        scrollToBottom()
    }

    private fun scrollToBottom() {
        val count = chatAdapter.itemCount
        if (count > 0) recyclerMessages.scrollToPosition(count - 1)
    }

    // ---------------------------------------------------------------------------
    // Engine context header
    // ---------------------------------------------------------------------------

    /**
     * Update the engine context bar from the engine_signal returned by /chat.
     * Always shows evaluation band and game phase; hides the bar if both are empty.
     */
    private fun updateEngineContextHeader(engineSignal: JSONObject) {
        val eval = engineSignal.optJSONObject("evaluation")
        val band = eval?.optString("band", "") ?: ""
        val side = eval?.optString("side", "") ?: ""
        val phase = engineSignal.optString("phase", "")

        if (band.isEmpty() && phase.isEmpty()) return

        val label = buildString {
            if (phase.isNotEmpty()) append(phase.uppercase())
            if (phase.isNotEmpty() && (side.isNotEmpty() || band.isNotEmpty())) append("  ·  ")
            if (side.isNotEmpty()) append(side)
            if (side.isNotEmpty() && band.isNotEmpty()) append(": ")
            if (band.isNotEmpty()) append(band.replace('_', ' '))
        }
        txtEngineContext.text = label
        engineContextHeader.visibility = View.VISIBLE
    }

    // ---------------------------------------------------------------------------
    // Backend integration
    // ---------------------------------------------------------------------------

    /**
     * Build the JSON request body for POST /chat.
     * Includes current FEN, full conversation history, and no player profile
     * (the demo flow omits auth; a real integration would inject player_profile).
     */
    private fun buildRequestBody(): String {
        val root = JSONObject()
        root.put("fen", currentFen ?: STARTING_FEN)

        val arr = JSONArray()
        for (msg in sessionStore.messages) {
            arr.put(JSONObject().apply {
                put("role", msg.role)
                put("content", msg.text)
            })
        }
        root.put("messages", arr)
        // player_profile and past_mistakes omitted in demo mode (optional fields)
        return root.toString()
    }

    /**
     * Call POST /chat on a background thread.
     * Returns (reply, engineSignal?) — both null-safe.
     * Never throws; returns ("", null) on any error so the fallback path triggers.
     */
    private suspend fun fetchChatReply(): Pair<String, JSONObject?> =
        withContext(Dispatchers.IO) {
            try {
                val url = URL("$COACH_API_BASE/chat")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("X-Api-Key", DEV_API_KEY)
                conn.doOutput = true
                conn.connectTimeout = 8_000
                conn.readTimeout = 15_000

                conn.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(buildRequestBody()) }

                if (conn.responseCode == 200) {
                    val body = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                    val root = JSONObject(body)
                    Pair(root.optString("reply", ""), root.optJSONObject("engine_signal"))
                } else {
                    Pair("", null)
                }
            } catch (_: Exception) {
                Pair("", null)
            }
        }

    /**
     * Send the current query to the backend, display the structured reply,
     * and update the engine context header.
     *
     * Falls back to [FALLBACK_REPLY] when the backend is unreachable or
     * returns an empty reply — no crash on missing explanation.
     */
    private fun sendToBackend(query: String) {
        isStreaming = true
        sendBtn.isEnabled = false

        viewLifecycleOwner.lifecycleScope.launch {
            val (reply, engineSignal) = fetchChatReply()

            val displayReply = reply.takeIf { it.isNotBlank() } ?: FALLBACK_REPLY

            appendAssistant(displayReply)

            engineSignal?.let { updateEngineContextHeader(it) }

            isStreaming = false
            sendBtn.isEnabled = true
        }
    }
}
