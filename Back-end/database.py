# database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the DATABASE_URL and Base from your models file
from models import DATABASE_URL, Base

# Create the SQLAlchemy engine using the connection string
engine = create_engine(DATABASE_URL)

# Create a SessionLocal class. Instances of this class will be the actual database sessions.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# This is a dependency function for your FastAPI routes.
# It creates a new database session for each incoming request and ensures it's closed afterward.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()