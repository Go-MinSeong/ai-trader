import unittest

import pandas as pd

from strategy import BacktestConfig, prepare_bars, run_backtest


def sample_bars():
    return pd.DataFrame(
        [
            ["2026-01-05 09:30", 100, 101, 99, 100, 1000],
            ["2026-01-05 09:35", 100, 101, 99, 100, 1000],
            ["2026-01-05 09:40", 100, 101, 99, 100, 1000],
            ["2026-01-05 09:45", 101, 103, 100.5, 102, 1000],
            ["2026-01-05 09:50", 102, 106, 101, 105, 1000],
            ["2026-01-06 09:30", 100, 101, 99, 100, 1000],
            ["2026-01-06 09:35", 100, 101, 99, 100, 1000],
            ["2026-01-06 09:40", 100, 101, 99, 100, 1000],
            ["2026-01-06 09:45", 101, 103, 100.5, 102, 1000],
            ["2026-01-06 09:50", 102, 103, 99, 100, 1000],
            ["2026-01-07 09:30", 100, 101, 99, 100, 1000],
            ["2026-01-07 09:35", 100, 101, 99, 100, 1000],
            ["2026-01-07 09:40", 100, 101, 99, 100, 1000],
            ["2026-01-07 09:45", 100, 100.5, 99.5, 100, 1000],
        ],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )


class StrategyTests(unittest.TestCase):
    def test_opening_range_breakout_records_target_stop_and_flat_day(self):
        result = run_backtest(
            sample_bars(),
            BacktestConfig(
                initial_cash=10_000,
                risk_per_trade_pct=1,
                reward_risk=1,
                commission_bps=0,
                slippage_bps=0,
            ),
        )
        self.assertEqual(result["trades"]["reason"].tolist(), ["목표", "손절"])
        self.assertEqual(result["metrics"]["final_equity"], 10_000)

    def test_percentage_commission_is_charged_on_entry_and_exit(self):
        result = run_backtest(
            sample_bars().iloc[:5],
            BacktestConfig(
                initial_cash=10_000,
                risk_per_trade_pct=1,
                reward_risk=1,
                commission_bps=10,
                slippage_bps=0,
            ),
        )
        trade = result["trades"].iloc[0]
        self.assertGreater(trade.fees, 0)
        self.assertLess(trade.pnl, (trade.exit - trade.entry) * trade.shares)

    def test_rejects_invalid_candle(self):
        bars = sample_bars()
        bars.loc[0, "high"] = 98
        with self.assertRaises(ValueError):
            prepare_bars(bars)


if __name__ == "__main__":
    unittest.main()
