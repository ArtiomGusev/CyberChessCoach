package com.example.myapplication

import android.content.Context
import android.content.Intent
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
import kotlinx.coroutines.launch

/**
 * Long-form chat coaching bottom sheet.
 *
 * Displays a GPT-style chess conversation that:
 *  - Sends full conversation context (FEN + history) to the backend /chat endpoint.
 *  - Displays a structured response that always references engine evaluation.
 *  - Shows an engine context header (evaluation band + game phase).
 *  - Falls back gracefully when the backend is unavailable or returns no reply.
 *
 * Auth tokens, timeouts, and base URL are configured in [BuildConfig] per build
 * variant and owned by [HttpCoachApiClient] — not duplicated here.
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

    /**
     * Player profile injected by the host Activity when a game has been completed.
     * Sourced from [GameFinishResponse.newRating] and [GameFinishResponse.confidence].
     * Null when no game has finished in this session (opening/pre-game chat).
     */
    private var playerProfile: PlayerProfileDto? = null

    /**
     * Weakness categories from the most recent game, used to personalise coaching.
     * Derived from [GameFinishResponse.coachAction.weakness] when available.
     * Null when no game has finished in this session.
     */
    private var pastMistakes: List<String>? = null

    private val sessionStore = ChatSessionStore(maxMessages = 50)
    private val chatAdapter = ChatAdapter()

    /**
     * Auth repository — wired in [onAttach] so the Context is available.
     * Provides the JWT to [coachApiClient] via the [tokenProvider] lambda.
     */
    private var authRepository: AuthRepository? = null

    /**
     * Shared API client — constructed once from [BuildConfig] constants.
     * Injects the current JWT (if any) via [tokenProvider] so user-specific
     * backend endpoints receive an Authorization: Bearer header automatically.
     */
    private val coachApiClient: CoachApiClient by lazy {
        HttpCoachApiClient(
            baseUrl = BuildConfig.COACH_API_BASE,
            apiKey = BuildConfig.COACH_API_KEY,
            tokenProvider = { authRepository?.getToken() },
        )
    }

    companion object {
        private const val ARG_FEN = "arg_fen"
        private const val ARG_HAS_PROFILE = "arg_has_profile"
        private const val ARG_PLAYER_RATING = "arg_player_rating"
        private const val ARG_PLAYER_CONFIDENCE = "arg_player_confidence"
        private const val ARG_PAST_MISTAKES = "arg_past_mistakes"

        private const val STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

        private const val FALLBACK_REPLY =
            "Coach is offline. Review the position and consider piece activity, " +
                "centre control, and king safety."

        /**
         * Create a new instance with the current board position and optional
         * player context for personalised coaching.
         *
         * @param fen           Current board position in FEN notation.
         * @param playerProfile Rating + confidence from the last [GameFinishResponse];
         *                      null when no game has completed in this session.
         * @param pastMistakes  Weakness categories from the last game; null when not available.
         */
        fun newInstance(
            fen: String,
            playerProfile: PlayerProfileDto? = null,
            pastMistakes: List<String>? = null,
        ): ChatBottomSheet {
            val fragment = ChatBottomSheet()
            val args = Bundle()
            args.putString(ARG_FEN, fen)
            if (playerProfile != null) {
                args.putBoolean(ARG_HAS_PROFILE, true)
                args.putFloat(ARG_PLAYER_RATING, playerProfile.rating)
                args.putFloat(ARG_PLAYER_CONFIDENCE, playerProfile.confidence)
            }
            pastMistakes?.let { args.putStringArrayList(ARG_PAST_MISTAKES, ArrayList(it)) }
            fragment.arguments = args
            return fragment
        }
    }

    // ---------------------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------------------

    override fun onAttach(context: Context) {
        super.onAttach(context)
        authRepository = AuthRepository(EncryptedTokenStorage(context))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        currentFen = arguments?.getString(ARG_FEN)
        if (arguments?.getBoolean(ARG_HAS_PROFILE, false) == true) {
            val rating = arguments!!.getFloat(ARG_PLAYER_RATING)
            val confidence = arguments!!.getFloat(ARG_PLAYER_CONFIDENCE)
            playerProfile = PlayerProfileDto(rating = rating, confidence = confidence)
        }
        pastMistakes = arguments?.getStringArrayList(ARG_PAST_MISTAKES)?.toList()
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
        val layoutManager =
            LinearLayoutManager(requireContext()).apply {
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
     * Update the engine context bar from the [EngineSignalDto] returned by /chat.
     * Always shows evaluation band and game phase; hides the bar if both are empty.
     */
    private fun updateEngineContextHeader(signal: EngineSignalDto) {
        val band = signal.evaluation?.band ?: ""
        val side = signal.evaluation?.side ?: ""
        val phase = signal.phase ?: ""

        if (band.isEmpty() && phase.isEmpty()) return

        val label =
            buildString {
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
    // Token expiry
    // ---------------------------------------------------------------------------

    /**
     * Called when the backend returns HTTP 401, indicating the stored JWT has
     * expired or been invalidated. Clears the local token and redirects to
     * [LoginActivity] with CLEAR_TASK so the user must re-authenticate.
     */
    private fun handleTokenExpiry() {
        authRepository?.clearToken()
        val intent =
            Intent(requireContext(), LoginActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        startActivity(intent)
    }

    // ---------------------------------------------------------------------------
    // Backend integration
    // ---------------------------------------------------------------------------

    /**
     * Send the current position and conversation history to [coachApiClient],
     * display the structured reply, and update the engine context header.
     *
     * Falls back to [FALLBACK_REPLY] on any error ([ApiResult.HttpError],
     * [ApiResult.NetworkError], [ApiResult.Timeout]) or when the backend
     * returns an empty reply — no crash on missing explanation.
     */
    private fun sendToBackend(@Suppress("UNUSED_PARAMETER") query: String) {
        isStreaming = true
        sendBtn.isEnabled = false

        viewLifecycleOwner.lifecycleScope.launch {
            val messages =
                sessionStore.messages.map { msg ->
                    ChatMessageDto(role = msg.role, content = msg.text)
                }

            val (reply, engineSignal) =
                when (
                    val result =
                        coachApiClient.chat(
                            fen = currentFen ?: STARTING_FEN,
                            messages = messages,
                            playerProfile = playerProfile,
                            pastMistakes = pastMistakes,
                        )
                ) {
                    is ApiResult.Success -> Pair(result.data.reply, result.data.engineSignal)
                    is ApiResult.HttpError -> {
                        // 401 means the JWT has expired server-side; clear the
                        // stored token and redirect to login so the user can
                        // re-authenticate without losing their game state.
                        if (result.code == 401) handleTokenExpiry()
                        Pair("", null)
                    }
                    is ApiResult.NetworkError,
                    ApiResult.Timeout -> Pair("", null)
                }

            val displayReply = reply.takeIf { it.isNotBlank() } ?: FALLBACK_REPLY
            appendAssistant(displayReply)
            engineSignal?.let { updateEngineContextHeader(it) }

            isStreaming = false
            sendBtn.isEnabled = true
        }
    }
}
