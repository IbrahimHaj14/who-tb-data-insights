import pytest
import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory
from src.transformers import (
    LocationTransformer,
    IndicatorTransformer,
    OutcomeFactTransformer,
)
from src.data_cleaning.SDO import LocationRecord, IndicatorRecord, OutcomeFactRecord


# Fixtures
@pytest.fixture
def temp_dir():
    """Create temporary directory for transformer outputs."""
    with TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_cleaned_df():
    """Sample cleaned outcomes DataFrame."""
    return pd.DataFrame([
        {
            "country": "Argentina",
            "iso2": "AR",
            "iso3": "ARG",
            "iso_numeric": 32,
            "g_whoregion": "AMR",
            "year": 2020,
            "rep_meth": "est",
            "new_sp_coh": 100,
            "new_sp_cmplt": 80,
            "new_sp_died": 5,
            "rel_with_new_flg": True,
            "used_2021_defs_flg": False,
            "inferred_new_sp_coh": False,
            "data_completeness_score": 0.95,
        },
        {
            "country": "Brazil",
            "iso2": "BR",
            "iso3": "BRA",
            "iso_numeric": 76,
            "g_whoregion": "AMR",
            "year": 2020,
            "rep_meth": "obs",
            "new_sp_coh": 200,
            "new_sp_cmplt": 150,
            "new_sp_died": 10,
            "rel_with_new_flg": False,
            "used_2021_defs_flg": True,
            "inferred_new_sp_coh": False,
            "data_completeness_score": 1.0,
        },
        {
            "country": "Argentina",
            "iso2": "AR",
            "iso3": "ARG",
            "iso_numeric": 32,
            "g_whoregion": "AMR",
            "year": 2021,
            "rep_meth": "est",
            "new_sp_coh": 110,
            "new_sp_cmplt": 90,
            "new_sp_died": 3,
            "rel_with_new_flg": True,
            "used_2021_defs_flg": True,
            "inferred_new_sp_coh": False,
            "data_completeness_score": 0.98,
        },
    ])


@pytest.fixture
def sample_dictionary_df():
    """Sample data dictionary DataFrame."""
    return pd.DataFrame([
        {
            "variable_name": "new_sp_coh",
            "dataset": "Outcomes",
            "definition": "New smear-positive cohort",
            "code_list": None,
        },
        {
            "variable_name": "new_sp_cmplt",
            "dataset": "Outcomes",
            "definition": "New smear-positive completed",
            "code_list": None,
        },
        {
            "variable_name": "new_sp_died",
            "dataset": "Outcomes",
            "definition": "New smear-positive died",
            "code_list": None,
        },
        {
            "variable_name": "budget_tot",
            "dataset": "Budget",
            "definition": "Total budget",
            "code_list": "0=No; 1=Yes",
        },
    ])


# LocationTransformer Tests
class TestLocationTransformer:
    def test_transform_deduplicates_locations(self, sample_cleaned_df, temp_dir):
        transformer = LocationTransformer(output_dir=temp_dir)
        records = list(transformer.transform(sample_cleaned_df))
        
        # Unique constraint countries (Argentina, Brazil)
        assert len(records) == 2
        assert all(isinstance(r, LocationRecord) for r in records)
        
        countries = [r.country for r in records]
        assert "Argentina" in countries
        assert "Brazil" in countries

    def test_transform_extracts_location_fields(self, sample_cleaned_df, temp_dir):
        transformer = LocationTransformer(output_dir=temp_dir)
        records = list(transformer.transform(sample_cleaned_df))
        
        arg_record = [r for r in records if r.country == "Argentina"][0]
        assert arg_record.iso2 == "AR"
        assert arg_record.iso3 == "ARG"
        assert arg_record.iso_numeric == 32
        assert arg_record.who_region == "AMR"

    def test_run_writes_csv(self, sample_cleaned_df, temp_dir):
        transformer = LocationTransformer(output_dir=temp_dir)
        
        # Write sample to temp file
        input_path = Path(temp_dir) / "input.csv"
        sample_cleaned_df.to_csv(input_path, index=False)
        
        result = transformer.run(str(input_path))
        
        assert result["records_out"] == 2
        assert Path(transformer.output_path()).exists()
        
        # Verify CSV content
        output_df = pd.read_csv(transformer.output_path())
        assert len(output_df) == 2
        assert "country" in output_df.columns
        assert "iso3" in output_df.columns

    def test_transform_handles_missing_country(self, temp_dir):
        # Test with country column present but empty value
        df = pd.DataFrame([{"country": None, "iso3": "ARG", "year": 2020}])
        transformer = LocationTransformer(output_dir=temp_dir)
        records = list(transformer.transform(df))
        
        # Should log error and skip row with validation error
        assert len(records) == 0
        assert len(transformer.issues) > 0


