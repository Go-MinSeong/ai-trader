from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import pandas as pd

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000
    risk_per_trade_pct: float = 0.5
    reward_risk: float = 1.5
    commission_per_share: float = 0.005
    slippage_bps: float = 5
    market_timezone: str = "America/New_York"
    session_open: str = "09:30"
    session_close: str = "16:00"


def prepare_bars(
    frame: pd.DataFrame, market_timezone="America/New_York"
) -> pd.DataFrame:
    """Validate OHLCV input and normalize timestamps to US Eastern time."""
    missing = REQUIRED_COLUMNS - set(frame.columns.str.lower())
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

    bars = frame.copy()
    bars.columns = [str(column).strip().lower() for column in bars.columns]
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], errors="coerce")
    if bars["timestamp"].isna().any():
        raise ValueError("timestamp에 해석할 수 없는 날짜/시간이 있습니다.")

    timestamps = bars["timestamp"]
    if timestamps.dt.tz is None:
        bars["timestamp"] = timestamps.dt.tz_localize(market_timezone)
    else:
        bars["timestamp"] = timestamps.dt.tz_convert(market_timezone)

    for column in ("open", "high", "low", "close", "volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    if bars[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError("OHLCV 컬럼에는 숫자만 입력할 수 있습니다.")
    if (bars["volume"] < 0).any():
        raise ValueError("volume은 음수일 수 없습니다.")
    if (bars["high"] < bars[["open", "close", "low"]].max(axis=1)).any() or (
        bars["low"] > bars[["open", "close", "high"]].min(axis=1)
    ).any():
        raise ValueError("각 봉은 low ≤ open/close ≤ high 조건을 만족해야 합니다.")

    bars = bars.sort_values("timestamp").reset_index(drop=True)
    if bars["timestamp"].duplicated().any():
        raise ValueError("중복된 timestamp가 있습니다.")
    bars["session"] = bars["timestamp"].dt.date
    return bars


def run_backtest(frame: pd.DataFrame, config: BacktestConfig) -> dict:
    if config.initial_cash <= 0 or not 0 < config.risk_per_trade_pct <= 100:
        raise ValueError("초기 자금과 거래당 위험 비율을 확인해 주세요.")
    if config.reward_risk <= 0 or config.commission_per_share < 0:
        raise ValueError("목표 손익비와 수수료 설정을 확인해 주세요.")
    if config.slippage_bps < 0:
        raise ValueError("슬리피지는 음수일 수 없습니다.")

    bars = prepare_bars(frame, config.market_timezone)
    open_minute = int(config.session_open[:2]) * 60 + int(config.session_open[3:])
    close_minute = int(config.session_close[:2]) * 60 + int(config.session_close[3:])
    local_minute = bars["timestamp"].dt.hour * 60 + bars["timestamp"].dt.minute
    bars = bars[(local_minute >= open_minute) & (local_minute < close_minute)]
    if bars.empty:
        raise ValueError("선택한 기간에 해당 시장의 정규장 데이터가 없습니다.")
    cash = config.initial_cash
    slippage = config.slippage_bps / 10_000
    trades: list[dict] = []
    equity: list[dict] = []

    for session, day in bars.groupby("session", sort=True):
        day = day.reset_index(drop=True)
        if len(day) < 4:
            continue

        opening = day.iloc[:3]
        expected_opening = [
            pd.Timestamp(config.session_open).hour * 60
            + pd.Timestamp(config.session_open).minute
            + 5 * offset
            for offset in range(3)
        ]
        actual_opening = (
            opening["timestamp"].dt.hour * 60 + opening["timestamp"].dt.minute
        ).tolist()
        if actual_opening != expected_opening:
            continue
        range_high = float(opening["high"].max())
        range_low = float(opening["low"].min())
        stop = (range_high + range_low) / 2
        trade = None

        for index in range(3, len(day)):
            bar = day.iloc[index]
            if trade is None:
                if index == len(day) - 1:
                    break
                if float(bar.close) <= range_high:
                    continue
                entry = float(bar.close) * (1 + slippage)
                risk_per_share = entry - stop
                if risk_per_share <= 0:
                    break
                risk_budget = cash * config.risk_per_trade_pct / 100
                shares = math.floor(
                    min(
                        risk_budget / risk_per_share,
                        cash / (entry + config.commission_per_share),
                    )
                )
                if shares < 1:
                    break
                target = entry + risk_per_share * config.reward_risk
                trade = {
                    "session": str(session),
                    "entry_time": bar.timestamp,
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "shares": shares,
                    "entry_index": index,
                }
                continue

            exit_price = None
            exit_reason = None
            if float(bar.low) <= stop:
                exit_price, exit_reason = stop * (1 - slippage), "손절"
            elif float(bar.high) >= trade["target"]:
                exit_price, exit_reason = trade["target"] * (1 - slippage), "목표"
            elif index == len(day) - 1:
                exit_price, exit_reason = float(bar.close) * (1 - slippage), "장 마감"

            if exit_price is not None:
                fees = trade["shares"] * config.commission_per_share * 2
                pnl = (exit_price - trade["entry"]) * trade["shares"] - fees
                cash += pnl
                trades.append(
                    {
                        **trade,
                        "exit_time": bar.timestamp,
                        "exit": exit_price,
                        "reason": exit_reason,
                        "fees": fees,
                        "pnl": pnl,
                        "return_pct": pnl / (trade["entry"] * trade["shares"]) * 100,
                    }
                )
                break

        equity.append({"session": pd.Timestamp(session), "equity": cash})

    trade_frame = pd.DataFrame(trades)
    equity_frame = pd.DataFrame(equity)
    values = [config.initial_cash]
    values.extend(equity_frame["equity"].tolist())
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value / peak - 1) * 100)

    wins = trade_frame[trade_frame["pnl"] > 0] if not trade_frame.empty else trade_frame
    losses = (
        trade_frame[trade_frame["pnl"] < 0] if not trade_frame.empty else trade_frame
    )
    gross_loss = abs(float(losses["pnl"].sum())) if not losses.empty else 0.0
    metrics = {
        "initial_cash": config.initial_cash,
        "final_equity": cash,
        "net_pnl": cash - config.initial_cash,
        "net_return_pct": (cash / config.initial_cash - 1) * 100,
        "max_drawdown_pct": max_drawdown,
        "trades": len(trade_frame),
        "win_rate_pct": len(wins) / len(trade_frame) * 100 if trades else 0.0,
        "profit_factor": (
            float(wins["pnl"].sum()) / gross_loss
            if gross_loss
            else (math.inf if not wins.empty else 0.0)
        ),
        "average_trade_pnl": float(trade_frame["pnl"].mean()) if trades else 0.0,
    }
    return {
        "metrics": metrics,
        "trades": trade_frame,
        "equity": equity_frame,
        "config": asdict(config),
    }
