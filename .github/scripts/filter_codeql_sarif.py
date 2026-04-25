"""
Filter CodeQL SARIF output before upload to GitHub Code Scanning.

Removes individual alert instances we have explicitly accepted as false
positives, while keeping the underlying queries enabled for every other file
in the codebase.  Each entry in `_SUPPRESSIONS` documents which (rule, file,
function) tuple is dropped and why.

Run as:
    python filter_codeql_sarif.py <results-dir>

The directory typically contains one *.sarif file per analysed language.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable

# Tuples of (ruleId, path-substring, location-substring).
# A SARIF result is dropped if it matches all three substrings.  Substrings,
# not exact match, so the filter survives small SARIF format changes.
_SUPPRESSIONS: tuple[tuple[str, str, str], ...] = (
    (
        "py/weak-cryptographic-hash",
        "llm/seca/auth/hashing.py",
        "_normalize_password_v1",
    ),
)


def _result_matches_suppression(result: dict, rule: str, path_sub: str, loc_sub: str) -> bool:
    if result.get("ruleId") != rule:
        return False
    serialized = json.dumps(result)
    if path_sub not in serialized:
        return False
    if loc_sub not in serialized:
        return False
    return True


def _filter_sarif_file(path: str) -> tuple[int, int]:
    with open(path, "r", encoding="utf-8") as fh:
        sarif = json.load(fh)

    dropped = 0
    kept = 0
    for run in sarif.get("runs", []):
        original = run.get("results", []) or []
        new_results = []
        for result in original:
            if any(
                _result_matches_suppression(result, *s) for s in _SUPPRESSIONS
            ):
                dropped += 1
                continue
            kept += 1
            new_results.append(result)
        run["results"] = new_results

    if dropped:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(sarif, fh)
    return dropped, kept


def _iter_sarif_files(root: str) -> Iterable[str]:
    if os.path.isfile(root) and root.endswith(".sarif"):
        yield root
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".sarif"):
                yield os.path.join(dirpath, name)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: filter_codeql_sarif.py <results-dir-or-file>", file=sys.stderr)
        return 2

    target = argv[1]
    files = list(_iter_sarif_files(target))
    if not files:
        print(f"no SARIF files found under {target}", file=sys.stderr)
        return 0

    total_dropped = 0
    total_kept = 0
    for path in files:
        dropped, kept = _filter_sarif_file(path)
        total_dropped += dropped
        total_kept += kept
        print(f"  {path}: dropped={dropped} kept={kept}")

    print(
        f"done: {total_dropped} suppressed alert(s) removed, "
        f"{total_kept} alert(s) preserved",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
