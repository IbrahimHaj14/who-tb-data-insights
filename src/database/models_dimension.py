"""
Dimension Tables for WHO TB Outcomes Dataset
"""

from sqlalchemy import Column, Integer, String, Text, CHAR
from .models_base import Base, PKMixin, TimestampMixin


class Location(PKMixin, TimestampMixin, Base):
    __tablename__ = "location"

    country = Column(Text, nullable=False)
    iso2 = Column(CHAR(2), nullable=True)
    iso3 = Column(CHAR(3), nullable=True, unique=True)
    iso_numeric = Column(Integer, nullable=True)
    who_region = Column(Text, nullable=True)


class Indicator(PKMixin, TimestampMixin, Base):
    __tablename__ = "indicator"

    variable_name = Column(Text, nullable=False, unique=True)
    dataset_group = Column(Text, nullable=True)
    definition = Column(Text, nullable=True)
    code_list = Column(Text, nullable=True)
