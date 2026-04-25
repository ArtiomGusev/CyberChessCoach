package ai.chesscoach.app

import android.graphics.Color
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

data class ChatMessage(
    val role: String,
    val text: String
)

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.VH>() {

    private val messages = mutableListOf<ChatMessage>()

    /** Called when the user taps 👍 or 👎 on an assistant message. */
    var onFeedback: ((position: Int, isHelpful: Boolean) -> Unit)? = null

    fun addMessage(msg: ChatMessage) {
        messages.add(msg)
        notifyItemInserted(messages.size - 1)
    }

    fun updateLastMessage(text: String) {
        if (messages.isEmpty()) return
        val lastIndex = messages.size - 1
        messages[lastIndex] = messages[lastIndex].copy(text = text)
        notifyItemChanged(lastIndex)
    }

    fun clear() {
        val count = messages.size
        messages.clear()
        notifyItemRangeRemoved(0, count)
    }

    override fun getItemViewType(position: Int): Int =
        if (messages[position].role == "assistant") TYPE_ASSISTANT else TYPE_DEFAULT

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val ctx = parent.context
        return if (viewType == TYPE_ASSISTANT) {
            val root = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                )
            }
            val tv = TextView(ctx).apply {
                setPadding(24, 16, 24, 8)
                textSize = 15f
                setBackgroundColor(Color.parseColor("#221122"))
                setTextColor(Color.GREEN)
                gravity = Gravity.START
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                )
            }
            val thumbRow = LinearLayout(ctx).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.END
                setPadding(24, 0, 24, 8)
                setBackgroundColor(Color.parseColor("#221122"))
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                )
            }
            val thumbUp = Button(ctx).apply {
                text = "👍"
                textSize = 16f
                setBackgroundColor(Color.TRANSPARENT)
                setPadding(12, 0, 12, 0)
            }
            val thumbDown = Button(ctx).apply {
                text = "👎"
                textSize = 16f
                setBackgroundColor(Color.TRANSPARENT)
                setPadding(12, 0, 12, 0)
            }
            thumbRow.addView(thumbUp)
            thumbRow.addView(thumbDown)
            root.addView(tv)
            root.addView(thumbRow)
            VH(root, tv, thumbUp, thumbDown)
        } else {
            val tv = TextView(ctx).apply {
                setPadding(24, 16, 24, 16)
                textSize = 15f
            }
            VH(tv, tv, null, null)
        }
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val msg = messages[position]
        holder.text.text = msg.text

        when (msg.role) {
            "user" -> {
                holder.text.setBackgroundColor(Color.parseColor("#112244"))
                holder.text.setTextColor(Color.CYAN)
                holder.text.gravity = Gravity.END
            }
            "assistant" -> {
                // Reset tint on recycle so previously-rated items don't bleed into new ones
                holder.thumbUp?.setTextColor(Color.LTGRAY)
                holder.thumbDown?.setTextColor(Color.LTGRAY)
                holder.thumbUp?.setOnClickListener {
                    onFeedback?.invoke(holder.bindingAdapterPosition, true)
                    holder.thumbUp.setTextColor(Color.GREEN)
                    holder.thumbDown?.setTextColor(Color.DKGRAY)
                }
                holder.thumbDown?.setOnClickListener {
                    onFeedback?.invoke(holder.bindingAdapterPosition, false)
                    holder.thumbDown.setTextColor(Color.RED)
                    holder.thumbUp?.setTextColor(Color.DKGRAY)
                }
            }
            else -> {
                holder.text.setBackgroundColor(Color.BLACK)
                holder.text.setTextColor(Color.LTGRAY)
                holder.text.gravity = Gravity.CENTER
            }
        }
    }

    override fun getItemCount() = messages.size

    class VH(
        itemView: View,
        val text: TextView,
        val thumbUp: Button?,
        val thumbDown: Button?,
    ) : RecyclerView.ViewHolder(itemView)

    companion object {
        private const val TYPE_ASSISTANT = 1
        private const val TYPE_DEFAULT = 0
    }
}
