from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flowlog:flowlog123@localhost:5433/flowlog"
)

# Engine is the connection pool to PostgreSQL
engine = create_engine(DATABASE_URL)

# SessionLocal is a factory that creates database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency injection for FastAPI.
    Creates a new database session for each request.
    Closes it when request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()