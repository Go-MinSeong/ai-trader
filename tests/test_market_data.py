import tempfile
import unittest
from pathlib import Path

import pandas as pd

from storage import BarStore
from toss_market import aggregate_to_five_minutes, validate_symbol


class MarketDataTests(unittest.TestCase):
    def test_symbol_is_normalized_and_invalid_input_rejected(self):
        self.assertEqual(validate_symbol(" aapl "), "AAPL")
        with self.assertRaises(ValueError):
            validate_symbol("AAPL/../../secret")

    def test_aggregation_ignores_premarket_and_preserves_partial_bar_count(self):
        timestamps = pd.date_range("2026-01-05 14:28", periods=8, freq="min", tz="UTC")
        frame = pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": range(100, 108),
                "high": range(101, 109),
                "low": range(99, 107),
                "close": range(100, 108),
                "volume": [10] * 8,
            }
        )
        bars = aggregate_to_five_minutes(frame, "US")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars.minute_bars.tolist(), [5, 1])
        self.assertEqual(bars.iloc[0].open, 102)

    def test_store_upserts_and_loads_utc_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BarStore(Path(tmp) / "bars.sqlite3")
            bars = pd.DataFrame(
                [[pd.Timestamp("2026-01-05 14:30", tz="UTC"), 1, 2, 0.5, 1.5, 10]],
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            store.save("US", "AAPL", bars)
            store.save("US", "AAPL", bars.assign(close=1.6))
            loaded = store.load("US", "AAPL", 3650)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded.iloc[0].close, 1.6)
            self.assertEqual(store.latest_sync("US", "AAPL")["bars_received"], 1)


if __name__ == "__main__":
    unittest.main()
