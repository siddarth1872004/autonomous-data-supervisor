import React from "react";
import "./index.css";
import { ChatInterface } from "./components/ChatInterface";

const App: React.FC = () => {
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-brand">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--accent-cyan)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ filter: "drop-shadow(0 0 8px rgba(56,189,248,0.4))" }}
            >
              <ellipse cx="12" cy="5" rx="9" ry="3" />
              <path d="M3 5v6c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              <path d="M3 11v6c0 1.66 4 3 9 3s9-1.34 9-3v-6" />
            </svg>
            <div>
              <span className="app-brand-name">Autonomous Data Supervisor</span>
              <span className="app-brand-tagline">
                LangGraph · Text-to-SQL · Isolation Forest · Plotly
              </span>
            </div>
          </div>

          <nav className="app-nav">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
              id="api-docs-link"
            >
              API Docs ↗
            </a>
            <a
              href="https://github.com/siddarth1872004/autonomous-data-supervisor"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
              id="github-link"
            >
              GitHub ↗
            </a>
          </nav>
        </div>
      </header>

      {/* Main app */}
      <main>
        <ChatInterface />
      </main>

      <style>{`
        .app-header {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          background: rgba(8,10,18,0.85);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border-bottom: 1px solid var(--glass-border);
        }
        .app-header-inner {
          max-width: 1600px;
          margin: 0 auto;
          padding: 10px 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .app-brand {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .app-brand-icon {
          font-size: 1.4rem;
          filter: drop-shadow(0 0 8px rgba(56,189,248,0.4));
        }
        .app-brand-name {
          display: block;
          font-size: 0.9rem;
          font-weight: 700;
          background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          line-height: 1.2;
        }
        .app-brand-tagline {
          display: block;
          font-size: 0.65rem;
          color: var(--text-muted);
          letter-spacing: 0.04em;
          font-weight: 400;
          margin-top: 2px;
        }
        .app-nav {
          display: flex;
          gap: 8px;
        }
        main {
          padding-top: 58px;
        }
      `}</style>
    </>
  );
};

export default App;
