"""
agents/state.py — LangGraph state definition + in-memory DataFrame store.

The AgentState TypedDict is the single source of truth passed through the
LangGraph state machine. Raw Pandas DataFrames are NOT stored in the state
(to avoid LLM context window bloat); instead they live in the DataFrameStore
singleton and are referenced by a UUID key.
"""

from __future__ import annotations

import threading
import uuid
import logging
from typing import Optional, TypedDict

import pandas as pd

logger = logging.getLogger(__name__)


# ── In-Memory DataFrame Store ─────────────────────────────────────────────────

class DataFrameStore:
    """
    Process-scoped singleton that holds raw DataFrames during agent execution.

    DataFrames are keyed by UUID so multiple concurrent requests each have
    their own isolated storage slot. Each slot is cleaned up after the
    agent run completes.
    """

    _instance: "DataFrameStore | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._store: dict[str, pd.DataFrame] = {}
        self._store_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "DataFrameStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def save(self, df: pd.DataFrame) -> str:
        """Persist a DataFrame and return its unique key."""
        key = str(uuid.uuid4())
        with self._store_lock:
            self._store[key] = df
        logger.debug("DataFrameStore: saved key=%s shape=%s", key, df.shape)
        return key

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve a DataFrame by key. Returns None if key doesn't exist."""
        with self._store_lock:
            return self._store.get(key)

    def delete(self, key: str) -> None:
        """Remove a DataFrame from memory (call after agent run completes)."""
        with self._store_lock:
            if key in self._store:
                del self._store[key]
                logger.debug("DataFrameStore: deleted key=%s", key)

    def update(self, key: str, df: pd.DataFrame) -> None:
        """Replace the DataFrame stored under an existing key (e.g. after annotating it)."""
        with self._store_lock:
            self._store[key] = df
        logger.debug("DataFrameStore: updated key=%s shape=%s", key, df.shape)


# ── Agent State ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    State passed between LangGraph nodes.

    Fields that grow large (DataFrames, raw SQL results) are NOT stored here;
    they use the DataFrameStore above with a UUID reference.
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    user_query: str
    db_schema: str                         # DB schema injected at graph entry

    # ── Text-to-SQL Node ──────────────────────────────────────────────────────
    sql_query: Optional[str]               # Generated SQL SELECT statement

    # ── SQL Executor Node ─────────────────────────────────────────────────────
    sql_error: Optional[str]               # Error message if execution failed
    retry_count: int                       # Number of SQL retries attempted
    dataframe_key: Optional[str]           # Key into DataFrameStore
    data_summary: Optional[str]            # Compact stats summary for LLM
    row_count: int                         # Actual number of rows returned

    # ── ML Analysis Node ──────────────────────────────────────────────────────
    anomaly_count: int                     # Number of anomalies detected
    anomaly_indices: Optional[list[int]]   # Row indices flagged as anomalies
    anomaly_summary: Optional[str]         # Human-readable anomaly description

    # ── Visualization Node ────────────────────────────────────────────────────
    plotly_figure: Optional[dict]          # JSON-serialized Plotly figure

    # ── Final Output ──────────────────────────────────────────────────────────
    final_summary: Optional[str]           # LLM-generated narrative summary
    error_message: Optional[str]           # Terminal error shown to user
