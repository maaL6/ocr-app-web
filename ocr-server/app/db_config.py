import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


def load_db_settings():
    load_dotenv("app/.env")

    running_in_docker = os.getenv("RUNNING_IN_DOCKER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    db_host = os.getenv("DB_HOST") or ("postgres" if running_in_docker else "127.0.0.1")
    db_port = os.getenv("DB_PORT") or ("5432" if running_in_docker else "5433")
    db_user = os.getenv("DB_USER", "ocr_user")
    db_password = os.getenv("DB_PASSWORD", "ocr_password")
    db_name = os.getenv("DB_NAME", "ocr")

    return {
        "host": db_host,
        "port": db_port,
        "user": db_user,
        "password": db_password,
        "name": db_name,
    }


def build_database_url(driver: str = "postgresql+psycopg2") -> str:
    cfg = load_db_settings()
    return (
        f"{driver}://{quote_plus(cfg['user'])}:{quote_plus(cfg['password'])}@"
        f"{cfg['host']}:{cfg['port']}/{cfg['name']}"
    )
