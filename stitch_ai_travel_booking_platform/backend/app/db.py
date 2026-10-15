from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if _sqlite else {})

if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def create_schema():
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("destinations")}
        if "avg_cost_inr" not in columns:
            connection.exec_driver_sql("ALTER TABLE destinations ADD COLUMN avg_cost_inr INTEGER")
        if "climate" not in columns:
            connection.exec_driver_sql("ALTER TABLE destinations ADD COLUMN climate VARCHAR(120)")
        booking_item_columns = {column["name"] for column in inspect(connection).get_columns("booking_items")}
        if "start_time" not in booking_item_columns:
            connection.exec_driver_sql("ALTER TABLE booking_items ADD COLUMN start_time TIME")
        if "duration_min" not in booking_item_columns:
            connection.exec_driver_sql("ALTER TABLE booking_items ADD COLUMN duration_min INTEGER")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
