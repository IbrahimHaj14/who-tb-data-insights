"""
Database connection handling for the TB Outcomes Dashboard.

Creates:
- SQLAlchemy Engine
- SessionLocal factory
- Base metadata binding
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file 
load_dotenv()

# SQLite 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tb_outcomes.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,         
    future=True
)

# Session maker
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)

def get_db():
    """
    Dependency/helper to provide a DB session.
    Ensures session is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
