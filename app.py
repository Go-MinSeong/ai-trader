from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from strategy import BacktestConfig, run_backtest

ROOT = Path(__file__).parent
st.set_page_config(page_title="Paper Trader", page_icon="📈", layout="wide")
st.title("Paper Trader")
st.caption("미국 주식 ORB 전략을 과거 봉 데이터와 가상 자금으로 점검합니다.")

with st.sidebar:
    st.header("백테스트 설정")
    source = st.radio("가격 데이터", ["CSV 업로드", "합성 예시 데이터"])
    initial_cash = st.number_input(
        "가상 초기 자금 ($)", min_value=100.0, value=10_000.0, step=500.0
    )
    risk_pct = st.number_input(
        "거래당 계좌 위험 (%)", min_value=0.1, max_value=10.0, value=0.5, step=0.1
    )
    reward_risk = st.number_input(
        "목표 손익비 (R)", min_value=0.25, max_value=5.0, value=1.5, step=0.25
    )
    fee = st.number_input(
        "수수료 ($/주/편도)", min_value=0.0, value=0.005, step=0.001, format="%.3f"
    )
    slippage = st.number_input("슬리피지 (bp)", min_value=0.0, value=5.0, step=1.0)

if source == "CSV 업로드":
    uploaded = st.file_uploader(
        "5분봉 CSV",
        type="csv",
        help="timestamp, open, high, low, close, volume 컬럼이 필요합니다.",
    )
    if uploaded is None:
        st.info("CSV를 올리거나 왼쪽 메뉴에서 합성 예시 데이터를 선택하세요.")
        st.stop()
    try:
        bars = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"CSV를 읽지 못했습니다: {exc}")
        st.stop()
else:
    bars = pd.read_csv(ROOT / "examples" / "synthetic_5m.csv")
    st.warning(
        "합성 예시 데이터입니다. 화면 동작 확인용이며 실제 시장 데이터나 수익성 증거가 아닙니다."
    )

try:
    result = run_backtest(
        bars,
        BacktestConfig(
            initial_cash=initial_cash,
            risk_per_trade_pct=risk_pct,
            reward_risk=reward_risk,
            commission_per_share=fee,
            slippage_bps=slippage,
        ),
    )
except (ValueError, KeyError) as exc:
    st.error(str(exc))
    st.stop()

metrics = result["metrics"]
st.subheader("가상 계좌 결과")
cols = st.columns(5)
cols[0].metric(
    "최종 잔고",
    f"${metrics['final_equity']:,.2f}",
    f"{metrics['net_return_pct']:+.2f}%",
)
cols[1].metric("순손익", f"${metrics['net_pnl']:,.2f}")
cols[2].metric("최대 낙폭", f"{metrics['max_drawdown_pct']:.2f}%")
cols[3].metric(
    "승률 / 거래", f"{metrics['win_rate_pct']:.1f}%", f"{metrics['trades']}회"
)
pf = metrics["profit_factor"]
cols[4].metric("손익비 계수", "∞" if pf == float("inf") else f"{pf:.2f}")
st.caption(
    "모든 진입·청산에 설정한 슬리피지를 반영하고, 왕복 수수료를 차감했습니다. 거래당 위험 비율은 현재 가상 잔고 기준입니다."
)

equity = result["equity"]
if not equity.empty:
    curve = go.Figure()
    curve.add_trace(
        go.Scatter(
            x=equity["session"],
            y=equity["equity"],
            mode="lines+markers",
            name="가상 잔고",
        )
    )
    curve.add_hline(
        y=initial_cash,
        line_dash="dot",
        line_color="#8b95a5",
        annotation_text="초기 자금",
    )
    curve.update_layout(
        height=320,
        margin=dict(l=8, r=8, t=24, b=8),
        yaxis_title="USD",
        xaxis_title="거래일",
        hovermode="x unified",
    )
    st.plotly_chart(curve, use_container_width=True)

trades = result["trades"]
st.subheader("모의 거래 내역")
if trades.empty:
    st.info("설정한 조건에 맞는 거래가 없습니다.")
else:
    display = trades[
        [
            "session",
            "entry_time",
            "entry",
            "exit_time",
            "exit",
            "shares",
            "reason",
            "fees",
            "pnl",
        ]
    ].copy()
    display.columns = [
        "날짜",
        "진입 시각",
        "진입가",
        "청산 시각",
        "청산가",
        "수량",
        "결과",
        "수수료",
        "손익",
    ]
    st.dataframe(
        display.style.format(
            {
                "진입가": "${:,.2f}",
                "청산가": "${:,.2f}",
                "수수료": "${:,.2f}",
                "손익": "${:+,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("전략 및 입력 데이터 안내"):
    st.markdown("""
        - 매 거래일 첫 3개 봉으로 15분 시가 범위를 계산합니다.
        - 이후 봉이 범위 고점 위에서 마감하면 해당 종가에 매수했다고 가정합니다.
        - 손절은 시가 범위 중간값, 목표가는 설정한 R 배수로 둡니다. 하루 최대 1회 진입합니다.
        - 한 봉에서 손절과 목표가가 모두 닿으면 보수적으로 손절을 먼저 적용합니다.
        - timestamp가 시간대 없는 값이면 미국 동부시간으로 해석합니다. 미국 정규장 5분봉 CSV를 권장합니다.
        - CSV 필수 컬럼: `timestamp, open, high, low, close, volume` (헤더 대소문자 무관)
        - 이 결과는 과거 데이터 시뮬레이션이며 미래 수익을 보장하지 않습니다. 데이터 품질, 체결 지연, 갭과 시장 충격은 반영되지 않습니다.
        """)
