"""
main.py — FastAPI application entry point.

Security hardening:
  - Strict security headers on every response (CSP, X-Frame, nosniff, etc.)
  - API key authentication on all /api/* endpoints
  - CORS restricted to configured origins only (no wildcard)
  - Rate limiting via slowapi (default: 30 requests/minute per IP)
  - No sensitive data in error responses returned to clients
  - TODO(security): Replace API key auth with OAuth 2.0 / OIDC for production.
  - TODO(security): Enable mTLS for database connections in production.
  - TODO(security): Add MFA support for admin endpoints.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import config
from agents.graph import agent_graph
from database.connection import get_schema_description
from database.seed import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Lifespan: seed DB on startup ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate()
    seed_database()
    logger.info("🚀 Autonomous Data Supervisor is ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Autonomous Data Engineering & Anomaly Supervisor",
    version="1.0.0",
    description="ReAct agent pipeline: NL → SQL → ML anomaly detection → Plotly dashboards",
    lifespan=lifespan,
    # Disable default /docs in production; enable for development
    docs_url="/docs" if os.environ.get("ENV", "development") == "development" else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],   # Minimal allowed methods
    allow_headers=["Content-Type", "X-API-Key"],
)

# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'none'; "
        "object-src 'none'; "
        "frame-ancestors 'none';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


# ── Authentication ────────────────────────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """Dependency that validates the X-API-Key header."""
    if not api_key or api_key != config.API_SECRET_KEY:
        # Return 403 without disclosing whether the key exists or its format
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key


# ── Request / Response models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question must not be empty.")
        if len(stripped) > 1000:
            raise ValueError("Question must not exceed 1000 characters.")
        return stripped


class QueryResponse(BaseModel):
    sql_query: str | None
    row_count: int
    anomaly_count: int
    anomaly_summary: str | None
    plotly_figure: dict[str, Any] | None
    data_summary: str | None
    error_message: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Health check — no authentication required."""
    return {"status": "ok", "version": "1.0.0"}


@app.get(
    "/api/schema",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute")
async def get_schema(request: Request):
    """Return the database schema as plain text (for dev tooling / debug)."""
    try:
        schema = get_schema_description()
        return {"schema": schema}
    except Exception:
        logger.exception("Schema retrieval failed")
        # Do NOT expose internal error details to the client
        raise HTTPException(status_code=500, detail="Schema retrieval failed.")


@app.post(
    "/api/query",
    response_model=QueryResponse,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute")
async def run_query(request: Request, body: QueryRequest):
    """
    Main agent endpoint: accepts a natural language question and runs the
    full LangGraph pipeline (Text-to-SQL → SQL Exec → ML → Visualization).
    """
    logger.info("Query received: %s", body.question[:100])

    try:
        schema = get_schema_description()
    except Exception:
        logger.exception("Failed to load schema")
        raise HTTPException(status_code=500, detail="Database unavailable.")

    initial_state: dict = {
        "user_query": body.question,
        "db_schema": schema,
        "sql_query": None,
        "sql_error": None,
        "retry_count": 0,
        "dataframe_key": None,
        "data_summary": None,
        "row_count": 0,
        "anomaly_count": 0,
        "anomaly_indices": [],
        "anomaly_summary": None,
        "plotly_figure": None,
        "final_summary": None,
        "error_message": None,
    }

    try:
        final_state = await agent_graph.ainvoke(initial_state)
    except Exception:
        logger.exception("Agent graph execution failed")
        raise HTTPException(status_code=500, detail="Agent pipeline failed.")

    return QueryResponse(
        sql_query=final_state.get("sql_query"),
        row_count=final_state.get("row_count", 0),
        anomaly_count=final_state.get("anomaly_count", 0),
        anomaly_summary=final_state.get("anomaly_summary"),
        plotly_figure=final_state.get("plotly_figure"),
        data_summary=final_state.get("data_summary"),
        error_message=final_state.get("error_message"),
    )


# ── Example queries endpoint (unauthenticated — for onboarding UX) ────────────
@app.get("/api/examples")
async def get_example_queries():
    """Return suggested queries to help non-technical users get started."""
    return {
        "examples": [
            "Show me total revenue by region",
            "What are the top 5 products by profit?",
            "Detect anomalies in daily sales over the last 6 months",
            "Which sensors have the highest temperature readings?",
            "Show me the revenue trend for the North region",
            "Find sensor readings with abnormal vibration levels",
        ]
    }
