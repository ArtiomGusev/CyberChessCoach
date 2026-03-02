from __future__ import annotations

import hashlib
import queue
import threading
import time
from dataclasses import dataclass

import chess
import chess.engine

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None


@dataclass(frozen=True)
class EnginePoolSettings:
    stockfish_path: str
    pool_size: int = 8
    threads: int = 1
    hash_mb: int = 128
    skill_level: int = 10
    default_movetime_ms: int = 40
    training_movetime_ms: int = 40
    analysis_movetime_ms: int = 80
    blitz_movetime_ms: int = 25
    queue_timeout_ms: int = 50
    min_movetime_ms: int = 20
    max_movetime_ms: int = 2000


class FenMoveCache:
    def __init__(
        self,
        *,
        redis_url: str | None,
        ttl_seconds: int = 3600,
        namespace: str = "fen_move:v2",
    ):
        self._ttl_seconds = ttl_seconds
        self._namespace = namespace
        self._memory_cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._redis = None

        if redis_url and redis is not None:
            try:
                client = redis.Redis.from_url(redis_url)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def _cache_key(
        self,
        *,
        fen: str,
        mode: str,
        movetime_ms: int,
        target_elo: int | None,
    ) -> str:
        # Keep the key coarse so tiny movetime tweaks still hit cache.
        digest = hashlib.sha256(
            f"{fen}|{mode}|{target_elo}".encode("utf-8")
        ).hexdigest()
        return f"{self._namespace}:{digest}"

    def get(
        self,
        *,
        fen: str,
        mode: str,
        movetime_ms: int,
        target_elo: int | None,
    ) -> str | None:
        key = self._cache_key(
            fen=fen,
            mode=mode,
            movetime_ms=movetime_ms,
            target_elo=target_elo,
        )

        if self._redis is not None:
            try:
                cached = self._redis.get(key)
                if cached:
                    return cached.decode("utf-8")
            except Exception:
                pass

        now = time.time()
        with self._lock:
            cached = self._memory_cache.get(key)
            if not cached:
                return None

            value, expires_at = cached
            if expires_at < now:
                self._memory_cache.pop(key, None)
                return None
            return value

    def set(
        self,
        *,
        fen: str,
        mode: str,
        movetime_ms: int,
        target_elo: int | None,
        move_uci: str,
    ) -> None:
        key = self._cache_key(
            fen=fen,
            mode=mode,
            movetime_ms=movetime_ms,
            target_elo=target_elo,
        )

        if self._redis is not None:
            try:
                self._redis.set(key, move_uci, ex=self._ttl_seconds)
                return
            except Exception:
                pass

        with self._lock:
            self._memory_cache[key] = (move_uci, time.time() + self._ttl_seconds)


