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
        # Older favorites omitted item_type from the key, so package #1 and stay
        # #1 could not coexist. Preserve every row while upgrading that key.
        key = inspect(connection).get_pk_constraint("favorites")
        if "item_type" not in key["constrained_columns"]:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("CREATE TABLE favorites_v2 (user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE, item_type VARCHAR(10) NOT NULL, item_id INTEGER NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (user_id, item_type, item_id))")
                connection.exec_driver_sql("INSERT INTO favorites_v2 SELECT user_id, item_type, item_id, created_at FROM favorites")
                connection.exec_driver_sql("DROP TABLE favorites")
                connection.exec_driver_sql("ALTER TABLE favorites_v2 RENAME TO favorites")
            elif connection.dialect.name == "postgresql":
                name = connection.dialect.identifier_preparer.quote(key["name"])
                connection.exec_driver_sql(f"ALTER TABLE favorites DROP CONSTRAINT {name}")
                connection.exec_driver_sql("ALTER TABLE favorites ADD PRIMARY KEY (user_id, item_type, item_id)")
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
