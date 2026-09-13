import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def get_db_path() -> str:
    """
    Returns the path to data.db.
    - When running as a packaged .exe (PyInstaller), puts it next to the .exe
    - When running as a script during development, puts it in the project root
    """
    if getattr(sys, "frozen", False):
        # Running as compiled .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as a script during development
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_dir, "data.db")


DB_PATH = get_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite with Qt
    echo=False, 
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db():
    """
    Creates all tables if they do not exist yet.
    Called once at application startup.
    Safe to call multiple times — will not drop or overwrite existing data.
    """
    from core import models  # imported here to avoid circular imports
    Base.metadata.create_all(bind=engine)


def get_session():
    """
    Returns a new database session.
    Always close it when done:
        session = get_session()
        try:
            ...
        finally:
            session.close()
    """
    return SessionLocal()