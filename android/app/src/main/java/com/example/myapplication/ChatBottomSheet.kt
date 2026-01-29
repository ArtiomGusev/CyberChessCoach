package com.example.myapplication

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.core.widget.NestedScrollView
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ChatBottomSheet : BottomSheetDialogFragment() {

    private lateinit var scrollView: NestedScrollView
    private lateinit var messagesLayout: LinearLayout
    private lateinit var input: EditText
    private lateinit var sendBtn: Button

    private var currentFen: String? = null
    private var autoScrollEnabled = true

    companion object {
        private const val ARG_FEN = "arg_fen"

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
        // ✅ Enable cancellation (swipe down, back button, etc.)
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

        setupScrollDetection()

        sendBtn.setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isNotEmpty()) {
                input.setText("")
                addUserMessage(text)
                simulateStreamingResponse()
            }
        }

        // Greeting message
        addAssistantMessage("👋 Hi! Ask me about the position, strategy, or next move.")
    }

    private fun setupScrollDetection() {
        scrollView.setOnScrollChangeListener { v: NestedScrollView, _, scrollY, _, _ ->
            val contentHeight = v.getChildAt(0).measuredHeight
            val scrollViewHeight = v.height
            val atBottom = scrollY + scrollViewHeight >= contentHeight - 10
            autoScrollEnabled = atBottom
        }
    }

    private fun scrollToBottom() {
        if (!autoScrollEnabled) return
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
        scrollToBottom()
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
        scrollToBottom()
        return tv
    }

    private fun simulateStreamingResponse() {
        autoScrollEnabled = true
        val assistantView = addAssistantMessage("")
        
        val response = if (currentFen != null) {
            "Analyzing position: $currentFen\n\nThis move controls the center and prepares development. Consider castling soon."
        } else {
            "This move controls the center and prepares development. Consider castling soon."
        }

        viewLifecycleOwner.lifecycleScope.launch {
            for (char in response) {
                assistantView.append(char.toString())
                scrollToBottom()
                delay(25)
            }
        }
    }
}
