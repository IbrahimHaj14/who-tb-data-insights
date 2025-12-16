#!/usr/bin/env python3
"""Verify database insertion: print counts and sample joins.

Usage:
  python scripts/verify_insertion.py
"""
import logging
from sqlalchemy import select, func
from src.database.connection import SessionLocal, engine
from src.database.models_base import Base
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def verify_counts():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        loc_count = session.execute(select(func.count(Location.id))).scalar_one()
        ind_count = session.execute(select(func.count(Indicator.id))).scalar_one()
        fact_count = session.execute(select(func.count(TBOutcomeFact.id))).scalar_one()
        logger.info("Counts → locations: %d, indicators: %d, facts: %d", loc_count, ind_count, fact_count)


def sample_join(country_iso3: str = "ARG", variable: str = "new_sp_coh", year: int = 2008, limit: int = 5):
    with SessionLocal() as session:
        q = (
            session.query(TBOutcomeFact, Location, Indicator)
            .join(Location, TBOutcomeFact.location_id == Location.id)
            .join(Indicator, TBOutcomeFact.indicator_id == Indicator.id)
            .filter(Location.iso3 == country_iso3)
            .filter(Indicator.variable_name == variable)
            .filter(TBOutcomeFact.year == year)
        )
        rows = q.limit(limit).all()
        if not rows:
            logger.warning("No rows found for iso3=%s, variable=%s, year=%d", country_iso3, variable, year)
            return
        for fact, loc, ind in rows:
            logger.info(
                "Sample → %s (%s) %d %s = %s",
                loc.country,
                loc.iso3,
                fact.year,
                ind.variable_name,
                fact.value,
            )


if __name__ == "__main__":
    verify_counts()
    
    sample_join("ARG", "new_sp_coh", 2008, limit=5)
    sample_join("ARG", "new_snep_died", 2008, limit=5)