from src.database.connection import engine, SessionLocal
from src.database.models_base import Base
from src.database.models_base import DummyTest

def test_engine():
    print("Testing engine creation...")
    print(engine)
    print("Engine OK.")

def test_create_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

def test_session():
    print("Testing session...")
    db = SessionLocal()
    db.close()
    print("Session opened and closed successfully.")

if __name__ == "__main__":
    print("\n=== Running Database Base Setup Tests ===")
    test_engine()
    test_create_tables()
    test_session()
    print("\nAll tests completed successfully ✓")