class StockfishEnginePool:
    def __init__(self, settings: EnginePoolSettings):
        self.settings = settings
        self._engines: queue.Queue[chess.engine.SimpleEngine] = queue.Queue(
            maxsize=settings.pool_size
        )
        self._started = False
        self._lock = threading.Lock()

    def startup(self) -> None:
        with self._lock:
            if self._started:
                return
            for _ in range(self.settings.pool_size):
                self._engines.put(self._spawn_engine())
            self._started = True

    def qsize(self) -> int:
        return self._engines.qsize()

    def _spawn_engine(self) -> chess.engine.SimpleEngine:
        engine = chess.engine.SimpleEngine.popen_uci(self.settings.stockfish_path)
        options = {
            "Threads": self.settings.threads,
            "Hash": self.settings.hash_mb,
            "Skill Level": self.settings.skill_level,
            "MultiPV": 1,
        }
        try:
            engine.configure(options)
        except chess.engine.EngineError:
            # Engines can reject MultiPV in managed modes; keep core tuning.
            options.pop("MultiPV", None)
            engine.configure(options)
        return engine

    def close(self) -> None:
        with self._lock:
            if not self._started:
                return
            while not self._engines.empty():
                engine = self._engines.get_nowait()
                try:
                    engine.quit()
                except Exception:
                    pass
            self._started = False

    def resolve_movetime_ms(self, mode: str, movetime_ms: int | None) -> int:
        if movetime_ms is not None:
            ms = movetime_ms
        else:
            normalized = (mode or "default").lower()
            mode_map = {
                "blitz": self.settings.blitz_movetime_ms,
                "training": self.settings.training_movetime_ms,
                "analysis": self.settings.analysis_movetime_ms,
                # Backward-compatible aliases.
                "puzzle": self.settings.training_movetime_ms,
                "deep": self.settings.analysis_movetime_ms,
            }
            ms = mode_map.get(normalized, self.settings.default_movetime_ms)

        if ms < self.settings.min_movetime_ms:
            return self.settings.min_movetime_ms
        if ms > self.settings.max_movetime_ms:
            return self.settings.max_movetime_ms
        return ms

    def _apply_runtime_options(
        self,
        engine: chess.engine.SimpleEngine,
        *,
        target_elo: int | None,
    ) -> None:
        if target_elo is None:
            return
        try:
            engine.configure({"UCI_LimitStrength": True, "UCI_Elo": int(target_elo)})
        except chess.engine.EngineError:
            # Not all Stockfish builds expose ELO limiting.
            pass

    def fast_fallback_move(self, board: chess.Board) -> chess.Move:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise RuntimeError("No legal moves available")

        captures = [mv for mv in legal_moves if board.is_capture(mv)]
        candidates = captures or legal_moves
        # Stable and cheap fallback: deterministic lexical move ordering.
        return min(candidates, key=lambda mv: mv.uci())

    def select_move(
        self,
        *,
        fen: str,
        board: chess.Board | None = None,
        moves_uci: list[str] | None = None,
        mode: str = "default",
        movetime_ms: int | None = None,
        queue_timeout_ms: int | None = None,
        target_elo: int | None = None,
    ) -> chess.Move:
        if not self._started:
            raise RuntimeError("Engine pool not started")

        resolved_board = board
        if resolved_board is None:
            resolved_board = chess.Board(fen)
            if moves_uci:
                # For start-position games this preserves move stack and can send
                # `position startpos moves ...` to UCI engines.
                candidate = chess.Board()
                try:
                    for move_uci in moves_uci:
                        candidate.push_uci(move_uci)
                    if candidate.fen() == fen:
                        resolved_board = candidate
                except ValueError:
                    resolved_board = chess.Board(fen)

        timeout_ms = queue_timeout_ms
        if timeout_ms is None:
            timeout_ms = self.settings.queue_timeout_ms
        if timeout_ms <= 0:
            timeout_ms = 1

        try:
            engine = self._engines.get(timeout=timeout_ms / 1000.0)
        except queue.Empty as exc:
            raise RuntimeError(
                f"Stockfish queue wait exceeded {timeout_ms}ms"
            ) from exc
        try:
            self._apply_runtime_options(engine, target_elo=target_elo)
            limit = chess.engine.Limit(
                time=self.resolve_movetime_ms(mode, movetime_ms) / 1000.0
            )
            result = engine.play(resolved_board, limit)
            if result.move is None:
                raise RuntimeError("Stockfish returned no move")
            return result.move
        finally:
            self._engines.put(engine)

    def prewarm_cache(
        self,
        *,
        move_cache: FenMoveCache,
        fens: list[str],
        mode: str = "blitz",
        target_elo: int | None = None,
    ) -> int:
        warmed = 0
        movetime_ms = self.resolve_movetime_ms(mode, None)

        for fen in fens:
            fen = fen.strip()
            if not fen:
                continue

            try:
                cached_uci = move_cache.get(
                    fen=fen,
                    mode=mode,
                    movetime_ms=movetime_ms,
                    target_elo=target_elo,
                )
                if cached_uci:
                    warmed += 1
                    continue

                move = self.select_move(
                    fen=fen,
                    mode=mode,
                    movetime_ms=movetime_ms,
                    target_elo=target_elo,
                )
                move_cache.set(
                    fen=fen,
                    mode=mode,
                    movetime_ms=movetime_ms,
                    target_elo=target_elo,
                    move_uci=move.uci(),
                )
                warmed += 1
            except Exception:
                continue

        return warmed
