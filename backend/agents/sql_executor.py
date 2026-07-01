"""
agents/sql_executor.py — LangGraph node: Execute SQL safely.

Pipeline:
  1. Run query_guard (parse-level validation + LIMIT injection).
  2. Execute via SQLAlchemy (parameterized — no string concatenation).
  3. Save raw DataFrame to DataFrameStore (not in LangGraph state).
  4. Return compact stats summary to state for LLM consumption.
  5. On error: increment retry_count, store error in state → triggers retry edge.
"""

import logging

import pandas as pd
from sqlalchemy import text

import config
from agents.state import AgentState, DataFrameStore
from database.connection import sync_engine
from security.query_guard import QueryGuardError, guard

logger = logging.getLogger(__name__)


def _build_data_summary(df: pd.DataFrame) -> str:
    """
    Create a compact, LLM-friendly summary of the DataFrame.
    Deliberately avoids putting raw rows into the summary.
    """
    lines: list[str] = [
        f"Data Shape: {df.shape[0]:,} rows × {df.shape[1]} columns",
        f"Columns: {', '.join(df.columns.tolist())}",
    ]

    numeric_cols = df.select_dtypes(include=["number"]).columns
    for col in numeric_cols[:6]:  # Cap at 6 numeric columns for brevity
        series = df[col].dropna()
        if len(series) > 0:
            lines.append(
                f"{col}: min={series.min():.2f}, max={series.max():.2f}, "
                f"mean={series.mean():.2f}, std={series.std():.2f}"
            )

    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    for col in cat_cols[:3]:
        top_vals = df[col].value_counts().head(5).to_dict()
        lines.append(f"{col} top values: {top_vals}")

    return "\n".join(lines)


def sql_executor_node(state: AgentState) -> dict:
    """
    LangGraph node: validates and executes state['sql_query'].
    Saves raw DataFrame to DataFrameStore; only a compact summary goes to state.
    """
    sql_query = state.get("sql_query")
    retry_count = state.get("retry_count", 0)

    if not sql_query:
        return {
            "sql_error": "No SQL query was generated.",
            "retry_count": retry_count + 1,
        }

    logger.info("[sql_executor] Executing (attempt %d): %s", retry_count + 1, sql_query[:200])

    # ── Step 1: Parse-level guard ──────────────────────────────────────────────
    try:
        safe_sql = guard(sql_query)
    except QueryGuardError as exc:
        logger.warning("[sql_executor] Guard rejected query: %s", exc)
        return {
            "sql_error": f"Security guard rejected query: {exc}",
            "retry_count": retry_count + 1,
        }

    # ── Step 2: Execute via SQLAlchemy ────────────────────────────────────────
    # text() with no user-controlled parameters — the SQL was LLM-generated and
    # guard-validated. User input is NOT interpolated into the SQL string.
    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text(safe_sql))  # noqa: S608
            rows = result.fetchall()
            columns = list(result.keys())

        df = pd.DataFrame(rows, columns=columns)

        # Convert likely date/timestamp columns.
        # pandas >= 2.2 deprecated (and pandas 3.0 removed) errors="ignore" on
        # pd.to_datetime, so we explicitly catch failures and leave the
        # original column untouched instead of coercing to NaT.
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ("date", "timestamp", "time", "created", "updated")):
                try:
                    df[col] = pd.to_datetime(df[col])
                except (ValueError, TypeError):
                    pass

        logger.info("[sql_executor] Returned %d rows, %d columns", len(df), len(df.columns))

    except Exception as exc:
        logger.warning("[sql_executor] SQL execution failed: %s", exc)
        return {
            "sql_error": str(exc),
            "retry_count": retry_count + 1,
        }

    if df.empty:
        return {
            "sql_error": None,
            "retry_count": retry_count,
            "dataframe_key": None,
            "data_summary": "Query executed successfully but returned 0 rows.",
            "row_count": 0,
        }

    # ── Step 3: Store DataFrame in memory store ────────────────────────────────
    store = DataFrameStore.get_instance()
    # Delete previous key if retrying (avoids memory leak)
    if old_key := state.get("dataframe_key"):
        store.delete(old_key)

    df_key = store.save(df)
    summary = _build_data_summary(df)

    return {
        "sql_error": None,
        "retry_count": retry_count,
        "dataframe_key": df_key,
        "data_summary": summary,
        "row_count": len(df),
    }
