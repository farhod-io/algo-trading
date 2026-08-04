"""SQLAlchemy models and helper functions for persisting signals, results, and user settings.
"""

import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from config import DATABASE_URL, INITIAL_BALANCE, DEFAULT_RISK_PCT

engine_kwargs = {"echo": False, "future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30.0}
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=10000;")
        cursor.close()

session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Session = scoped_session(session_factory)
Base = declarative_base()


class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, index=True)
    pair = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    source_strategy = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    raw_message = Column(String)
    sent = Column(Boolean, default=False)


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    analysis = Column(String)


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id = Column(Integer, primary_key=True, index=True)
    pair = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    position_size = Column(Float, nullable=True)
    status = Column(String, default="OPEN")
    pnl = Column(Float, default=0.0)
    reject_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    pair = Column(String, nullable=False)
    fvg_detected = Column(Boolean, default=False)
    liquidity_sweep = Column(Boolean, default=False)
    mss_detected = Column(Boolean, default=False)
    unicorn_detected = Column(Boolean, default=False)
    ote_low = Column(Float, nullable=True)
    ote_mid = Column(Float, nullable=True)
    ote_high = Column(Float, nullable=True)
    close_price = Column(Float, nullable=False)


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id = Column(Integer, primary_key=True, index=True)
    deposit = Column(Float, default=50000.0)
    risk_pct = Column(Float, default=0.5)
    selected_symbols = Column(String, default="GC,NQ,ES")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db() -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables ensured with WAL mode enabled.")


def get_session():
    """Convenience wrapper."""
    return Session()


def get_user_settings_db(user_id: int) -> dict:
    """Fetch user risk settings from DB, inserting defaults if not found."""
    session = get_session()
    try:
        user_cfg = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not user_cfg:
            user_cfg = UserSettings(user_id=user_id, deposit=INITIAL_BALANCE, risk_pct=DEFAULT_RISK_PCT)
            session.add(user_cfg)
            session.commit()
        return {"deposit": user_cfg.deposit, "risk_pct": user_cfg.risk_pct}
    except Exception as e:
        logging.error(f"Error reading UserSettings for {user_id}: {e}")
        return {"deposit": INITIAL_BALANCE, "risk_pct": DEFAULT_RISK_PCT}
    finally:
        session.close()


def save_user_settings_db(user_id: int, deposit: float, risk_pct: float) -> dict:
    """Save/update user risk settings in DB."""
    session = get_session()
    try:
        user_cfg = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not user_cfg:
            user_cfg = UserSettings(user_id=user_id, deposit=deposit, risk_pct=risk_pct)
            session.add(user_cfg)
        else:
            user_cfg.deposit = deposit
            user_cfg.risk_pct = risk_pct
            user_cfg.updated_at = datetime.utcnow()
        session.commit()
        return {"deposit": deposit, "risk_pct": risk_pct}
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving UserSettings for {user_id}: {e}")
        return {"deposit": deposit, "risk_pct": risk_pct}
    finally:
        session.close()
