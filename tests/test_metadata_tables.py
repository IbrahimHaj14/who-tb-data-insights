import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from src.database.models_base import Base
from src.database.models_metadata import DataSource, IngestionLog

# Fixture for in-memory SQLite DB
@pytest.fixture(scope="function")
def session():
    engine = create_engine("sqlite:///:memory:")

    # Enable FK constraints for SQLite
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

# Create a sample DataSource
def create_sample_source(session):
    source = DataSource(
        name="WHO TB Treatment Outcomes 2025",
        original_file_name="who_tb_2025.csv",
        original_url="https://www.who.int/tb/data.csv",
        fetched_at=None,
        notes="Sample dataset"
    )
    session.add(source)
    session.commit()
    return source

# Tests
def test_datasource_table_columns(session):
    inspector = inspect(session.bind)
    columns = inspector.get_columns("data_source")
    column_names = [col['name'] for col in columns]

    expected_columns = ['id', 'created_at', 'name', 'original_file_name', 'original_url', 'fetched_at', 'notes']
    for col in expected_columns:
        assert col in column_names


def test_ingestionlog_table_columns(session):
    inspector = inspect(session.bind)
    columns = inspector.get_columns("ingestion_log")
    column_names = [col['name'] for col in columns]

    expected_columns = ['id', 'created_at', 'source_id', 'action', 'details', 'timestamp']
    for col in expected_columns:
        assert col in column_names


def test_datasource_insert(session):
    source = create_sample_source(session)

    assert source.id is not None
    assert source.created_at is not None

    fetched = session.query(DataSource).first()
    assert fetched.name == "WHO TB Treatment Outcomes 2025"
    assert fetched.original_file_name == "who_tb_2025.csv"


def test_ingestionlog_insert(session):
    source = create_sample_source(session)

    log = IngestionLog(
        source_id=source.id,
        action="Row cleaned",
        details='{"rows_dropped": 5}'
    )
    session.add(log)
    session.commit()

    assert log.id is not None
    assert log.created_at is not None
    assert log.timestamp is not None

    fetched = session.query(IngestionLog).first()
    assert fetched.action == "Row cleaned"
    assert fetched.details == '{"rows_dropped": 5}'
    assert fetched.data_source.id == source.id  # Relationship works


def test_ingestionlog_foreign_key(session):
    # Attempt to insert log with invalid source_id
    log = IngestionLog(source_id=9999, action="Invalid FK test")
    session.add(log)
    with pytest.raises(IntegrityError):
        session.commit()
