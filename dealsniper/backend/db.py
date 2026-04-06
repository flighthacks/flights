import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./dealsniper.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, index=True, nullable=False)
    destination = Column(String, index=True, nullable=False)
    cabin = Column(String, nullable=False)  # economy, premium-economy, business, first
    trip_type = Column(String, nullable=False)  # oneway, return
    price = Column(Float, nullable=False)
    airline = Column(String, nullable=True)
    outbound_date = Column(String, nullable=True)
    return_date = Column(String, nullable=True)
    duration_mins = Column(Integer, nullable=True)
    stops = Column(Integer, nullable=True)
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MonitoredRoute(Base):
    __tablename__ = "monitored_routes"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    cabin = Column(String, nullable=False, default="economy")
    trip_type = Column(String, nullable=False, default="return")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    found_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    "min_observations_before_alert": "10",
}


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for key, value in DEFAULT_SETTINGS.items():
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
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
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        return setting.value
    return DEFAULT_SETTINGS.get(key, "")


def set_setting(db: Session, key: str, value: str):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()
