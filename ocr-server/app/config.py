from app.db_config import build_database_url


class Config:
    SQLALCHEMY_DATABASE_URI = build_database_url("postgresql")
    SQLALCHEMY_TRACK_MODIFICATIONS = False