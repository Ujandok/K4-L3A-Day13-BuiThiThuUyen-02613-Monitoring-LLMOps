"""Dashboard 6 panel cho Day 13, đọc trực tiếp data/logs.jsonl.

Chạy:  streamlit run scripts/dashboard.py
Contract: config/dashboard.yaml (time range, refresh, threshold đọc từ đó).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"

CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
PANELS = {panel["id"]: panel for panel in CONFIG["panels"]}
TIME_RANGE_MIN = CONFIG["time_range_minutes"]
REFRESH_S = CONFIG["refresh_seconds"]
LOG_PATH = REPO_ROOT / PANELS["latency"]["source"]


def threshold(panel_id: str) -> float:
    return float(PANELS[panel_id]["threshold"]["value"])


def unit(panel_id: str) -> str:
    return PANELS[panel_id]["unit"]


def load_logs(window_min: int) -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    since = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    df = df[df["ts"] >= since].copy()
    df["minute"] = df["ts"].dt.floor("1min")
    return df


def col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name] if name in df.columns else pd.Series(dtype="float64")


def rule(value: float, label: str) -> alt.Chart:
    """Đường threshold/SLO màu đỏ, nét đứt."""
    return (
        alt.Chart(pd.DataFrame({"y": [value], "label": [label]}))
        .mark_rule(color="#d62728", strokeDash=[6, 4], size=2)
        .encode(y="y:Q", tooltip=["label:N", "y:Q"])
    )


def line_with_threshold(data: pd.DataFrame, y_title: str, thr: float, thr_label: str):
    base = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X("minute:T", title="Thời gian (UTC, theo phút)"),
            y=alt.Y("value:Q", title=y_title),
            color=alt.Color("series:N", title=None),
            tooltip=["minute:T", "series:N", alt.Tooltip("value:Q", format=",.4f")],
        )
    )
    return (base + rule(thr, thr_label)).properties(height=220)


def render(df: pd.DataFrame) -> None:
    resp = df[df["event"] == "response_sent"] if not df.empty else df
    recv = df[df["event"] == "request_received"] if not df.empty else df
    fail = df[df["event"] == "request_failed"] if not df.empty else df

    row1 = st.columns(3)
    row2 = st.columns(3)

    # 1) Latency P50/P95/P99 + TTFT P95
    with row1[0]:
        p = PANELS["latency"]
        st.subheader(p["title"])
        lat = col(resp, "latency_ms").dropna()
        ttft = col(resp, "ttft_ms").dropna()
        if lat.empty:
            st.info("Chưa có response_sent trong cửa sổ này.")
        else:
            c = st.columns(4)
            c[0].metric("P50", f"{lat.quantile(.50):.0f} ms")
            c[1].metric("P95", f"{lat.quantile(.95):.0f} ms")
            c[2].metric("P99", f"{lat.quantile(.99):.0f} ms")
            c[3].metric("TTFT P95", f"{ttft.quantile(.95):.0f} ms" if not ttft.empty else "–")
            g = resp.groupby("minute")
            series = pd.concat([
                g["latency_ms"].quantile(.50).rename("P50"),
                g["latency_ms"].quantile(.95).rename("P95"),
                g["latency_ms"].quantile(.99).rename("P99"),
                g["ttft_ms"].quantile(.95).rename("TTFT P95"),
            ], axis=1).reset_index().melt("minute", var_name="series", value_name="value")
            st.altair_chart(line_with_threshold(series, f"Latency ({unit('latency')})",
                                                threshold("latency"), "SLO P95 ≤ 3000 ms"),
                            width="stretch")

    # 2) Traffic
    with row1[1]:
        p = PANELS["traffic"]
        st.subheader(p["title"])
        if recv.empty:
            st.info("Chưa có request_received trong cửa sổ này.")
        else:
            per_min = recv.groupby("minute").size().rename("value").reset_index()
            st.metric("Tổng request (60 phút)", f"{len(recv)}")
            bars = alt.Chart(per_min).mark_bar().encode(
                x=alt.X("minute:T", title="Thời gian (UTC, theo phút)"),
                y=alt.Y("value:Q", title=unit("traffic")),
                tooltip=["minute:T", "value:Q"],
            )
            st.altair_chart((bars + rule(threshold("traffic"), "≥ 1 req/phút")).properties(height=220),
                            width="stretch")

    # 3) Errors + retrieval success
    with row1[2]:
        p = PANELS["errors"]
        st.subheader(p["title"])
        total = len(recv)
        err_rate = (len(fail) / total * 100) if total else 0.0
        tool = col(df, "tool_success").dropna() if not df.empty else pd.Series(dtype=bool)
        tool_rate = (tool.astype(bool).sum() / len(tool) * 100) if len(tool) else None
        c = st.columns(2)
        c[0].metric("Error rate", f"{err_rate:.1f} %",
                    delta="vượt ngưỡng" if err_rate > threshold("errors") else "OK",
                    delta_color="inverse" if err_rate > threshold("errors") else "off")
        c[1].metric("Retrieval success", f"{tool_rate:.1f} %" if tool_rate is not None else "–")
        if total:
            recv_m = recv.groupby("minute").size()
            fail_m = fail.groupby("minute").size().reindex(recv_m.index, fill_value=0)
            per_min = (fail_m / recv_m * 100).rename("Error rate %").to_frame()
            if not df.empty and "tool_success" in df.columns:
                t = df.dropna(subset=["tool_success"]).groupby("minute")["tool_success"]
                per_min["Retrieval success %"] = (t.sum() / t.count() * 100)
            series = per_min.reset_index().melt("minute", var_name="series", value_name="value")
            st.altair_chart(line_with_threshold(series, unit("errors"), threshold("errors"),
                                                "Error rate ≤ 2 %"), width="stretch")
        if not fail.empty and "error_type" in fail.columns:
            st.caption("Breakdown theo error_type")
            st.dataframe(fail["error_type"].value_counts().rename("count"), width="stretch")

    # 4) Cost
    with row2[0]:
        p = PANELS["cost"]
        st.subheader(p["title"])
        cost = col(resp, "cost_usd").dropna()
        if cost.empty:
            st.info("Chưa có dữ liệu cost.")
        else:
            st.metric("Tổng cost (60 phút)", f"${cost.sum():.4f}",
                      help=f"Ngưỡng tổng: ${threshold('cost')}")
            per_min = resp.groupby("minute")["cost_usd"].sum().sort_index()
            data = pd.DataFrame({
                "Cost/phút": per_min,
                "Cost cộng dồn": per_min.cumsum(),
            }).reset_index().melt("minute", var_name="series", value_name="value")
            st.altair_chart(line_with_threshold(data, unit("cost"), threshold("cost"),
                                                "Tổng ≤ $2.5"), width="stretch")

    # 5) Tokens
    with row2[1]:
        p = PANELS["tokens"]
        st.subheader(p["title"])
        if resp.empty:
            st.info("Chưa có dữ liệu token.")
        else:
            sums = pd.DataFrame({
                "field": ["tokens_in", "tokens_out"],
                "value": [int(col(resp, "tokens_in").sum()), int(col(resp, "tokens_out").sum())],
            })
            c = st.columns(2)
            c[0].metric("tokens_in", f"{sums.value[0]:,}")
            c[1].metric("tokens_out", f"{sums.value[1]:,}")
            bars = alt.Chart(sums).mark_bar().encode(
                x=alt.X("field:N", title=None),
                y=alt.Y("value:Q", title=unit("tokens")),
                tooltip=["field:N", "value:Q"],
            )
            st.altair_chart((bars + rule(threshold("tokens"), "≤ 50,000 tokens/field")).properties(height=220),
                            width="stretch")

    # 6) Quality
    with row2[2]:
        p = PANELS["quality"]
        st.subheader(p["title"])
        q = col(resp, "quality_score").dropna()
        if q.empty:
            st.info("Chưa có quality_score.")
        else:
            st.metric("Mean quality", f"{q.mean():.3f}")
            data = resp.groupby("minute")["quality_score"].mean().rename("Mean quality") \
                .reset_index().melt("minute", var_name="series", value_name="value")
            st.altair_chart(line_with_threshold(data, unit("quality"), threshold("quality"),
                                                "Mean ≥ 0.75"), width="stretch")


st.set_page_config(page_title=CONFIG["title"], layout="wide")
st.title(CONFIG["title"])
st.caption(
    f"Nguồn: {PANELS['latency']['source']} · Time range: {TIME_RANGE_MIN} phút gần nhất · "
    f"Tự refresh mỗi {REFRESH_S} giây · Đường đỏ nét đứt = threshold/SLO"
)


@st.fragment(run_every=REFRESH_S)
def live() -> None:
    df = load_logs(TIME_RANGE_MIN)
    st.caption(f"Cập nhật lúc {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC · {len(df)} log records")
    if df.empty:
        st.warning("Không có log trong 60 phút gần nhất. Chạy API rồi `python scripts/load_test.py`.")
        return
    render(df)


live()
