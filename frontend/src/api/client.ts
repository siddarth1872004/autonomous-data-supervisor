/**
 * api/client.ts — Type-safe API client for the FastAPI BFF backend.
 *
 * Security:
 *  - API key sent via X-API-Key header (NOT localStorage or sessionStorage).
 *  - All requests go to the backend BFF — LLM keys never reach the browser.
 *  - VITE_API_KEY is the backend's API_SECRET_KEY, NOT the Google/OpenAI key.
 */

export interface QueryResponse {
  sql_query: string | null;
  row_count: number;
  anomaly_count: number;
  anomaly_summary: string | null;
  plotly_figure: Record<string, unknown> | null;
  data_summary: string | null;
  error_message: string | null;
}

export interface SchemaResponse {
  schema: string;
}

export interface ExamplesResponse {
  examples: string[];
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
// NOTE: VITE_API_KEY is the backend auth key only — Google/OpenAI keys never touch the browser.
const API_KEY = import.meta.env.VITE_API_KEY || "";

function buildHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async runQuery(question: string): Promise<QueryResponse> {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ question }),
    });
    return handleResponse<QueryResponse>(res);
  },

  async getExamples(): Promise<ExamplesResponse> {
    const res = await fetch(`${API_BASE}/api/examples`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    return handleResponse<ExamplesResponse>(res);
  },

  async health(): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/health`);
    return handleResponse<{ status: string }>(res);
  },
};
