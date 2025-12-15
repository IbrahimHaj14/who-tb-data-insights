import pytest
from datetime import datetime
from src.data_cleaning.SDO import (
    LocationRecord,
    IndicatorRecord,
    OutcomeFactRecord,
    location_from_row,
    indicator_from_dict,
    outcomefact_from_values,
)

# LocationRecord tests
def test_location_record_valid():
    loc = LocationRecord(country="Argentina", iso2="AR", iso3="ARG", iso_numeric=32, who_region="AMR")
    assert loc.country == "Argentina"
    assert loc.iso2 == "AR"
    assert loc.iso3 == "ARG"
    assert loc.iso_numeric == 32
    assert loc.who_region == "AMR"

#blank country should raise error
def test_location_record_country_required():
    with pytest.raises(ValueError):
        LocationRecord(country="")  


def test_location_from_row():
    row = {"country": "Brazil", "iso2": "BR", "iso_numeric": "76", "g_whoregion": "AMR"}
    loc = location_from_row(row)
    assert isinstance(loc, LocationRecord)
    assert loc.iso_numeric == 76
    assert loc.who_region == "AMR"


# IndicatorRecord tests
def test_indicator_record():
    ind = IndicatorRecord(variable_name="new_sp_coh", dataset_group="TB", definition="New sputum positive cases", code_list=None)
    assert ind.variable_name == "new_sp_coh"
    assert ind.dataset_group == "TB"

#blank variable_name should raise error
def test_indicator_record_variable_required():
    with pytest.raises(ValueError):
        IndicatorRecord(variable_name="  ")  

#test indicator_from_dict function
def test_indicator_from_dict():
    d = {"variable_name": "new_sp_cmplt", "dataset": "TB", "definition": "Completed treatment"}
    ind = indicator_from_dict(d)
    assert isinstance(ind, IndicatorRecord)
    assert ind.variable_name == "new_sp_cmplt"

# OutcomeFactRecord tests
def test_outcomefact_record():
    fact = OutcomeFactRecord(location_id=1, indicator_id=2, year=2020, value=100.0, rep_meth="est")
    assert fact.location_id == 1
    assert fact.value == 100.0
    assert fact.rep_meth == "est"
    assert isinstance(fact.ingested_at, datetime)


def test_outcomefact_record_year_validation():
    # lower and upper bounds for year
    with pytest.raises(ValueError):
        OutcomeFactRecord(location_id=1, indicator_id=2, year=1800, value=10)  

    with pytest.raises(ValueError):
        OutcomeFactRecord(location_id=1, indicator_id=2, year=2200, value=10)  

#test value validation
def test_outcomefact_record_value_validation():
    with pytest.raises(ValueError):
        OutcomeFactRecord(location_id=1, indicator_id=2, year=2020, value=-5)  # negative value not allowed

    fact = OutcomeFactRecord(location_id=1, indicator_id=2, year=2020, value=None)
    assert fact.value is None

#test outcomefact_from_values function
def test_outcomefact_from_values():
    flags = {"estimate": True}
    fact = outcomefact_from_values(location_id=10, indicator_id=20, year=2021, value=50, rep_meth="obs", flags=flags, source_file="file.csv", source_col="col1")
    assert fact.flags == flags
    assert fact.source_file == "file.csv"
    assert fact.source_col == "col1"
    assert fact.location_id == 10
