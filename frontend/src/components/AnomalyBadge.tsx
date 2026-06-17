import React from "react";

interface AnomalyBadgeProps {
  count: number;
  total: number;
}

export const AnomalyBadge: React.FC<AnomalyBadgeProps> = ({ count, total }) => {
  if (total === 0) return null;

  const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";
  const severity =
    count === 0 ? "clean" : count < 5 ? "low" : count < 20 ? "medium" : "high";

  const config = {
    clean: {
      icon: (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
      label: "No Anomalies",
      className: "badge badge-green",
      glow: "rgba(52, 211, 153, 0.15)",
    },
    low: {
      icon: (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
      label: `${count} Anomaly`,
      className: "badge badge-cyan",
      glow: "rgba(56, 189, 248, 0.15)",
    },
    medium: {
      icon: (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
      label: `${count} Anomalies`,
      className: "badge badge-orange",
      glow: "rgba(249, 115, 22, 0.15)",
    },
    high: {
      icon: (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
      label: `${count} Anomalies`,
      className: "badge badge-red",
      glow: "rgba(248, 113, 113, 0.15)",
    },
  }[severity];

  return (
    <div className="anomaly-badge-container">
      <div
        className={config.className}
        style={{ boxShadow: `0 0 12px ${config.glow}` }}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
        {count > 0 && (
          <span style={{ opacity: 0.7 }}>({pct}%)</span>
        )}
      </div>

      {count > 0 && (
        <div className="anomaly-bar">
          <div
            className="anomaly-bar-fill"
            style={{
              width: `${Math.min(100, parseFloat(pct))}%`,
              background:
                severity === "high"
                  ? "var(--accent-red)"
                  : severity === "medium"
                  ? "var(--accent-orange)"
                  : "var(--accent-cyan)",
            }}
          />
        </div>
      )}

      <style>{`
        .anomaly-badge-container {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .anomaly-bar {
          height: 3px;
          background: rgba(255,255,255,0.06);
          border-radius: 99px;
          overflow: hidden;
        }
        .anomaly-bar-fill {
          height: 100%;
          border-radius: 99px;
          transition: width 800ms cubic-bezier(0.4, 0, 0.2, 1);
        }
      `}</style>
    </div>
  );
};
