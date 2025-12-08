import os
import pandas as pd
from pandas._libs import missing

RAW_DATA_DIR = "data/raw"

class TBDataLoader:
    """
    Handles loading raw WHO TB Outcomes CSV files.
    - Verifies file existence
    - Loads using pandas
    - Validates expected columns
    """

    EXPECTED_COLUMNS = [
        "country", "iso2", "iso3", "iso_numeric", "g_whoregion", "year", "rep_meth",
        "new_sp_coh", "new_sp_cur", "new_sp_cmplt", "new_sp_died", "new_sp_fail", "new_sp_def",
        "c_new_sp_tsr", "new_snep_coh", "new_snep_cmplt", "new_snep_died", "new_snep_fail",
        "new_snep_def", "c_new_snep_tsr", "ret_coh", "ret_cur", "ret_cmplt", "ret_died",
        "ret_fail", "ret_def", "hiv_new_sp_coh", "hiv_new_sp_cur", "hiv_new_sp_cmplt",
        "hiv_new_sp_died", "hiv_new_sp_fail", "hiv_new_sp_def", "hiv_new_snep_coh",
        "hiv_new_snep_cmplt", "hiv_new_snep_died", "hiv_new_snep_fail", "hiv_new_snep_def",
        "hiv_ret_coh", "hiv_ret_cur", "hiv_ret_cmplt", "hiv_ret_died", "hiv_ret_fail",
        "hiv_ret_def", "rel_with_new_flg", "used_2021_defs_flg", "newrel_coh", "newrel_succ",
        "newrel_fail", "newrel_died", "newrel_lost", "c_new_tsr", "ret_nrel_coh",
        "ret_nrel_succ", "ret_nrel_fail", "ret_nrel_died", "ret_nrel_lost", "c_ret_tsr",
        "tbhiv_coh", "tbhiv_succ", "tbhiv_fail", "tbhiv_died", "tbhiv_lost", "c_tbhiv_tsr",
        "mdr_coh", "mdr_succ", "mdr_fail", "mdr_died", "mdr_lost", "xdr_coh", "xdr_succ",
        "xdr_fail", "xdr_died", "xdr_lost"
    ]

    def __init__(self, filename: str):
        self.filepath = os.path.join(RAW_DATA_DIR, filename)
    #load method
    def load(self) -> pd.DataFrame:
        """Load a raw CSV file into a pandas DataFrame."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"CSV file not found: {self.filepath}")

        df = pd.read_csv(self.filepath)

        #strip whitespace and lowercase column names
        df.columns = [col.strip().lower() for col in df.columns]

        # Validate
        self._validate_columns(df)

        return df

    #validation method
    def _validate_columns(self, df: pd.DataFrame):
        """Ensure the file contains all expected columns."""
        df_cols = set(df.columns)
        expected_cols = set(col.lower() for col in self.EXPECTED_COLUMNS)

        missing = expected_cols - df_cols
        extra = df_cols - expected_cols

        if missing:
            raise ValueError(f"Missing expected columns: {missing}")

        if extra:
            print("INFO: Extra columns detected:", extra)