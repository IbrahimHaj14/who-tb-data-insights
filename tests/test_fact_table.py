import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from src.database.models_base import Base
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact  
from sqlalchemy.exc import IntegrityError

def test_fact_foreign_key_constraint(session):
    # Test invalid foreign keys
    fact = TBOutcomeFact(location_id=9999, indicator_id=9999, year=2023, value=10.0)
    session.add(fact)
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.fixture(scope="function")
def session():
    engine = create_engine("sqlite:///:memory:")

    # Foreign key enforcement in SQLite
    if "sqlite" in str(engine.url):
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def create_sample_location(session):
    loc = Location(country="Jordan", iso2="JO", iso3="JOR", iso_numeric=400, who_region="EMR")
    session.add(loc)
    session.commit()
    return loc


def create_sample_indicator(session):
    ind = Indicator(variable_name="new_sp_cur", dataset_group="Treatment outcomes",
                    definition="Number of new smear positive cases cured")
    session.add(ind)
    session.commit()
    return ind


def test_fact_table_columns(session):
    inspector = inspect(session.bind)
    columns = inspector.get_columns("tb_outcome_fact")
    column_names = [col['name'] for col in columns]

    expected_columns = ['id', 'created_at', 'location_id', 'indicator_id', 'year', 'value']
    for col in expected_columns:
        assert col in column_names


def test_fact_insert(session):
    loc = create_sample_location(session)
    ind = create_sample_indicator(session)

    fact = TBOutcomeFact(
        location_id=loc.id,
        indicator_id=ind.id,
        year=2023,
        value=123.4,
    )
    session.add(fact)
    session.commit()

    assert fact.id is not None
    assert fact.created_at is not None

    fetched = session.query(TBOutcomeFact).first()
    assert fetched.value == 123.4
    assert fetched.location_id == loc.id
    assert fetched.indicator_id == ind.id


def test_fact_relationships(session):
    loc = create_sample_location(session)
    ind = create_sample_indicator(session)

    fact = TBOutcomeFact(
        location_id=loc.id,
        indicator_id=ind.id,
        year=2023,
        value=56.7
    )
    session.add(fact)
    session.commit()

    #Relationship properties
    fetched = session.query(TBOutcomeFact).first()
    assert fetched.location.country == "Jordan"
    assert fetched.indicator.variable_name == "new_sp_cur"


def test_fact_foreign_key(session):
    # Test invalid location_id/indicator_id
    fact = TBOutcomeFact(location_id=9999, indicator_id=9999, year=2023, value=10.0)
    session.add(fact)
    with pytest.raises(Exception):
        session.commit()  
