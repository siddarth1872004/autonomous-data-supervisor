"""
security/query_guard.py — Parse-level SQL injection & DML guard.

Defence-in-depth layer that sits *before* SQLAlchemy execution.
It provides a second line of defence on top of parameterized queries to
catch cases where the LLM accidentally generates destructive SQL.

Rules enforced:
  1. Only SELECT statements are allowed.
  2. Dangerous keywords / functions are blocked.
  3. SQL comments are stripped and the query is re-parsed.
  4. LIMIT is injected if missing (capped at MAX_ROWS from config).
"""

import re
import logging

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML

import config

logger = logging.getLogger(__name__)

# ── Blocklist of dangerous SQL constructs ────────────────────────────────────
_DANGEROUS_PATTERNS = re.compile(
    r"\b("
    r"xp_cmdshell|sp_executesql|exec|execute|"
    r"openrowset|opendatasource|bulk\s+insert|"
    r"information_schema\.routines|sysobjects|"
    r"pg_sleep|dbms_pipe|waitfor\s+delay|"
    r"load_file|into\s+outfile|into\s+dumpfile|"
    r"attach\s+database|pragma\s+(?!table_info)"
    r")\b",
    re.IGNORECASE,
)

# Statement types that are allowed
_ALLOWED_DML = {"SELECT"}


class QueryGuardError(ValueError):
    """Raised when a query fails the guard checks."""


def strip_comments(sql: str) -> str:
    """Remove all SQL comments to prevent comment-based injection bypasses."""
    # Use sqlparse's strip_whitespace + strip_comments
    parsed = sqlparse.format(sql, strip_comments=True, reindent=False)
    return parsed.strip()


def validate_select_only(sql: str) -> None:
    """
    Ensure the query is a single, pure SELECT statement.
    Raises QueryGuardError for any non-SELECT SQL.
    """
    cleaned = strip_comments(sql)

    if not cleaned:
        raise QueryGuardError("Empty query rejected.")

    statements = sqlparse.parse(cleaned)

    if len(statements) > 1:
        raise QueryGuardError(
            f"Multiple statements detected ({len(statements)}). Only single SELECT queries are allowed."
        )

    stmt: Statement = statements[0]

    # Walk token tree to find the first meaningful keyword
    stmt_type: str | None = None
    for token in stmt.flatten():
        if token.ttype in (DDL, DML, Keyword):
            stmt_type = token.normalized.upper()
            break

    if stmt_type not in _ALLOWED_DML:
        raise QueryGuardError(
            f"Statement type '{stmt_type}' is not allowed. Only SELECT queries are permitted."
        )


def check_dangerous_patterns(sql: str) -> None:
    """Block known dangerous SQL functions and stored procedure calls."""
    match = _DANGEROUS_PATTERNS.search(sql)
    if match:
        raise QueryGuardError(
            f"Dangerous SQL pattern detected: '{match.group()}'. Query rejected."
        )


def inject_limit(sql: str, max_rows: int = None) -> str:
    """
    Inject a LIMIT clause if the query doesn't already have one.
    This caps memory consumption from large result sets.
    """
    if max_rows is None:
        max_rows = config.MAX_ROWS

    sql_upper = sql.upper()

    # If LIMIT already present, enforce it's not higher than max_rows
    if "LIMIT" in sql_upper:
        # Extract existing limit value and cap it
        limit_match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > max_rows:
                sql = re.sub(
                    r"\bLIMIT\s+\d+",
                    f"LIMIT {max_rows}",
                    sql,
                    flags=re.IGNORECASE,
                )
        return sql

    # Strip trailing semicolon before adding LIMIT
    sql_stripped = sql.rstrip().rstrip(";")
    return f"{sql_stripped} LIMIT {max_rows}"


def guard(sql: str) -> str:
    """
    Full guard pipeline. Call this before any SQL execution.

    Returns the cleaned, validated, limit-injected SQL string.
    Raises QueryGuardError if the query fails any check.
    """
    try:
        cleaned = strip_comments(sql)
        check_dangerous_patterns(cleaned)
        validate_select_only(cleaned)
        safe_sql = inject_limit(cleaned)
        logger.debug("Query passed guard: %s", safe_sql[:200])
        return safe_sql
    except QueryGuardError:
        raise
    except Exception as exc:
        # Wrap unexpected parsing errors as guard errors
        raise QueryGuardError(f"Query parsing failed: {exc}") from exc
