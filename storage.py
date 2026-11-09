from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


def data_directory() -> Path:
    path = Path.home() / "Library" / "Application Support" / "AI Trader"
    path.mkdir(parents=True, exist_ok=True)
    return path


class BarStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_directory() / "market-data.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS minute_bars (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (market, symbol, timestamp_utc)
                )""")
            db.execute("""CREATE TABLE IF NOT EXISTS sync_history (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    bars_received INTEGER NOT NULL,
                    first_bar TEXT NOT NULL,
                    last_bar TEXT NOT NULL,
                    PRIMARY KEY (market, symbol)
                )""")

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def save(self, market: str, symbol: str, bars: pd.DataFrame) -> None:
        if bars.empty:
            return
        rows = []
        for item in bars.itertuples(index=False):
            ts = pd.Timestamp(item.timestamp)
            if ts.tzinfo is None:
                raise ValueError("캐시 timestamp에는 시간대 정보가 필요합니다.")
            rows.append(
                (
                    market.upper(),
                    symbol.upper(),
                    ts.tz_convert("UTC").isoformat(),
                    float(item.open),
                    float(item.high),
                    float(item.low),
                    float(item.close),
                    float(item.volume),
                )
            )
        first_bar = min(row[2] for row in rows)
        last_bar = max(row[2] for row in rows)
        with self._connect() as db:
            db.executemany(
                """INSERT INTO minute_bars
                (market, symbol, timestamp_utc, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market, symbol, timestamp_utc) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume""",
                rows,
            )
            db.execute(
                """INSERT INTO sync_history
                (market, symbol, synced_at, bars_received, first_bar, last_bar)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(market, symbol) DO UPDATE SET
                synced_at=excluded.synced_at, bars_received=excluded.bars_received,
                first_bar=excluded.first_bar, last_bar=excluded.last_bar""",
                (
                    market.upper(),
                    symbol.upper(),
                    datetime.now(timezone.utc).isoformat(),
                    len(rows),
                    first_bar,
                    last_bar,
                ),
            )

    def load(self, market: str, symbol: str, days: int) -> pd.DataFrame:
        with self._connect() as db:
            rows = db.execute(
                """SELECT timestamp_utc, open, high, low, close, volume
                FROM minute_bars WHERE market=? AND symbol=?
                AND timestamp_utc >= ? ORDER BY timestamp_utc""",
                (
                    market.upper(),
                    symbol.upper(),
                    (
                        datetime.now(timezone.utc) - timedelta(days=int(days))
                    ).isoformat(),
                ),
            ).fetchall()
        return pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

    def latest_sync(self, market: str, symbol: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT synced_at, bars_received, first_bar, last_bar
                FROM sync_history WHERE market=? AND symbol=?""",
                (market.upper(), symbol.upper()),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("synced_at", "bars_received", "first_bar", "last_bar"), row))
