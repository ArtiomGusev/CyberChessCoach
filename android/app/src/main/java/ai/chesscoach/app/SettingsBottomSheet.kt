package ai.chesscoach.app

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import com.google.android.material.bottomsheet.BottomSheetDialogFragment

/**
 * Cereveon · Atrium · Settings (handoff screen #10).
 *
 * Sections (each separated by an Atrium hairline rule):
 *   1.  Coach voice  — radio (formal / conversational / terse)
 *   2.  Board style  — radio (flat / engraved / wireframe)
 *   3.  Sound        — switch
 *   4.  Notifications — switch
 *   5.  Account      — chevron rows: Change password, Sign out
 *
 * Persistence: [PREFS_NAME] SharedPreferences (the same store
 * MainActivity uses for the rating cache and curriculum chip).
 *
 * **Consumer wiring is intentionally out of scope for this scaffold:**
 *   - Coach voice persists, but [chat_pipeline] does not yet read it.
 *   - Board style persists, but [ChessBoardView] does not yet accept
 *     a variant — the rendered board stays "flat" until the variant
 *     parameter lands.
 *   - Sound / notifications persist, but no audio system or
 *     notification channel exists yet to consume them.
 *
 * The settings UI is the right place to put these toggles ahead of the
 * features that read them, so users see one consistent surface.  The
 * downstream readers can opt-in via [readCoachVoice], [readBoardStyle],
 * [readSoundEnabled], [readNotificationsEnabled] when they're built.
 */
class SettingsBottomSheet : BottomSheetDialogFragment() {

    /**
     * Optional callbacks the host activity can wire to handle
     * Account-section taps.  Both default to no-ops; MainActivity
     * sets them to forward to its existing change-password dialog
     * and logout flow.
     */
    var onChangePasswordTapped: (() -> Unit)? = null
    var onSignOutTapped: (() -> Unit)? = null

    private val voiceDots = mutableMapOf<String, View>()
    private val boardDots = mutableMapOf<String, View>()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View = inflater.inflate(R.layout.bottom_sheet_settings, container, false)

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val prefs = requireContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        // ── Coach voice radio ────────────────────────────────────────
        voiceDots["formal"]         = view.findViewById(R.id.voiceFormalDot)
        voiceDots["conversational"] = view.findViewById(R.id.voiceConversationalDot)
        voiceDots["terse"]          = view.findViewById(R.id.voiceTerseDot)
        applyRadioState(voiceDots, prefs.getString(PREF_COACH_VOICE, DEFAULT_COACH_VOICE)!!)

        bindRow(view, R.id.voiceFormal,         voiceDots, PREF_COACH_VOICE)
        bindRow(view, R.id.voiceConversational, voiceDots, PREF_COACH_VOICE)
        bindRow(view, R.id.voiceTerse,          voiceDots, PREF_COACH_VOICE)

        // ── Board style radio ────────────────────────────────────────
        boardDots["flat"]      = view.findViewById(R.id.boardFlatDot)
        boardDots["engraved"]  = view.findViewById(R.id.boardEngravedDot)
        boardDots["wireframe"] = view.findViewById(R.id.boardWireframeDot)
        applyRadioState(boardDots, prefs.getString(PREF_BOARD_STYLE, DEFAULT_BOARD_STYLE)!!)

        bindRow(view, R.id.boardFlat,      boardDots, PREF_BOARD_STYLE)
        bindRow(view, R.id.boardEngraved,  boardDots, PREF_BOARD_STYLE)
        bindRow(view, R.id.boardWireframe, boardDots, PREF_BOARD_STYLE)

        // ── Sound switch ─────────────────────────────────────────────
        val sound = view.findViewById<SwitchCompat>(R.id.switchSound)
        sound.isChecked = prefs.getBoolean(PREF_SOUND_ENABLED, true)
        sound.setOnCheckedChangeListener { _, checked ->
            prefs.edit().putBoolean(PREF_SOUND_ENABLED, checked).apply()
        }
        view.findViewById<View>(R.id.rowSound).setOnClickListener { sound.toggle() }

        // ── Notifications switch ─────────────────────────────────────
        val notif = view.findViewById<SwitchCompat>(R.id.switchNotifications)
        notif.isChecked = prefs.getBoolean(PREF_NOTIFICATIONS_ENABLED, true)
        notif.setOnCheckedChangeListener { _, checked ->
            prefs.edit().putBoolean(PREF_NOTIFICATIONS_ENABLED, checked).apply()
        }
        view.findViewById<View>(R.id.rowNotifications).setOnClickListener { notif.toggle() }

        // ── Account chevron rows ─────────────────────────────────────
        view.findViewById<View>(R.id.rowChangePassword).setOnClickListener {
            dismiss()
            onChangePasswordTapped?.invoke()
        }
        view.findViewById<View>(R.id.rowSignOut).setOnClickListener {
            dismiss()
            onSignOutTapped?.invoke()
        }
    }

    /**
     * Wire a radio-row click: write [prefKey] = row.tag and update
     * the visual selection so only the tapped dot is filled.
     */
    private fun bindRow(
        root: View,
        rowId: Int,
        dots: Map<String, View>,
        prefKey: String,
    ) {
        val row = root.findViewById<LinearLayout>(rowId)
        val value = row.tag as String
        row.setOnClickListener {
            requireContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().putString(prefKey, value).apply()
            applyRadioState(dots, value)
        }
    }

    /** Set the dot drawable for each entry in [dots]: filled if its key matches [selected]. */
    private fun applyRadioState(dots: Map<String, View>, selected: String) {
        val ctx = requireContext()
        val filled = ContextCompat.getDrawable(ctx, R.drawable.atrium_radio_selected)
        val hollow = ContextCompat.getDrawable(ctx, R.drawable.atrium_radio_unselected)
        dots.forEach { (key, dot) ->
            dot.background = if (key == selected) filled else hollow
        }
    }

    companion object {
        // Same SharedPreferences store MainActivity uses for rating
        // cache + curriculum chip.  One prefs file keeps the app's
        // user-state surface coherent.
        const val PREFS_NAME = "chesscoach_prefs"

        const val PREF_COACH_VOICE = "setting_coach_voice"
        const val DEFAULT_COACH_VOICE = "conversational"

        const val PREF_BOARD_STYLE = "setting_board_style"
        const val DEFAULT_BOARD_STYLE = "flat"

        const val PREF_SOUND_ENABLED = "setting_sound_enabled"
        const val PREF_NOTIFICATIONS_ENABLED = "setting_notifications_enabled"

        // ── Reader helpers — call these from downstream features ──

        fun readCoachVoice(ctx: Context): String =
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(PREF_COACH_VOICE, DEFAULT_COACH_VOICE)!!

        fun readBoardStyle(ctx: Context): String =
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(PREF_BOARD_STYLE, DEFAULT_BOARD_STYLE)!!

        fun readSoundEnabled(ctx: Context): Boolean =
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getBoolean(PREF_SOUND_ENABLED, true)

        fun readNotificationsEnabled(ctx: Context): Boolean =
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getBoolean(PREF_NOTIFICATIONS_ENABLED, true)
    }
}
