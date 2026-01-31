package com.example.myapplication

import android.graphics.Color
import android.view.Gravity
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

data class ChatMessage(
    val role: String,
    val text: String
)

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.VH>() {

    private val messages = mutableListOf<ChatMessage>()

    fun addMessage(msg: ChatMessage) {
        messages.add(msg)
        notifyItemInserted(messages.size - 1)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val tv = TextView(parent.context).apply {
            setPadding(24, 16, 24, 16)
            textSize = 15f
        }
        return VH(tv)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val msg = messages[position]
        val tv = holder.text

        tv.text = msg.text

        when (msg.role) {
            "user" -> {
                tv.setBackgroundColor(Color.parseColor("#112244"))
                tv.setTextColor(Color.CYAN)
                tv.gravity = Gravity.END
            }
            "assistant" -> {
                tv.setBackgroundColor(Color.parseColor("#221122"))
                tv.setTextColor(Color.GREEN)
                tv.gravity = Gravity.START
            }
            else -> {
                tv.setBackgroundColor(Color.BLACK)
                tv.setTextColor(Color.LTGRAY)
                tv.gravity = Gravity.CENTER
            }
        }
    }

    override fun getItemCount() = messages.size

    class VH(val text: TextView) : RecyclerView.ViewHolder(text)
}
