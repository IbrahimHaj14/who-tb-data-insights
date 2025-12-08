"""
Metadata Tables for WHO TB Outcomes Dataset
"""

from sqlalchemy import Column, Integer, BigInteger, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship
from .models_base import Base, PKMixin, TimestampMixin, JSONMixin


class DataSource(PKMixin, TimestampMixin, Base):
    """
    Ingestion Source Information
    Tracks each dataset ingested (CSV, API, etc.)
    """
    __tablename__ = "data_source"

    name = Column(Text, nullable=False)
    original_file_name = Column(Text, nullable=True)
    original_url = Column(Text, nullable=True)
    fetched_at = Column(TIMESTAMP(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationship to ingestion logs
    ingestion_logs = relationship("IngestionLog", back_populates="data_source")


class IngestionLog(PKMixin, TimestampMixin, Base):
    """
    Data Cleaning & Validation Logs
    Records actions performed during data ingestion.
    """
    __tablename__ = "ingestion_log"

    source_id = Column(Integer, ForeignKey("data_source.id"), nullable=False)
    action = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # Could store JSON text
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationship back to data_source
    data_source = relationship("DataSource", back_populates="ingestion_logs")
