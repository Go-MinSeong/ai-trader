from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import keyring
import pandas as pd
import webview

from storage import BarStore
from strategy import BacktestConfig, run_backtest
from toss_market import TossMarketClient, aggregate_to_five_minutes, validate_symbol

SERVICE_NAME = "AI Trader"


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return root / relative


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


class DesktopAPI:
    def __init__(self):
        self.store = BarStore()

    def get_initial_state(self) -> dict:
        return {
            "app_name": "AI Trader",
            "version": "0.2.0",
            "data_source": None,
            "has_data": False,
            "data_status": "데이터 연결 전",
            "trades": [],
            "metrics": None,
        }

    def test_connection(self, client_id: str, client_secret: str) -> dict:
        try:
            TossMarketClient(client_id, client_secret).test_connection()
            self._save_credentials(client_id, client_secret)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def fetch_and_backtest(self, config: dict) -> dict:
        try:
            symbol = validate_symbol(config.get("symbol", ""))
            market = config.get("market", "US").upper()
            if market not in {"US", "KR"}:
                raise ValueError("시장은 미국 또는 한국으로 선택해 주세요.")
            days = int(config.get("period_days", 30))
            risk_pct = float(config.get("risk_pct", 0.5))
            reward_risk = float(config.get("reward_risk", 1.5))
            if not 1 <= days <= 365:
                raise ValueError("조회 기간은 1~365일이어야 합니다.")
            if not 0.1 <= risk_pct <= 5:
                raise ValueError("거래당 위험은 0.1~5% 범위로 설정해 주세요.")
            if not 0.5 <= reward_risk <= 5:
                raise ValueError("목표 손익비는 0.5~5R 범위로 설정해 주세요.")

            client_id = (config.get("client_id") or "").strip()
            client_secret = config.get("client_secret") or ""
            if not client_id:
                client_id = keyring.get_password(SERVICE_NAME, "toss_client_id") or ""
            if not client_secret:
                client_secret = (
                    keyring.get_password(SERVICE_NAME, "toss_client_secret") or ""
                )
            client = TossMarketClient(client_id, client_secret)
            minute_bars = client.fetch_minute_bars(symbol, days)
            self._save_credentials(client_id, client_secret)
            self.store.save(market, symbol, minute_bars)
            cached = self.store.load(market, symbol, days)
            five_minute_bars = aggregate_to_five_minutes(cached, market)

            timezone_name, session_open, session_close = {
                "US": ("America/New_York", "09:30", "16:00"),
                "KR": ("Asia/Seoul", "09:00", "15:30"),
            }[market]
            result = run_backtest(
                five_minute_bars,
                BacktestConfig(
                    risk_per_trade_pct=risk_pct,
                    reward_risk=reward_risk,
                    market_timezone=timezone_name,
                    session_open=session_open,
                    session_close=session_close,
                ),
            )
            trades = result["trades"].to_dict("records")
            for trade in trades:
                trade["symbol"] = symbol
            equity = result["equity"].to_dict("records")
            dates = five_minute_bars["timestamp"]
            return json_safe(
                {
                    "ok": True,
                    "symbol": symbol,
                    "market": market,
                    "data_source": "Toss Open API · 로컬 캐시",
                    "start_date": str(dates.min().date()),
                    "end_date": str(dates.max().date()),
                    "minute_bar_count": len(minute_bars),
                    "bar_count": len(five_minute_bars),
                    "metrics": result["metrics"],
                    "trades": trades,
                    "equity": equity,
                    "agent_review": self._review(five_minute_bars, result),
                }
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def load_demo(self) -> dict:
        try:
            demo = pd.read_csv(resource_path("examples/synthetic_5m.csv"))
            result = run_backtest(
                demo, BacktestConfig(slippage_bps=0, commission_per_share=0)
            )
            return json_safe(
                {
                    "ok": True,
                    "symbol": "DEMO",
                    "market": "US",
                    "data_source": "합성 예시 데이터",
                    "start_date": str(pd.to_datetime(demo.timestamp).min().date()),
                    "end_date": str(pd.to_datetime(demo.timestamp).max().date()),
                    "bar_count": len(demo),
                    "metrics": result["metrics"],
                    "trades": result["trades"].to_dict("records"),
                    "equity": result["equity"].to_dict("records"),
                    "agent_review": self._review(demo, result),
                }
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _save_credentials(client_id: str, client_secret: str) -> None:
        keyring.set_password(SERVICE_NAME, "toss_client_id", client_id.strip())
        keyring.set_password(SERVICE_NAME, "toss_client_secret", client_secret)

    @staticmethod
    def _review(bars: pd.DataFrame, result: dict) -> list[dict]:
        completeness = float(
            (bars.get("minute_bars", pd.Series([5] * len(bars))) == 5).mean()
        )
        trades = result["metrics"]["trades"]
        drawdown = result["metrics"]["max_drawdown_pct"]
        return [
            {"role": "data", "status": "양호" if completeness >= 0.95 else "주의"},
            {"role": "quant", "status": "검토" if trades >= 30 else "표본 부족"},
            {"role": "risk", "status": "양호" if drawdown >= -10 else "주의"},
        ]


def main() -> None:
    html = resource_path("ui/index.html").read_text(encoding="utf-8")
    for path in ("examples/synthetic_5m.csv",):
        resource_path(path)
    webview.create_window(
        "AI Trader",
        html=html,
        js_api=DesktopAPI(),
        width=1440,
        height=920,
        min_size=(1024, 720),
        background_color="#f5f5f7",
        text_select=True,
    )
    webview.start(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
