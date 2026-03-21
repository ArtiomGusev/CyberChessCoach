package com.example.myapplication

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.launch

/**
 * Bottom sheet shown after a game ends.
 *
 * Displays:
 *  - New rating and confidence progress bar (Gap 6)
 *  - Coach action type badge (Gap 2)
 *  - Coach content title and description (Gap 2)
 *  - Inline training recommendation card from GET /next-training (Gap 3)
 *
 * Arguments are passed via [newInstance]; see [ARG_*] constants.
 */
class GameSummaryBottomSheet : BottomSheetDialogFragment() {

    companion object {
        private const val ARG_RATING      = "rating"
        private const val ARG_CONFIDENCE  = "confidence"
        private const val ARG_ACTION_TYPE = "action_type"
        private const val ARG_TITLE       = "title"
        private const val ARG_DESCRIPTION = "description"
        private const val ARG_PLAYER_ID   = "player_id"

        const val PREFS_NAME  = MainActivity.PREFS_NAME
        const val PREF_RATING = MainActivity.PREF_RATING

        fun newInstance(
            response: GameFinishResponse,
            playerId: String,
        ): GameSummaryBottomSheet = GameSummaryBottomSheet().apply {
            arguments = Bundle().apply {
                putFloat(ARG_RATING,      response.newRating)
                putFloat(ARG_CONFIDENCE,  response.confidence)
                putString(ARG_ACTION_TYPE, response.coachAction.type)
                putString(ARG_TITLE,       response.coachContent.title)
                putString(ARG_DESCRIPTION, response.coachContent.description)
                putString(ARG_PLAYER_ID,   playerId)
            }
        }

        // ── Pure helper functions — testable without Android framework ────────

        /** Format a rating float as "Rating: 1 200" (no decimal). */
        fun formatRating(rating: Float): String = "Rating: %.0f".format(rating)

        /** Format confidence 0.0–1.0 as "Confidence: 72%". */
        fun formatConfidence(confidence: Float): String =
            "Confidence: %.0f%%".format(confidence * 100f)

        /** Convert confidence 0.0–1.0 to ProgressBar integer (0–100). */
        fun confidenceProgress(confidence: Float): Int =
            (confidence.coerceIn(0f, 1f) * 100f).toInt()

        /**
         * Map a coach action type string to a display badge label.
         * Unknown types fall back to "COACH".
         */
        fun actionBadgeLabel(type: String): String = when (type.uppercase()) {
            "DRILL"       -> "DRILL"
            "PUZZLE"      -> "PUZZLE"
            "REFLECT"     -> "REFLECT"
            "PLAN_UPDATE" -> "PLAN"
            "REST"        -> "REST"
            "CELEBRATE"   -> "CELEBRATE"
            else          -> "COACH"
        }

        /** Format a training topic string as "Topic: Endgame technique". */
        fun formatTopic(topic: String): String =
            "Topic: ${topic.replaceFirstChar { it.uppercase() }.replace('_', ' ')}"

        /** Format training format as "Format: Puzzle". */
        fun formatFormat(format: String): String =
            "Format: ${format.replaceFirstChar { it.uppercase() }}"

        /** Format expected gain as "+14 Elo". */
        fun formatGain(gain: Float): String = "+%.0f Elo".format(gain)

        /** Convert difficulty 0.0–1.0 to ProgressBar integer (0–100). */
        fun difficultyProgress(difficulty: Float): Int =
            (difficulty.coerceIn(0f, 1f) * 100f).toInt()
    }

    /** Injected in [newInstance] path; set by [MainActivity] before showing. */
    var gameApiClient: GameApiClient? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View = inflater.inflate(R.layout.bottom_sheet_game_summary, container, false)

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val args = requireArguments()
        val rating     = args.getFloat(ARG_RATING)
        val confidence = args.getFloat(ARG_CONFIDENCE)
        val actionType = args.getString(ARG_ACTION_TYPE, "")
        val title      = args.getString(ARG_TITLE, "")
        val description = args.getString(ARG_DESCRIPTION, "")
        val playerId   = args.getString(ARG_PLAYER_ID, "demo")

        // ── Bind views ────────────────────────────────────────────────────────
        view.findViewById<TextView>(R.id.txtNewRating).text      = formatRating(rating)
        view.findViewById<TextView>(R.id.txtActionBadge).text    = actionBadgeLabel(actionType)
        view.findViewById<TextView>(R.id.txtCoachTitle).text     = title.ifBlank { "Game Over" }
        view.findViewById<TextView>(R.id.txtCoachDescription).text = description

        val progressBar = view.findViewById<ProgressBar>(R.id.progressConfidence)
        progressBar.progress = confidenceProgress(confidence)
        view.findViewById<TextView>(R.id.txtConfidenceLabel).text = formatConfidence(confidence)

        // ── Persist rating to SharedPreferences (Gap 6) ───────────────────────
        requireContext()
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putFloat(PREF_RATING, rating)
            .apply()

        // ── Fetch training recommendation (Gap 3) ─────────────────────────────
        val trainingCard  = view.findViewById<LinearLayout>(R.id.trainingCard)
        val trainingEmpty = view.findViewById<TextView>(R.id.txtTrainingEmpty)
        val client = gameApiClient
        if (client != null) {
            lifecycleScope.launch {
                when (val result = client.getNextTraining(playerId)) {
                    is ApiResult.Success -> {
                        val rec = result.data
                        view.findViewById<TextView>(R.id.txtTrainingTopic).text  = formatTopic(rec.topic)
                        view.findViewById<TextView>(R.id.txtTrainingFormat).text = formatFormat(rec.format)
                        view.findViewById<TextView>(R.id.txtTrainingGain).text   = formatGain(rec.expectedGain)
                        view.findViewById<ProgressBar>(R.id.progressDifficulty).progress =
                            difficultyProgress(rec.difficulty)
                        trainingCard.visibility  = View.VISIBLE
                        trainingEmpty.visibility = View.GONE
                    }
                    is ApiResult.HttpError -> {
                        trainingCard.visibility  = View.GONE
                        trainingEmpty.visibility = View.VISIBLE
                    }
                    is ApiResult.NetworkError, ApiResult.Timeout -> {
                        trainingCard.visibility  = View.GONE
                        trainingEmpty.visibility = View.VISIBLE
                    }
                }
            }
        }

        // ── Start training button ─────────────────────────────────────────────
        view.findViewById<Button>(R.id.btnStartTraining).setOnClickListener {
            if (parentFragmentManager.isStateSaved) return@setOnClickListener
            // Open ChatBottomSheet with a training seed prompt
            val fen = "startpos"
            ChatBottomSheet
                .newInstance(fen, null, null, 0)
                .show(parentFragmentManager, "ChatBottomSheet")
            dismiss()
        }
    }
}
