"""
Regression test: StockfishAdapter must not be imported or referenced in any
live code path.

StockfishAdapter (llm/seca/engines/stockfish/adapter.py) runs a depth-limited
SimpleEngine outside all pool and limit-resolution governance. If it is ever
wired into a live route, it bypasses:
  - Limit resolution and clamping
  - Pool lifecycle and back-pressure
  - Result caching
  - Score normalization

Any change that introduces a reference to StockfishAdapter in a live module
must be caught here before merging.
"""
import ast
from pathlib import Path

# Repo root is three levels above this test file:
# llm/tests/test_*.py -> llm/tests -> llm -> <repo-root>
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Modules that handle live requests and must not use StockfishAdapter.
_LIVE_MODULES = [
    "llm/server.py",
    "llm/host_app.py",
    "llm/elite_engine_service.py",
    "llm/engine_eval.py",
    "llm/seca/engines/stockfish/pool.py",
]


def _parse_module(rel_path: str) -> tuple[ast.Module, str]:
    source_path = _REPO_ROOT / rel_path
    source = source_path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(source_path)), rel_path


def _imported_names(tree: ast.Module) -> list[str]:
    """Return every name imported from any module, preserving aliases."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.name)
                if alias.asname:
                    names.append(alias.asname)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
                if alias.asname:
                    names.append(alias.asname)
    return names


def _imported_module_paths(tree: ast.Module) -> list[str]:
    """Return every module path in from-import statements."""
    paths: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            paths.append(node.module)
    return paths


def test_stockfish_adapter_not_imported_as_name_in_live_modules():
    """No live module may import 'StockfishAdapter' by name or alias."""
    for rel_path in _LIVE_MODULES:
        tree, label = _parse_module(rel_path)
        imported = _imported_names(tree)
        assert "StockfishAdapter" not in imported, (
            f"{label} imports 'StockfishAdapter' by name or alias. "
            "StockfishAdapter bypasses pool lifecycle and limit-resolution governance. "
            "If it is needed, it must first be brought under pool management and "
            "limit-normalization, and this test must be updated with a documented rationale."
        )


def test_stockfish_adapter_module_not_imported_in_live_modules():
    """No live module may import from the stockfish.adapter module path."""
    for rel_path in _LIVE_MODULES:
        tree, label = _parse_module(rel_path)
        module_paths = _imported_module_paths(tree)
        assert not any("adapter" in p and "stockfish" in p for p in module_paths), (
            f"{label} imports from a stockfish adapter module: {module_paths}. "
            "The adapter module runs its own depth-limited SimpleEngine instance "
            "outside pool and limit-resolution governance."
        )
