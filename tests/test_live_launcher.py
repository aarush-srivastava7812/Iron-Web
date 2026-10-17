"""Exercise fresh-root filesystem setup before seeding the local website."""
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from scripts import run_live_dashboard


@pytest.mark.parametrize("custom_database", [False, True])
def test_website_launcher_seeds_a_writable_database_from_a_fresh_root(
    tmp_path, monkeypatch, custom_database,
):
    monkeypatch.setattr(run_live_dashboard, "__file__", str(tmp_path / "scripts/run_live_dashboard.py"))
    monkeypatch.setattr(sys, "argv", ["run_live_dashboard.py", "website"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    # Keep the launcher's environment mutations local to this test.
    for key in ["DATABASE_URL", "SECRET_KEY", "DEV_LOGIN_ENABLED", "COOKIE_SECURE",
                "DASHBOARD_PUBLISH_TOKEN", "DASHBOARD_USER_USERNAME", "DASHBOARD_SOURCE_TOKEN",
                "DASHBOARD_SOURCE_URL", "DASHBOARD_CORS_ORIGINS"]:
        monkeypatch.setenv(key, "temporary-test-setup")
        monkeypatch.delenv(key)
    target = tmp_path / "data/voyara_app/travel.db"
    if custom_database:
        target = tmp_path / "custom.db"
        monkeypatch.setenv("DATABASE_URL", "sqlite:///" + target.as_posix())
    seeded = []
    def seed():
        import os
        path = os.environ["DATABASE_URL"].removeprefix("sqlite:///")
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE startup_probe (id INTEGER)")
        seeded.append(path)
    servers = []
    monkeypatch.setitem(sys.modules, "seed", SimpleNamespace(run=seed))
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *args, **kwargs: servers.append(kwargs)))
    run_live_dashboard.main()
    assert seeded == [target.as_posix()]
    assert target.is_file()
    assert servers == [dict(host="127.0.0.1", port=8000, workers=1)]
