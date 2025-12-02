"""
Fact Table for WHO TB Outcomes Dataset
"""

from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from .models_base import Base, PKMixin, TimestampMixin
from .models_dimension import Location, Indicator  

class TBOutcomeFact(PKMixin, TimestampMixin, Base):
    __tablename__ = "tb_outcome_fact"

    # Foreign keys to dimension tables
    location_id = Column(Integer, ForeignKey("location.id"), nullable=False)
    indicator_id = Column(Integer, ForeignKey("indicator.id"), nullable=False)

    # Year of the observation
    year = Column(Integer, nullable=False)

    # Metric value (float, null if data missing)
    value = Column(Float, nullable=True)

    # Relationships 
    location = relationship("Location", backref="tb_outcomes")
    indicator = relationship("Indicator", backref="tb_outcomes")