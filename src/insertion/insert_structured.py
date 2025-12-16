import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.connection import engine, SessionLocal
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

STRUCTURED_DIR = Path("data/structured")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def upsert_locations(session: Session, df: pd.DataFrame) -> Dict[str, int]:
    """Insert new or update if exists (upsert) locations keyed by iso3 and return iso3->id map."""
    iso_to_id: Dict[str, int] = {}
    for _, row in df.iterrows():
        iso3 = row.get("iso3")
        if pd.isna(iso3):
            continue
        # Try find existing
        existing = session.execute(select(Location).where(Location.iso3 == iso3)).scalar_one_or_none()
        if existing:
            # Update minimal fields
            existing.country = row.get("country") or existing.country
            existing.iso2 = row.get("iso2") or existing.iso2
            existing.iso_numeric = int(row.get("iso_numeric")) if pd.notna(row.get("iso_numeric")) else existing.iso_numeric
            existing.who_region = row.get("who_region") or row.get("g_whoregion") or existing.who_region
            iso_to_id[iso3] = existing.id
        else:
            loc = Location(
                country=row.get("country"),
                iso2=row.get("iso2"),
                iso3=iso3,
                iso_numeric=int(row.get("iso_numeric")) if pd.notna(row.get("iso_numeric")) else None,
                who_region=row.get("who_region") or row.get("g_whoregion"),
            )
            session.add(loc)
            session.flush()  
            iso_to_id[iso3] = loc.id
    session.commit()
    logger.info("Locations upserted: %d", len(iso_to_id))
    return iso_to_id


def upsert_indicators(session: Session, df: pd.DataFrame) -> Dict[str, int]:
    """Upsert indicators keyed by variable_name and return variable_name->id map."""
    var_to_id: Dict[str, int] = {}
    for _, row in df.iterrows():
        var = row.get("variable_name")
        if not var or pd.isna(var):
            continue
        existing = session.execute(select(Indicator).where(Indicator.variable_name == var)).scalar_one_or_none()
        if existing:
            existing.dataset_group = row.get("dataset_group") or existing.dataset_group
            existing.definition = row.get("definition") or existing.definition
            existing.code_list = str(row.get("code_list")) if pd.notna(row.get("code_list")) else existing.code_list
            var_to_id[var] = existing.id
        else:
            ind = Indicator(
                variable_name=var,
                dataset_group=row.get("dataset_group"),
                definition=row.get("definition"),
                code_list=str(row.get("code_list")) if pd.notna(row.get("code_list")) else None,
            )
            session.add(ind)
            session.flush()
            var_to_id[var] = ind.id
    session.commit()
    logger.info("Indicators upserted: %d", len(var_to_id))
    return var_to_id


def insert_outcome_facts(session: Session, facts_df: pd.DataFrame, iso_to_id: Dict[str, int], var_to_id: Dict[str, int], batch_size: int = 5000) -> int:
    """Insert outcome facts, resolving IDs to DB keys if necessary."""
    # DB-resolved ids 
    inserted = 0

    # if iso3/source_col, map to location_id/indicator_id
    
    has_iso3 = "iso3" in facts_df.columns
    has_source_col = "source_col" in facts_df.columns

    
    if has_iso3:
        facts_df["location_id"] = facts_df["iso3"].map(iso_to_id).astype("Int64")
    if has_source_col:
        facts_df["indicator_id"] = facts_df["source_col"].map(var_to_id).astype("Int64")

    # Filter invalid
    pre = len(facts_df)
    facts_df = facts_df[facts_df["location_id"].notna() & facts_df["indicator_id"].notna()].copy()
    logger.info("Outcome facts rows after FK resolution: %d (dropped %d)", len(facts_df), pre - len(facts_df))

    # Prepare rows
    cols_needed = ["location_id", "indicator_id", "year", "value"]
    missing_cols = [c for c in cols_needed if c not in facts_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in outcome_facts.csv: {missing_cols}")

    # Chunked insert
    for start in range(0, len(facts_df), batch_size):
        chunk = facts_df.iloc[start:start+batch_size]
        objs: List[TBOutcomeFact] = []
        for _, r in chunk.iterrows():
            objs.append(
                TBOutcomeFact(
                    location_id=int(r["location_id"]),
                    indicator_id=int(r["indicator_id"]),
                    year=int(r["year"]),
                    value=float(r["value"]) if pd.notna(r["value"]) else None,
                )
            )
        session.bulk_save_objects(objs)
        session.commit()
        inserted += len(objs)
        logger.info("Inserted chunk: %d (total %d)", len(objs), inserted)

    return inserted


def run_insertion(structured_dir: Optional[Path] = None):
    base_dir = Path(structured_dir or STRUCTURED_DIR)
    loc_csv = base_dir / "locations.csv"
    ind_csv = base_dir / "indicators.csv"
    facts_csv = base_dir / "outcome_facts.csv"

    # Read structured CSVs
    loc_df = read_csv(loc_csv)
    ind_df = read_csv(ind_csv)
    facts_df = read_csv(facts_csv)

    # Create tables 
    from src.database.models_base import Base
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        iso_to_id = upsert_locations(session, loc_df)
        var_to_id = upsert_indicators(session, ind_df)
        inserted = insert_outcome_facts(session, facts_df, iso_to_id, var_to_id)
        logger.info("Outcome facts inserted: %d", inserted)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Insert structured CSVs into the database")
    parser.add_argument("--dir", default=str(STRUCTURED_DIR), help="Structured data directory")
    parser.add_argument("--batch-size", type=int, default=5000, help="Bulk insert batch size")

    args = parser.parse_args()
    run_insertion(Path(args.dir))
