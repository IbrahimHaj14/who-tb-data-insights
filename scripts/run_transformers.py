#!/usr/bin/env python3
"""Orchestrate transformer pipeline: locations -> indicators -> outcome facts.

This script:
1. Transforms locations from cleaned outcomes CSV
2. Transforms indicators from TB data dictionary
3. Transforms outcome facts, resolving FKs to location/indicator IDs
"""

import logging
import sys
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transformers import (
    LocationTransformer,
    IndicatorTransformer,
    OutcomeFactTransformer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_location_map(locations_csv: str) -> Dict[str, int]:
    """Build mapping from iso3 -> location_id by reading locations CSV.
    
    For now, uses row index as location_id. In production, would query database.
    
    Args:
        locations_csv: Path to locations output CSV
        
    Returns:
        Dict mapping iso3 -> location_id
    """
    import pandas as pd
    
    if not Path(locations_csv).exists():
        logger.warning("Locations CSV not found: %s", locations_csv)
        return {}
    
    df = pd.read_csv(locations_csv)
    # Use row index as location_id (surrogate key, 0-based matching CSV row numbers)
    location_map = dict(zip(df["iso3"], df.index))
    logger.info("Built location_map with %d entries", len(location_map))
    return location_map


def build_indicator_map(indicators_csv: str) -> Dict[str, int]:
    """Build mapping from variable_name -> indicator_id by reading indicators CSV.
    
    For now, uses row index as indicator_id. In production, would query database.
    
    Args:
        indicators_csv: Path to indicators output CSV
        
    Returns:
        Dict mapping variable_name -> indicator_id
    """
    import pandas as pd
    
    if not Path(indicators_csv).exists():
        logger.warning("Indicators CSV not found: %s", indicators_csv)
        return {}
    
    df = pd.read_csv(indicators_csv)
    # Use row index as indicator_id (surrogate key, 0-based matching CSV row numbers)
    indicator_map = dict(zip(df["variable_name"], df.index))
    logger.info("Built indicator_map with %d entries", len(indicator_map))
    return indicator_map


def run_pipeline(
    cleaned_csv: str,
    dict_csv: str,
    output_dir: str = "data/structured",
) -> Dict:
    """Run full transformation pipeline.
    
    Args:
        cleaned_csv: Path to cleaned outcomes CSV (from data_cleaning/clean_tb_data.py)
        dict_csv: Path to TB data dictionary CSV
        output_dir: Output directory for structured CSVs
        
    Returns:
        Summary dict with results from all transformers
    """
    logger.info("Starting transformer pipeline")
    logger.info("  cleaned_csv: %s", cleaned_csv)
    logger.info("  dict_csv: %s", dict_csv)
    logger.info("  output_dir: %s", output_dir)
    
    results = {}
    
    # Step 1: Transform locations
    logger.info("\n=== Step 1: LocationTransformer ===")
    loc_transformer = LocationTransformer(output_dir=output_dir)
    loc_result = loc_transformer.run(cleaned_csv)
    results["locations"] = loc_result
    logger.info("Locations: %d records written", loc_result.get("records_out", 0))
    
    # Step 2: Transform indicators
    logger.info("\n=== Step 2: IndicatorTransformer ===")
    ind_transformer = IndicatorTransformer(output_dir=output_dir)
    ind_result = ind_transformer.run(dict_csv)
    results["indicators"] = ind_result
    logger.info("Indicators: %d records written", ind_result.get("records_out", 0))
    
    # Step 3: Build FK maps from steps 1-2
    logger.info("\n=== Step 3: Building Foreign Key Maps ===")
    location_map = build_location_map(loc_transformer.output_path())
    indicator_map = build_indicator_map(ind_transformer.output_path())
    
    if not location_map:
        logger.error("Failed to build location_map; outcome facts cannot be created")
        results["facts"] = {"error": "missing location_map"}
        return results
    
    if not indicator_map:
        logger.error("Failed to build indicator_map; outcome facts cannot be created")
        results["facts"] = {"error": "missing indicator_map"}
        return results
    
    # Step 4: Transform outcome facts with FK resolution
    logger.info("\n=== Step 4: OutcomeFactTransformer ===")
    fact_transformer = OutcomeFactTransformer(
        output_dir=output_dir,
        location_map=location_map,
        indicator_map=indicator_map,
    )
    fact_result = fact_transformer.run(cleaned_csv)
    results["facts"] = fact_result
    logger.info("Outcome Facts: %d records written", fact_result.get("records_out", 0))
    
    # Summary
    logger.info("\n=== Pipeline Summary ===")
    logger.info("Locations: %d", results["locations"].get("records_out", 0))
    logger.info("Indicators: %d", results["indicators"].get("records_out", 0))
    logger.info("Outcome Facts: %d", results["facts"].get("records_out", 0))
    
    if results["locations"].get("issues"):
        logger.warning("Location issues (%d):", len(results["locations"]["issues"]))
        for issue in results["locations"]["issues"][:3]:
            logger.warning("  - %s", issue)
    
    if results["indicators"].get("issues"):
        logger.warning("Indicator issues (%d):", len(results["indicators"]["issues"]))
        for issue in results["indicators"]["issues"][:3]:
            logger.warning("  - %s", issue)
    
    if results["facts"].get("issues"):
        logger.warning("Outcome Fact issues (%d):", len(results["facts"]["issues"]))
        for issue in results["facts"]["issues"][:3]:
            logger.warning("  - %s", issue)
    
    if results["facts"].get("unmapped_indicators"):
        logger.warning("Unmapped indicators (%d):", len(results["facts"]["unmapped_indicators"]))
        for ind in results["facts"]["unmapped_indicators"][:5]:
            logger.warning("  - %s", ind)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run transformer pipeline: locations -> indicators -> outcome facts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults
  python scripts/run_transformers.py
  
  # Run with custom paths
  python scripts/run_transformers.py \\
    --cleaned data/cleaned/tb_outcomes_cleaned.csv \\
    --dict data/raw/TB_data_dictionary_2025-12-01.csv \\
    --output data/structured
        """,
    )
    parser.add_argument(
        "--cleaned",
        default="data/cleaned/tb_outcomes_cleaned.csv",
        help="Path to cleaned outcomes CSV (default: data/cleaned/tb_outcomes_cleaned.csv)",
    )
    parser.add_argument(
        "--dict",
        default="data/raw/TB_data_dictionary_2025-12-01.csv",
        help="Path to TB data dictionary CSV (default: data/raw/TB_data_dictionary_2025-12-01.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/structured",
        help="Output directory for structured CSVs (default: data/structured)",
    )
    
    args = parser.parse_args()
    
    # Validate input files
    if not Path(args.cleaned).exists():
        logger.error("Cleaned CSV not found: %s", args.cleaned)
        sys.exit(1)
    
    if not Path(args.dict).exists():
        logger.error("Data dictionary CSV not found: %s", args.dict)
        sys.exit(1)
    
    try:
        results = run_pipeline(
            cleaned_csv=args.cleaned,
            dict_csv=args.dict,
            output_dir=args.output,
        )
        logger.info("Pipeline completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)
