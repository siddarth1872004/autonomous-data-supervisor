"""
agents/visualization.py — LangGraph node: Plotly Chart Generation.

Retrieves the anomaly-annotated DataFrame from DataFrameStore and generates
an appropriate interactive Plotly chart based on data shape:

  - Datetime + numeric columns → Time Series with anomaly markers
  - Categorical + numeric      → Grouped Bar Chart with anomaly overlay
  - Multiple numeric columns   → Scatter Plot with anomaly coloring
  - Fallback                  → Summary Statistics Table

The figure is serialized to a JSON dict (via plotly's to_dict()) and stored
in state for the API to return to the frontend, where react-plotly.js renders
it as a fully interactive chart.
"""

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents.state import AgentState, DataFrameStore

logger = logging.getLogger(__name__)

# ── Design tokens matching the frontend dark theme ────────────────────────────
_BG = "rgba(13, 14, 22, 0.0)"
_GRID = "rgba(255,255,255,0.06)"
_NORMAL_COLOR = "#38bdf8"      # Sky blue for normal points
_ANOMALY_COLOR = "#f97316"     # Orange for anomalies
_BAR_COLORS = [
    "#38bdf8", "#818cf8", "#34d399", "#fb7185", "#fbbf24", "#a78bfa"
]
_FONT = dict(family="Inter, system-ui, sans-serif", color="#cbd5e1", size=13)
_LAYOUT_DEFAULTS = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_BG,
    font=_FONT,
    legend=dict(
        bgcolor="rgba(255,255,255,0.05)",
        bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1,
    ),
    margin=dict(l=60, r=30, t=60, b=60),
    xaxis=dict(
        gridcolor=_GRID,
        zerolinecolor=_GRID,
        showgrid=True,
    ),
    yaxis=dict(
        gridcolor=_GRID,
        zerolinecolor=_GRID,
        showgrid=True,
    ),
    hovermode="closest",
)


def _detect_datetime_cols(df: pd.DataFrame) -> list[str]:
    return [
        col for col in df.columns
        if pd.api.types.is_datetime64_any_dtype(df[col])
        or any(kw in col.lower() for kw in ("date", "timestamp", "time"))
    ]


