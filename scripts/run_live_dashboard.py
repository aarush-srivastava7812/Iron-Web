"""Run the local website, memory relay, or configured dashboard frontend."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["website", "dashboard", "frontend"])
    parser.add_argument("--website-port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.service == "frontend":
        frontend = root / "dashboard" / "frontend"
        node = shutil.which("node")
        vite = frontend / "node_modules" / "vite" / "bin" / "vite.js"
        if not node or not vite.is_file():
            parser.error("Install Node.js and run npm --prefix dashboard/frontend ci first.")
        # Always load the React JSX plugin, even when launched from another directory.
        raise SystemExit(subprocess.call([
            node, str(vite), str(frontend), "--config", str(frontend / "vite.config.js"),
            "--host", "127.0.0.1", "--port", "5174", "--strictPort", "--force",
        ], cwd=frontend))
    sys.path.insert(0, str(root))
    backend = root / "stitch_ai_travel_booking_platform" / "backend"
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv, dotenv_values

    load_dotenv(backend / ".env")
    os.environ.setdefault("FALKORDB_PORT", "6380")
    os.environ.setdefault("LEGACY_FALKORDB_PORT", "6379")
    os.environ.setdefault("USE_GPU", "true")
    os.environ.setdefault("TINYFISH_CACHE_PATH", str(root / ".scratch" / "tinyfish-public-research"))
    private = root / ".scratch" / "ironweb-live"
    private.mkdir(parents=True, exist_ok=True)
    grant_file = private / ".env"
    if not grant_file.exists():
        grant_file.write_text("LOCAL_DASHBOARD_GRANT=" + secrets.token_urlsafe(48) + "\nLOCAL_SESSION_SECRET=" + secrets.token_urlsafe(48) + "\n", encoding="utf-8")
    values = dotenv_values(grant_file)
    grant = values["LOCAL_DASHBOARD_GRANT"]
    # An explicitly named, ordinary local developer account; no other account is published.
    os.environ["DASHBOARD_PUBLISH_TOKEN"] = grant
    os.environ.setdefault("DASHBOARD_USER_USERNAME", "voyara_local_developer")
    os.environ["DASHBOARD_SOURCE_TOKEN"] = grant
    os.environ["DASHBOARD_SOURCE_URL"] = f"http://127.0.0.1:{args.website_port}"
    os.environ["DASHBOARD_CORS_ORIGINS"] = "http://127.0.0.1:5174,http://localhost:5174"
    import uvicorn

    if args.service == "dashboard":
        uvicorn.run("dashboard.backend.main:app", host="127.0.0.1", port=8200, workers=1)
    else:
        os.environ["DEV_LOGIN_ENABLED"] = "true"
        os.environ["COOKIE_SECURE"] = "false"
        if not os.environ.get("SECRET_KEY") or os.environ["SECRET_KEY"].startswith(("dev-only", "change-me")):
            os.environ["SECRET_KEY"] = values["LOCAL_SESSION_SECRET"]
        data = root / "data" / "voyara_app"
        data.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data / "travel.db").as_posix())
        from seed import run
        run()
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.website_port, workers=1)


if __name__ == "__main__":
    main()
