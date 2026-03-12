#pragma once
#include <string>
#include <vector>

enum Spalva { BALTA, JUODA };

class Piece {
public:
    Piece(char s, Spalva sp) : symbol(s), spalva(sp) {}
    char getSymbol() const { return symbol; }
    void setSymbol(char s) { symbol = s; }
    Spalva getSpalva() const { return spalva; }
private:
    char symbol;
    Spalva spalva;
};

class SachmatuLenta {
public:
    struct Move {
        int fromX, fromY, toX, toY;
        Move() : fromX(-1), fromY(-1), toX(-1), toY(-1) {}
        Move(int fx, int fy, int tx, int ty) : fromX(fx), fromY(fy), toX(tx), toY(ty) {}
        bool isValid() const { return fromX != -1; }
    };

    SachmatuLenta();
    ~SachmatuLenta();

    void reset();
    void setupLenta();
    void loadFromBoard64(const char* board);

    /** Pure state mutation for internal sync */
    bool syncMove(int fr, int fc, int tr, int tc);
    
    /** Pure search: compute best move for a given side */
    Move getBestMove(Spalva s);

    /** Promotion support */
    bool promotePawn(int r, int c, char type);

    /** State export */
    std::string toBoard64String() const;
    Spalva getCurrentTurn() const { return currentTurn; }

    // AI logic helpers (Pure functions)
    bool isLegalMove(int fr, int fc, int tr, int tc, Spalva s) const;
    std::vector<Move> generateLegalMoves(Spalva s) const;
    int evaluateBoard() const;
    int minimax(int depth, bool isMaximizing, int alpha, int beta);
    bool isSquareAttacked(int r, int c, Spalva byColor) const;
    bool isInCheck(Spalva s) const;

private:
    Piece* lent[8][8];
    Spalva currentTurn;
    int epX, epY; // En Passant analysis state

    void clearLenta();
    bool movePieceInternal(int fr, int fc, int tr, int tc);
    bool isPathClear(int fr, int fc, int tr, int tc) const;
};
