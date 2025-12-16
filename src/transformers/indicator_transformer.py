"""Transformer for converting data dictionary into IndicatorRecords."""

import logging
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from src.data_cleaning.SDO import IndicatorRecord, indicator_from_dict

logger = logging.getLogger(__name__)


class IndicatorTransformer:
    """Converts TB data dictionary into IndicatorRecords.
    
    Reads the data dictionary CSV and deduplicates by variable_name.
    """

    def __init__(self, output_dir: str = "data/structured"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.issues = []

    def transform(self, df: pd.DataFrame) -> Iterable[IndicatorRecord]:
        """Convert dictionary rows into IndicatorRecords.
        
        Args:
            df: Data dictionary DataFrame (from TB_data_dictionary_*.csv)
            
        Yields:
            IndicatorRecord instances
        """
        # Normalize column names
        df.columns = [col.strip().lower() for col in df.columns]
        
        # Check for variable_name column
        if "variable_name" not in df.columns:
            logger.error("variable_name column not found in data dictionary")
            return
        
        seen = set()
        for _, row in df.iterrows():
            var_name = row.get("variable_name")
            if not var_name or var_name in seen:
                continue
            seen.add(var_name)
            
            try:
                rec = indicator_from_dict(row.to_dict())
                yield rec
            except Exception as e:
                self.issues.append({"error": str(e), "variable_name": var_name})
                logger.warning("Failed to create IndicatorRecord for %s: %s", var_name, e)

    def output_path(self) -> Path:
        """Return target output path."""
        return self.output_dir / "indicators.csv"

    def run(self, dict_path: str) -> dict:
        """Execute indicator extraction.
        
        Args:
            dict_path: Path to data dictionary CSV
            
        Returns:
            Summary dict
        """
        logger.info("Starting IndicatorTransformer")
        
        df = pd.read_csv(dict_path)
        records = list(self.transform(df))
        
        # Write output
        if records:
            data = [r.dict() for r in records]
            out_df = pd.DataFrame(data)
            self.output_path().parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(self.output_path(), index=False)
            logger.info("Wrote %d indicators to %s", len(records), self.output_path())
        
        return {
            "transformer": "IndicatorTransformer",
            "input_file": dict_path,
            "output_file": str(self.output_path()),
            "records_out": len(records),
            "issues": self.issues,
        }
