import React from "react";

export type StepStatus = "pending" | "active" | "done" | "error" | "skipped";

export interface AgentStep {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  status: StepStatus;
}

interface AgentStepsProps {
  steps: AgentStep[];
}

const statusStyles: Record<StepStatus, { dot: string; text: string; bg: string }> = {
  pending: { dot: "#334155", text: "#475569", bg: "transparent" },
  active:  { dot: "#38bdf8", text: "#e2e8f0", bg: "rgba(56,189,248,0.06)" },
  done:    { dot: "#34d399", text: "#94a3b8", bg: "transparent" },
  error:   { dot: "#f87171", text: "#f87171", bg: "rgba(248,113,113,0.06)" },
  skipped: { dot: "#334155", text: "#475569", bg: "transparent" },
};

export const AgentSteps: React.FC<AgentStepsProps> = ({ steps }) => {
  return (
    <div className="agent-steps">
      {steps.map((step, index) => {
        const style = statusStyles[step.status];
        const isLast = index === steps.length - 1;

        return (
          <div key={step.id} className="agent-step-item">
            {/* Connector line */}
            {!isLast && (
              <div
                className="agent-step-line"
                style={{
                  background:
                    step.status === "done" ? "var(--accent-green)" : "var(--glass-border)",
                }}
              />
            )}

            {/* Dot */}
            <div
              className="agent-step-dot"
              style={{ background: style.dot, boxShadow: step.status === "active" ? `0 0 10px ${style.dot}` : "none" }}
            >
              {step.status === "active" && (
                <span
                  style={{
                    position: "absolute",
                    inset: -3,
                    borderRadius: "50%",
                    border: `1px solid ${style.dot}`,
                    animation: "pulse-ring 1.5s ease infinite",
                  }}
                />
              )}
              {step.status === "done" && (
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                  <path d="M1 4l2 2 4-4" stroke="#0d0f1a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </div>

            {/* Content */}
            <div
              className="agent-step-content"
              style={{
                background: style.bg,
                color: style.text,
                borderColor:
                  step.status === "active"
                    ? "rgba(56,189,248,0.2)"
                    : step.status === "error"
                    ? "rgba(248,113,113,0.2)"
                    : "transparent",
              }}
            >
              <div className="agent-step-header">
                <span className="agent-step-icon">{step.icon}</span>
                <span className="agent-step-label">{step.label}</span>
                {step.status === "active" && (
                  <span className="loading-spinner" style={{ marginLeft: "auto" }} />
                )}
                {step.status === "done" && (
                  <span style={{ marginLeft: "auto", color: "var(--accent-green)", fontSize: "0.75rem" }}>Done</span>
                )}
                {step.status === "error" && (
                  <span style={{ marginLeft: "auto", color: "var(--accent-red)", fontSize: "0.75rem" }}>Failed</span>
                )}
              </div>
              {(step.status === "active" || step.status === "error") && (
                <p className="agent-step-desc">{step.description}</p>
              )}
            </div>
          </div>
        );
      })}

      <style>{`
        .agent-steps {
          display: flex;
          flex-direction: column;
          gap: 0;
          padding: 8px 0;
        }
        .agent-step-item {
          position: relative;
          display: grid;
          grid-template-columns: 16px 1fr;
          gap: 12px;
          align-items: start;
          padding-bottom: 8px;
        }
        .agent-step-line {
          position: absolute;
          left: 7px;
          top: 20px;
          width: 2px;
          height: calc(100% - 12px);
          border-radius: 1px;
          transition: background 300ms;
        }
        .agent-step-dot {
          position: relative;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          margin-top: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          z-index: 1;
          transition: all 200ms;
        }
        .agent-step-content {
          padding: 8px 12px;
          border-radius: 8px;
          border: 1px solid transparent;
          transition: all 200ms;
        }
        .agent-step-header {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.82rem;
          font-weight: 500;
        }
        .agent-step-icon {
          font-size: 0.9rem;
        }
        .agent-step-label {
          font-weight: 500;
        }
        .agent-step-desc {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin-top: 4px;
          line-height: 1.5;
        }
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 1; }
          100% { transform: scale(1.8); opacity: 0; }
        }
      `}</style>
    </div>
  );
};
