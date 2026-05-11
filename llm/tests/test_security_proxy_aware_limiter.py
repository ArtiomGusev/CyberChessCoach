"""
Trusted-proxy-aware rate-limit key tests — llm/tests/test_security_proxy_aware_limiter.py

Pins the behaviour of `proxy_aware_remote_address` in
`llm/seca/shared_limiter.py`.  Without this key function, slowapi's
default `get_remote_address` returns the immediate TCP peer, which
behind Caddy is the Caddy container's IP — collapsing every per-IP
rate-limit bucket into one.  With this key function:

  - X-Forwarded-For is honoured ONLY when the immediate peer is in
    TRUSTED_PROXIES, so an untrusted client cannot spoof their IP.
  - The chain is walked right-to-left so an attacker who controls the
    leftmost XFF entry (the one a proxy was given by its upstream)
    cannot escape their bucket.
  - In SECA_ENV=prod with TRUSTED_PROXIES unset, XFF is never trusted
    (silent no-op rather than silent regression).

Stable test IDs (do NOT rename):
  TPA_01  Untrusted peer, no XFF → returns peer
  TPA_02  Untrusted peer, spoofed XFF → returns peer (XFF ignored)
  TPA_03  Trusted peer, single XFF → returns XFF
  TPA_04  Trusted peer, chain ending in trusted hop → returns leftmost-untrusted
  TPA_05  Trusted peer, leftmost-spoofed chain → right-to-left walk wins
  TPA_06  Trusted peer, missing XFF → falls back to peer
  TPA_07  Trusted peer, all-trusted XFF → falls back to peer
  TPA_08  IPv6 trusted peer + IPv6 XFF → resolves correctly
  TPA_09  CIDR trust matches range, not just exact IP
  TPA_10  Malformed XFF entries are skipped, valid neighbours considered
  TPA_11  Prod default with no TRUSTED_PROXIES → empty trust list
  TPA_12  Non-prod default with no TRUSTED_PROXIES → loopback only
  TPA_13  Malformed env entries skipped, valid entries kept
  TPA_14  Limiter binds proxy_aware_remote_address (regression guard)
"""

from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import patch

from starlette.requests import Request as StarletteRequest


def _request(peer_ip: str, xff: str | None = None) -> StarletteRequest:
    """Build a minimal ASGI scope with the given peer + optional XFF."""
    headers: list[tuple[bytes, bytes]] = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode("ascii")))
    return StarletteRequest(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer_ip, 0),
        }
    )


def _reload_with_env(**env_overrides: str | None) -> object:
    """Reload `shared_limiter` with the given env overrides applied.

    `None` values delete the env var.  Returns the reloaded module so
    the caller can pull `proxy_aware_remote_address` and friends out
    of it without leaking module-state across tests.
    """
    import llm.seca.shared_limiter as mod

    with patch.dict(os.environ, {}, clear=False):
        for key, value in env_overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(mod)
    return mod


