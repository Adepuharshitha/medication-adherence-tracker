import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, datetime, timedelta
import database as db


def render_adherence_gauge(rate: float):
    """Render a gauge chart for adherence rate."""
    color = "#2ecc71" if rate >= 80 else "#f39c12" if rate >= 60 else "#e74c3c"
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=rate,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Adherence Rate (%)", "font": {"size": 18}},
            delta={"reference": 80, "increasing": {"color": "#2ecc71"}, "decreasing": {"color": "#e74c3c"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 60], "color": "#fdecea"},
                    {"range": [60, 80], "color": "#fff3e0"},
                    {"range": [80, 100], "color": "#e8f5e9"},
                ],
                "threshold": {
                    "line": {"color": "#2c3e50", "width": 4},
                    "thickness": 0.75,
                    "value": 80,
                },
            },
            number={"suffix": "%", "font": {"size": 28}},
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


def render_daily_trend(daily_data: list, title="30-Day Adherence Trend"):
    """Render a line chart of daily adherence rates."""
    if not daily_data:
        st.info("No data available for trend chart.")
        return

    df = pd.DataFrame(daily_data)
    df["rate"] = df.apply(lambda r: round(r["taken"] / r["total"] * 100, 1) if r["total"] > 0 else 0, axis=1)
    df["scheduled_date"] = pd.to_datetime(df["scheduled_date"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["scheduled_date"],
            y=df["rate"],
            mode="lines+markers",
            name="Adherence %",
            line=dict(color="#3b82d4", width=2.5),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(59,130,212,0.1)",
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color="#e74c3c", annotation_text="80% Target", annotation_position="bottom right")
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Adherence (%)",
        yaxis=dict(range=[0, 105]),
        height=320,
        margin=dict(l=20, r=20, t=50, b=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_medication_breakdown(logs: list):
    """Render a bar chart breaking down adherence per medication."""
    if not logs:
        st.info("No logs available.")
        return

    df = pd.DataFrame(logs)
    summary = df.groupby(["med_name", "status"]).size().unstack(fill_value=0).reset_index()

    for col in ["taken", "missed", "skipped"]:
        if col not in summary.columns:
            summary[col] = 0

    fig = go.Figure(data=[
        go.Bar(name="Taken", x=summary["med_name"], y=summary["taken"], marker_color="#2ecc71"),
        go.Bar(name="Missed", x=summary["med_name"], y=summary["missed"], marker_color="#e74c3c"),
        go.Bar(name="Skipped", x=summary["med_name"], y=summary["skipped"], marker_color="#f39c12"),
    ])
    fig.update_layout(
        barmode="group",
        title="Medication-wise Adherence Breakdown",
        xaxis_title="Medication",
        yaxis_title="Doses",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_status_donut(stats: dict):
    """Render a donut chart for taken/missed/skipped distribution."""
    labels = ["Taken", "Missed", "Skipped"]
    values = [stats.get("taken", 0), stats.get("missed", 0), stats.get("skipped", 0)]
    colors = ["#2ecc71", "#e74c3c", "#f39c12"]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colors),
            textinfo="label+percent",
            hoverinfo="label+value",
        )
    )
    fig.update_layout(
        title="Dose Status Distribution",
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_weekly_heatmap(patient_id: int):
    """Render a weekly adherence heatmap (last 8 weeks)."""
    logs = db.get_logs(patient_id, days=56)
    if not logs:
        st.info("Not enough data for heatmap.")
        return

    df = pd.DataFrame(logs)
    df["scheduled_date"] = pd.to_datetime(df["scheduled_date"])
    df["week"] = df["scheduled_date"].dt.isocalendar().week.astype(str)
    df["day_name"] = df["scheduled_date"].dt.day_name()

    summary = df.groupby(["week", "day_name"]).apply(
        lambda g: round(g["status"].eq("taken").sum() / len(g) * 100, 1)
    ).reset_index(name="rate")

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = summary.pivot(index="day_name", columns="week", values="rate").reindex(day_order)

    fig = px.imshow(
        pivot,
        color_continuous_scale=[[0, "#fdecea"], [0.5, "#fff3e0"], [1, "#2ecc71"]],
        zmin=0, zmax=100,
        aspect="auto",
        title="Weekly Adherence Heatmap (%)",
        labels=dict(x="Week", y="Day", color="Adherence %"),
    )
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


def metric_card(label: str, value: str, delta: str = "", color: str = "#3b82d4"):
    """Render a styled metric card."""
    delta_html = f"<p style='color:#888;font-size:12px;margin:0'>{delta}</p>" if delta else ""
    st.markdown(
        f"""
        <div style='background:#f7f8fa;border-left:4px solid {color};
                    padding:16px 20px;border-radius:8px;margin-bottom:8px'>
            <p style='color:#57606a;font-size:13px;margin:0 0 4px 0'>{label}</p>
            <p style='color:#1f2328;font-size:26px;font-weight:700;margin:0'>{value}</p>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
