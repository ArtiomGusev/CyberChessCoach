from __future__ import annotations

import hashlib


def fen_hash(fen: str) -> str:
    return hashlib.sha1(fen.encode("utf-8")).hexdigest()[:8]
