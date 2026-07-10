from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.db_config import build_database_url

DATABASE_URL = build_database_url("postgresql+psycopg2")
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()