from __future__ import annotations

from io import BytesIO
from datetime import datetime
from math import ceil, floor
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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
    axis_min: float,
    axis_max: float,
    axis_dtick: float,
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
            "range": [axis_min, axis_max],
            "dtick": axis_dtick,
        },
        hovermode="closest",
    )
    return figure


class PdfControlChart(Flowable):
    def __init__(self, frame: pd.DataFrame, measurement: str, result: dict[str, object], axis_min: float, axis_max: float):
        super().__init__()
        self.frame = frame
        self.measurement = measurement
        self.result = result
        self.axis_min = axis_min
        self.axis_max = axis_max
        self.height = 2.8 * inch

    def draw(self) -> None:
        canvas = self.canv
        plot_left, plot_bottom = 42, 32
        plot_width, plot_height = self.width - 142, self.height - 54
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(plot_left, plot_bottom, plot_width, plot_height, fill=1, stroke=0)

        for tick in range(5):
            value = self.axis_min + (self.axis_max - self.axis_min) * tick / 4
            y = plot_bottom + plot_height * tick / 4
            canvas.setStrokeColor(colors.HexColor("#dce3dc"))
            canvas.setLineWidth(0.5)
            canvas.line(plot_left, y, plot_left + plot_width, y)
            canvas.setFillColor(colors.HexColor("#43514d"))
            canvas.setFont("Helvetica", 7)
            canvas.drawRightString(plot_left - 5, y - 2, f"{value:.3f}")

        def y_position(value: float) -> float:
            return plot_bottom + (value - self.axis_min) / (self.axis_max - self.axis_min) * plot_height

        for key, color, dash in (
            ("lower_limit", "#b84f24", [3, 2]),
            ("mean", "#146b52", []),
            ("upper_limit", "#b84f24", [3, 2]),
        ):
            y = y_position(float(self.result[key]))
            canvas.setStrokeColor(colors.HexColor(color))
            canvas.setDash(dash)
            canvas.setLineWidth(1)
            canvas.line(plot_left, y, plot_left + plot_width, y)
            canvas.setDash()
            canvas.setFillColor(colors.HexColor(color))
            canvas.setFont("Helvetica", 7)
            label = {"lower_limit": "Lower limit", "mean": "Mean", "upper_limit": "Upper limit"}[key]
            canvas.drawString(plot_left + plot_width + 5, y - 2, f"{label}: {float(self.result[key]):.3f}")

        values = self.frame[self.measurement].tolist()
        positions = [
            (plot_left + plot_width * index / max(len(values) - 1, 1), y_position(value))
            for index, value in enumerate(values)
        ]
        canvas.setStrokeColor(colors.HexColor("#aab9b2"))
        canvas.setLineWidth(0.8)
        for start, end in zip(positions, positions[1:]):
            canvas.line(start[0], start[1], end[0], end[1])

        legend_y = self.height - 10
        for legend_x, label, color, marker in (
            (plot_left, "In control", "#146b52", "circle"),
            (plot_left + 78, "Trend", "#d58a20", "circle"),
            (plot_left + 126, "Beyond 3 sigma", "#b84f24", "cross"),
        ):
            canvas.setStrokeColor(colors.HexColor(color))
            canvas.setFillColor(colors.HexColor(color))
            if marker == "cross":
                canvas.line(legend_x - 3, legend_y - 3, legend_x + 3, legend_y + 3)
                canvas.line(legend_x - 3, legend_y + 3, legend_x + 3, legend_y - 3)
            else:
                canvas.circle(legend_x, legend_y, 2.5, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#43514d"))
            canvas.setFont("Helvetica", 7)
            canvas.drawString(legend_x + 6, legend_y - 2, label)

        outliers = self.result["outliers"]
        trends = self.result["trends"]
        for index, (x, y) in enumerate(positions):
            if index in outliers:
                canvas.setStrokeColor(colors.HexColor("#b84f24"))
                canvas.line(x - 3, y - 3, x + 3, y + 3)
                canvas.line(x - 3, y + 3, x + 3, y - 3)
            else:
                canvas.setFillColor(colors.HexColor("#d58a20" if index in trends else "#146b52"))
                canvas.circle(x, y, 2.5, fill=1, stroke=0)

        canvas.setFillColor(colors.HexColor("#43514d"))
        canvas.setFont("Helvetica", 7)
        serials = self.frame["_serial_label"].tolist()
        for index in sorted({0, len(serials) // 2, len(serials) - 1}):
            x = positions[index][0]
            label = str(serials[index])[:24]
            if index == 0:
                canvas.drawString(x, plot_bottom - 12, label)
            elif index == len(serials) - 1:
                canvas.drawRightString(x, plot_bottom - 12, label)
            else:
                canvas.drawCentredString(x, plot_bottom - 12, label)
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(plot_left + plot_width / 2, 4, "Serial number (upload order)")
        canvas.restoreState()


def build_pdf_report(
    frame: pd.DataFrame,
    analysis: dict[str, dict[str, object]],
    statistics: dict[str, dict[str, float]],
    outlier_count: int,
    trend_sides: list[str],
    axis_min: float,
    axis_max: float,
    source_name: str,
    sheet_name: str,
    generated_at: datetime,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title="Axle Grinding Process Report",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#162522"), alignment=0))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#146b52"), spaceBefore=10, spaceAfter=5))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    story: list[Flowable] = [
        Paragraph("Grinding Machine Performance Monitor", styles["ReportTitle"]),
        Paragraph(
            f"Generated {generated_at:%d %b %Y, %H:%M:%S} IST &nbsp; | &nbsp; "
            f"Workbook: {escape(source_name)} &nbsp; | &nbsp; Worksheet: {escape(sheet_name)}",
            styles["Small"],
        ),
        Spacer(1, 10),
        Paragraph("Process summary", styles["Section"]),
    ]

    summary_table = Table(
        [
            ["Left mean", "Right mean", "Valid measurements"],
            [f"{statistics['left']['mean']:.3f}", f"{statistics['right']['mean']:.3f}", f"{len(frame):,}"],
        ],
        colWidths=[2.4 * inch] * 3,
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1ec")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#43514d")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#162522")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce3dc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce3dc")),
    ]))
    story.append(summary_table)

    if outlier_count:
        recommendation = (
            f"<b>STOP MACHINE: {outlier_count} point(s) beyond 3 sigma.</b> "
            "Stop the machine and hand over to maintenance for inspection before resuming production."
        )
    elif trend_sides:
        sides = " and ".join(side.title() for side in trend_sides)
        recommendation = (
            f"<b>Possible process trend: {escape(sides)}.</b> "
            "Check setup, tooling, and measurement conditions; inform the process owner and monitor the next measurements closely."
        )
    else:
        recommendation = (
            "<b>No 3 sigma outliers or sustained trend detected.</b> "
            "Continue normal operation and routine monitoring."
        )
    recommendation_table = Table([[Paragraph(recommendation, styles["BodyText"])]], colWidths=[7.2 * inch])
    recommendation_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8ece5" if outlier_count or trend_sides else "#e8f1ec")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#b84f24" if outlier_count or trend_sides else "#146b52")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([Spacer(1, 9), recommendation_table])

    for measurement in ("left", "right"):
        result = analysis[measurement]
        story.extend([
            Paragraph(f"{measurement.title()} measurement", styles["Section"]),
            Paragraph(
                f"Mean: {float(result['mean']):.3f} &nbsp; | &nbsp; "
                f"Sample standard deviation: {float(result['stddev']):.3f} &nbsp; | &nbsp; "
                f"Control limits: {float(result['lower_limit']):.3f} to {float(result['upper_limit']):.3f}",
                styles["Small"],
            ),
            PdfControlChart(frame, measurement, result, axis_min, axis_max),
        ])
        if result["outliers"]:
            labels = ", ".join(str(value) for value in frame.loc[sorted(result["outliers"]), "_serial_label"])
            finding = f"Beyond 3 sigma: serial number(s) {labels}. Stop machine and hand over for maintenance."
        elif result["trends"]:
            finding = "A run of 7 consecutive increases or decreases was detected. Check for process drift and monitor closely."
        else:
            finding = "No outliers or sustained trend detected for this measurement."
        story.append(Paragraph(escape(finding), styles["Small"]))

    story.extend([Paragraph("Validated measurements", styles["Section"])])
    table_data = [["Serial number", "Left", "Right"]]
    table_data.extend([
        [str(row["serial number"]), f"{row['left']:.3f}", f"{row['right']:.3f}"]
        for _, row in frame.iterrows()
    ])
    measurement_table = LongTable(table_data, colWidths=[3.6 * inch, 1.8 * inch, 1.8 * inch], repeatRows=1)
    measurement_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#162522")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f2")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce3dc")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(measurement_table)

    def add_page_number(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#65736f"))
        canvas.drawRightString(letter[0] - 0.55 * inch, 0.32 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()


#st.markdown('<div class="eyebrow"> \n\n Axle grinding / process control</div>', unsafe_allow_html=True)
title_col, date_col, download_col = st.columns([5, 1.1, 1.5])
with title_col:
    st.title("Grinding Machine Performance Monitor")
pdf_download_slot = download_col.empty()
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
axis_values = pd.concat(
    [
        data["left"],
        data["right"],
        pd.Series([result["lower_limit"] for result in analysis.values()]),
        pd.Series([result["upper_limit"] for result in analysis.values()]),
    ]
)
axis_min_value = float(axis_values.min())
axis_max_value = float(axis_values.max())
axis_span = axis_max_value - axis_min_value
axis_padding = axis_span * 0.05 if axis_span else max(abs(axis_max_value) * 0.05, 0.5)
axis_min = axis_min_value - axis_padding
axis_max = axis_max_value + axis_padding
axis_dtick = (axis_max - axis_min) / 6
axis_min = floor(axis_min / axis_dtick) * axis_dtick
axis_max = ceil(axis_max / axis_dtick) * axis_dtick
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
            make_chart(
                data,
                measurement,
                result["mean"],
                result["stddev"],
                result["outliers"],
                result["trends"],
                axis_min,
                axis_max,
                axis_dtick,
            ),
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

pdf_bytes = build_pdf_report(
    data,
    analysis,
    statistics,
    outlier_count,
    trend_sides,
    axis_min,
    axis_max,
    uploaded_file.name,
    selected_sheet,
    current_time,
)
pdf_download_slot.download_button(
    "Download PDF",
    data=pdf_bytes,
    file_name=f"axle_process_report_{current_time:%Y%m%d}.pdf",
    mime="application/pdf",
    width="stretch",
)
