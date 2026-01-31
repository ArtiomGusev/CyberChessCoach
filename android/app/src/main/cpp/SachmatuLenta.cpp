#include "SachmatuLenta.h"
#include <cstring>
#include <cctype>
#include <algorithm>
#include <cmath>
#include <android/log.h>

#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, "AI_NATIVE", __VA_ARGS__)

SachmatuLenta::SachmatuLenta() : epX(-1), epY(-1) {
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++)
            lent[r][c] = nullptr;
    setupLenta();
}

SachmatuLenta::~SachmatuLenta() {
    clearLenta();
}

void SachmatuLenta::clearLenta() {
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            if (lent[r][c]) {
                delete lent[r][c];
                lent[r][c] = nullptr;
            }
        }
    }
}

void SachmatuLenta::reset() {
    clearLenta();
    setupLenta();
    epX = -1;
    epY = -1;
}

void SachmatuLenta::setupLenta() {
    const char* start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1";
    loadFromBoard64(start);
}

void SachmatuLenta::loadFromBoard64(const char* board) {
    clearLenta();
    if (!board) return;

    if (strchr(board, '/')) {
        int r = 0, c = 0;
        for (int i = 0; board[i] != '\0' && board[i] != ' '; i++) {
            char ch = board[i];
            if (ch == '/') { r++; c = 0; }
            else if (isdigit(ch)) { c += (ch - '0'); }
            else {
                if (r < 8 && c < 8) lent[r][c] = new Piece(ch, isupper(ch) ? BALTA : JUODA);
                c++;
            }
        }
    } else {
        for (int i = 0; i < 64 && board[i] != '\0'; i++) {
            char c = board[i];
            if (c == '.' || c == ' ') continue;
            lent[i / 8][i % 8] = new Piece(c, isupper(c) ? BALTA : JUODA);
        }
    }
}

bool SachmatuLenta::syncMove(int fr, int fc, int tr, int tc) {
    return movePieceInternal(fr, fc, tr, tc);
}

bool SachmatuLenta::movePieceInternal(int fr, int fc, int tr, int tc) {
    if (fr < 0 || fr > 7 || fc < 0 || fc > 7 || tr < 0 || tr > 7 || tc < 0 || tc > 7) return false;
    Piece* p = lent[fr][fc];
    if (!p) return false;

    char type = std::tolower(p->getSymbol());

    // Basic EP Capture sync
    if (type == 'p' && fc != tc && !lent[tr][tc] && tr == epX && tc == epY) {
        if (lent[fr][tc]) delete lent[fr][tc];
        lent[fr][tc] = nullptr;
    }

    // Basic Castling sync
    if (type == 'k' && std::abs(tc - fc) == 2) {
        if (tc > fc) { 
            if (lent[fr][5]) delete lent[fr][5];
            lent[fr][5] = lent[fr][7]; lent[fr][7] = nullptr; 
        } else { 
            if (lent[fr][3]) delete lent[fr][3];
            lent[fr][3] = lent[fr][0]; lent[fr][0] = nullptr; 
        }
    }

    epX = -1; epY = -1;
    if (type == 'p' && std::abs(tr - fr) == 2) {
        epX = (fr + tr) / 2;
        epY = fc;
    }

    if (lent[tr][tc]) delete lent[tr][tc];
    lent[tr][tc] = lent[fr][fc];
    lent[fr][fc] = nullptr;
    return true;
}

bool SachmatuLenta::promotePawn(int r, int c, char type) {
    if (r < 0 || r > 7 || c < 0 || c > 7) return false;
    Piece* p = lent[r][c];
    if (!p || std::tolower(p->getSymbol()) != 'p') return false;
    p->setSymbol(isupper(p->getSymbol()) ? std::toupper(type) : std::tolower(type));
    return true;
}

SachmatuLenta::Move SachmatuLenta::getBestMove(Spalva s) {
    std::vector<Move> moves = generateLegalMoves(s);
    if (moves.empty()) return Move();

    Move bestMove = moves[0];
    int bestVal = (s == BALTA) ? -10000 : 10000;

    for (const auto& m : moves) {
        Piece* backup_from = lent[m.fromX][m.fromY];
        Piece* backup_to = lent[m.toX][m.toY];
        lent[m.toX][m.toY] = backup_from;
        lent[m.fromX][m.fromY] = nullptr;

        int val = minimax(2, (s == JUODA), -10000, 10000);

        lent[m.fromX][m.fromY] = backup_from;
        lent[m.toX][m.toY] = backup_to;

        if (s == BALTA) {
            if (val > bestVal) { bestVal = val; bestMove = m; }
        } else {
            if (val < bestVal) { bestVal = val; bestMove = m; }
        }
    }
    return bestMove;
}

bool SachmatuLenta::isPathClear(int fr, int fc, int tr, int tc) const {
    int dr = (tr > fr) ? 1 : (tr < fr ? -1 : 0);
    int dc = (tc > fc) ? 1 : (tc < fc ? -1 : 0);
    int r = fr + dr;
    int c = fc + dc;
    while (r != tr || c != tc) {
        if (lent[r][c]) return false;
        r += dr; c += dc;
    }
    return true;
}

