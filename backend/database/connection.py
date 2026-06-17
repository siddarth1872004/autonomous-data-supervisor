"""
database/connection.py — SQLAlchemy engine setup.

Security:
- Read-only enforcement via query_guard (application level).
- mTLS: TODO(security) — Enable for production Postgres/MySQL deployments.
- Database user should only have SELECT privileges on the target schema.
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import config

# ── Async engine (for FastAPI request handling) ───────────────────────────────
async_engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
    if "sqlite" in config.DATABASE_URL
    else {},
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (for seeding & schema inspection) ────────────────────────────
sync_engine = create_engine(
    config.DATABASE_SYNC_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in config.DATABASE_SYNC_URL
    else {},
)


def get_schema_description() -> str:
    """
    Introspect the database and return a human-readable schema description
    for injection into the LLM system prompt.
    """
    inspector = inspect(sync_engine)
    lines: list[str] = ["Database Schema:\n"]

    for table_name in inspector.get_table_names():
        lines.append(f"Table: {table_name}")
        cols = inspector.get_columns(table_name)
        for col in cols:
            nullable = "" if col["nullable"] else " NOT NULL"
            lines.append(f"  - {col['name']} ({col['type']!s}{nullable})")

        # Add sample data hint (no actual data — just row count)
        with sync_engine.connect() as conn:
            # Using parameterized table name is not possible in SQL identifiers,
            # but table names here come from inspector (trusted source, not user input).
            count = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')  # noqa: S608
            ).scalar()
            lines.append(f"  Rows: ~{count:,}")
        lines.append("")

    return "\n".join(lines)


async def get_async_session():
    """FastAPI dependency: yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
