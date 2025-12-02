"""
db_generator.py
Generates the WHO TB Outcomes database with all dimension and fact tables.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models_base import Base
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact

# 1. Configure database URL
# Example environment variable DATABASE_URL

# PostgreSQL: "postgresql://user:password@localhost:5432/tb_db"
# SQLite: "sqlite:///tb_db.sqlite3"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tb_outcomes.db")

# 2. Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)  

# Enable FK constraints for SQLite
if "sqlite" in DATABASE_URL:
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# 3. Create tables
def generate_db():
    """Creates all tables defined in the models."""
    Base.metadata.create_all(engine)
    print("Database and tables created successfully!")

#session
def get_session():
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    generate_db()
