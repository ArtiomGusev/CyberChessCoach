"""
SECA Safety Kernel v1
---------------------
Minimal production-style safety kernel that:
- Wraps every action
- Enforces hard safety invariants
- Validates self-updates
- Provides auditable logging

Designed to be SMALL and REVIEWABLE -> future formal verification target.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

# ============================================================
# Exceptions
# ============================================================


class SafetyViolation(Exception):
    """Raised when an action or update violates safety constraints."""


class UpdateRejected(Exception):
    """Raised when a self-evolution proposal is rejected."""


# ============================================================
# Data structures
# ============================================================


@dataclass
class ActionContext:
    player_id: Optional[str]
    action_type: str
    payload: Dict[str, Any]
    timestamp: float


@dataclass
class UpdateProposal:
    name: str
    version: str
    artifact_bytes: bytes
    declared_constraints: Dict[str, Any]
    proof: Dict[str, Any]  # placeholder for future formal proof object


# ============================================================
# Safety Kernel
# ============================================================


class SafetyKernel:
    """
    Root-of-trust runtime guard.

    Responsibilities:
    - Enforce action-level invariants
    - Gate self-modification
    - Produce tamper-evident audit logs
    """

    # ---------------------------
    # Construction
    # ---------------------------

    def __init__(self, *, max_payload_bytes: int = 50_000, max_actions_per_min: int = 120):
        self.max_payload_bytes = max_payload_bytes
        self.max_actions_per_min = max_actions_per_min

        self._action_timestamps: list[float] = []
        self._audit_chain_hash: str = "GENESIS"

    # ========================================================
    # Public API
    # ========================================================

    # ---------------------------
    # Action wrapper
    # ---------------------------

    def run_action(self, ctx: ActionContext, fn: Callable[[ActionContext], Any]) -> Any:
        """Execute an action through safety enforcement."""

        self._enforce_rate_limit(ctx)
        self._enforce_payload_size(ctx)

        result = fn(ctx)

        self._log_event("action_executed", {"action": ctx.action_type})

        return result

    # ---------------------------
    # Self-update gate
    # ---------------------------

    def validate_update(self, proposal: UpdateProposal) -> None:
        """
        Decide whether a self-evolution proposal is safe to accept.

        Current implementation = deterministic rule checks.
        Future = formal proof verification.
        """

        self._require_semantic_version(proposal.version)
        self._require_constraints_present(proposal)
        self._require_proof_stub(proposal)

        self._log_event("update_validated", {"name": proposal.name, "version": proposal.version})

    # ---------------------------
    # Commit update
    # ---------------------------

    def commit_update(self, proposal: UpdateProposal) -> str:
        """Record accepted update and return artifact hash."""

        self.validate_update(proposal)

        artifact_hash = hashlib.sha256(proposal.artifact_bytes).hexdigest()

        self._log_event(
            "update_committed",
            {
                "name": proposal.name,
                "version": proposal.version,
                "hash": artifact_hash,
            },
        )

        return artifact_hash

    # ========================================================
    # Invariants
    # ========================================================

    def _enforce_payload_size(self, ctx: ActionContext) -> None:
        size = len(json.dumps(ctx.payload).encode("utf-8"))
        if size > self.max_payload_bytes:
            raise SafetyViolation(f"Payload too large: {size} bytes")

    def _enforce_rate_limit(self, ctx: ActionContext) -> None:
        now = ctx.timestamp
        window_start = now - 60

        self._action_timestamps = [t for t in self._action_timestamps if t >= window_start]

        if len(self._action_timestamps) >= self.max_actions_per_min:
            raise SafetyViolation("Rate limit exceeded")

        self._action_timestamps.append(now)

    # ========================================================
    # Update validation rules (deterministic -> provable later)
    # ========================================================

    def _require_semantic_version(self, version: str) -> None:
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise UpdateRejected("Version must follow semantic versioning: X.Y.Z")

    def _require_constraints_present(self, proposal: UpdateProposal) -> None:
        if "safety_invariants" not in proposal.declared_constraints:
            raise UpdateRejected("Missing safety_invariants in constraints")

    def _require_proof_stub(self, proposal: UpdateProposal) -> None:
        # Placeholder until real theorem-prover integration
        if proposal.proof.get("type") != "stub_proof":
            raise UpdateRejected("Invalid or missing proof object")

    # ========================================================
    # Tamper-evident audit log
    # ========================================================

    def _log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "time": time.time(),
            "event": event_type,
            "payload": payload,
            "prev_hash": self._audit_chain_hash,
        }

        serialized = json.dumps(record, sort_keys=True).encode("utf-8")
        self._audit_chain_hash = hashlib.sha256(serialized).hexdigest()

        # In production -> write to append-only storage
        print("[SAFETY-LOG]", record, "->", self._audit_chain_hash)


# ============================================================
# Example usage (dev smoke test)
# ============================================================

if __name__ == "__main__":
    kernel = SafetyKernel()

    # ---- action test ----
    ctx = ActionContext(
        player_id="demo",
        action_type="finish_game",
        payload={"result": "win"},
        timestamp=time.time(),
    )

    def fake_action(c: ActionContext):
        return {"status": "ok"}

    print("Action result:", kernel.run_action(ctx, fake_action))

    # ---- update test ----
    proposal = UpdateProposal(
        name="world_model",
        version="1.0.0",
        artifact_bytes=b"model-bytes",
        declared_constraints={"safety_invariants": ["bounded_output"]},
        proof={"type": "stub_proof"},
    )

    print("Committed hash:", kernel.commit_update(proposal))