# IndicatorTransformer Tests
class TestIndicatorTransformer:
    def test_transform_processes_indicators(self, sample_dictionary_df, temp_dir):
        transformer = IndicatorTransformer(output_dir=temp_dir)
        records = list(transformer.transform(sample_dictionary_df))
        
        assert len(records) == 4
        assert all(isinstance(r, IndicatorRecord) for r in records)
        
        var_names = [r.variable_name for r in records]
        assert "new_sp_coh" in var_names
        assert "budget_tot" in var_names

    def test_transform_extracts_indicator_fields(self, sample_dictionary_df, temp_dir):
        transformer = IndicatorTransformer(output_dir=temp_dir)
        records = list(transformer.transform(sample_dictionary_df))
        
        coh_record = [r for r in records if r.variable_name == "new_sp_coh"][0]
        assert coh_record.dataset_group == "Outcomes"
        assert "cohort" in coh_record.definition.lower()

    def test_transform_deduplicates_by_variable_name(self, temp_dir):
        df = pd.DataFrame([
            {"variable_name": "new_sp_coh", "dataset": "Outcomes", "definition": "First"},
            {"variable_name": "new_sp_coh", "dataset": "Outcomes", "definition": "Duplicate"},
            {"variable_name": "ret_coh", "dataset": "Outcomes", "definition": "Second"},
        ])
        
        transformer = IndicatorTransformer(output_dir=temp_dir)
        records = list(transformer.transform(df))
        
        # Unique constraint variable_name
        assert len(records) == 2
        var_names = [r.variable_name for r in records]
        assert var_names.count("new_sp_coh") == 1

    def test_run_writes_csv(self, sample_dictionary_df, temp_dir):
        transformer = IndicatorTransformer(output_dir=temp_dir)
        
        input_path = Path(temp_dir) / "dict.csv"
        sample_dictionary_df.to_csv(input_path, index=False)
        
        result = transformer.run(str(input_path))
        
        assert result["records_out"] == 4
        assert Path(transformer.output_path()).exists()
        
        output_df = pd.read_csv(transformer.output_path())
        assert len(output_df) == 4
        assert "variable_name" in output_df.columns


# OutcomeFactTransformer Tests
class TestOutcomeFactTransformer:
    def test_transform_melts_to_long_format(self, sample_cleaned_df, temp_dir):
        # Build simple maps
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # 9 records: 3 rows * 3 indicators
        assert len(records) == 9
        assert all(isinstance(r, OutcomeFactRecord) for r in records)

    def test_transform_excludes_flags_and_computed_cols(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # Verify no flag columns in source_col
        source_cols = [r.source_col for r in records]
        assert "rel_with_new_flg" not in source_cols
        assert "used_2021_defs_flg" not in source_cols
        assert "inferred_new_sp_coh" not in source_cols
        assert "data_completeness_score" not in source_cols

    def test_transform_maps_foreign_keys(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 10, "BRA": 20}
        indicator_map = {"new_sp_coh": 100, "new_sp_cmplt": 101, "new_sp_died": 102}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # Check Argentina records
        arg_records = [r for r in records if r.location_id == 10]
        assert len(arg_records) == 6  
        
        # Check indicator mapping
        coh_records = [r for r in records if r.indicator_id == 100]
        assert len(coh_records) == 3  

    def test_transform_preserves_values(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # Find Argentina 2020 new_sp_coh record
        target = [r for r in records 
                  if r.location_id == 0 and r.year == 2020 and r.indicator_id == 0][0]
        
        assert target.value == 100.0
        assert target.rep_meth == "est"
        assert target.source_col == "new_sp_coh"

    def test_transform_filters_na_values(self, temp_dir):
        df = pd.DataFrame([
            {
                "country": "Test",
                "iso3": "TST",
                "year": 2020,
                "rep_meth": "obs",
                "new_sp_coh": None,  
                "new_sp_cmplt": 50,
            }
        ])
        
        location_map = {"TST": 0}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(df))
        
        # Should only have 1 record (new_sp_cmplt), not 2
        assert len(records) == 1
        assert records[0].indicator_id == 1  

    def test_transform_handles_missing_location_mapping(self, sample_cleaned_df, temp_dir):
        location_map = {"BRA": 1}  
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # Brazil records only
        assert all(r.location_id == 1 for r in records)
        assert len(transformer.issues) > 0  

    def test_transform_handles_missing_indicator_mapping(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0}  # Missing other indicators
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        records = list(transformer.transform(sample_cleaned_df))
        
        # Should only have new_sp_coh records
        assert all(r.indicator_id == 0 for r in records)
        assert len(records) == 3  # 3 rows
        assert len(transformer.unmapped_indicators) > 0

    def test_run_writes_csv(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        input_path = Path(temp_dir) / "cleaned.csv"
        sample_cleaned_df.to_csv(input_path, index=False)
        
        result = transformer.run(str(input_path))
        
        assert result["records_out"] == 9
        assert Path(transformer.output_path()).exists()
        
        output_df = pd.read_csv(transformer.output_path())
        assert len(output_df) == 9
        assert "location_id" in output_df.columns
        assert "indicator_id" in output_df.columns
        assert "value" in output_df.columns

    def test_run_validates_nonzero_values(self, sample_cleaned_df, temp_dir):
        location_map = {"ARG": 0, "BRA": 1}
        indicator_map = {"new_sp_coh": 0, "new_sp_cmplt": 1, "new_sp_died": 2}
        
        transformer = OutcomeFactTransformer(
            output_dir=temp_dir,
            location_map=location_map,
            indicator_map=indicator_map,
        )
        
        input_path = Path(temp_dir) / "cleaned.csv"
        sample_cleaned_df.to_csv(input_path, index=False)
        
        result = transformer.run(str(input_path))
        
        # Should have non-zero values (from sample data)
        output_df = pd.read_csv(transformer.output_path())
        nonzero_count = (output_df["value"] != 0).sum()
        assert nonzero_count > 0
