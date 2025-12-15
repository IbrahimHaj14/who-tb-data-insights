# import os
# import pytest
# import pandas as pd
# from tempfile import NamedTemporaryFile, TemporaryDirectory
# from src.data_cleaning.data_cleaner import clean_tb_outcomes  

# # Fixture: createraw CSV for testing
# @pytest.fixture
# def minimal_raw_csv():
#     columns = [
#         "country", "iso2", "iso3", "iso_numeric", "g_whoregion", "year", "rep_meth",
#         "new_sp_coh", "new_sp_cmplt", "new_sp_died", "ret_coh", "tbhiv_coh",
#         "rel_with_new_flg", "used_2021_defs_flg"
#     ]
#     df = pd.DataFrame([
#         ["Aland", None, None, None, None, 2020, None, 10, 5, 0, 20, 15, "1", "0"],
#         # [None, "BR", "BRA", 76, "AMR", 2020, "obs", 200, 150, 0, 50, 25, "0", "1"],
#         ["Canada", "CA", "CAN", 124, "AMR", None, "est", 100, 50, 0, 30, 20, "1", "1"]
#     ], columns=columns)

#     with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
#         df.to_csv(f.name, index=False)
#         temp_path = f.name

#     yield temp_path

#     os.remove(temp_path)


# # Test clean_tb_outcomes function
# def test_clean_tb_outcomes(minimal_raw_csv):
#     with TemporaryDirectory() as tmpdir:
#         result = clean_tb_outcomes(raw_path=minimal_raw_csv, out_dir=tmpdir)

#         # Check returned dict has keys
#         assert "cleaned_path" in result
#         assert "imputation_log" in result
#         assert "rows_in" in result
#         assert "rows_out" in result

#         # Check cleaned CSV exists
#         cleaned_path = result["cleaned_path"]
#         assert os.path.exists(cleaned_path)
#         df_clean = pd.read_csv(cleaned_path)

#         # Row with missing country or year should be dropped
#         assert len(df_clean) == 1
#         assert df_clean["country"].iloc[0] == "Aland"

#         # rep_meth should be filled with 'not_reported'
#         assert df_clean["rep_meth"].iloc[0] == "not_reported"

#         # Flag columns converted to boolean
#         for f in ["rel_with_new_flg", "used_2021_defs_flg"]:
#             assert df_clean[f].dtype == bool

#         # Numeric columns are numeric
#         for col in ["new_sp_coh", "new_sp_cmplt", "new_sp_died", "ret_coh", "tbhiv_coh", "iso_numeric", "year"]:
#             assert pd.api.types.is_numeric_dtype(df_clean[col])


# # Test imputation log
# def test_imputation_log_entries(minimal_raw_csv):
#     with TemporaryDirectory() as tmpdir:
#         result = clean_tb_outcomes(raw_path=minimal_raw_csv, out_dir=tmpdir)

#         log_path = result["imputation_log"]
#         assert os.path.exists(log_path)

#         log_df = pd.read_csv(log_path)
#         # Should contain at least one 'drop' and one 'fill'
#         actions = log_df["action"].tolist()
#         assert "drop" in actions or "fill" in actions
