"""Transformer for melting cleaned outcomes data into OutcomeFactRecords."""

import logging
from pathlib import Path
from typing import Iterable, Dict, Optional, List

import pandas as pd

from src.data_cleaning.SDO import OutcomeFactRecord, outcomefact_from_values

logger = logging.getLogger(__name__)


class OutcomeFactTransformer:
    """Melts wide cleaned TB outcomes into long-form OutcomeFactRecords.
    
    Steps:
    1. Load cleaned outcomes CSV
    2. Melt from wide to long format
    3. Map column names to indicator_id (via mapping file)
    4. Resolve location_id from location data (via iso3 lookup)
    5. Create OutcomeFactRecord for each fact
    """

    def __init__(
        self,
        output_dir: str = "data/structured",
        location_map: Optional[Dict[str, int]] = None,
        indicator_map: Optional[Dict[str, int]] = None,
    ):
        """Initialize OutcomeFactTransformer.
        
        Args:
            output_dir: Output directory for structured data
            location_map: Dict mapping iso3 -> location_id (if available)
            indicator_map: Dict mapping variable_name -> indicator_id (if available)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.location_map = location_map or {}
        self.indicator_map = indicator_map or {}
        self.issues = []
        self.unmapped_indicators = set()

    def set_location_map(self, location_map: Dict[str, int]):
        """Set or update location mapping.
        
        Args:
            location_map: Dict mapping iso3 -> location_id
        """
        self.location_map = location_map
        logger.info("Set location_map with %d entries", len(location_map))

    def set_indicator_map(self, indicator_map: Dict[str, int]):
        """Set or update indicator mapping.
        
        Args:
            indicator_map: Dict mapping variable_name -> indicator_id
        """
        self.indicator_map = indicator_map
        logger.info("Set indicator_map with %d entries", len(indicator_map))

    def transform(self, df: pd.DataFrame) -> Iterable[OutcomeFactRecord]:
        """Melt and transform cleaned outcomes into facts.
        
        Args:
            df: Cleaned outcomes DataFrame
            
        Yields:
            OutcomeFactRecord instances
        """
        if df.empty:
            logger.warning("Input DataFrame is empty")
            return

        # Identify identifier columns
        id_cols = ["country", "iso2", "iso3", "iso_numeric", "g_whoregion", "year", "rep_meth"]
        id_cols = [c for c in id_cols if c in df.columns]
        
        # Identify flag columns to EXCLUDE from melting (keep as metadata)
        flag_cols = [c for c in df.columns if c.endswith("_flg") or "flag" in c.lower()]
        
        # Identify computed/inferred columns to exclude
        computed_cols = [c for c in df.columns if c.startswith("inferred_") or c.startswith("missing_") 
                        or c.endswith("_recomputed") or c == "data_completeness_score"]
        
        # Exclude columns: IDs, flags, computed fields
        exclude_cols = set(id_cols + flag_cols + computed_cols)
        
        # Value columns = all numeric outcome columns (cohorts, counts, rates, TSRs)
        value_cols = [c for c in df.columns if c not in exclude_cols]
        
        # Further filter to only numeric-like columns (indicators from data dictionary)
        numeric_patterns = ["_coh", "_cmplt", "_died", "_fail", "_def", "_cur", "_lost", "_succ", "_tsr"]
        value_cols = [c for c in value_cols if any(p in c for p in numeric_patterns)]
        
        if not value_cols:
            logger.warning("No numeric value columns found to melt")
            logger.warning("Available columns: %s", list(df.columns))
            return
        
        logger.info("Melting %d value columns, excluding %d flags/computed cols", len(value_cols), len(exclude_cols))

        # Melt wide to long
        melted = df.melt(
            id_vars=id_cols,
            value_vars=value_cols,
            var_name="variable_name",
            value_name="value",
        )
        
        # Drop rows where value is NA (missing = no data)
        melted = melted[melted["value"].notna()].copy()
        
        # Convert value to numeric, coercing errors
        melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
        melted = melted[melted["value"].notna()].copy()
        
        logger.info("After filtering NAs: %d fact records", len(melted))
        
        # Resolve location_id from iso3
        melted["location_id"] = melted["iso3"].map(self.location_map)
        missing_locs = melted[melted["location_id"].isna()]
        if not missing_locs.empty:
            for _, row in missing_locs.iterrows():
                self.issues.append({
                    "type": "missing_location_id",
                    "iso3": row.get("iso3"),
                    "country": row.get("country"),
                })
        
        melted = melted[melted["location_id"].notna()].copy()
        melted["location_id"] = melted["location_id"].astype(int)
        
        # Resolve indicator_id from variable_name
        melted["indicator_id"] = melted["variable_name"].map(self.indicator_map)
        missing_inds = melted[melted["indicator_id"].isna()]
        if not missing_inds.empty:
            for _, row in missing_inds.iterrows():
                var = row.get("variable_name")
                self.unmapped_indicators.add(var)
                self.issues.append({
                    "type": "missing_indicator_id",
                    "variable_name": var,
                })
        
        melted = melted[melted["indicator_id"].notna()].copy()
        melted["indicator_id"] = melted["indicator_id"].astype(int)
        
        # Create OutcomeFactRecords
        for _, row in melted.iterrows():
            try:
                flags = {}
                # Preserve flags from original cleaning
                if "flags" in row and pd.notna(row["flags"]):
                    flags = eval(row["flags"]) if isinstance(row["flags"], str) else row["flags"]
                
                fact = outcomefact_from_values(
                    location_id=int(row["location_id"]),
                    indicator_id=int(row["indicator_id"]),
                    year=int(row["year"]),
                    value=float(row["value"]) if pd.notna(row["value"]) else None,
                    rep_meth=row.get("rep_meth"),
                    source_file="tb_outcomes.csv",
                    source_col=row.get("variable_name"),
                    flags=flags if flags else None,
                )
                yield fact
            except Exception as e:
                self.issues.append({"type": "fact_creation_error", "error": str(e), "row": row.to_dict()})
                logger.warning("Failed to create fact: %s", e)

    def output_path(self) -> Path:
        """Return target output path."""
        return self.output_dir / "outcome_facts.csv"

    def run(self, input_path: str) -> dict:
        """Execute outcome fact transformation.
        
        Args:
            input_path: Path to cleaned CSV
            
        Returns:
            Summary dict
        """
        logger.info("Starting OutcomeFactTransformer")
        
        if not self.location_map:
            logger.warning("location_map is empty; run set_location_map() first")
        if not self.indicator_map:
            logger.warning("indicator_map is empty; run set_indicator_map() first")
        
        df = pd.read_csv(input_path)
        df.columns = [col.strip().lower() for col in df.columns]
        
        records = list(self.transform(df))
        
        # Write output
        if records:
            data = [r.dict() for r in records]
            out_df = pd.DataFrame(data)
            self.output_path().parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(self.output_path(), index=False)
            logger.info("Wrote %d outcome facts to %s", len(records), self.output_path())
        
        summary = {
            "transformer": "OutcomeFactTransformer",
            "input_file": input_path,
            "output_file": str(self.output_path()),
            "records_out": len(records),
            "unmapped_indicators": list(self.unmapped_indicators)[:10],
            "issues_count": len(self.issues),
            "issues": self.issues[:10],
        }
        
        # Validation warnings
        if records:
            values = [r.value for r in records if r.value is not None]
            if values:
                non_zero = sum(1 for v in values if v != 0)
                logger.info("Non-zero values: %d / %d (%.1f%%)", non_zero, len(values), non_zero/len(values)*100)
                if non_zero == 0:
                    logger.warning("⚠️  All values are zero - possible data issue!")
        
        return summary
