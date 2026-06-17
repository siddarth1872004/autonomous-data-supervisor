import React, { useEffect, useRef, useState } from "react";
import type { QueryResponse } from "../api/client";
import { api } from "../api/client";
import { AgentSteps, type AgentStep, type StepStatus } from "./AgentSteps";
import { Dashboard } from "./Dashboard";

interface Message {
  id: string;
  type: "user" | "agent" | "error";
  content: string;
  result?: QueryResponse;
  timestamp: Date;
}

const INITIAL_STEPS: AgentStep[] = [
  { id: "sql",  label: "Text-to-SQL",  icon: "🧠", description: "Translating your question into SQL...", status: "pending" },
  { id: "exec", label: "SQL Executor", icon: "⚡", description: "Executing query safely...", status: "pending" },
  { id: "ml",   label: "ML Analysis",  icon: "🔍", description: "Running anomaly detection...", status: "pending" },
  { id: "viz",  label: "Visualization", icon: "📈", description: "Generating dashboard...", status: "pending" },
];

function updateStep(steps: AgentStep[], id: string, status: StepStatus): AgentStep[] {
  return steps.map((s) => (s.id === id ? { ...s, status } : s));
}

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>(INITIAL_STEPS);
  const [examples, setExamples] = useState<string[]>([]);
  const [activeResult, setActiveResult] = useState<QueryResponse | null>(null);
  const [showSteps, setShowSteps] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load example queries on mount
  useEffect(() => {
    api.getExamples().then((r) => setExamples(r.examples)).catch(() => {});
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const simulateAgentSteps = async (result: QueryResponse) => {
    const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
    setShowSteps(true);
    setSteps(INITIAL_STEPS.map((s) => ({ ...s, status: "pending" })));

    setSteps((prev) => updateStep(prev, "sql", "active"));
    await delay(500);
    setSteps((prev) => updateStep(prev, "sql", result.sql_query ? "done" : "error"));

    await delay(200);
    setSteps((prev) => updateStep(prev, "exec", "active"));
    await delay(600);
    setSteps((prev) =>
      updateStep(prev, "exec", result.row_count > 0 ? "done" : result.error_message ? "error" : "done")
    );

    await delay(200);
    setSteps((prev) => updateStep(prev, "ml", "active"));
    await delay(800);
    setSteps((prev) => updateStep(prev, "ml", "done"));

    await delay(200);
    setSteps((prev) => updateStep(prev, "viz", "active"));
    await delay(500);
    setSteps((prev) => updateStep(prev, "viz", result.plotly_figure ? "done" : "done"));
  };

  const handleSubmit = async (question?: string) => {
    const q = (question || input).trim();
    if (!q || isLoading) return;

    setInput("");
    setIsLoading(true);
    setActiveResult(null);

    const userMsg: Message = {
      id: Date.now().toString(),
      type: "user",
      content: q,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      // Animate steps in parallel with the real API call
      const [result] = await Promise.all([
        api.runQuery(q),
        simulateAgentSteps({ sql_query: null, row_count: 0, anomaly_count: 0, anomaly_summary: null, plotly_figure: null, data_summary: null, error_message: null }),
      ]);

      setActiveResult(result);

      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        type: result.error_message ? "error" : "agent",
        content: result.error_message
          ? result.error_message
          : `Query complete. Found **${result.row_count.toLocaleString()} rows** with **${result.anomaly_count} anomalies** detected.`,
        result,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        type: "error",
        content: err instanceof Error ? err.message : "An unexpected error occurred.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setShowSteps(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-layout">
      {/* Left panel: Chat */}
      <div className="chat-panel glass-card">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-left">
            <div className="chat-logo">
              <span>🤖</span>
            </div>
            <div>
              <h2 className="chat-title">Data Supervisor</h2>
              <p className="chat-subtitle">ReAct Agent Pipeline</p>
            </div>
          </div>
          <div className="badge badge-green">
            <span className="status-dot" />
            Live
          </div>
        </div>

        <div className="divider" />

        {/* Messages */}
        <div className="messages-area" id="messages-area">
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">💬</div>
              <h3 className="empty-title">Ask anything about your data</h3>
              <p className="empty-desc">
                The agent will translate your question into SQL, detect anomalies with ML, and build an interactive dashboard — automatically.
              </p>
              {examples.length > 0 && (
                <div className="example-queries">
                  <p className="examples-label">Try these:</p>
                  <div className="examples-grid">
                    {examples.slice(0, 4).map((ex) => (
                      <button
                        key={ex}
                        className="example-chip"
                        onClick={() => handleSubmit(ex)}
                        id={`example-${ex.slice(0, 20).replace(/\s/g, "-")}`}
                        type="button"
                      >
                        {ex}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message message-${msg.type} animate-fade-in`}
            >
              <div className="message-avatar">
                {msg.type === "user" ? "👤" : msg.type === "error" ? "❌" : "🤖"}
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <span className="message-role">
                    {msg.type === "user" ? "You" : "Data Supervisor"}
                  </span>
                  <span className="message-time">
                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <div
                  className={`message-content ${msg.type === "error" ? "message-content-error" : ""}`}
                >
                  {/* Render bold markdown */}
                  {msg.content.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
                    part.startsWith("**") && part.endsWith("**")
                      ? <strong key={i}>{part.slice(2, -2)}</strong>
                      : <span key={i}>{part}</span>
                  )}
                </div>

                {/* Agent pipeline steps inline */}
                {msg.type === "agent" && showSteps && msg.id === messages.filter(m => m.type !== "user").pop()?.id && (
                  <div className="message-steps">
                    <AgentSteps steps={steps} />
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message message-agent animate-fade-in">
              <div className="message-avatar">🤖</div>
              <div className="message-body">
                <div className="message-meta">
                  <span className="message-role">Data Supervisor</span>
                </div>
                <div className="thinking-indicator">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span style={{ marginLeft: 8, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    Running agent pipeline...
                  </span>
                </div>
                {showSteps && <AgentSteps steps={steps} />}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="input-area">
          <div className="input-wrapper">
            <textarea
              ref={inputRef}
              id="query-input"
              className="query-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your data... (Enter to send, Shift+Enter for newline)"
              rows={2}
              disabled={isLoading}
              maxLength={1000}
            />
            <button
              id="send-button"
              className="btn btn-primary send-button"
              onClick={() => handleSubmit()}
              disabled={isLoading || !input.trim()}
              type="button"
            >
              {isLoading ? <span className="loading-spinner" /> : <span>→</span>}
            </button>
          </div>
          <p className="input-hint">
            Powered by LangGraph · Gemini · Isolation Forest · Plotly
          </p>
        </div>
      </div>

      {/* Right panel: Dashboard */}
      <div className="dashboard-panel">
        {activeResult ? (
          <Dashboard result={activeResult} />
        ) : (
          <div className="glass-card dashboard-empty">
            <div className="dashboard-empty-content">
              <span className="dashboard-empty-icon">📊</span>
              <h3>Dashboard</h3>
              <p>Ask a question to see your interactive analytics dashboard here.</p>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .chat-layout {
          display: grid;
          grid-template-columns: 420px 1fr;
          gap: 16px;
          height: calc(100vh - 32px);
          padding: 16px;
          position: relative;
          z-index: 1;
        }
        .chat-panel {
          display: flex;
          flex-direction: column;
          overflow: hidden;
          padding: 0;
        }
        .chat-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 18px 20px 14px;
        }
        .chat-header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .chat-logo {
          width: 40px;
          height: 40px;
          border-radius: 12px;
          background: linear-gradient(135deg, rgba(56,189,248,0.2), rgba(129,140,248,0.2));
          border: 1px solid rgba(56,189,248,0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.2rem;
        }
        .chat-title {
          font-size: 0.95rem;
          font-weight: 700;
          color: var(--text-primary);
        }
        .chat-subtitle {
          font-size: 0.72rem;
          color: var(--text-muted);
          margin-top: 1px;
        }
        .status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent-green);
          animation: pulse-dot 2s ease infinite;
          display: inline-block;
        }
        .messages-area {
          flex: 1;
          overflow-y: auto;
          padding: 12px 16px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 32px 16px;
          gap: 12px;
          margin: auto 0;
        }
        .empty-icon {
          font-size: 2.5rem;
          filter: drop-shadow(0 0 20px rgba(56,189,248,0.3));
        }
        .empty-title {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .empty-desc {
          font-size: 0.8rem;
          color: var(--text-muted);
          line-height: 1.6;
          max-width: 280px;
        }
        .example-queries {
          width: 100%;
          margin-top: 8px;
        }
        .examples-label {
          font-size: 0.72rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-weight: 600;
          margin-bottom: 8px;
          text-align: left;
        }
        .examples-grid {
          display: grid;
          gap: 6px;
        }
        .example-chip {
          display: block;
          width: 100%;
          text-align: left;
          padding: 9px 14px;
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-md);
          color: var(--text-secondary);
          font-size: 0.78rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          font-family: inherit;
          line-height: 1.4;
        }
        .example-chip:hover {
          background: var(--glass-bg-hover);
          border-color: var(--accent-cyan-dim);
          color: var(--text-primary);
          transform: translateX(4px);
        }
        .message {
          display: grid;
          grid-template-columns: 32px 1fr;
          gap: 10px;
          align-items: start;
        }
        .message-user {
          direction: ltr;
        }
        .message-avatar {
          width: 32px;
          height: 32px;
          border-radius: 10px;
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.9rem;
          flex-shrink: 0;
        }
        .message-body {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .message-meta {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .message-role {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
        .message-time {
          font-size: 0.68rem;
          color: var(--text-muted);
        }
        .message-content {
          font-size: 0.84rem;
          color: var(--text-primary);
          line-height: 1.6;
          background: var(--glass-bg);
          padding: 10px 14px;
          border-radius: var(--radius-md);
          border: 1px solid var(--glass-border);
        }
        .message-user .message-content {
          background: rgba(56,189,248,0.08);
          border-color: rgba(56,189,248,0.2);
        }
        .message-content-error {
          background: rgba(248,113,113,0.08) !important;
          border-color: rgba(248,113,113,0.2) !important;
          color: var(--accent-red) !important;
        }
        .message-steps {
          margin-top: 8px;
          padding: 10px 12px;
          background: rgba(0,0,0,0.15);
          border-radius: var(--radius-md);
          border: 1px solid var(--glass-border);
        }
        .thinking-indicator {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 10px 14px;
          background: var(--glass-bg);
          border-radius: var(--radius-md);
          border: 1px solid var(--glass-border);
          margin-bottom: 8px;
        }
        .thinking-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent-cyan);
          animation: thinking-bounce 1.2s ease infinite;
        }
        .thinking-dot:nth-child(2) { animation-delay: 0.2s; }
        .thinking-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes thinking-bounce {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(-5px); opacity: 1; }
        }
        .input-area {
          padding: 12px 16px 16px;
          border-top: 1px solid var(--glass-border);
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .input-wrapper {
          display: flex;
          gap: 10px;
          align-items: flex-end;
        }
        .query-input {
          flex: 1;
          background: rgba(0,0,0,0.25);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          font-family: inherit;
          font-size: 0.85rem;
          padding: 10px 14px;
          resize: none;
          outline: none;
          transition: border-color var(--transition-fast);
          line-height: 1.5;
        }
        .query-input:focus {
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px var(--accent-cyan-dim);
        }
        .query-input::placeholder {
          color: var(--text-muted);
        }
        .query-input:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .send-button {
          flex-shrink: 0;
          width: 42px;
          height: 42px;
          padding: 0;
          justify-content: center;
          font-size: 1.1rem;
        }
        .input-hint {
          font-size: 0.68rem;
          color: var(--text-muted);
          text-align: center;
        }
        .dashboard-panel {
          overflow-y: auto;
          padding-right: 2px;
        }
        .dashboard-empty {
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .dashboard-empty-content {
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          color: var(--text-muted);
        }
        .dashboard-empty-icon {
          font-size: 3rem;
          opacity: 0.4;
        }
        .dashboard-empty-content h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
        .dashboard-empty-content p {
          font-size: 0.82rem;
          max-width: 260px;
          line-height: 1.6;
        }

        @media (max-width: 900px) {
          .chat-layout {
            grid-template-columns: 1fr;
            grid-template-rows: auto 1fr;
            height: auto;
            overflow-y: auto;
          }
          .chat-panel {
            height: 60vh;
          }
          .dashboard-panel {
            max-height: none;
          }
        }
      `}</style>
    </div>
  );
};
