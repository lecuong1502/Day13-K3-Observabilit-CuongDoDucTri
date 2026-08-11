"""
Dashboard runtime cho Day 13 Observability Lab.
Nguồn dữ liệu chuẩn: data/logs.jsonl
Chạy: streamlit run scripts/dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_PATH = Path("data/logs.jsonl")

# Ngưỡng lấy từ config/slo.yaml — giữ đồng bộ, không tự đổi khi chỉnh contract
SLO = {
    "latency_p95_ms": 3000,
    "error_rate_pct": 2,
    "daily_cost_usd": 2.5,
    "quality_score_avg": 0.75,
}


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    with LOG_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)


st.set_page_config(page_title="Day 13 Observability Dashboard", layout="wide")
st.title("Day 13 — Observability Dashboard")
st.caption("Time range: 60 phút gần nhất · Refresh: chạy lại app hoặc bấm 'R' để reload · Nguồn: data/logs.jsonl")

df = load_logs()

if df.empty:
    st.warning("Chưa có log nào trong data/logs.jsonl. Chạy `python scripts/load_test.py` trước.")
    st.stop()

df["ts"] = pd.to_datetime(df["ts"])
now = df["ts"].max()
window = df[df["ts"] >= now - pd.Timedelta(minutes=60)]

received = window[window["event"] == "request_received"]
sent = window[window["event"] == "response_sent"]
failed = window[window["event"] == "request_failed"]

col1, col2, col3 = st.columns(3)

# 1. Latency
with col1:
    st.subheader("1. Latency (ms)")
    if not sent.empty:
        lat = sent["latency_ms"].dropna()
        p50 = lat.quantile(0.50)
        p95 = lat.quantile(0.95)
        p99 = lat.quantile(0.99)
        st.metric("P50", f"{p50:.0f} ms")
        st.metric("P95", f"{p95:.0f} ms", delta=f"SLO {SLO['latency_p95_ms']} ms",
                   delta_color="inverse" if p95 > SLO["latency_p95_ms"] else "normal")
        st.metric("P99", f"{p99:.0f} ms")
        st.line_chart(sent.set_index("ts")["latency_ms"])
    else:
        st.info("Chưa có dữ liệu latency")

# 2. Traffic
with col2:
    st.subheader("2. Traffic")
    total_requests = len(received)
    minutes = max(1, (window["ts"].max() - window["ts"].min()).total_seconds() / 60)
    rpm = total_requests / minutes
    st.metric("Tổng request", total_requests)
    st.metric("Request/phút", f"{rpm:.2f}")

# 3. Errors
with col3:
    st.subheader("3. Error rate")
    total_errors = len(failed)
    total_all = total_requests + total_errors if (total_requests + total_errors) > 0 else 1
    error_rate = total_errors / total_all * 100
    st.metric("Error rate (%)", f"{error_rate:.2f}", delta=f"SLO < {SLO['error_rate_pct']}%",
               delta_color="inverse" if error_rate > SLO["error_rate_pct"] else "normal")
    if not failed.empty and "error_type" in failed.columns:
        st.bar_chart(failed["error_type"].value_counts())
    else:
        st.caption("Không có lỗi trong khoảng thời gian này")

col4, col5, col6 = st.columns(3)

# 4. Cost
with col4:
    st.subheader("4. Cost (USD)")
    if not sent.empty and "cost_usd" in sent.columns:
        total_cost = sent["cost_usd"].sum()
        avg_cost = sent["cost_usd"].mean()
        st.metric("Tổng cost", f"${total_cost:.4f}", delta=f"SLO < ${SLO['daily_cost_usd']}/ngày",
                   delta_color="inverse" if total_cost > SLO["daily_cost_usd"] else "normal")
        st.metric("Cost trung bình/request", f"${avg_cost:.6f}")
    else:
        st.info("Chưa có dữ liệu cost")

# 5. Tokens
with col5:
    st.subheader("5. Tokens")
    if not sent.empty:
        tokens_in = sent.get("tokens_in", pd.Series(dtype=float)).sum()
        tokens_out = sent.get("tokens_out", pd.Series(dtype=float)).sum()
        st.metric("Tokens in", int(tokens_in))
        st.metric("Tokens out", int(tokens_out))
        st.bar_chart(pd.DataFrame({"tokens_in": [tokens_in], "tokens_out": [tokens_out]}).T)
    else:
        st.info("Chưa có dữ liệu token")

# 6. Quality
with col6:
    st.subheader("6. Quality")
    if not sent.empty and "quality_score" in sent.columns:
        quality_avg = sent["quality_score"].mean()
        st.metric("Quality trung bình", f"{quality_avg:.2f}", delta=f"SLO ≥ {SLO['quality_score_avg']}",
                   delta_color="normal" if quality_avg >= SLO["quality_score_avg"] else "inverse")
        st.line_chart(sent.set_index("ts")["quality_score"])
    else:
        st.info("Chưa có dữ liệu quality")

st.divider()
st.caption(f"Tổng bản ghi trong log: {len(df)} · Cửa sổ 60 phút: {len(window)} bản ghi · Cập nhật lúc: {now}")