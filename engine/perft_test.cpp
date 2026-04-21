// Standalone perft correctness test.
// Compile from repo root:
//   g++ -std=c++17 -O2 -I android/app/src/main/cpp \
//       engine/perft_test.cpp android/app/src/main/cpp/SachmatuLenta.cpp \
//       -o engine/perft_bin && ./engine/perft_bin
//
// Exit 0 = all counts matched; non-zero = regression.

#include "SachmatuLenta.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>

static int failures = 0;

static void check(const char* label, uint64_t got, uint64_t want) {
    if (got == want) {
        printf("  PASS  %-40s  %llu\n", label, (unsigned long long)got);
    } else {
        printf("  FAIL  %-40s  got %llu  want %llu\n",
               label, (unsigned long long)got, (unsigned long long)want);
        ++failures;
    }
}

static void run(const char* posName, const char* fen,
                const uint64_t* expected, int maxDepth) {
    printf("\n%s\n  %s\n", posName, fen);
    SachmatuLenta engine;
    engine.loadFromBoard64(fen);

    for (int d = 1; d <= maxDepth; d++) {
        char label[64];
        snprintf(label, sizeof(label), "perft(%d)", d);

        auto t0 = std::chrono::steady_clock::now();
        uint64_t nodes = engine.perft(d);
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                      std::chrono::steady_clock::now() - t0).count();

        check(label, nodes, expected[d - 1]);
        printf("        (%lld ms)\n", (long long)ms);
    }
}

// ── Tactical search test ────────────────────────────────────────────────────
// Position: white rook on h1, white king on b6, black king on a8.
// White plays Rh8# — only mating move at any depth.
static void testMateInOne() {
    printf("\nTactical: White Rh8# (mate-in-1)\n");
    const char* fen = "k7/8/1K6/8/8/8/8/7R w - - 0 1";
    SachmatuLenta engine;
    engine.loadFromBoard64(fen);
    SachmatuLenta::Move m = engine.getBestMove(BALTA);

    // Rh8 = rook from h1(7,7) to h8(0,7)
    bool ok = m.isValid() && m.fromX==7 && m.fromY==7 && m.toX==0 && m.toY==7;
    if (ok) {
        printf("  PASS  found Rh8# (7,7)->(0,7)\n");
    } else {
        printf("  FAIL  expected Rh8# (7,7)->(0,7), got (%d,%d)->(%d,%d)\n",
               m.fromX, m.fromY, m.toX, m.toY);
        ++failures;
    }
}

int main() {
    printf("=== SachmatuLenta perft + tactical tests ===\n");

    // Starting position
    {
        static const uint64_t kStart[] = { 20, 400, 8902, 197281 };
        run("Starting position",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            kStart, 4);
    }

    // Kiwipete — exercises castling, EP, promotions
    {
        static const uint64_t kKiwi[] = { 48, 2039, 97862 };
        run("Kiwipete",
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
            kKiwi, 3);
    }

    // Position 3 (en-passant + promotion stress)
    {
        static const uint64_t kPos3[] = { 14, 191, 2812, 43238 };
        run("Position 3 (EP/promo)",
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            kPos3, 4);
    }

    testMateInOne();

    printf("\n=== %s (%d failure%s) ===\n",
           failures ? "FAILED" : "PASSED",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
