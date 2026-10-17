"""Failures must be actionable without leaking provider or connection secrets."""
import json

import pytest

from scripts import preflight


@pytest.mark.parametrize("mode, expected", [("start", [True, True, True, False]), ("running", [False] * 4)])
def test_port_modes_and_sanitized_connection_failures(monkeypatch, mode, expected):
    import falkordb
    def unavailable(*args, **kwargs):
        raise OSError("private-connection-secret-must-not-appear")
    monkeypatch.setattr(preflight.socket, "create_connection", unavailable)
    monkeypatch.setattr(falkordb, "FalkorDB", unavailable)
    rows = preflight.check(mode=mode, offline=True)
    assert [r["ok"] for r in rows if r["check"].startswith("port:")] == expected
    assert not next(r["ok"] for r in rows if r["check"] == "FalkorDB PING")
    assert "private-connection-secret" not in json.dumps(rows)
