from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Axle Process Monitor", page_icon="⚙️", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');
    :root {
        --ink: #162522;
        --muted: #65736f;
        --paper: #f4f6f2;
        --line: #dce3dc;
        --green: #146b52;
        --orange: #b84f24;
    }
    html, body, [class*="st-"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: var(--paper); color: var(--ink); }
    .block-container { padding-top: 2.2rem; max-width: 1440px; }
    h1, h2, h3 { color: var(--ink); letter-spacing: 0; }
    h1 { font-size: 2.15rem; font-weight: 700; }
    [data-testid="stMetric"] {
        background: #fff; border: 1px solid var(--line); border-radius: 6px;
        padding: 16px 18px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); }
    .eyebrow { color: var(--green); font: 500 0.76rem 'DM Mono', monospace;
        letter-spacing: 0; text-transform: uppercase; }
    .status-box { border-left: 4px solid var(--green); background: #e8f1ec;
        padding: 14px 18px; border-radius: 0 5px 5px 0; margin: 0.5rem 0 1.25rem; }
    .status-box.alert { border-left-color: var(--orange); background: #f8ece5; }
    .status-title { font-weight: 700; margin-bottom: 3px; }
    .status-copy { color: #43514d; }
    .date-time { color: var(--muted); font: 500 0.82rem 'DM Mono', monospace;
        text-align: right; padding-top: 0.65rem; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)


def find_trend(values: pd.Series, run_length: int = 7) -> set[int]:
    """Return row positions belonging to a run of consecutive rises or falls."""
    trend_positions: set[int] = set()
    numbers = values.tolist()
    for start in range(len(numbers) - run_length + 1):
        window = numbers[start : start + run_length]
        if all(left < right for left, right in zip(window, window[1:])) or all(
            left > right for left, right in zip(window, window[1:])
        ):
            trend_positions.update(range(start, start + run_length))
    return trend_positions


def make_chart(
    frame: pd.DataFrame,
    measurement: str,
    mean: float,
    stddev: float,
    outlier_positions: set[int],
    trend_positions: set[int],
) -> go.Figure:
    values = frame[measurement]
    x_values = frame["_serial_label"]
    outlier_mask = [position in outlier_positions for position in range(len(frame))]
    trend_mask = [
        position in trend_positions and position not in outlier_positions
        for position in range(len(frame))
    ]
    regular_mask = [
        position not in outlier_positions and position not in trend_positions
        for position in range(len(frame))
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=values,
            mode="lines",
            line={"color": "#b9c7c0", "width": 1.5},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    for mask, name, color, symbol, size in (
        (regular_mask, "In control", "#146b52", "circle", 8),
        (trend_mask, "Trend", "#d58a20", "diamond", 10),
        (outlier_mask, "Beyond 3σ", "#b84f24", "x", 12),
    ):
        indices = [position for position, include in enumerate(mask) if include]
        if indices:
            figure.add_trace(
                go.Scatter(
                    x=x_values.iloc[indices],
                    y=values.iloc[indices],
                    mode="markers",
                    name=name,
                    marker={"color": color, "symbol": symbol, "size": size},
                    customdata=frame["_serial_label"].iloc[indices],
                    hovertemplate="Serial: %{customdata}<br>" + measurement + ": %{y}<extra></extra>",
                )
            )

    lower_limit = mean - 3 * stddev
    upper_limit = mean + 3 * stddev
    for value, label, dash in (
        (mean, "Mean", "solid"),
        (upper_limit, "Upper limit (+3σ)", "dash"),
        (lower_limit, "Lower limit (-3σ)", "dash"),
    ):
        figure.add_hline(
            y=value,
            line_color="#000000",
            line_dash=dash,
            line_width=1.7,
            annotation_text=label,
            annotation_position="top left",
            annotation_font_color="#000000",
        )

    figure.update_layout(
        height=390,
        margin={"l": 12, "r": 18, "t": 26, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font={"family": "DM Sans, sans-serif", "color": "#000000", "size": 12},
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"color": "#000000"}},
        xaxis={
            "title": {"text": "Serial number (upload order)", "font": {"color": "#000000"}},
            "type": "category",
            "showgrid": False,
            "showline": True,
            "linecolor": "#000000",
            "linewidth": 1.5,
            "ticks": "outside",
            "tickcolor": "#000000",
            "ticklen": 5,
            "tickfont": {"color": "#000000"},
        },
        yaxis={
            "title": {"text": measurement.title(), "font": {"color": "#000000"}},
            "showline": True,
            "linecolor": "#000000",
            "linewidth": 1.5,
            "ticks": "outside",
            "tickcolor": "#000000",
            "ticklen": 5,
            "tickfont": {"color": "#000000"},
            "gridcolor": "#000000",
            "gridwidth": 0.6,
            "zeroline": True,
            "zerolinecolor": "#000000",
            "zerolinewidth": 1,
        },
        hovermode="closest",
    )
    return figure


#st.markdown('<div class="eyebrow"> \n\n Axle grinding / process control</div>', unsafe_allow_html=True)
title_col, date_col = st.columns([5, 1])
with title_col:
    st.title("Grinding Machine Performance Monitor")
with date_col:
    current_time = datetime.now(ZoneInfo("Asia/Kolkata"))
    st.markdown(
        f'<div class="date-time">{current_time:%d %b %Y}<br>{current_time:%H:%M:%S}</div>',
        unsafe_allow_html=True,
    )
st.write("Utility to review the axle journal dia measurements on Control Chart")

with st.sidebar:
    st.markdown("### Measurement file")
    uploaded_file = st.file_uploader(
        "Upload an Excel workbook", type=["xlsx", "xls"], help="Required columns: serial number, left, right."
    )
    st.caption("Expected columns: serial number, left, right")
    st.caption("Trend rule: 7 consecutive measurements, all increasing or all decreasing.")

if uploaded_file is None:
    st.info("Upload an Excel workbook to view the control charts and process recommendations.")
    st.stop()

try:
    workbook = pd.ExcelFile(uploaded_file)
    selected_sheet = st.selectbox("Worksheet", workbook.sheet_names) if len(workbook.sheet_names) > 1 else workbook.sheet_names[0]
    data = pd.read_excel(workbook, sheet_name=selected_sheet)
except Exception as error:
    st.error(f"Could not read this Excel workbook: {error}")
    st.stop()

data.columns = [str(column).strip().lower() for column in data.columns]
required_columns = ["serial number", "left", "right"]
missing_columns = [column for column in required_columns if column not in data.columns]
if missing_columns:
    st.error("Missing required column(s): " + ", ".join(missing_columns))
    st.stop()

data = data[required_columns].copy()
for column in ("left", "right"):
    data[column] = pd.to_numeric(data[column], errors="coerce")
data = data.dropna(subset=required_columns).reset_index(drop=True)
if data.empty:
    st.error("No complete rows with a serial number and numeric left/right values were found.")
    st.stop()

data["_serial_label"] = data["serial number"].astype(str)
statistics = {
    measurement: {
        "mean": float(data[measurement].mean()),
        "stddev": float(data[measurement].std(ddof=1)) if len(data) > 1 else float("nan"),
    }
    for measurement in ("left", "right")
}

if len(data) < 2:
    st.warning("At least two valid measurements are needed to calculate standard deviation and control limits.")
    st.stop()

analysis: dict[str, dict[str, object]] = {}
for measurement, summary in statistics.items():
    mean = summary["mean"]
    stddev = summary["stddev"]
    lower_limit = mean - 3 * stddev
    upper_limit = mean + 3 * stddev
    outliers = set(data.index[(data[measurement] < lower_limit) | (data[measurement] > upper_limit)])
    trends = find_trend(data[measurement])
    analysis[measurement] = {
        **summary,
        "lower_limit": lower_limit,
        "upper_limit": upper_limit,
        "outliers": outliers,
        "trends": trends,
    }

outlier_count = sum(len(result["outliers"]) for result in analysis.values())
trend_sides = [name for name, result in analysis.items() if result["trends"]]
left_col, right_col, sample_col = st.columns(3)
left_col.metric("Left mean", f"{statistics['left']['mean']:.3f}")
right_col.metric("Right mean", f"{statistics['right']['mean']:.3f}")
sample_col.metric("Valid measurements", f"{len(data):,}")

if outlier_count:
    st.markdown(
        f'<div class="status-box alert"><div class="status-title">STOP MACHINE · {outlier_count} point(s) beyond 3σ</div>'
        '<div class="status-copy">Stop the machine and hand over to maintenance for inspection before resuming production.</div></div>',
        unsafe_allow_html=True,
    )
elif trend_sides:
    sides = " and ".join(side.title() for side in trend_sides)
    st.markdown(
        f'<div class="status-box alert"><div class="status-title">Possible process trend · {sides}</div>'
        '<div class="status-copy">Check setup, tooling, and measurement conditions; inform the process owner and monitor the next measurements closely.</div></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-box"><div class="status-title">No 3σ outliers or sustained trend detected</div>'
        '<div class="status-copy">Continue normal operation and routine monitoring.</div></div>',
        unsafe_allow_html=True,
    )

left_chart, right_chart = st.columns(2, gap="large")
for column, measurement in ((left_chart, "left"), (right_chart, "right")):
    result = analysis[measurement]
    with column:
        st.subheader(measurement.title() + " measurement")
        stat_col, dev_col = st.columns(2)
        stat_col.metric("Mean", f"{result['mean']:.3f}")
        dev_col.metric("Std. deviation (sample)", f"{result['stddev']:.3f}")
        st.plotly_chart(
            make_chart(data, measurement, result["mean"], result["stddev"], result["outliers"], result["trends"]),
            width="stretch",
        )
        if result["outliers"]:
            labels = ", ".join(data.loc[sorted(result["outliers"]), "_serial_label"].tolist())
            st.error(f"Beyond 3σ: serial number(s) {labels}. Stop machine and hand over for maintenance.")
        elif result["trends"]:
            st.warning("A run of 7 consecutive increases or decreases was detected. Check for process drift and monitor closely.")
        else:
            st.caption("No outliers or sustained trend detected for this measurement.")

with st.expander("Validated measurements"):
    st.dataframe(data[required_columns], width="stretch", hide_index=True)
