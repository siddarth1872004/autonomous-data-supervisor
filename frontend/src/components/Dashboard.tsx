import React, { useEffect, useRef } from "react";
import type { QueryResponse } from "../api/client";
import { AnomalyBadge } from "./AnomalyBadge";

interface DashboardProps {
  result: QueryResponse;
}

// Local interface for the dynamically loaded Plotly UMD bundle
interface PlotlyWindow {
  Plotly?: {
    newPlot(el: HTMLElement, data: unknown[], layout?: unknown, config?: unknown): void;
  };
}

export const Dashboard: React.FC<DashboardProps> = ({ result }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const hasChart = result.plotly_figure != null;
  const hasError = result.error_message != null;

  // Dynamically load Plotly and render the figure
  useEffect(() => {
    if (!hasChart || !chartRef.current || !result.plotly_figure) return;

    let cancelled = false;

    // Plotly is loaded as a UMD bundle from CDN with Subresource Integrity (SRI).
    // TODO(security): Update the SRI hash when upgrading plotly.js version.
    // Generate new hash with: curl -s https://cdn.plot.ly/plotly-X.Y.Z.min.js | openssl dgst -sha384 -binary | openssl base64
    const getPlotly = () => (window as unknown as PlotlyWindow).Plotly;

    const render = async () => {
      if (!getPlotly()) {
        await new Promise<void>((resolve, reject) => {
          const script = document.createElement("script");
          script.src = "https://cdn.plot.ly/plotly-2.32.0.min.js";
          // SRI hash for plotly-2.32.0.min.js — update when upgrading version
          script.integrity = "sha384-T0gO5cMaXbT/gDa+blxbkPCPPHpD1e0BknOe/5TBTlqNyijSMqMXEJJFt3tT0Ld";
          script.crossOrigin = "anonymous";
          script.onload = () => resolve();
          script.onerror = () => reject(new Error("Failed to load Plotly"));
          document.head.appendChild(script);
        });
      }
      if (!cancelled && chartRef.current) {
        const fig = result.plotly_figure!;
        const layout = {
          ...(fig.layout as Record<string, unknown>),
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          autosize: true,
        };
        getPlotly()?.newPlot(
          chartRef.current,
          (fig.data as unknown[]) || [],
          layout,
          {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
          }
        );
      }
    };

    render();
    return () => {
      cancelled = true;
    };
  }, [result.plotly_figure, hasChart]);

  return (
    <div className="dashboard animate-fade-in">
      {/* Stats Row */}
      <div className="dashboard-stats">
        <StatCard
          label="Rows Retrieved"
          value={result.row_count.toLocaleString()}
          icon="📊"
          color="var(--accent-cyan)"
        />
        <StatCard
          label="Anomalies"
          value={result.anomaly_count.toString()}
          icon="⚠️"
          color={result.anomaly_count > 0 ? "var(--accent-orange)" : "var(--accent-green)"}
          highlight={result.anomaly_count > 0}
        />
        {result.row_count > 0 && (
          <StatCard
            label="Anomaly Rate"
            value={`${((result.anomaly_count / result.row_count) * 100).toFixed(1)}%`}
            icon="🔍"
            color="var(--accent-purple)"
          />
        )}

        <div className="stat-card glass-card" style={{ alignItems: "flex-start" }}>
          <span className="stat-label">Detection Status</span>
          <AnomalyBadge count={result.anomaly_count} total={result.row_count} />
        </div>
      </div>

      {/* SQL query display */}
      {result.sql_query && (
        <div className="glass-card dashboard-section">
          <div className="section-header">
            <span className="section-icon">⚡</span>
            <span className="section-title">Generated SQL</span>
            <span className="badge badge-green" style={{ marginLeft: "auto" }}>Read-Only</span>
          </div>
          <pre className="code-block">{result.sql_query}</pre>
        </div>
      )}

      {/* Plotly Chart */}
      {hasChart && (
        <div className="glass-card dashboard-section">
          <div className="section-header">
            <span className="section-icon">📈</span>
            <span className="section-title">Interactive Dashboard</span>
            <span className="badge badge-cyan" style={{ marginLeft: "auto" }}>
              {result.anomaly_count > 0 ? "Anomalies Highlighted" : "Clean Data"}
            </span>
          </div>
          <div ref={chartRef} className="plotly-container" id="plotly-chart" />
        </div>
      )}

      {/* Anomaly Summary */}
      {result.anomaly_summary && result.anomaly_count > 0 && (
        <div className="glass-card dashboard-section">
          <div className="section-header">
            <span className="section-icon">🔬</span>
            <span className="section-title">ML Analysis Report</span>
          </div>
          <pre className="anomaly-summary">{result.anomaly_summary}</pre>
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <div className="glass-card dashboard-section dashboard-error">
          <div className="section-header">
            <span className="section-icon">❌</span>
            <span className="section-title" style={{ color: "var(--accent-red)" }}>
              Pipeline Error
            </span>
          </div>
          <p className="error-text">{result.error_message}</p>
        </div>
      )}

      <style>{`
        .dashboard {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }
        .dashboard-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 10px;
        }
        .stat-card {
          padding: 14px 16px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .stat-label {
          font-size: 0.7rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-weight: 600;
        }
        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }
        .dashboard-section {
          padding: 16px 18px;
        }
        .section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
        }
        .section-icon {
          font-size: 1rem;
        }
        .section-title {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .plotly-container {
          width: 100%;
          min-height: 360px;
          border-radius: var(--radius-sm);
          overflow: hidden;
        }
        .anomaly-summary {
          font-family: "JetBrains Mono", monospace;
          font-size: 0.77rem;
          color: var(--text-secondary);
          white-space: pre-wrap;
          line-height: 1.7;
          background: rgba(0,0,0,0.2);
          padding: 12px;
          border-radius: var(--radius-sm);
          border: 1px solid rgba(249,115,22,0.15);
        }
        .dashboard-error {
          border-color: rgba(248,113,113,0.2);
        }
        .error-text {
          font-size: 0.83rem;
          color: var(--accent-red);
          opacity: 0.85;
        }
      `}</style>
    </div>
  );
};

interface StatCardProps {
  label: string;
  value: string;
  icon: string;
  color: string;
  highlight?: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, icon, color, highlight }) => (
  <div
    className="stat-card glass-card"
    style={highlight ? { borderColor: "rgba(249,115,22,0.25)", boxShadow: "0 0 16px rgba(249,115,22,0.08)" } : {}}
  >
    <span style={{ fontSize: "1.2rem" }}>{icon}</span>
    <span className="stat-label">{label}</span>
    <span className="stat-value" style={{ color }}>
      {value}
    </span>
  </div>
);


