import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(override=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def _parse_database_url(raw_url: str) -> URL:
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]
    url = make_url(raw_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    query = dict(url.query)
    sslmode = os.getenv("DB_SSLMODE")
    if sslmode:
        query["sslmode"] = sslmode
    elif ENVIRONMENT in {"staging", "production"}:
        query.setdefault("sslmode", "require")
    return url.set(query=query)


def get_database_url(*, for_migrations: bool = False) -> URL:
    raw_url = os.getenv("MIGRATION_DATABASE_URL") if for_migrations else None
    raw_url = raw_url or os.getenv("DATABASE_URL")
    if raw_url:
        return _parse_database_url(raw_url)

    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
        query={
            "sslmode": os.getenv(
                "DB_SSLMODE",
                "require" if ENVIRONMENT in {"staging", "production"} else "prefer",
            )
        },
    )


engine = create_engine(
    get_database_url(),
    pool_size=int(os.getenv("DB_POOL_SIZE", "2")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "0")),
    pool_pre_ping=True,
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
