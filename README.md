# DataVigil-AI: Autonomous Data Engineering & Anomaly Supervisor

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B6B?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![Scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Plotly](https://img.shields.io/badge/Plotly-5.22-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)

**An end-to-end ReAct agent that connects to a live SQL database, processes natural language queries, detects anomalies with ML, and generates interactive dashboards — all in one autonomous loop.**

[Live Demo](#quick-start) · [Architecture](#architecture) · [API Docs](#api-reference) · [Security](#security)

</div>

---

## What This Does

Ask a question like *"Show me revenue anomalies across regions for the last 6 months"* and the system autonomously:

1. **Translates** your question into a secure SQL SELECT query using Gemini/GPT
2. **Self-corrects** if the SQL fails (up to 3 retries with error context)
3. **Executes** the query safely against the database
4. **Detects anomalies** using Scikit-learn Isolation Forest
5. **Generates** an interactive Plotly dashboard highlighting anomalous data points

No SQL knowledge required. Built for non-technical stakeholders.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph State Machine                       │
│                                                                 │
│  User Query                                                     │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────┐   SQL Error + Context    ┌──────────────┐    │
│  │ Text-to-SQL  │ ◄──────────────────────── │ SQL Executor │    │
│  │   (Gemini)   │                           │ + Guard      │    │
│  └──────┬───────┘                           └──────┬───────┘    │
│         │ Generated SQL                            │ Success     │
│         └──────────────────────────────────────────┘            │
│                                                    │            │
│                                                    ▼            │
│                                           ┌──────────────┐     │
│                                           │ ML Analysis  │     │
│                                           │ (Isolation   │     │
│                                           │  Forest)     │     │
│                                           └──────┬───────┘     │
│                                                  │             │
│                                                  ▼             │
│                                           ┌──────────────┐     │
│                                           │ Visualization│     │
│                                           │ (Plotly)     │     │
│                                           └──────┬───────┘     │
└──────────────────────────────────────────────────┼─────────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  FastAPI BFF    │
                                          │  (API + Auth)   │
                                          └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  React Frontend │
                                          │  (Chat + Chart) │
                                          └─────────────────┘
```

### Agent Nodes

| Node | Responsibility | Key Design Decision |
|------|---------------|---------------------|
| **Text-to-SQL** | NL → SQL via LLM | Few-shot prompting; raw SQL output enforced |
| **SQL Executor** | Validate + run SQL | Parse-level guard → parameterized execution → LIMIT 1000 cap |
| **ML Analysis** | Anomaly detection | IsolationForest on numeric features; DataFrame stored in memory (not in state) |
| **Visualization** | Chart generation | Smart chart selector: time-series / bar / scatter / table |

### State Bloat Prevention

Raw DataFrames live in a **process-scoped `DataFrameStore`** (UUID-keyed in-memory dict), not in the LangGraph state. Only a compact statistical summary (~200 chars) is passed through the state for LLM consumption, preventing context window overflow even on large result sets.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Google AI Studio](https://aistudio.google.com) API key (or OpenAI API key)

### 1. Clone and configure

```bash
git clone https://github.com/siddarth1872004/DataVigil-AI.git
cd DataVigil-AI

cp .env.example .env
# Edit .env and set your GOOGLE_API_KEY and API_SECRET_KEY
```

### 2. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# The database is auto-seeded on first startup
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the app

Navigate to **http://localhost:5173** and start asking questions!

**Try these sample queries:**
- *"Show me total revenue by region"*
- *"Detect anomalies in daily sales over the last 6 months"*
- *"Which sensors have the highest temperature readings?"*
- *"What are the top 5 products by profit?"*

---

## Database

The app ships with a **pre-seeded SQLite demo database** containing:

| Table | Rows | Description |
|-------|------|-------------|
| `sales` | ~17,500 | 2 years of daily sales: date, region, product, revenue, units, cost, profit |
| `sensor_readings` | ~21,900 | 6 months of hourly sensor data: temperature, pressure, vibration |

Both tables contain **deliberately injected anomalies** so the ML agent has real signals to detect.

To use a real database, set `DATABASE_URL` in `.env`:
```
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/mydb
```

---

## API Reference

All endpoints require `X-API-Key: <your_api_secret_key>` header (except `/api/health` and `/api/examples`).

### `POST /api/query`

Run the full agent pipeline on a natural language question.

**Request:**
```json
{
  "question": "Show me revenue anomalies by region"
}
```

**Response:**
```json
{
  "sql_query": "SELECT region, date, SUM(revenue) ... GROUP BY region, date",
  "row_count": 832,
  "anomaly_count": 23,
  "anomaly_summary": "23/832 rows flagged (2.8%). Revenue anomalies are 847% HIGHER than normal.",
  "plotly_figure": { "data": [...], "layout": {...} },
  "data_summary": "Data Shape: 832 rows × 4 columns\nrevenue: min=189.23, max=142834.10...",
  "error_message": null
}
```

### `GET /api/schema`
Returns the database schema for debugging.

### `GET /api/examples`
Returns suggested starter queries (unauthenticated).

### `GET /api/health`
Health check (unauthenticated).

Interactive docs at **http://localhost:8000/docs** (development mode only).

---

## Security

| Threat | Mitigation |
|--------|------------|
| **SQL Injection** | `sqlparse` parse-level guard + SQLAlchemy `text()` (no string concatenation) |
| **LLM Prompt Injection** | User input isolated as `HumanMessage`; schema context in `SystemMessage` |
| **DML / DDL execution** | Guard rejects anything that isn't `SELECT`; strips SQL comments first |
| **Result set overflow** | `LIMIT 1000` injected/enforced by `query_guard.py` |
| **Secret exposure** | All secrets from env vars; LLM API keys never sent to browser (BFF pattern) |
| **XSS** | React JSX auto-escaping; no `dangerouslySetInnerHTML` |
| **Clickjacking** | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` |
| **CSRF** | Stateless API key auth (no cookie sessions) |
| **DoS** | Rate limiting: 30 requests/minute per IP via `slowapi` |
| **Content sniffing** | `X-Content-Type-Options: nosniff` |
| **Data in transit** | `Strict-Transport-Security` header; HTTPS enforced in production |

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

The test suite covers:
- SQL guard: DML/DDL rejection, dangerous patterns, multi-statement injection
- LIMIT injection and capping
- Comment stripping bypass prevention

---

## Project Structure

```
autonomous-data-supervisor/
├── backend/
│   ├── main.py              # FastAPI app (security headers, auth, rate limiting)
│   ├── config.py            # Secure config (env vars, no hardcoded secrets)
│   ├── database/
│   │   ├── connection.py    # SQLAlchemy engines + schema introspection
│   │   └── seed.py          # Demo database seeder
│   ├── agents/
│   │   ├── state.py         # AgentState + DataFrameStore
│   │   ├── text_to_sql.py   # NL → SQL (few-shot LLM)
│   │   ├── sql_executor.py  # Safe SQL execution
│   │   ├── ml_analysis.py   # Isolation Forest anomaly detection
│   │   ├── visualization.py # Plotly chart generation
│   │   └── graph.py         # LangGraph state machine
│   ├── security/
│   │   └── query_guard.py   # Parse-level SQL guard
│   └── tests/
│       └── test_query_guard.py
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── ChatInterface.tsx
│       │   ├── Dashboard.tsx
│       │   ├── AgentSteps.tsx
│       │   └── AnomalyBadge.tsx
│       └── api/client.ts
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google Gemini API key |
| `HUGGINGFACE_API_KEY` | — | **Optional** Hugging Face API key (required for prompt guard & summary insights, or when LLM_PROVIDER is huggingface) |
| `LLM_PROVIDER` | `google` | `google`, `openai`, or `huggingface` |
| `LLM_MODEL` | `gemini-1.5-flash` | Model name (e.g. `Qwen/Qwen2.5-Coder-32B-Instruct` for Hugging Face) |
| `DATABASE_URL` | SQLite demo | SQLAlchemy connection string |
| `API_SECRET_KEY` | auto-generated | Backend authentication key |
| `MAX_RETRIES` | `3` | Max SQL retry attempts |
| `MAX_ROWS` | `1000` | Hard cap on SQL result rows |
| `RATE_LIMIT_PER_MINUTE` | `30` | API rate limit per IP |

---

## Tech Stack

- **Orchestration**: LangGraph (ReAct state graph with security and retry loops)
- **LLM**: Google Gemini 1.5 Flash (default) or Hugging Face serverless (Qwen2.5-Coder)
- **Security Guard**: Hugging Face Deberta Prompt Injection Guard + parse-level SQL guard
- **Insights Generator**: Hugging Face Llama-3 Summarizer (NL data insights reports)
- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (demo) / SQLAlchemy (Postgres/MySQL compatible)
- **ML**: Pandas + Scikit-learn (Isolation Forest)
- **Visualization**: Plotly (server-side JSON → react-plotly.js)
- **Frontend**: Vite + React + TypeScript
- **Security**: slowapi, sqlparse, BFF pattern

---

## License

MIT © 2024 Siddarth