bool SachmatuLenta::isSquareAttacked(int r, int c, Spalva byColor) const {
    for (int fr = 0; fr < 8; fr++) {
        for (int fc = 0; fc < 8; fc++) {
            Piece* p = lent[fr][fc];
            if (p && p->getSpalva() == byColor) {
                int dr = std::abs(r - fr);
                int dc = std::abs(c - fc);
                char type = std::tolower(p->getSymbol());
                if (type == 'p') {
                    int dir = (byColor == BALTA) ? -1 : 1;
                    if (r == fr + dir && dc == 1) return true;
                } else if (type == 'n') {
                    if ((dr == 2 && dc == 1) || (dr == 1 && dc == 2)) return true;
                } else if (type == 'k') {
                    if (dr <= 1 && dc <= 1) return true;
                } else if (type == 'r' || type == 'b' || type == 'q') {
                    if (((type == 'r' && (fr == r || fc == c)) || (type == 'b' && (dr == dc)) || (type == 'q' && (fr == r || fc == c || dr == dc))) && isPathClear(fr, fc, r, c)) return true;
                }
            }
        }
    }
    return false;
}

bool SachmatuLenta::isInCheck(Spalva s) const {
    int kr = -1, kc = -1;
    char kingSym = (s == BALTA) ? 'K' : 'k';
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            if (lent[r][c] && lent[r][c]->getSymbol() == kingSym) { kr = r; kc = c; break; }
        }
    }
    if (kr == -1) return false;
    return isSquareAttacked(kr, kc, (s == BALTA) ? JUODA : BALTA);
}

bool SachmatuLenta::isLegalMove(int fr, int fc, int tr, int tc, Spalva s) const {
    if (fr < 0 || fr > 7 || fc < 0 || fc > 7 || tr < 0 || tr > 7 || tc < 0 || tc > 7) return false;
    Piece* p = lent[fr][fc];
    if (!p || p->getSpalva() != s) return false;
    Piece* target = lent[tr][tc];
    if (target && target->getSpalva() == s) return false;
    char type = std::tolower(p->getSymbol());
    int dr = std::abs(tr - fr);
    int dc = std::abs(tc - fc);
    bool movePossible = false;
    switch (type) {
        case 'p':
            if (fc == tc) {
                int dir = (s == BALTA) ? -1 : 1;
                if (tr == fr + dir && !target) movePossible = true;
                else if (fr == ((s == BALTA) ? 6 : 1) && tr == fr + 2 * dir && !target && !lent[fr + dir][fc]) movePossible = true;
            } else if (dc == 1 && tr == fr + ((s == BALTA) ? -1 : 1) && (target || (tr == epX && tc == epY))) movePossible = true;
            break;
        case 'r': if (fr == tr || fc == tc) movePossible = isPathClear(fr, fc, tr, tc); break;
        case 'n': if ((dr == 2 && dc == 1) || (dr == 1 && dc == 2)) movePossible = true; break;
        case 'b': if (dr == dc) movePossible = isPathClear(fr, fc, tr, tc); break;
        case 'q': if (fr == tr || fc == tc || dr == dc) movePossible = isPathClear(fr, fc, tr, tc); break;
        case 'k': if (dr <= 1 && dc <= 1) movePossible = true; break;
    }
    return movePossible;
}

std::vector<SachmatuLenta::Move> SachmatuLenta::generateLegalMoves(Spalva s) const {
    std::vector<Move> moves;
    for (int fr = 0; fr < 8; fr++) {
        for (int fc = 0; fc < 8; fc++) {
            if (lent[fr][fc] && lent[fr][fc]->getSpalva() == s) {
                for (int tr = 0; tr < 8; tr++) {
                    for (int tc = 0; tc < 8; tc++) {
                        if (isLegalMove(fr, fc, tr, tc, s)) moves.push_back(Move(fr, fc, tr, tc));
                    }
                }
            }
        }
    }
    return moves;
}

int SachmatuLenta::evaluateBoard() const {
    int score = 0;
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            if (lent[r][c]) {
                int val = 0;
                switch (tolower(lent[r][c]->getSymbol())) {
                    case 'p': val = 10; break;
                    case 'n': val = 30; break;
                    case 'b': val = 30; break;
                    case 'r': val = 50; break;
                    case 'q': val = 90; break;
                    case 'k': val = 900; break;
                }
                score += (lent[r][c]->getSpalva() == BALTA) ? val : -val;
            }
        }
    }
    return score;
}

int SachmatuLenta::minimax(int depth, bool isMaximizing, int alpha, int beta) {
    if (depth == 0) return evaluateBoard();
    Spalva side = isMaximizing ? BALTA : JUODA;
    std::vector<Move> moves = generateLegalMoves(side);
    if (moves.empty()) return evaluateBoard();
    if (isMaximizing) {
        int best = -10000;
        for (const auto& m : moves) {
            Piece* b1 = lent[m.fromX][m.fromY]; Piece* b2 = lent[m.toX][m.toY];
            lent[m.toX][m.toY] = b1; lent[m.fromX][m.fromY] = nullptr;
            best = std::max(best, minimax(depth - 1, false, alpha, beta));
            lent[m.fromX][m.fromY] = b1; lent[m.toX][m.toY] = b2;
            alpha = std::max(alpha, best); if (beta <= alpha) break;
        }
        return best;
    } else {
        int best = 10000;
        for (const auto& m : moves) {
            Piece* b1 = lent[m.fromX][m.fromY]; Piece* b2 = lent[m.toX][m.toY];
            lent[m.toX][m.toY] = b1; lent[m.fromX][m.fromY] = nullptr;
            best = std::min(best, minimax(depth - 1, true, alpha, beta));
            lent[m.fromX][m.fromY] = b1; lent[m.toX][m.toY] = b2;
            beta = std::min(beta, best); if (beta <= alpha) break;
        }
        return best;
    }
}

std::string SachmatuLenta::toBoard64String() const {
    std::string s;
    s.reserve(64);
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            if (!lent[r][c]) s.push_back('.');
            else {
                s.push_back(lent[r][c]->getSymbol());
            }
        }
    }
    return s;
}
