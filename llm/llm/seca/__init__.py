from __future__ import annotations

from pathlib import Path

# When running from inside the repo (cwd = .../llm), the "llm" package
# resolves to .../llm/llm. Extend the llm.seca package path to include
# the sibling top-level "seca" package so imports like llm.seca.auth work.
_repo_root = Path(__file__).resolve().parents[2]
_seca_path = _repo_root / "seca"
if _seca_path.exists():
    __path__.append(str(_seca_path))
