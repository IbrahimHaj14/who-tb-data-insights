"""Transformer for converting cleaned outcomes into LocationRecords."""

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data_cleaning.SDO import LocationRecord, location_from_row

logger = logging.getLogger(__name__)


class LocationTransformer:
    """Extracts unique locations from cleaned TB outcomes data.
    
    Deduplicates by (country, iso3, iso2, iso_numeric) and emits LocationRecords.
    """

    def __init__(self, output_dir: str = "data/structured"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.issues = []

    def transform(self, df: pd.DataFrame) -> Iterable[LocationRecord]:
        """Extract unique locations from cleaned DataFrame.
        
        Args:
            df: Cleaned outcomes DataFrame with columns: country, iso2, iso3, iso_numeric, g_whoregion
            
        Yields:
            LocationRecord instances
        """
        # Duplicate by (country, iso3, iso2, iso_numeric)
        cols = ["country", "iso2", "iso3", "iso_numeric", "g_whoregion"]
        existing_cols = [c for c in cols if c in df.columns]
        
        if "country" not in existing_cols:
            logger.error("country column not found in DataFrame")
            return
        
        locations_df = df[existing_cols].drop_duplicates().reset_index(drop=True)
        
        for _, row in locations_df.iterrows():
            try:
                loc = location_from_row(row.to_dict())
                yield loc
            except Exception as e:
                self.issues.append({"error": str(e), "row": row.to_dict()})
                logger.warning("Failed to create LocationRecord: %s", e)

    def output_path(self) -> Path:
        """Return target output path."""
        return self.output_dir / "locations.csv"

    def run(self, input_path: str) -> dict:
        """Execute location extraction.
        
        Args:
            input_path: Path to cleaned CSV
            
        Returns:
            Summary dict
        """
        logger.info("Starting LocationTransformer")
        
        df = pd.read_csv(input_path)
        df.columns = [col.strip().lower() for col in df.columns]
        
        records = list(self.transform(df))
        
        # Write output
        if records:
            data = [r.dict() for r in records]
            out_df = pd.DataFrame(data)
            self.output_path().parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(self.output_path(), index=False)
            logger.info("Wrote %d locations to %s", len(records), self.output_path())
        
        return {
            "transformer": "LocationTransformer",
            "input_file": input_path,
            "output_file": str(self.output_path()),
            "records_out": len(records),
            "issues": self.issues,
        }
