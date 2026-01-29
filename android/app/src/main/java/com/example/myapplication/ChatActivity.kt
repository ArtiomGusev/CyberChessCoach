package com.example.myapplication

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class ChatActivity : AppCompatActivity() {

    private lateinit var chatMessages: TextView
    private lateinit var chatInput: EditText
    private lateinit var btnSend: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        chatMessages = findViewById(R.id.chatMessages)
        chatInput = findViewById(R.id.chatInput)
        btnSend = findViewById(R.id.btnSend)

        val fen = intent.getStringExtra("fen") ?: "No FEN received"

        appendMessage("SYSTEM", "Current board position:\n$fen")

        btnSend.setOnClickListener {
            val text = chatInput.text.toString().trim()
            if (text.isNotEmpty()) {
                appendMessage("YOU", text)

                // Placeholder LLM response
                appendMessage("LLM", "I received: \"$text\"")

                chatInput.setText("")
            }
        }
    }

    private fun appendMessage(author: String, message: String) {
        chatMessages.append("$author:\n$message\n\n")
    }
}
