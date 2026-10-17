"""Run either local memory owner or read-only relay with one private shared grant."""
import argparse
import os
from pathlib import Path
import secrets
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["website", "dashboard"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    backend = root / "stitch_ai_travel_booking_platform" / "backend"
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv, dotenv_values

    load_dotenv(backend / ".env")
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
    os.environ["DASHBOARD_SOURCE_URL"] = "http://127.0.0.1:8000"
    os.environ["DASHBOARD_CORS_ORIGINS"] = "http://127.0.0.1:5174,http://localhost:5174"
    import uvicorn

    if args.service == "dashboard":
        uvicorn.run("dashboard.backend.main:app", host="127.0.0.1", port=8200, workers=1)
    else:
        os.environ["DEV_LOGIN_ENABLED"] = "true"
        os.environ["COOKIE_SECURE"] = "false"
        if not os.environ.get("SECRET_KEY") or os.environ["SECRET_KEY"].startswith(("dev-only", "change-me")):
            os.environ["SECRET_KEY"] = values["LOCAL_SESSION_SECRET"]
        os.environ.setdefault("DATABASE_URL", "sqlite:///" + (root / "data/voyara_app/travel.db").as_posix())
        from seed import run
        run()
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, workers=1)


if __name__ == "__main__":
    main()
