import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from src.data_cleaning.extract_raw import TBDataExtractor

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


NA_VALUES = ["", "NA", "N/A", "null", "NULL", " "]


def _to_bool_like(val) -> bool:
    if pd.isna(val):
        return False
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return False


def _numeric_cols(cols: List[str]) -> List[str]:
    patterns = ["_coh", "_cmplt", "_died", "_fail", "_def", "_cur", "_lost", "_succ", "_tsr", "_num", "_pct"]
    return [c for c in cols if any(c.endswith(p) or p in c for p in patterns)]


def _flag_cols(cols: List[str]) -> List[str]:
    return [c for c in cols if c.endswith("_flg") or c in {"rel_with_new_flg", "used_2021_defs_flg"}]


def clean_tb_outcomes(
    raw_path: str = "data/raw/tb_outcomes.csv",
    dict_path: str = "data/raw/TB_data_dictionary_2025-12-01.csv",
    out_dir: str = "data/cleaned",
) -> Dict[str, Any]:
    """Load raw tb outcomes, apply cleaning rules and save cleaned CSV and imputation log.

    Returns a dict with paths and summary.
    """
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    imputation_log: List[Dict[str, Any]] = []

    logger.info("Loading raw data from %s", raw_path)
    # Use TBDataExtractor to load the data
    df = None

    filename = os.path.basename(raw_path)
    loader = TBDataExtractor(filename)
    df = loader.load()

    df = df.replace(NA_VALUES, pd.NA)
    logger.info("Loaded raw data using TBDataExtractor")
    
    #strip whitespace from string columns
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    orig_rows = len(df)

    # Enforce critical identifier fields
    # Drop rows missing country or year
    missing_country = df["country"].isna()
    if missing_country.any():
        cnt = missing_country.sum()
        imputation_log.append({"action": "drop", "reason": "missing_country", "rows_affected": int(cnt)})
        df = df.loc[~missing_country].copy()

    missing_year = df["year"].isna()
    if missing_year.any():
        cnt = missing_year.sum()
        imputation_log.append({"action": "drop", "reason": "missing_year", "rows_affected": int(cnt)})
        df = df.loc[~missing_year].copy()

    # Lookup missing iso2/iso3/iso_numeric/g_whoregion by country
    # Use the most common mapping per country
    for col in ("iso2", "iso3", "iso_numeric", "g_whoregion"):
        df[col] = df[col].replace(NA_VALUES, pd.NA)

    mappings = {}
    for col in ("iso2", "iso3", "iso_numeric", "g_whoregion"):
        grp = df.dropna(subset=[col]).groupby("country")[col].agg(lambda s: s.mode().iat[0] if not s.mode().empty else None)
        mappings[col] = grp.to_dict()

    # Fill iso / region from mapping when missing
    for col in ("iso2", "iso3", "iso_numeric", "g_whoregion"):
        filled = 0
        for idx, val in df[col].items():
            if pd.isna(val):
                country = df.at[idx, "country"]
                candidate = mappings[col].get(country)
                if candidate is not None:
                    df.at[idx, col] = candidate
                    filled += 1
        if filled:
            imputation_log.append({"action": "fill", "column": col, "method": "from_country_mode", "rows_affected": int(filled)})

    #missing all iso identifiers
    iso_missing = df["iso3"].isna() & df["iso2"].isna() & df["iso_numeric"].isna()
    if iso_missing.any():
        cnt = iso_missing.sum()
        imputation_log.append({"action": "drop", "reason": "missing_all_iso_identifiers", "rows_affected": int(cnt)})
        df = df.loc[~iso_missing].copy()

    # report method: fill missing with 'not_reported'
    if "rep_meth" in df.columns:
        filled_rm = df["rep_meth"].isna().sum()
        df["rep_meth"] = df["rep_meth"].fillna("not_reported")
        if filled_rm:
            imputation_log.append({"action": "fill", "column": "rep_meth", "method": "fill_not_reported", "rows_affected": int(filled_rm)})

    # Convert flag columns to boolean
    flags = _flag_cols(list(df.columns))
    for f in flags:
        df[f] = df[f].apply(_to_bool_like).astype(bool)
        imputation_log.append({"action": "convert", "column": f, "method": "to_bool", "rows_affected": int(len(df))})

    # Ensure year and iso_numeric are numeric
    num_cols = _numeric_cols(list(df.columns))

    extras = ["year", "iso_numeric"]
    for c in extras:
        if c in df.columns and c not in num_cols:
            num_cols.append(c)

    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            imputation_log.append({"action": "convert", "column": c, "method": "to_numeric_coerce", "rows_affected": int(df[c].isna().sum())})

    # Fill missing cohort and component values based on available data
    core_prefixes = ["new_sp", "new_snep", "ret"]
    core_components = ["coh", "cur", "cmplt", "died", "fail", "def"]
    for pref in core_prefixes:
        coh_col = f"{pref}_coh"
        comp_cols = [f"{pref}_{s}" for s in core_components if f"{pref}_{s}" in df.columns]
        if coh_col in df.columns:
            df[f"missing_components_{pref}"] = df[comp_cols].isna().all(axis=1) if comp_cols else False
            # flag rows where cohort present but all components missing
            mask = df[coh_col].notna() & df[f"missing_components_{pref}"]
            if mask.any():
                imputation_log.append({"action": "flag", "note": f"cohort_present_components_missing_{pref}", "rows_affected": int(mask.sum())})

    # Sum component columns to fill missing cohort values
    for pref in core_prefixes:
        coh_col = f"{pref}_coh"
        comp_cols = [c for c in df.columns if c.startswith(f"{pref}_") and c not in {coh_col}]
        if coh_col in df.columns and comp_cols:
            inferred = df[comp_cols].sum(axis=1, skipna=True)
            mask = df[coh_col].isna() & inferred.notna()
            if mask.any():
                df.loc[mask, coh_col] = inferred[mask]
                df.loc[mask, f"inferred_{coh_col}"] = True
                imputation_log.append({"action": "infer", "column": coh_col, "method": "sum_components", "rows_affected": int(mask.sum())})

    # Compute treatment success rates where missing
    tsr_cols = [c for c in df.columns if c.endswith("_tsr")]
    for tsr in tsr_cols:
        # find corresponding success and cohort columns heuristically
        base = tsr.replace("c_", "") if tsr.startswith("c_") else tsr.replace("_tsr", "")
        # try patterns: base + '_cmplt' or base + '_succ'
        succ_col = None
        candidates = [f"{base}_cmplt", f"{base}_succ", f"{base}_suc", f"{base}_succeded"]
        for cand in candidates:
            if cand in df.columns:
                succ_col = cand
                break
        # cohort candidate
        cohort_col = None
        if f"{base}_coh" in df.columns:
            cohort_col = f"{base}_coh"
        elif "new_sp_coh" in df.columns:
            cohort_col = "new_sp_coh"

        if succ_col and cohort_col:
            mask_recompute = df[tsr].isna() & df[succ_col].notna() & df[cohort_col].notna() & (df[cohort_col] != 0)
            if mask_recompute.any():
                df.loc[mask_recompute, f"{tsr}_recomputed"] = df.loc[mask_recompute, succ_col] / df.loc[mask_recompute, cohort_col]
                imputation_log.append({"action": "recompute", "column": tsr, "method": "from_success_over_cohort", "rows_affected": int(mask_recompute.sum())})
            # flag rows where tsr exists but components missing
            mask_warn = df[tsr].notna() & (df[succ_col].isna() | df[cohort_col].isna())
            if mask_warn.any():
                imputation_log.append({"action": "warn", "note": f"tsr_present_but_components_missing_{tsr}", "rows_affected": int(mask_warn.sum())})

    # Compute data completeness score based on presence of key columns
    priority_cols = ["new_sp_coh", "new_sp_cmplt", "new_sp_died", "ret_coh", "ret_cmplt", "tbhiv_coh"]
    existing_priority = [c for c in priority_cols if c in df.columns]
    if existing_priority:
        df["data_completeness_score"] = df[existing_priority].notna().sum(axis=1) / len(existing_priority)
        imputation_log.append({"action": "compute", "column": "data_completeness_score", "rows_affected": int(len(df))})

    # Ensure year is integer
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    cleaned_path = outp / "tb_outcomes_cleaned.csv"
    df.to_csv(cleaned_path, index=False)
    logger.info("Wrote cleaned data to %s (rows: %d -> %d)", cleaned_path, orig_rows, len(df))

    log_path = outp / "imputation_log.csv"
    pd.DataFrame(imputation_log).to_csv(log_path, index=False)
    logger.info("Wrote imputation log to %s (entries: %d)", log_path, len(imputation_log))

    return {"cleaned_path": str(cleaned_path), "imputation_log": str(log_path), "rows_in": orig_rows, "rows_out": len(df)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean WHO TB outcomes raw CSVs")
    parser.add_argument("--raw", default="data/raw/tb_outcomes.csv")
    parser.add_argument("--dict", default="data/raw/TB_data_dictionary_2025-12-01.csv")
    parser.add_argument("--out", default="data/cleaned")
    args = parser.parse_args()
    res = clean_tb_outcomes(raw_path=args.raw, dict_path=args.dict, out_dir=args.out)
    logger.info("Done: %s", res)
