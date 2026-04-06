"""SQLAlchemy models and database session for Deal Sniper."""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./dealsniper.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _set_sqlite_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class Base(DeclarativeBase):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, index=True, nullable=False)
    destination = Column(String, index=True, nullable=False)
    cabin = Column(String, nullable=False)
    trip_type = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    airline = Column(String, nullable=True)
    outbound_date = Column(String, nullable=True)
    return_date = Column(String, nullable=True)
    duration_mins = Column(Integer, nullable=True)
    stops = Column(Integer, nullable=True)
    checked_at = Column(String, default=_utcnow_iso)


class MonitoredRoute(Base):
    __tablename__ = "monitored_routes"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)  # or "ANYWHERE"
    cabin = Column(String, nullable=False, default="economy")
    trip_type = Column(String, nullable=False, default="return")
    active = Column(Boolean, default=True)
    created_at = Column(String, default=_utcnow_iso)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    cabin = Column(String, nullable=False)
    trip_type = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    discount_pct = Column(Float, nullable=False)
    airline = Column(String, nullable=True)
    outbound_date = Column(String, nullable=True)
    return_date = Column(String, nullable=True)
    booking_url = Column(String, nullable=True)
    found_at = Column(String, default=_utcnow_iso)
    is_dismissed = Column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)


DEFAULT_SETTINGS = {
    "origins": json.dumps(["PER", "SYD", "MEL", "BNE"]),
    "deal_threshold": "0.80",
    "scan_interval_hours": "6",
    "lookahead_days": "90",
    "min_observations": "10",
}


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for key, value in DEFAULT_SETTINGS.items():
            if not db.query(Setting).filter(Setting.key == key).first():
                db.add(Setting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_setting(db: Session, key: str) -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else DEFAULT_SETTINGS.get(key, "")


def set_setting(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()
