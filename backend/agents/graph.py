"""
agents/graph.py — LangGraph StateGraph definition.

Graph topology:
                     ┌──────────────┐
                     │  text_to_sql │ ←──────────────────┐
                     └──────┬───────┘                    │
                            ↓                            │ (retry < MAX_RETRIES)
                     ┌──────────────┐                    │
                     │ sql_executor │ ───── sql_error? ───┤
                     └──────┬───────┘                    │
                            │ (success)                  │ (max retries reached → END)
                            ↓                            │
                     ┌──────────────┐                    │
                     │ ml_analysis  │                    │
                     └──────┬───────┘                    │
                            ↓                            │
                     ┌──────────────┐                    │
                     │ visualization│                    │
                     └──────┬───────┘                    │
                            ↓                            │
                           END                           │
"""

import logging

from langgraph.graph import END, START, StateGraph

import config
from agents.ml_analysis import ml_analysis_node
from agents.sql_executor import sql_executor_node
from agents.state import AgentState
from agents.text_to_sql import text_to_sql_node
from agents.visualization import visualization_node

logger = logging.getLogger(__name__)


def _route_after_executor(state: AgentState) -> str:
    """
    Conditional edge: decides what happens after sql_executor runs.

      - SQL succeeded                  → "ml_analysis"
      - SQL failed, retries remaining  → "text_to_sql" (self-correction loop)
      - SQL failed, max retries hit    → END
      - CANNOT_ANSWER sentinel         → END
    """
    sql_error = state.get("sql_error")
    retry_count = state.get("retry_count", 0)

    if not sql_error:
        logger.info("[graph] SQL succeeded → routing to ml_analysis")
        return "ml_analysis"

    if sql_error == "CANNOT_ANSWER":
        logger.info("[graph] Cannot answer query → END")
        return END

    if retry_count < config.MAX_RETRIES:
        logger.info(
            "[graph] SQL failed (attempt %d/%d) → routing back to text_to_sql for self-correction",
            retry_count,
            config.MAX_RETRIES,
        )
        return "text_to_sql"

    logger.warning("[graph] Max retries (%d) reached → END with error", config.MAX_RETRIES)
    return END


def build_graph() -> StateGraph:
    """Build and compile the LangGraph state machine."""
    graph = StateGraph(AgentState)

    # ── Register nodes ──────────────────────────────────────────────────────────
    graph.add_node("text_to_sql", text_to_sql_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("ml_analysis", ml_analysis_node)
    graph.add_node("visualization", visualization_node)

    # ── Define edges ────────────────────────────────────────────────────────────
    graph.set_entry_point("text_to_sql")
    graph.add_edge("text_to_sql", "sql_executor")

    graph.add_conditional_edges(
        "sql_executor",
        _route_after_executor,
        {
            "text_to_sql": "text_to_sql",
            "ml_analysis": "ml_analysis",
            END: END,
        },
    )

    graph.add_edge("ml_analysis", "visualization")
    graph.add_edge("visualization", END)

    return graph.compile()


# Compile once at module load — reused across all requests
agent_graph = build_graph()
