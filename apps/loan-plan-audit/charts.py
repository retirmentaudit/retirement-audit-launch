"""Plotly figures. Colors stay tied to the same plan ids everywhere."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine import PAYE_SUNSET, PlanResult, add_months

PLAN_COLORS = {
    "standard_10": "#0B1F3A",
    "tiered_standard": "#FF6B5A",
    "rap": "#5AB8FF",
    "ibr_15": "#2BD9A0",
    "ibr_10": "#14956C",
    "paye_bridge": "#F5B841",
    "graduated": "#7C8EA3",
    "extended": "#3D4F66",
    "icr": "#C9842A",
}

_LAYOUT = dict(
    paper_bgcolor="#F7F5F0",
    plot_bgcolor="#FFFFFF",
    font=dict(family="Inter, sans-serif", color="#0B1F3A"),
    margin=dict(l=40, r=20, t=48, b=40),
)


def _eligible(plans: list[PlanResult]) -> list[PlanResult]:
    return [plan for plan in plans if plan.eligible and plan.first_year_monthly is not None]


def monthly_bar(plans: list[PlanResult]) -> go.Figure:
    rows = _eligible(plans)
    figure = go.Figure(
        go.Bar(
            x=[plan.label for plan in rows],
            y=[plan.first_year_monthly for plan in rows],
            marker_color=[PLAN_COLORS.get(plan.plan_id, "#0B1F3A") for plan in rows],
            text=[f"${plan.first_year_monthly:,.0f}" for plan in rows],
            textposition="outside",
            hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(title="First-year estimated monthly payment", yaxis_title="Dollars per month", **_LAYOUT)
    figure.update_yaxes(gridcolor="#E4DFD4")
    return figure


def comparison_chart(plans: list[PlanResult]) -> go.Figure:
    rows = _eligible(plans)
    metrics = (
        ("Monthly now", lambda plan: plan.first_year_monthly or 0),
        ("Total paid", lambda plan: plan.total_paid or 0),
        ("Interest paid", lambda plan: plan.interest_paid or 0),
        ("Balance at end", lambda plan: plan.forgiven_amount or 0),
    )
    figure = make_subplots(rows=1, cols=4, subplot_titles=[name for name, _getter in metrics])
    for column, (_name, getter) in enumerate(metrics, start=1):
        figure.add_trace(
            go.Bar(
                x=[plan.label for plan in rows],
                y=[getter(plan) for plan in rows],
                marker_color=[PLAN_COLORS.get(plan.plan_id, "#0B1F3A") for plan in rows],
                showlegend=False,
                hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
            ),
            row=1,
            col=column,
        )
    figure.update_layout(title="Side-by-side estimates", **_LAYOUT)
    figure.update_yaxes(gridcolor="#E4DFD4")
    return figure


def payoff_timeline(plans: list[PlanResult], start: date, pslf: bool, pslf_credited: int) -> go.Figure:
    figure = go.Figure()
    rows = _eligible(plans)
    for plan in rows:
        yearly = plan.yearly or []
        if not yearly:
            continue
        figure.add_trace(
            go.Scatter(
                x=[row["date"] for row in yearly],
                y=[row["balance"] for row in yearly],
                mode="lines+markers",
                name=plan.label,
                line=dict(color=PLAN_COLORS.get(plan.plan_id, "#0B1F3A"), width=3),
                customdata=[row["payment"] for row in yearly],
                hovertemplate="%{x}<br>Balance $%{y:,.0f}<br>Payment that year $%{customdata:,.0f}<extra>"
                + plan.label
                + "</extra>",
            )
        )
    markers = [
        ("2026-12-31", "Notices to former SAVE borrowers"),
        (PAYE_SUNSET.isoformat(), "PAYE/ICR sunset"),
        (add_months(start, 359).isoformat(), "RAP month 360"),
    ]
    if pslf:
        left = max(0, 120 - int(pslf_credited))
        when = start if left == 0 else add_months(start, max(left - 1, 0))
        markers.append((when.isoformat(), "PSLF month 120"))
    for x_value, label in markers:
        figure.add_vline(x=x_value, line_dash="dot", line_color="#8FA0B8", opacity=0.8)
        figure.add_annotation(x=x_value, y=1, yref="paper", text=label, showarrow=False, textangle=-90, font=dict(size=10, color="#0B1F3A"))
    figure.update_layout(title="Balance over time", yaxis_title="Estimated balance", legend_title="", **_LAYOUT)
    figure.update_yaxes(gridcolor="#E4DFD4")
    return figure
