import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from src.database.models_base import Base
from src.database.models_dimension import Location, Indicator 

# Create an in-memory SQLite database for testing
@pytest.fixture(scope="function")
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_location_table_columns(session):
    # Use SQLAlchemy inspector to check columns
    inspector = inspect(session.bind)
    columns = inspector.get_columns("location")
    column_names = [col['name'] for col in columns]

    # Check expected columns
    expected_columns = ['id', 'created_at', 'country', 'iso2', 'iso3', 'iso_numeric', 'who_region']
    for col in expected_columns:
        assert col in column_names


def test_indicator_table_columns(session):
    inspector = inspect(session.bind)
    columns = inspector.get_columns("indicator")
    column_names = [col['name'] for col in columns]

    expected_columns = ['id', 'created_at', 'variable_name', 'dataset_group', 'definition', 'code_list']
    for col in expected_columns:
        assert col in column_names


def test_location_insert(session):
    # Test inserting a row and auto PK / timestamp
    loc = Location(country="Jordan", iso2="JO", iso3="JOR", iso_numeric=400, who_region="EMR")
    session.add(loc)
    session.commit()

    assert loc.id is not None
    assert loc.created_at is not None

    fetched = session.query(Location).first()
    assert fetched.country == "Jordan"
    assert fetched.iso3 == "JOR"


def test_indicator_insert(session):
    ind = Indicator(variable_name="new_sp_cur", dataset_group="Treatment outcomes",
                    definition="Number of new smear positive cases cured", code_list=None)
    session.add(ind)
    session.commit()

    assert ind.id is not None
    assert ind.created_at is not None

    fetched = session.query(Indicator).first()
    assert fetched.variable_name == "new_sp_cur"
    assert fetched.dataset_group == "Treatment outcomes"


def test_indicator_unique(session):
    # unique indicators
    ind1 = Indicator(variable_name="unique_var")
    ind2 = Indicator(variable_name="unique_var")
    session.add(ind1)
    session.commit()

    session.add(ind2)
    with pytest.raises(Exception):
        session.commit()  # should raise IntegrityError or similar
