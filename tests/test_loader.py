import os
import pytest
import pandas as pd
from tempfile import NamedTemporaryFile
from src.data_cleaning.extract_raw import TBDataExtractor


# Fixture: create a temporary CSV
@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing."""
    columns = ["country", "iso2", "iso3", "iso_numeric", "g_whoregion", "year", "rep_meth",
               "new_sp_coh", "new_sp_cur"]
    # sample data
    df = pd.DataFrame([
        ["Argentina", "AR", "ARG", 32, "AMR", 2020, "est", 100, 50],
        ["Brazil", "BR", "BRA", 76, "AMR", 2020, "obs", 200, 150],
    ], columns=columns)

    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        temp_path = f.name

    yield temp_path

    os.remove(temp_path)


#file not found test
def test_load_missing_file():
    loader = TBDataExtractor("nonexistent.csv")
    with pytest.raises(FileNotFoundError):
        loader.load()


# Test normal loading
def test_load_valid_file(temp_csv_file):
    class TestLoader(TBDataExtractor):
        EXPECTED_COLUMNS = ["country", "iso2", "iso3", "iso_numeric", "g_whoregion", "year", "rep_meth", "new_sp_coh", "new_sp_cur"]


    loader = TestLoader(os.path.basename(temp_csv_file))
    #Temp file
    loader.filepath = temp_csv_file
    df = loader.load()

    assert isinstance(df, pd.DataFrame)
    assert "country" in df.columns
    # test column names are normalized
    assert all(col == col.lower() for col in df.columns)
    # row count correct
    assert len(df) == 2


# Test validation of missing columns
def test_missing_columns():
    # Create CSV with missing columns
    columns = ["country", "iso2", "year"]  # missing many expected columns
    df = pd.DataFrame([["X", "XX", 2020]], columns=columns)

    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        temp_path = f.name

    loader = TBDataExtractor(os.path.basename(temp_path))
    loader.filepath = temp_path

   # test missing columns detected
    with pytest.raises(ValueError) as record:  
        loader._validate_columns(df)

    os.remove(temp_path)



