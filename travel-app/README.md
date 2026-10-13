# Travel platform

backend/: FastAPI + SQLAlchemy 2 + SQLite (swap via DATABASE_URL).

    cd backend && pip install -r requirements.txt
    cp .env.example .env   # set SECRET_KEY
    python seed.py && uvicorn app.main:app --reload
    pytest

Docs: http://localhost:8000/docs
AI memory: app/memory_provider.py is an unwired interface; plug your implementation in there.
