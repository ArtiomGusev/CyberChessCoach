"""Unit tests for the SECA safety freeze guard.

Coverage
--------
Three independent layers in seca/safety/freeze.py are exercised:

1.  Brain allowlist — anything under llm.seca.brain.* that is not on the
    explicit allowlist must crash the scan.  This is the strongest defence:
    a renamed-but-equivalent re-introduction of bandit/world-model/training
    code under brain/ would slip past the keyword-only scan but is caught
    here.

2.  Source keyword scan — RL training entry points (optimizer.step,
    loss.backward, .partial_fit(, bandit.save) anywhere in the seca tree
    must crash the scan.  Verified by writing a small fixture .py file
    into a temp dir and loading it as a module.

3.  Runtime invariants — _assert_safe_world_model rejects None and any
    class other than SafeWorldModel; _assert_no_background_tasks rejects
    SECA_ENABLE_ONLINE_LEARNING=1.

The freeze guard's production behaviour is sys.exit(1).  Tests
monkey-patch ``_crash`` to raise a marker exception so the assertion
machinery can observe the rejection without terminating the test runner.
"""

from __future__ import annotations

import os
import sys
import textwrap
import types
import unittest
import importlib.util
import pathlib
import tempfile
from unittest.mock import patch

import llm.seca.safety.freeze as freeze


class _Crash(RuntimeError):
    """Raised by patched _crash so tests can assert without exiting."""


def _raise(reason: str) -> None:
    raise _Crash(reason)


# ---------------------------------------------------------------------------
# Brain-allowlist policy
# ---------------------------------------------------------------------------


class FreezeBrainAllowlistTest(unittest.TestCase):
    """Layer 1: only ALLOWED_BRAIN_MODULES may load under brain/*."""

    def setUp(self):
        self._snapshot = set(sys.modules.keys())

    def tearDown(self):
        for name in list(sys.modules.keys()):
            if name not in self._snapshot:
                del sys.modules[name]

    def _inject_module(self, name: str) -> None:
        """Insert a bare module object at *name* in sys.modules.  No source
        file is attached, so the source-keyword scan will skip it — the
        allowlist check fires first and this is what the test exercises."""
        sys.modules[name] = types.ModuleType(name)

    def test_allowlisted_brain_models_does_not_crash(self):
        """The real llm.seca.brain.models is loaded by auth/router.py at
        runtime; the scan must accept it."""
        import llm.seca.brain.models  # noqa: F401  — populate sys.modules
        with patch.object(freeze, "_crash", _raise):
            freeze._scan_loaded_modules()  # should not raise

    def test_allowlisted_brain_training_models_does_not_crash(self):
        """llm.seca.brain.training.models is loaded by storage/db.py at
        runtime; the scan must accept it."""
        import llm.seca.brain.training.models  # noqa: F401
        with patch.object(freeze, "_crash", _raise):
            freeze._scan_loaded_modules()  # should not raise

    def test_non_allowlisted_brain_bandit_crashes(self):
        """brain.bandit.global_bandit is NOT on the allowlist — must crash."""
        self._inject_module("llm.seca.brain.bandit.global_bandit")
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash) as cm:
                freeze._scan_loaded_modules()
            self.assertIn("brain", str(cm.exception))

    def test_non_allowlisted_brain_world_model_crashes(self):
        """brain.world_model.train_regression — must crash."""
        self._inject_module("llm.seca.brain.world_model.train_regression")
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._scan_loaded_modules()

    def test_non_allowlisted_brain_meta_crashes(self):
        """brain.meta.* — must crash."""
        self._inject_module("llm.seca.brain.meta.meta_coach")
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._scan_loaded_modules()

    def test_non_allowlisted_brain_rewards_crashes(self):
        """brain.rewards.* — must crash."""
        self._inject_module("llm.seca.brain.rewards.update_weekly_rewards")
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._scan_loaded_modules()


# ---------------------------------------------------------------------------
# Source-keyword policy
# ---------------------------------------------------------------------------


class FreezeKeywordScanTest(unittest.TestCase):
    """Layer 2: forbidden source keywords anywhere in seca/* must crash."""

    def setUp(self):
        self._snapshot = set(sys.modules.keys())
        # Use a temp directory so the fixture file is removed on teardown
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = pathlib.Path(self._tmp.name)

    def tearDown(self):
        for name in list(sys.modules.keys()):
            if name not in self._snapshot:
                del sys.modules[name]
        self._tmp.cleanup()

    def _load_fixture(self, fake_module_name: str, source: str) -> None:
        """Write *source* to a temp file and import it under *fake_module_name*
        so inspect.getsource() can recover the body during the scan."""
        path = self._tmp_path / f"{fake_module_name.replace('.', '_')}.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(fake_module_name, path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[fake_module_name] = mod
        spec.loader.exec_module(mod)

    def test_optimizer_step_keyword_blocked(self):
        """PyTorch gradient step in any seca module must trigger crash."""
        self._load_fixture(
            "llm.seca.henm.fake_train",
            textwrap.dedent("""
                def step(optimizer, loss):
                    loss.backward()
                    optimizer.step()
            """),
        )
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash) as cm:
                freeze._scan_loaded_modules()
            self.assertIn("Forbidden", str(cm.exception))

    def test_partial_fit_keyword_blocked(self):
        """sklearn online-learner entry point must trigger crash."""
        self._load_fixture(
            "llm.seca.learning.fake_online",
            textwrap.dedent("""
                def go(model, X, y):
                    model.partial_fit(X, y)
            """),
        )
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._scan_loaded_modules()

    def test_bandit_save_keyword_blocked(self):
        """Bandit persistence call must trigger crash even outside brain/."""
        self._load_fixture(
            "llm.seca.outcome.fake_bandit_persist",
            "def go(bandit):\n    bandit.save()\n",
        )
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._scan_loaded_modules()


# ---------------------------------------------------------------------------
# Runtime invariants
# ---------------------------------------------------------------------------


class FreezeWorldModelTest(unittest.TestCase):
    """Layer 3a: only SafeWorldModel may serve as the runtime world model."""

    def test_safe_world_model_accepted(self):
        from llm.seca.world_model.safe_stub import SafeWorldModel
        with patch.object(freeze, "_crash", _raise):
            freeze._assert_safe_world_model(SafeWorldModel())  # no raise

    def test_none_world_model_rejected(self):
        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash):
                freeze._assert_safe_world_model(None)

    def test_unsafe_world_model_class_rejected(self):
        class UnsafeWorldModel:  # name != SafeWorldModel
            pass

        with patch.object(freeze, "_crash", _raise):
            with self.assertRaises(_Crash) as cm:
                freeze._assert_safe_world_model(UnsafeWorldModel())
            self.assertIn("Unsafe", str(cm.exception))


class FreezeBackgroundTasksTest(unittest.TestCase):
    """Layer 3b: SECA_ENABLE_ONLINE_LEARNING=1 must be rejected."""

    def test_online_learning_env_var_rejected(self):
        with patch.dict(os.environ, {"SECA_ENABLE_ONLINE_LEARNING": "1"}):
            with patch.object(freeze, "_crash", _raise):
                with self.assertRaises(_Crash):
                    freeze._assert_no_background_tasks()

    def test_online_learning_env_var_unset_passes(self):
        env = {k: v for k, v in os.environ.items() if k != "SECA_ENABLE_ONLINE_LEARNING"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(freeze, "_crash", _raise):
                freeze._assert_no_background_tasks()  # no raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
