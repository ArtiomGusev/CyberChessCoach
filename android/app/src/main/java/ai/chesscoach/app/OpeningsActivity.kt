package ai.chesscoach.app

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import kotlin.math.roundToInt

/**
 * Cereveon · Atrium · Openings · Repertoire (handoff screen #7).
 *
 * Reached from HomeActivity row III ("Openings").  Static surface for
 * this scaffold pass — the [DEFAULT_REPERTOIRE] list mirrors the four
 * lines in the design exactly so the screen reads identically to the
 * handoff mock.
 *
 * When a real `/repertoire` backend lands the wiring becomes:
 *   - Replace [DEFAULT_REPERTOIRE] with a fetch on onCreate
 *   - "Drill active line" POSTs to /repertoire/drill or opens
 *     TrainingSessionBottomSheet pre-seeded with the active opening
 *   - "+" opens an opening picker (search by ECO / first move)
 *
 * For now both buttons toast "coming soon" — honest about the
 * not-yet-wired backend rather than silently failing on tap.
 *
 * Persistence: none.  When the player swaps their active opening the
 * choice would be local + server-side, but until there's a
 * /repertoire endpoint the active line stays at the design's default.
 */
class OpeningsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_openings)

        val container = findViewById<LinearLayout>(R.id.openingsCardContainer)
        renderRepertoire(container, DEFAULT_REPERTOIRE)
        renderStats(DEFAULT_REPERTOIRE)

        findViewById<Button>(R.id.btnOpeningsDrill).setOnClickListener {
            val active = DEFAULT_REPERTOIRE.firstOrNull { it.isActive }
            val label = active?.let { "${it.eco} · ${it.name}" } ?: "your active line"
            Toast.makeText(
                this,
                "Drill $label — coming soon",
                Toast.LENGTH_SHORT,
            ).show()
        }
        findViewById<Button>(R.id.btnOpeningsAdd).setOnClickListener {
            Toast.makeText(this, "Add opening — coming soon", Toast.LENGTH_SHORT).show()
        }
    }

    private fun renderRepertoire(container: ViewGroup, entries: List<OpeningEntry>) {
        container.removeAllViews()
        val inflater = LayoutInflater.from(this)
        for (entry in entries) {
            val card = inflater.inflate(R.layout.item_opening_card, container, false)
            bindCard(card, entry)
            container.addView(card)
        }
    }

    private fun bindCard(card: View, entry: OpeningEntry) {
        card.findViewById<TextView>(R.id.openingEco).apply {
            text = entry.eco
            setTextColor(
                ContextCompat.getColor(
                    this@OpeningsActivity,
                    if (entry.isActive) R.color.atrium_accent_cyan else R.color.atrium_dim,
                ),
            )
        }
        card.findViewById<TextView>(R.id.openingName).text = entry.name
        card.findViewById<TextView>(R.id.openingLine).text = entry.line
        card.findViewById<View>(R.id.openingActiveBadge).visibility =
            if (entry.isActive) View.VISIBLE else View.GONE

        // Mastery bar — width as a fraction of the parent track via
        // layoutParams.weight on a 0dp-wide child inside the FrameLayout
        // would need extra plumbing; simpler is to set width directly
        // once the parent has been measured.  We use post {} to wait
        // for layout pass.
        val fill = card.findViewById<View>(R.id.openingMasteryFill)
        fill.setBackgroundColor(
            ContextCompat.getColor(
                this,
                if (entry.isActive) R.color.atrium_accent_cyan else R.color.atrium_muted,
            ),
        )
        fill.post {
            val parentWidth = (fill.parent as? View)?.width ?: 0
            val targetWidth = (parentWidth * entry.mastery).roundToInt()
            fill.layoutParams = fill.layoutParams.apply { width = targetWidth }
            fill.requestLayout()
        }

        card.findViewById<TextView>(R.id.openingMasteryPct).apply {
            text = formatMastery(entry.mastery)
            setTextColor(
                ContextCompat.getColor(
                    this@OpeningsActivity,
                    if (entry.isActive) R.color.atrium_accent_cyan else R.color.atrium_dim,
                ),
            )
        }

        // Active card uses the cyan-tinted background; dormant uses
        // the hairline-bordered transparent fill.  Drawable swap (not
        // tint) so the border + fill colours stay paired correctly.
        card.background = ContextCompat.getDrawable(
            this,
            if (entry.isActive) R.drawable.atrium_opening_card_active
            else R.drawable.atrium_opening_card_dormant,
        )
    }

    private fun renderStats(entries: List<OpeningEntry>) {
        findViewById<TextView>(R.id.openingsStatLines).text = entries.size.toString()
        findViewById<TextView>(R.id.openingsStatDepth).text = formatAvgDepth(entries)
        findViewById<TextView>(R.id.openingsStatScore).text = DEFAULT_SCORE_DISPLAY
    }

    /**
     * One opening line in the user's repertoire.  Mirrors the shape a
     * future `/repertoire` response would carry; the mastery field is
     * 0–1 so it doubles as the bar's width fraction.
     */
    data class OpeningEntry(
        val eco: String,
        val name: String,
        val line: String,
        val mastery: Float,
        val isActive: Boolean,
    )

    companion object {
        /**
         * Hardcoded default repertoire matching the design mock 1-for-1
         * so the scaffold reads exactly like the handoff.  Lifted to
         * the companion object so unit tests can inspect the canonical
         * shape without launching the activity.
         */
        val DEFAULT_REPERTOIRE: List<OpeningEntry> = listOf(
            OpeningEntry(
                eco = "C84",
                name = "Ruy Lopez · Closed",
                line = "1.e4 e5 2.♘f3 ♘c6 3.♗b5 a6",
                mastery = 0.78f,
                isActive = true,
            ),
            OpeningEntry(
                eco = "B22",
                name = "Sicilian · Alapin",
                line = "1.e4 c5 2.c3 ♘f6 3.e5 ♘d5",
                mastery = 0.55f,
                isActive = false,
            ),
            OpeningEntry(
                eco = "D02",
                name = "Queen's Pawn · London",
                line = "1.d4 d5 2.♘f3 ♘f6 3.♗f4",
                mastery = 0.42f,
                isActive = false,
            ),
            OpeningEntry(
                eco = "A04",
                name = "Réti opening",
                line = "1.♘f3 d5 2.c4 e6 3.g3",
                mastery = 0.18f,
                isActive = false,
            ),
        )

        /**
         * Win-rate display for the third metric cell.  Backed by a real
         * stat once /game-history grows a per-opening rollup.  Until
         * then the design's hardcoded 68% reads as a reasonable
         * placeholder rather than "—" (which would imply the surface
         * is broken).
         */
        const val DEFAULT_SCORE_DISPLAY = "68%"

        /**
         * Average half-move depth of memorised lines, rounded to nearest
         * integer.  Counts one half-move per token in the line string;
         * the "1." / "2." numbering is stripped by the space-split since
         * the design's lines render moves with " " separators.
         */
        fun formatAvgDepth(entries: List<OpeningEntry>): String {
            if (entries.isEmpty()) return "0"
            val avg = entries.map { it.line.split(" ").size }.average()
            return avg.roundToInt().toString()
        }

        /** Bar percentage label — "%d%%" for 0–100 with a 1% floor / 100% ceiling. */
        fun formatMastery(mastery: Float): String {
            val clamped = mastery.coerceIn(0f, 1f)
            return "${(clamped * 100f).roundToInt()}%"
        }
    }
}