def _get_display_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Strip internal _* columns and extract anomaly mask."""
    anomaly_mask = df.get("_is_anomaly", pd.Series([False] * len(df), index=df.index))
    display_df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    return display_df, anomaly_mask


# ── Chart type implementations ────────────────────────────────────────────────

def _time_series_chart(
    df: pd.DataFrame, date_col: str, value_cols: list[str], anomaly_mask: pd.Series
) -> go.Figure:
    """Multi-line time series with anomaly scatter overlay."""
    fig = make_subplots(
        rows=1, cols=1,
        subplot_titles=("",),
    )

    # Sort by date
    df = df.sort_values(date_col)

    for i, col in enumerate(value_cols[:4]):  # Max 4 lines
        color = _BAR_COLORS[i % len(_BAR_COLORS)]
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[col],
            mode="lines",
            name=col,
            line=dict(color=color, width=2),
            opacity=0.9,
            hovertemplate=f"<b>{col}</b>: %{{y:,.2f}}<br>Date: %{{x}}<extra></extra>",
        ))

    # Anomaly markers on top of the first value column
    if value_cols and anomaly_mask.any():
        anomaly_df = df[anomaly_mask.values[:len(df)] if len(anomaly_mask) == len(df) else df.index.isin(anomaly_mask[anomaly_mask].index)]
        if not anomaly_df.empty:
            fig.add_trace(go.Scatter(
                x=anomaly_df[date_col],
                y=anomaly_df[value_cols[0]],
                mode="markers",
                name="Anomaly",
                marker=dict(
                    color=_ANOMALY_COLOR,
                    size=10,
                    symbol="x",
                    line=dict(width=2, color=_ANOMALY_COLOR),
                ),
                hovertemplate="<b>ANOMALY DETECTED</b><br>Value: %{y:,.2f}<br>Date: %{x}<extra></extra>",
            ))

    fig.update_layout(
        title=dict(text="Time Series Analysis", font=dict(size=16, color="#e2e8f0")),
        **_LAYOUT_DEFAULTS,
    )
    return fig


def _bar_chart(
    df: pd.DataFrame, cat_col: str, val_col: str, anomaly_mask: pd.Series
) -> go.Figure:
    """Grouped bar chart with anomaly highlighting."""
    grouped = df.groupby(cat_col)[val_col].agg(["sum", "mean", "count"]).reset_index()
    grouped.columns = [cat_col, "Total", "Average", "Count"]

    colors = [
        _ANOMALY_COLOR if (df[df[cat_col] == row[cat_col]].index.isin(
            anomaly_mask[anomaly_mask].index
        ).any()) else _NORMAL_COLOR
        for _, row in grouped.iterrows()
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grouped[cat_col],
        y=grouped["Total"],
        name="Total",
        marker=dict(
            color=colors,
            line=dict(color="rgba(255,255,255,0.1)", width=1),
        ),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Total: %{y:,.2f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=dict(text="Category Analysis", font=dict(size=16, color="#e2e8f0")),
        **_LAYOUT_DEFAULTS,
        bargap=0.25,
    )
    return fig


def _scatter_chart(
    df: pd.DataFrame, x_col: str, y_col: str, anomaly_mask: pd.Series
) -> go.Figure:
    """Scatter plot with anomaly color coding."""
    normal_df = df[~anomaly_mask.reindex(df.index, fill_value=False)]
    anomaly_df = df[anomaly_mask.reindex(df.index, fill_value=False)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=normal_df[x_col],
        y=normal_df[y_col],
        mode="markers",
        name="Normal",
        marker=dict(color=_NORMAL_COLOR, size=7, opacity=0.7),
        hovertemplate=f"<b>Normal</b><br>{x_col}: %{{x:,.2f}}<br>{y_col}: %{{y:,.2f}}<extra></extra>",
    ))
    if not anomaly_df.empty:
        fig.add_trace(go.Scatter(
            x=anomaly_df[x_col],
            y=anomaly_df[y_col],
            mode="markers",
            name="Anomaly",
            marker=dict(
                color=_ANOMALY_COLOR, size=11,
                symbol="x", line=dict(width=2),
            ),
            hovertemplate=f"<b>ANOMALY</b><br>{x_col}: %{{x:,.2f}}<br>{y_col}: %{{y:,.2f}}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="Anomaly Scatter Plot", font=dict(size=16, color="#e2e8f0")),
        xaxis_title=x_col,
        yaxis_title=y_col,
        **_LAYOUT_DEFAULTS,
    )
    return fig


def _table_figure(df: pd.DataFrame) -> go.Figure:
    """Fallback: render first 50 rows as a styled table."""
    sample = df.head(50)
    fig = go.Figure(
        data=[go.Table(
            header=dict(
                values=[f"<b>{c}</b>" for c in sample.columns],
                fill_color="rgba(56,189,248,0.15)",
                align="left",
                font=dict(color="#e2e8f0", size=13),
                line_color="rgba(255,255,255,0.1)",
            ),
            cells=dict(
                values=[sample[c].tolist() for c in sample.columns],
                fill_color="rgba(255,255,255,0.03)",
                align="left",
                font=dict(color="#94a3b8", size=12),
                line_color="rgba(255,255,255,0.05)",
            ),
        )]
    )
    fig.update_layout(
        title=dict(text="Query Results", font=dict(size=16, color="#e2e8f0")),
        paper_bgcolor=_BG,
        font=_FONT,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


# ── Main node function ────────────────────────────────────────────────────────

def visualization_node(state: AgentState) -> dict:
    """LangGraph node: generates a Plotly figure from the annotated DataFrame."""
    df_key = state.get("dataframe_key")

    if not df_key:
        return {"plotly_figure": None, "final_summary": state.get("data_summary", "")}

    store = DataFrameStore.get_instance()
    df = store.get(df_key)

    # Clean up memory after retrieving
    store.delete(df_key)

    if df is None or df.empty:
        return {"plotly_figure": None}

    display_df, anomaly_mask = _get_display_df(df)
    numeric_cols = display_df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = display_df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = _detect_datetime_cols(display_df)

    try:
        if datetime_cols and numeric_cols:
            fig = _time_series_chart(display_df, datetime_cols[0], numeric_cols, anomaly_mask)
        elif categorical_cols and numeric_cols:
            fig = _bar_chart(display_df, categorical_cols[0], numeric_cols[0], anomaly_mask)
        elif len(numeric_cols) >= 2:
            fig = _scatter_chart(display_df, numeric_cols[0], numeric_cols[1], anomaly_mask)
        else:
            fig = _table_figure(display_df)

        figure_dict = fig.to_dict()
        logger.info("[visualization] Chart generated successfully.")
        return {"plotly_figure": figure_dict}

    except Exception as exc:
        logger.exception("[visualization] Chart generation failed: %s", exc)
        # Fallback to table
        try:
            fig = _table_figure(display_df)
            return {"plotly_figure": fig.to_dict()}
        except Exception:
            return {"plotly_figure": None}
