"""
agents/ml_analysis.py — LangGraph node: Anomaly Detection.

Retrieves the raw DataFrame from DataFrameStore, runs Scikit-learn
IsolationForest on numeric features, and annotates the DataFrame with
anomaly flags and scores in-place (modifying the store entry).

Returns a compact anomaly summary to state for LLM narrative generation.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from agents.state import AgentState, DataFrameStore

logger = logging.getLogger(__name__)

# IsolationForest contamination: expected fraction of anomalies in the data.
# 0.1 = assume up to 10% of rows may be anomalous (reasonable default).
_CONTAMINATION = 0.1
_MIN_ROWS_FOR_ML = 10   # Need at least this many rows to fit a model


def _run_isolation_forest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run IsolationForest on all numeric columns.

    Adds two columns to the DataFrame:
      _is_anomaly (bool): True if the row is flagged as an anomaly.
      _anomaly_score (float): Lower score = more anomalous.
    """
    df = df.copy()

    numeric_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if not col.startswith("_")
    ]

    if not numeric_cols:
        df["_is_anomaly"] = False
        df["_anomaly_score"] = 0.0
        return df

    # Impute missing values with column mean before scaling
    feature_matrix = df[numeric_cols].fillna(df[numeric_cols].mean())

    # Standardize features (IsolationForest is scale-sensitive)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(feature_matrix)

    clf = IsolationForest(
        contamination=_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    predictions = clf.fit_predict(scaled)   # -1 = anomaly, 1 = normal
    scores = clf.score_samples(scaled)      # lower = more anomalous

    df["_is_anomaly"] = predictions == -1
    df["_anomaly_score"] = np.round(scores, 4)

    return df


def _build_anomaly_summary(df: pd.DataFrame) -> str:
    """Build a human-readable summary of detected anomalies for LLM narration."""
    anomalies = df[df["_is_anomaly"]]
    n_anomalies = len(anomalies)
    n_total = len(df)
    pct = (n_anomalies / n_total * 100) if n_total > 0 else 0

    lines = [
        f"Anomaly Detection Results ({n_anomalies} / {n_total} rows flagged, {pct:.1f}%):",
    ]

    numeric_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if not c.startswith("_")
    ]

    if n_anomalies > 0 and numeric_cols:
        lines.append("\nAnomaly vs Normal Comparison:")
        for col in numeric_cols[:5]:
            normal_mean = df[~df["_is_anomaly"]][col].mean()
            anomaly_mean = anomalies[col].mean()
            if normal_mean != 0:
                delta_pct = ((anomaly_mean - normal_mean) / abs(normal_mean)) * 100
                direction = "HIGHER" if delta_pct > 0 else "LOWER"
                lines.append(
                    f"  {col}: anomaly mean={anomaly_mean:.2f} vs normal mean={normal_mean:.2f} "
                    f"({abs(delta_pct):.0f}% {direction})"
                )

    return "\n".join(lines)


def ml_analysis_node(state: AgentState) -> dict:
    """LangGraph node: runs IsolationForest anomaly detection on the query results."""
    df_key = state.get("dataframe_key")

    if not df_key:
        logger.warning("[ml_analysis] No dataframe_key in state; skipping ML.")
        return {
            "anomaly_count": 0,
            "anomaly_indices": [],
            "anomaly_summary": "No data available for analysis.",
        }

    store = DataFrameStore.get_instance()
    df = store.get(df_key)

    if df is None or df.empty:
        return {
            "anomaly_count": 0,
            "anomaly_indices": [],
            "anomaly_summary": "Dataset is empty.",
        }

    if len(df) < _MIN_ROWS_FOR_ML:
        logger.info("[ml_analysis] Too few rows (%d) for IsolationForest; skipping.", len(df))
        df["_is_anomaly"] = False
        df["_anomaly_score"] = 0.0
        store._store[df_key] = df  # Update in-place
        return {
            "anomaly_count": 0,
            "anomaly_indices": [],
            "anomaly_summary": f"Dataset has only {len(df)} rows (minimum {_MIN_ROWS_FOR_ML} required for ML analysis).",
        }

    logger.info("[ml_analysis] Running IsolationForest on %d rows...", len(df))

    annotated_df = _run_isolation_forest(df)

    # Update the DataFrameStore entry in-place so visualization node gets annotations
    store._store[df_key] = annotated_df

    anomaly_indices = annotated_df.index[annotated_df["_is_anomaly"]].tolist()
    summary = _build_anomaly_summary(annotated_df)

    logger.info("[ml_analysis] Detected %d anomalies.", len(anomaly_indices))

    return {
        "anomaly_count": len(anomaly_indices),
        "anomaly_indices": anomaly_indices,
        "anomaly_summary": summary,
    }
