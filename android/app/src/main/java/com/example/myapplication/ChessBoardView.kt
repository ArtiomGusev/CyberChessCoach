package com.example.myapplication

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import kotlin.math.abs
import kotlin.math.min

class ChessBoardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    enum class MoveResult { SUCCESS, PROMOTION, FAILED }

    /* ================= STATE ================= */
    private val board = Array(8) { CharArray(8) { '.' } }
    private var whiteToMove = true
    private var selectedRow = -1
    private var selectedCol = -1
    private var enPassantTarget: Pair<Int, Int>? = null
    private var gameOver = false
    
    private var whiteKingMoved = false
    private var blackKingMoved = false
    private var whiteRookAMoved = false
    private var whiteRookHMoved = false
    private var blackRookAMoved = false
    private var blackRookHMoved = false

    var onMovePlayed: ((Int, Int, Int, Int) -> Unit)? = null
    var coachListener: ((String) -> Unit)? = null
    var promotionListener: ((Int, Int) -> Unit)? = null

    private data class MoveRecord(
        val sr: Int, val sc: Int, val tr: Int, val tc: Int,
        val piece: Char, val captured: Char,
        val epTarget: Pair<Int, Int>?,
        val wKM: Boolean, val bKM: Boolean,
        val wRAM: Boolean, val wRHM: Boolean,
        val bRAM: Boolean, val bRHM: Boolean
    )
    private val history = mutableListOf<MoveRecord>()

    /* ================= PAINT ================= */
    private val lightSquare = Paint().apply { color = Color.rgb(40, 40, 40) }
    private val darkSquare = Paint().apply { color = Color.BLACK }
    private val selectPaint = Paint().apply { color = Color.CYAN; alpha = 140 }
    private val piecePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.CYAN
        textAlign = Paint.Align.CENTER
    }

    private var squareSize = 0f

    init { resetBoard() }

    /* ================= PUBLIC API ================= */

    fun resetBoard() {
        val start = arrayOf("rnbqkbnr", "pppppppp", "........", "........", "........", "........", "PPPPPPPP", "RNBQKBNR")
        for (r in 0..7) for (c in 0..7) board[r][c] = start[r][c]
        whiteToMove = true; gameOver = false
        selectedRow = -1; selectedCol = -1; enPassantTarget = null
        whiteKingMoved = false; blackKingMoved = false
        whiteRookAMoved = false; whiteRookHMoved = false
        blackRookAMoved = false; blackRookHMoved = false
        history.clear(); invalidate()
    }

    fun applyMove(sr: Int, sc: Int, tr: Int, tc: Int): MoveResult {
        if (gameOver || !isLegal(sr, sc, tr, tc)) return MoveResult.FAILED
        val piece = board[sr][sc]
        val isPromotion = piece.lowercaseChar() == 'p' && (tr == 0 || tr == 7)
        executeMove(sr, sc, tr, tc)
        return if (isPromotion) MoveResult.PROMOTION else {
            whiteToMove = !whiteToMove
            invalidate()
            MoveResult.SUCCESS
        }
    }

    fun applyAIMove(fr: Int, fc: Int, tr: Int, tc: Int) {
        if (fr !in 0..7 || fc !in 0..7 || tr !in 0..7 || tc !in 0..7) return
        executeMove(fr, fc, tr, tc)
        whiteToMove = !whiteToMove
        invalidate()
    }

    fun undoMove(): Boolean? {
        if (history.isEmpty()) return null
        val last = history.removeAt(history.size - 1)
        board[last.sr][last.sc] = last.piece
        board[last.tr][last.tc] = last.captured
        if (last.piece.lowercaseChar() == 'k' && abs(last.tc - last.sc) == 2) {
            if (last.tc > last.sc) { board[last.sr][7] = board[last.sr][5]; board[last.sr][5] = '.' }
            else { board[last.sr][0] = board[last.sr][3]; board[last.sr][3] = '.' }
        }
        enPassantTarget = last.epTarget
        whiteKingMoved = last.wKM; blackKingMoved = last.bKM
        whiteRookAMoved = last.wRAM; whiteRookHMoved = last.wRHM
        blackRookAMoved = last.bRAM; blackRookHMoved = last.bRHM
        whiteToMove = last.piece.isUpperCase()
        gameOver = false; invalidate()
        return whiteToMove
    }

    fun undoBoth() {
        if (undoMove() == false) undoMove()
    }

    fun exportFEN(): String {
        val rows = board.joinToString("/") { 
            var empty = 0
            val row = StringBuilder()
            for (char in it) {
                if (char == '.') empty++
                else {
                    if (empty > 0) { row.append(empty); empty = 0 }
                    row.append(char)
                }
            }
            if (empty > 0) row.append(empty)
            row.toString()
        }
        return "$rows ${if (whiteToMove) "w" else "b"}"
    }

    fun promotePawn(r: Int, c: Int, to: Char) {
        board[r][c] = if (board[r][c].isUpperCase()) to.uppercaseChar() else to.lowercaseChar()
        whiteToMove = !whiteToMove
        invalidate()
    }

    /* ================= CHESS RULES ================= */

    private fun isLegal(sr: Int, sc: Int, tr: Int, tc: Int): Boolean {
        val piece = board[sr][sc]
        if (piece == '.' || piece.isUpperCase() != whiteToMove) return false
        if (!isLegalGeometry(piece, sr, sc, tr, tc)) return false
        
        val target = board[tr][tc]
        board[tr][tc] = piece; board[sr][sc] = '.'
        val inCheck = isInCheck(piece.isUpperCase())
        board[sr][sc] = piece; board[tr][tc] = target
        return !inCheck
    }

    private fun isLegalGeometry(p: Char, sr: Int, sc: Int, tr: Int, tc: Int): Boolean {
        if (sr == tr && sc == tc) return false
        val target = board[tr][tc]
        if (target != '.' && target.isUpperCase() == p.isUpperCase()) return false
        val dr = abs(tr - sr); val dc = abs(tc - sc)
        return when (p.lowercaseChar()) {
            'p' -> pawnGeometry(p, sr, sc, tr, tc)
            'r' -> (sr == tr || sc == tc) && pathClear(sr, sc, tr, tc)
            'n' -> (dr == 2 && dc == 1) || (dr == 1 && dc == 2)
            'b' -> (dr == dc) && pathClear(sr, sc, tr, tc)
            'q' -> (dr == dc || sr == tr || sc == tc) && pathClear(sr, sc, tr, tc)
            'k' -> (dr <= 1 && dc <= 1) || (dr == 0 && dc == 2 && canCastle(p, sr, sc, tr, tc))
            else -> false
        }
    }

    private fun pawnGeometry(p: Char, sr: Int, sc: Int, tr: Int, tc: Int): Boolean {
        val dir = if (p.isUpperCase()) -1 else 1
        if (sc == tc && tr == sr + dir && board[tr][tc] == '.') return true
        if (sc == tc && sr == (if (p.isUpperCase()) 6 else 1) && tr == sr + 2 * dir && board[tr][tc] == '.' && pathClear(sr, sc, tr, tc)) return true
        if (abs(tc - sc) == 1 && tr == sr + dir && (board[tr][tc] != '.' || enPassantTarget == tr to tc)) return true
        return false
    }

    private fun pathClear(sr: Int, sc: Int, tr: Int, tc: Int): Boolean {
        val dr = (tr - sr).coerceIn(-1, 1); val dc = (tc - sc).coerceIn(-1, 1)
        var r = sr + dr; var c = sc + dc
        while (r != tr || c != tc) { if (board[r][c] != '.') return false; r += dr; c += dc }
        return true
    }

    private fun canCastle(k: Char, sr: Int, sc: Int, tr: Int, tc: Int): Boolean {
        val white = k.isUpperCase()
        if (isInCheck(white)) return false
        if (white && whiteKingMoved) return false
        if (!white && blackKingMoved) return false
        
        val rookCol = if (tc > sc) 7 else 0
        if (white && ((tc > sc && whiteRookHMoved) || (tc < sc && whiteRookAMoved))) return false
        if (!white && ((tc > sc && blackRookHMoved) || (tc < sc && blackRookAMoved))) return false
        
        if (!pathClear(sr, sc, sr, rookCol)) return false
        
        // Cannot castle through check
        val step = if (tc > sc) 1 else -1
        if (isSquareAttacked(sr, sc + step, !white)) return false
        return true
    }

    private fun isInCheck(white: Boolean): Boolean {
        val king = if (white) 'K' else 'k'
        var kr = -1; var kc = -1
        for (r in 0..7) for (c in 0..7) if (board[r][c] == king) { kr = r; kc = c; break }
        if (kr == -1) return false
        return isSquareAttacked(kr, kc, !white)
    }

    private fun isSquareAttacked(r: Int, c: Int, byWhite: Boolean): Boolean {
        for (row in 0..7) {
            for (col in 0..7) {
                val p = board[row][col]
                if (p != '.' && p.isUpperCase() == byWhite) {
                    if (isLegalGeometry(p, row, col, r, c)) return true
                }
            }
        }
        return false
    }

    /* ================= INTERNAL LOGIC ================= */

    private fun executeMove(sr: Int, sc: Int, tr: Int, tc: Int) {
        val piece = board[sr][sc]
        val captured = board[tr][tc]
        history.add(MoveRecord(sr, sc, tr, tc, piece, captured, enPassantTarget,
            whiteKingMoved, blackKingMoved, whiteRookAMoved, whiteRookHMoved, blackRookAMoved, blackRookHMoved))

        if (piece.lowercaseChar() == 'k' && abs(tc - sc) == 2) {
            if (tc > sc) { board[sr][5] = board[sr][7]; board[sr][7] = '.' }
            else { board[sr][3] = board[sr][0]; board[sr][0] = '.' }
        }
        if (piece.lowercaseChar() == 'p' && tc != sc && board[tr][tc] == '.') board[sr][tc] = '.'
        
        board[tr][tc] = piece; board[sr][sc] = '.'
        updateFlags(piece, sr, sc)
        enPassantTarget = if (piece.lowercaseChar() == 'p' && abs(tr - sr) == 2) (sr + tr) / 2 to sc else null
        
        if (piece.lowercaseChar() == 'p' && (tr == 0 || tr == 7)) promotionListener?.invoke(tr, tc)
        invalidate()
    }

    private fun updateFlags(p: Char, r: Int, c: Int) {
        if (p == 'K') whiteKingMoved = true; if (p == 'k') blackKingMoved = true
        if (p == 'R') { if (r == 7 && c == 0) whiteRookAMoved = true; if (r == 7 && c == 7) whiteRookHMoved = true }
        if (p == 'r') { if (r == 0 && c == 0) blackRookAMoved = true; if (r == 0 && c == 7) blackRookHMoved = true }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (gameOver || event.action != MotionEvent.ACTION_DOWN) return true
        val col = (event.x / (width / 8f)).toInt(); val row = (event.y / (width / 8f)).toInt()
        if (row !in 0..7 || col !in 0..7) return true
        if (selectedRow == -1) {
            val piece = board[row][col]
            if (piece != '.' && piece.isUpperCase() == whiteToMove) {
                selectedRow = row; selectedCol = col; invalidate()
            }
        } else {
            val sr = selectedRow; val sc = selectedCol
            selectedRow = -1; selectedCol = -1; invalidate()
            onMovePlayed?.invoke(sr, sc, row, col)
        }
        return true
    }

    override fun onMeasure(w: Int, h: Int) {
        val size = min(MeasureSpec.getSize(w), MeasureSpec.getSize(h))
        setMeasuredDimension(size, size)
    }

    private fun pieceToUnicode(p: Char): String = when (p) {
        'k' -> "♔"; 'q' -> "♕"; 'r' -> "♖"; 'b' -> "♗"; 'n' -> "♘"; 'p' -> "♙"
        'K' -> "♚"; 'Q' -> "♛"; 'R' -> "♜"; 'B' -> "♝"; 'N' -> "♞"; 'P' -> "♟"
        else -> ""
    }

    override fun onDraw(canvas: Canvas) {
        squareSize = width / 8f
        piecePaint.textSize = squareSize * 0.8f
        for (r in 0..7) for (c in 0..7) {
            canvas.drawRect(c * squareSize, r * squareSize, (c + 1) * squareSize, (r + 1) * squareSize, if ((r + c) % 2 == 0) darkSquare else lightSquare)
            if (r == selectedRow && c == selectedCol) canvas.drawRect(c * squareSize, r * squareSize, (c + 1) * squareSize, (r + 1) * squareSize, selectPaint)
            val p = board[r][c]
            if (p != '.') canvas.drawText(pieceToUnicode(p), c * squareSize + squareSize / 2, r * squareSize + squareSize * 0.8f, piecePaint)
        }
    }
}
