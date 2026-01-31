package com.example.myapplication

import android.graphics.Typeface
import android.os.Bundle
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.style.TypefaceSpan
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.core.widget.NestedScrollView
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ChatBottomSheet : BottomSheetDialogFragment() {

    private lateinit var scrollView: NestedScrollView
    private lateinit var messagesLayout: LinearLayout
    private lateinit var input: EditText
    private lateinit var sendBtn: Button
    private lateinit var miniBoard: ChessBoardView

    private var currentFen: String? = null
    private var isStreaming = false

    companion object {
        private const val ARG_FEN = "arg_fen"
        private const val STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w"

        fun newInstance(fen: String): ChatBottomSheet {
            val fragment = ChatBottomSheet()
            val args = Bundle()
            args.putString(ARG_FEN, fen)
            fragment.arguments = args
            return fragment
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        currentFen = arguments?.getString(ARG_FEN)
        isCancelable = true
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.sheet_chat, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        scrollView = view.findViewById(R.id.scrollView)
        messagesLayout = view.findViewById(R.id.messagesLayout)
        input = view.findViewById(R.id.inputMessage)
        sendBtn = view.findViewById(R.id.btnSend)
        miniBoard = view.findViewById(R.id.miniBoard)

        miniBoard.isInteractive = false
        currentFen?.let { miniBoard.setFEN(it) }

        messagesLayout.addOnLayoutChangeListener { _, _, _, _, bottom, _, _, _, oldBottom ->
            if (bottom != oldBottom) {
                scrollToBottom()
            }
        }

        (dialog as? BottomSheetDialog)?.behavior?.apply {
            state = BottomSheetBehavior.STATE_EXPANDED
            skipCollapsed = true
            peekHeight = resources.displayMetrics.heightPixels
        }

        sendBtn.setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isNotEmpty() && !isStreaming) {
                input.setText("")
                addUserMessage(text)
                simulateStreamingResponse()
            }
        }

        addAssistantMessage("👋 Hi! Ask me about the position, strategy, or next move.")
    }

    private fun scrollToBottom() {
        scrollView.post {
            scrollView.fullScroll(View.FOCUS_DOWN)
        }
    }

    private fun addUserMessage(text: String) {
        val tv = TextView(requireContext()).apply {
            this.text = text
            setTextColor(0xFF00FFFF.toInt())
            textSize = 15f
            setPadding(24, 16, 24, 16)
        }

        val wrapper = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.END
            addView(tv)
        }

        messagesLayout.addView(wrapper)
    }

    private fun addAssistantMessage(text: String): TextView {
        val tv = TextView(requireContext()).apply {
            this.text = text
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 15f
            setPadding(24, 16, 24, 16)
        }

        val wrapper = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.START
            addView(tv)
        }

        messagesLayout.addView(wrapper)
        return tv
    }

    private fun simulateStreamingResponse() {
        isStreaming = true
        val assistantView = addAssistantMessage("")
        
        val analysis = when (currentFen) {
            STARTING_FEN -> "Standard starting position. White to move."
            null -> "Position context missing."
            else -> "Analyzing position:\n$currentFen"
        }

        val response = "$analysis\n\nThis move controls the center and prepares development. Consider castling soon."
        val ssb = SpannableStringBuilder()

        viewLifecycleOwner.lifecycleScope.launch {
            for (char in response) {
                ssb.append(char)
                
                // Dynamically apply monospace span to FEN string
                if (currentFen != null && response.contains(currentFen!!)) {
                    val start = ssb.indexOf(currentFen!!)
                    if (start != -1) {
                        val end = start + currentFen!!.length
                        val currentEnd = if (ssb.length < end) ssb.length else end
                        ssb.setSpan(
                            TypefaceSpan("monospace"),
                            start,
                            currentEnd,
                            Spannable.SPAN_EXCLUSIVE_EXCLUSIVE
                        )
                    }
                }
                
                assistantView.text = ssb
                delay(20)
            }
            isStreaming = false
        }
    }
}
