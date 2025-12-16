import pytest
import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from src.database.models_base import Base
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact
from src.insertion.insert_structured import (
    upsert_locations,
    upsert_indicators,
    insert_outcome_facts,
    read_csv,
)


@pytest.fixture
def temp_db():
    """Create temporary in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    
    yield SessionLocal
    
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sample_locations_df():
    """Sample locations DataFrame."""
    return pd.DataFrame([
        {"country": "Argentina", "iso2": "AR", "iso3": "ARG", "iso_numeric": 32, "who_region": "AMR"},
        {"country": "Brazil", "iso2": "BR", "iso3": "BRA", "iso_numeric": 76, "who_region": "AMR"},
        {"country": "Canada", "iso2": "CA", "iso3": "CAN", "iso_numeric": 124, "who_region": "AMR"},
    ])


@pytest.fixture
def sample_indicators_df():
    """Sample indicators DataFrame."""
    return pd.DataFrame([
        {"variable_name": "new_sp_coh", "dataset_group": "Outcomes", "definition": "New SP cohort", "code_list": None},
        {"variable_name": "new_sp_cmplt", "dataset_group": "Outcomes", "definition": "New SP completed", "code_list": None},
        {"variable_name": "ret_coh", "dataset_group": "Outcomes", "definition": "Retreatment cohort", "code_list": None},
    ])


@pytest.fixture
def sample_facts_df():
    """Sample outcome facts DataFrame."""
    return pd.DataFrame([
        {"iso3": "ARG", "source_col": "new_sp_coh", "year": 2020, "value": 100.0},
        {"iso3": "ARG", "source_col": "new_sp_cmplt", "year": 2020, "value": 80.0},
        {"iso3": "BRA", "source_col": "new_sp_coh", "year": 2020, "value": 200.0},
        {"iso3": "BRA", "source_col": "ret_coh", "year": 2021, "value": 50.0},
        {"iso3": "CAN", "source_col": "new_sp_coh", "year": 2020, "value": 30.0},
    ])


class TestLocationUpsert:
    def test_insert_new_locations(self, temp_db, sample_locations_df):
        with temp_db() as session:
            iso_to_id = upsert_locations(session, sample_locations_df)
            
            assert len(iso_to_id) == 3
            assert "ARG" in iso_to_id
            assert "BRA" in iso_to_id
            assert "CAN" in iso_to_id
            
            # Verify DB count
            count = session.execute(select(func.count(Location.id))).scalar_one()
            assert count == 3

    def test_upsert_existing_location(self, temp_db, sample_locations_df):
        with temp_db() as session:
            # First insert
            iso_to_id = upsert_locations(session, sample_locations_df)
            first_id = iso_to_id["ARG"]
            
            # Update Argentina's country name
            updated_df = sample_locations_df.copy()
            updated_df.loc[updated_df["iso3"] == "ARG", "country"] = "Argentine Republic"
            
            # Second upsert
            iso_to_id_2 = upsert_locations(session, updated_df)
            
            # Should have same ID
            assert iso_to_id_2["ARG"] == first_id
            

            count = session.execute(select(func.count(Location.id))).scalar_one()
            assert count == 3
            
            # Verify name was updated
            loc = session.execute(select(Location).where(Location.iso3 == "ARG")).scalar_one()
            assert loc.country == "Argentine Republic"

    def test_location_fields_populated(self, temp_db, sample_locations_df):
        with temp_db() as session:
            upsert_locations(session, sample_locations_df)
            
            arg = session.execute(select(Location).where(Location.iso3 == "ARG")).scalar_one()
            assert arg.country == "Argentina"
            assert arg.iso2 == "AR"
            assert arg.iso_numeric == 32
            assert arg.who_region == "AMR"


class TestIndicatorUpsert:
    def test_insert_new_indicators(self, temp_db, sample_indicators_df):
        with temp_db() as session:
            var_to_id = upsert_indicators(session, sample_indicators_df)
            
            assert len(var_to_id) == 3
            assert "new_sp_coh" in var_to_id
            assert "new_sp_cmplt" in var_to_id
            assert "ret_coh" in var_to_id
            
            count = session.execute(select(func.count(Indicator.id))).scalar_one()
            assert count == 3

    def test_upsert_existing_indicator(self, temp_db, sample_indicators_df):
        with temp_db() as session:
            # First insert
            var_to_id = upsert_indicators(session, sample_indicators_df)
            first_id = var_to_id["new_sp_coh"]
            
            # Update definition
            updated_df = sample_indicators_df.copy()
            updated_df.loc[updated_df["variable_name"] == "new_sp_coh", "definition"] = "Updated definition"
            
            # Second upsert
            var_to_id_2 = upsert_indicators(session, updated_df)
            
            # Should have same ID
            assert var_to_id_2["new_sp_coh"] == first_id
            
            count = session.execute(select(func.count(Indicator.id))).scalar_one()
            assert count == 3
            
            # Verify definition updated
            ind = session.execute(select(Indicator).where(Indicator.variable_name == "new_sp_coh")).scalar_one()
            assert ind.definition == "Updated definition"

    def test_indicator_fields_populated(self, temp_db, sample_indicators_df):
        with temp_db() as session:
            upsert_indicators(session, sample_indicators_df)
            
            ind = session.execute(select(Indicator).where(Indicator.variable_name == "new_sp_coh")).scalar_one()
            assert ind.variable_name == "new_sp_coh"
            assert ind.dataset_group == "Outcomes"
            assert ind.definition == "New SP cohort"


class TestOutcomeFactsInsert:
    def test_insert_facts_with_valid_fks(self, temp_db, sample_locations_df, sample_indicators_df, sample_facts_df):
        with temp_db() as session:
            # Setup dimensions
            iso_to_id = upsert_locations(session, sample_locations_df)
            var_to_id = upsert_indicators(session, sample_indicators_df)
            
            # Insert facts
            inserted = insert_outcome_facts(session, sample_facts_df, iso_to_id, var_to_id)
            
            assert inserted == 5
            
            count = session.execute(select(func.count(TBOutcomeFact.id))).scalar_one()
            assert count == 5

    def test_facts_foreign_keys(self, temp_db, sample_locations_df, sample_indicators_df, sample_facts_df):
        with temp_db() as session:
            iso_to_id = upsert_locations(session, sample_locations_df)
            var_to_id = upsert_indicators(session, sample_indicators_df)
            insert_outcome_facts(session, sample_facts_df, iso_to_id, var_to_id)
            
            # Query ARG new_sp_coh 2020
            fact = session.execute(
                select(TBOutcomeFact)
                .where(TBOutcomeFact.location_id == iso_to_id["ARG"])
                .where(TBOutcomeFact.indicator_id == var_to_id["new_sp_coh"])
                .where(TBOutcomeFact.year == 2020)
            ).scalar_one()
            
            assert fact.value == 100.0
            assert fact.year == 2020

    def test_facts_preserve_values(self, temp_db, sample_locations_df, sample_indicators_df, sample_facts_df):
        with temp_db() as session:
            iso_to_id = upsert_locations(session, sample_locations_df)
            var_to_id = upsert_indicators(session, sample_indicators_df)
            insert_outcome_facts(session, sample_facts_df, iso_to_id, var_to_id)
            
            # Verify specific values
            facts = session.execute(select(TBOutcomeFact)).scalars().all()
            values = [f.value for f in facts]
            
            assert 100.0 in values
            assert 80.0 in values
            assert 200.0 in values
            assert 50.0 in values
            assert 30.0 in values

class TestBatchInsertion:
    def test_batch_insertion(self, temp_db, sample_locations_df, sample_indicators_df):
        with temp_db() as session:
            iso_to_id = upsert_locations(session, sample_locations_df)
            var_to_id = upsert_indicators(session, sample_indicators_df)
            
            # Create large fact set
            large_facts = pd.DataFrame([
                {"iso3": "ARG", "source_col": "new_sp_coh", "year": year, "value": float(year)}
                for year in range(2000, 2025)
            ])
            
            inserted = insert_outcome_facts(session, large_facts, iso_to_id, var_to_id, batch_size=10)
            
            assert inserted == 25
            count = session.execute(select(func.count(TBOutcomeFact.id))).scalar_one()
            assert count == 25
