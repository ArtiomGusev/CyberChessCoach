"""
Filter CodeQL SARIF output before upload to GitHub Code Scanning.

Removes individual alert instances we have explicitly accepted as false
positives, while keeping the underlying queries enabled for every other
file in the codebase.  Each entry in `_SUPPRESSIONS` documents which
(rule, file) tuple is dropped and why.

Run as:
    python filter_codeql_sarif.py <results-dir>

The directory typically contains one *.sarif file per analysed language.

Why match only (ruleId, file-path)?
-----------------------------------
A real CodeQL SARIF result for py/weak-cryptographic-hash carries the
ruleId, a short message, and a physicalLocation pointing at the line.
It does NOT carry the surrounding function name anywhere in the result
object — that information is computed by the GitHub UI from the line
number, not stored in the SARIF.  An older version of this script also
required a function-name substring to match; that condition silently
failed every run, so the alert was uploaded unchanged on every CodeQL
scan even though the file said "filter applied".

Each suppression entry must therefore narrowly identify a single ruleId
in a single file.  If a file ever needs the same query suppressed in
more than one place, refactor instead — bypass-by-config should be the
last resort, not the first.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable

# Tuples of (ruleId, file-path-substring).  A SARIF result is dropped
# if its ruleId matches AND any of its locations[].physicalLocation
# .artifactLocation.uri contains the file-path-substring.
_SUPPRESSIONS: tuple[tuple[str, str], ...] = (
    # py/weak-cryptographic-hash on llm/seca/auth/hashing.py
    # ───────────────────────────────────────────────────────
    # The flagged call is hashlib.sha256(password.encode("utf-8")).digest()
    # inside _normalize_password_v1.  This is the legacy v1 password-hash
    # pre-normalisation step; the SHA-256 output is fed into PBKDF2-SHA256
    # (600 000 iterations + per-hash random 16-byte salt) immediately
    # afterwards.  The chain is secure; CodeQL's taint analysis cannot
    # see past the first hash call, so it raises the alert in isolation.
    # The function CANNOT be changed (any change breaks every existing
    # v1 hash in the database).  The full rationale lives in the function
    # docstring — anyone removing this suppression should read it first.
    ("py/weak-cryptographic-hash", "llm/seca/auth/hashing.py"),
)


def _result_matches_suppression(result: dict, rule: str, path_sub: str) -> bool:
    if result.get("ruleId") != rule:
        return False
    for loc in result.get("locations", []) or []:
        physical = loc.get("physicalLocation", {}) or {}
        artifact = physical.get("artifactLocation", {}) or {}
        uri = artifact.get("uri") or ""
        if path_sub in uri:
            return True
    return False


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
                _result_matches_suppression(result, rule, path_sub)
                for rule, path_sub in _SUPPRESSIONS
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
