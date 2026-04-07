"""
SECA SAFETY FREEZE GUARD
Hard-disables any self-modifying or adaptive learning behavior.

SAFE SECA v1 MUST import and execute this on startup.
If unsafe components are detected → crash immediately.
"""

import logging
import os
import sys
import inspect

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

SAFE_WORLD_MODEL_CLASS = "SafeWorldModel"

FORBIDDEN_KEYWORDS = [
    "train(",
    ".update(",
    "OnlineSECALearner",
    "train_rl",
    "train_value_model",
    "bandit.update",
]

FORBIDDEN_MODULE_PARTS = [
    "brain.rl",
    "brain.bandit.online",
]


# ------------------------------------------------------------------
# Guards
# ------------------------------------------------------------------


def _scan_loaded_modules():
    """Scan already imported modules for forbidden adaptive components."""
    for name, module in sys.modules.items():
        if module is None:
            continue
        if not name.startswith("llm.seca"):
            continue
        if name.startswith("llm.seca.safety"):
            continue
        if "mock" in name:
            continue

        # block forbidden module paths
        for bad in FORBIDDEN_MODULE_PARTS:
            if bad in name:
                _crash(f"Forbidden adaptive module loaded: {name}")

        # scan source if available
        try:
            src = inspect.getsource(module)
        except (OSError, TypeError):
            continue

        for kw in FORBIDDEN_KEYWORDS:
            if kw in src:
                _crash(f"Forbidden adaptive code detected in module: {name}")


def _assert_safe_world_model(world_model):
    """Ensure only SafeWorldModel is used at runtime."""
    if world_model is None:
        _crash("World model not initialized")

    cls_name = world_model.__class__.__name__
    if cls_name != SAFE_WORLD_MODEL_CLASS:
        _crash(f"Unsafe world model detected: {cls_name}")


def _assert_no_background_tasks():
    """Detect accidental async learner loops via env flags."""
    if os.getenv("SECA_ENABLE_ONLINE_LEARNING") == "1":
        _crash("Online learning explicitly enabled via env")


def _crash(reason: str):
    """Immediate hard stop."""
    logger.critical("=" * 60)
    logger.critical("SECA SAFETY FREEZE TRIGGERED")
    logger.critical("Reason: %s", reason)
    logger.critical("Runtime is NOT SAFE. Shutting down.")
    logger.critical("=" * 60)
    sys.exit(1)


# ------------------------------------------------------------------
# Public entrypoint
# ------------------------------------------------------------------


def enforce(world_model):
    """
    Call once during FastAPI startup.

    Example:
        from llm.seca.safety.freeze import enforce
        enforce(world_model)
    """
    _assert_safe_world_model(world_model)
    _assert_no_background_tasks()
    _scan_loaded_modules()

    logger.info("SECA SAFETY FREEZE: runtime verified SAFE")
