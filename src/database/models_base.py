"""
Shared Base classes and Mixins for SQLAlchemy models.
"""

import os
from sqlalchemy import Column, Integer, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Adds automatic created_at timestamps to tables."""
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class JSONMixin:
    """For tables using JSON fields (e.g., logging)."""
    # Determine column type depending on database
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        json_type = JSONB
    else:
        json_type = Text

    metadata_json = Column(json_type, nullable=True)


class PKMixin:
    """Reusable primary key mixin."""
    id = Column(Integer, primary_key=True, autoincrement=True)


# Example table using the mixins
class DummyTest(PKMixin, TimestampMixin, Base):
    __tablename__ = "dummy_test"

    name = Column(String(50), nullable=False)
