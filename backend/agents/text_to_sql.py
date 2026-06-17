"""
agents/text_to_sql.py — LangGraph node: Natural Language → SQL.

Uses few-shot prompting with explicit output format enforcement to prevent
the LLM from wrapping the SQL in markdown, explanations, or conversational
filler that would break downstream parsing.

Security:
  - Only generates SELECT statements (system prompt + guard in sql_executor).
  - DB schema injected as trusted context from server-side inspection.
  - User query is passed as a user message (not injected into system prompt).
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

import config
from agents.state import AgentState

logger = logging.getLogger(__name__)


def _build_llm():
    """Build the LLM client based on configured provider."""
    if config.LLM_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config.LLM_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.0,  # Deterministic SQL generation
        )
    elif config.LLM_PROVIDER == "openai":
        try:
            from langchain_openai import ChatOpenAI  # pip install langchain-openai>=0.2.0
        except ImportError as e:
            raise ImportError(
                "OpenAI support requires an additional install: "
                "pip install 'langchain-openai>=0.2.0'"
            ) from e
        return ChatOpenAI(
            model=config.LLM_MODEL,
            openai_api_key=config.OPENAI_API_KEY,
            temperature=0.0,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")


# Build LLM once at module load (connection pooled by LangChain)
_llm = _build_llm()

_SYSTEM_PROMPT_TEMPLATE = """You are an expert SQL analyst for a data engineering platform.
Your ONLY job is to convert a user's natural language question into a single, valid SQL SELECT query.

CRITICAL OUTPUT RULES — VIOLATION WILL BREAK THE SYSTEM:
1. Output ONLY the raw SQL query. Nothing else.
2. Do NOT include markdown code blocks (no ```sql), backticks, or explanations.
3. Do NOT include any conversational text like "Here is the query..." or "Sure!".
4. Do NOT generate INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any non-SELECT SQL.
5. Always include LIMIT {max_rows} at the end UNLESS the query uses GROUP BY aggregations.
6. Use only table and column names that exist in the schema below.
7. If you cannot answer from the schema, output exactly: CANNOT_ANSWER

{schema}

--- FEW-SHOT EXAMPLES ---

Q: What are the total sales by region?
A: SELECT region, SUM(revenue) AS total_revenue, SUM(units_sold) AS total_units, SUM(profit) AS total_profit FROM sales GROUP BY region ORDER BY total_revenue DESC

Q: Show me sensor readings with abnormally high temperature in the last month
A: SELECT sensor_id, timestamp, temperature, pressure, vibration, status FROM sensor_readings WHERE temperature > 90 AND timestamp >= date('now', '-30 days') ORDER BY temperature DESC LIMIT {max_rows}

Q: What is the daily revenue trend for the North region over the last 90 days?
A: SELECT date, SUM(revenue) AS daily_revenue, SUM(units_sold) AS daily_units FROM sales WHERE region = 'North' AND date >= date('now', '-90 days') GROUP BY date ORDER BY date ASC

--- END EXAMPLES ---

Now answer the following question with ONLY the SQL query:"""


def _clean_llm_output(raw: str) -> str:
    """
    Strip any markdown fences, backticks, or explanatory text that the LLM
    might include despite strict instructions. Returns clean SQL.
    """
    # Remove ```sql ... ``` or ``` ... ``` blocks
    cleaned = re.sub(r"```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")

    # Take only the first SQL-looking line block (SELECT ... ;)
    lines = [l.strip() for l in cleaned.strip().splitlines() if l.strip()]
    sql_lines: list[str] = []
    in_sql = False
    for line in lines:
        upper = line.upper()
        if upper.startswith("SELECT") or upper.startswith("WITH"):
            in_sql = True
        if in_sql:
            sql_lines.append(line)
            # Stop at semicolon or blank line
            if line.endswith(";") or (sql_lines and not line):
                break

    result = " ".join(sql_lines) if sql_lines else cleaned.strip()
    return result.rstrip(";").strip()


def text_to_sql_node(state: AgentState) -> dict:
    """
    LangGraph node: translates state['user_query'] → state['sql_query'].
    On retry, the previous error is appended so the LLM can self-correct.
    """
    logger.info("[text_to_sql] Generating SQL (retry=%d)", state.get("retry_count", 0))

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        schema=state["db_schema"],
        max_rows=config.MAX_ROWS,
    )

    # On retry, include the previous failed query and error to guide correction
    user_content = state["user_query"]
    if state.get("sql_error") and state.get("sql_query"):
        user_content = (
            f"Previous attempt failed.\n"
            f"Failed SQL: {state['sql_query']}\n"
            f"Error: {state['sql_error']}\n\n"
            f"Please fix the query and try again for: {state['user_query']}"
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    try:
        response = _llm.invoke(messages)
        raw_sql = response.content.strip()

        if raw_sql == "CANNOT_ANSWER":
            return {
                "sql_query": None,
                "error_message": "I cannot answer this question from the available database schema.",
                "sql_error": "CANNOT_ANSWER",
            }

        sql_query = _clean_llm_output(raw_sql)
        logger.info("[text_to_sql] Generated: %s", sql_query[:200])
        return {"sql_query": sql_query, "sql_error": None}

    except Exception as exc:
        logger.exception("[text_to_sql] LLM call failed")
        return {
            "sql_query": None,
            "error_message": f"LLM error: {exc}",
            "sql_error": str(exc),
        }