class TestTpaProxyAwareRateLimitKey(unittest.TestCase):
    def setUp(self):
        # Prod-style env so the prod defaults run, but we override
        # TRUSTED_PROXIES explicitly per test.  Each test that mutates
        # the env reloads the module via _reload_with_env.
        self.mod = _reload_with_env(
            SECA_ENV="prod",
            TRUSTED_PROXIES="10.0.0.0/8, 192.168.1.5, fd00::/8",
        )

    def tearDown(self):
        # Restore a benign default so cross-test pollution can't make
        # an unrelated test rely on a leaked TRUSTED_PROXIES list.
        _reload_with_env(SECA_ENV="dev", TRUSTED_PROXIES=None)

    # --------------------------------------------------------------
    # Core decision tree
    # --------------------------------------------------------------

    def test_tpa_01_untrusted_peer_no_xff_returns_peer(self):
        req = _request(peer_ip="203.0.113.5")
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.5")

    def test_tpa_02_untrusted_peer_spoofed_xff_ignored(self):
        # An attacker connects directly and sends X-Forwarded-For: 1.2.3.4.
        # We must NOT trust that header — return the real peer.
        req = _request(peer_ip="203.0.113.5", xff="1.2.3.4")
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.5")

    def test_tpa_03_trusted_peer_single_xff_returns_xff(self):
        # Caddy in front, single client.  Caddy sets XFF=client.
        req = _request(peer_ip="10.0.0.5", xff="203.0.113.99")
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.99")

    def test_tpa_04_trusted_peer_chain_returns_first_untrusted(self):
        # Two trusted proxies + real client at the start of XFF.
        # Walk right-to-left: 10.0.0.42 (trusted) → 10.0.0.5 (trusted)
        # → 203.0.113.99 (untrusted, return).
        req = _request(
            peer_ip="10.0.0.5",
            xff="203.0.113.99, 10.0.0.5, 10.0.0.42",
        )
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.99")

    def test_tpa_05_leftmost_spoof_does_not_escape_bucket(self):
        # Client tries to spoof "1.2.3.4" by sending X-Forwarded-For: 1.2.3.4
        # to Caddy.  Caddy appends its peer (the real client 203.0.113.99).
        # API receives XFF = "1.2.3.4, 203.0.113.99".  Right-to-left walk
        # returns 203.0.113.99 — the spoof attempt failed.
        req = _request(
            peer_ip="10.0.0.5",
            xff="1.2.3.4, 203.0.113.99",
        )
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.99")

    def test_tpa_06_trusted_peer_missing_xff_falls_back(self):
        req = _request(peer_ip="10.0.0.5")
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "10.0.0.5")

    def test_tpa_07_trusted_peer_all_trusted_xff_falls_back(self):
        # Degenerate: every entry is a trusted proxy (e.g. internal probe).
        # Falls back to immediate peer rather than returning empty / None.
        req = _request(
            peer_ip="10.0.0.5",
            xff="10.0.0.42, 10.0.0.5",
        )
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "10.0.0.5")

    # --------------------------------------------------------------
    # IP-format edge cases
    # --------------------------------------------------------------

    def test_tpa_08_ipv6_chain_resolves(self):
        # fd00::/8 is in the trust list.  fd00::1 is the proxy peer;
        # 2001:db8::1 is the real (public) client.
        req = _request(
            peer_ip="fd00::1",
            xff="2001:db8::1, fd00::1",
        )
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "2001:db8::1")

    def test_tpa_09_cidr_matches_range(self):
        # 10.0.0.0/8 covers 10.42.99.7 — same trust verdict as 10.0.0.5.
        req = _request(peer_ip="10.42.99.7", xff="203.0.113.10")
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.10")

    def test_tpa_10_malformed_xff_entries_skipped(self):
        # Garbage entries between valid IPs are skipped silently;
        # walk continues until a valid untrusted IP is found.  An
        # entry that fails ip_address() parsing is treated as
        # untrusted — that mirrors the "any non-IP token cannot be
        # one of our proxies" intuition and crucially does not crash
        # the request handler.
        req = _request(
            peer_ip="10.0.0.5",
            xff="not-an-ip, 203.0.113.50, 10.0.0.5",
        )
        self.assertEqual(self.mod.proxy_aware_remote_address(req), "203.0.113.50")

    # --------------------------------------------------------------
    # Configuration loading
    # --------------------------------------------------------------

    def test_tpa_11_prod_default_unset_means_empty_trust(self):
        mod = _reload_with_env(SECA_ENV="prod", TRUSTED_PROXIES=None)
        # An empty trust list means even loopback is untrusted: the
        # immediate peer always wins.  This is the documented prod
        # default — no silent regression on a misconfigured deploy.
        req = _request(peer_ip="127.0.0.1", xff="203.0.113.50")
        self.assertEqual(mod.proxy_aware_remote_address(req), "127.0.0.1")

    def test_tpa_12_dev_default_unset_means_loopback_only(self):
        mod = _reload_with_env(SECA_ENV="dev", TRUSTED_PROXIES=None)
        # Loopback is trusted by default in dev so a local proxy works
        # without extra config; nothing else is.
        req_loopback = _request(peer_ip="127.0.0.1", xff="203.0.113.50")
        self.assertEqual(mod.proxy_aware_remote_address(req_loopback), "203.0.113.50")
        req_lan = _request(peer_ip="10.0.0.5", xff="203.0.113.50")
        self.assertEqual(mod.proxy_aware_remote_address(req_lan), "10.0.0.5")

    def test_tpa_13_malformed_env_entries_dropped_valid_kept(self):
        mod = _reload_with_env(
            SECA_ENV="prod",
            TRUSTED_PROXIES="10.0.0.0/8, garbage, , 192.168.1.5/33, 192.168.1.5",
        )
        # 10.0.0.0/8 and 192.168.1.5 survive; "garbage" and the bad
        # CIDR are dropped.  Empty whitespace tokens are tolerated.
        req_good = _request(peer_ip="10.0.0.5", xff="203.0.113.50")
        self.assertEqual(mod.proxy_aware_remote_address(req_good), "203.0.113.50")
        req_other_good = _request(peer_ip="192.168.1.5", xff="203.0.113.51")
        self.assertEqual(mod.proxy_aware_remote_address(req_other_good), "203.0.113.51")

    # --------------------------------------------------------------
    # Wiring guard
    # --------------------------------------------------------------

    def test_tpa_14_limiter_binds_proxy_aware_key(self):
        # Regression guard: a future "simplification" reverting to
        # slowapi.util.get_remote_address would silently re-introduce
        # the per-Caddy-IP coarse limiting.  Pin the wiring.
        self.assertIs(
            self.mod.limiter._key_func,  # pylint: disable=protected-access
            self.mod.proxy_aware_remote_address,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
