from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

BASE_URL = "https://openapi.tossinvest.com"
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")
PAGE_SIZE = 200
MAX_PAGES = 600


class TossAPIError(Exception):
    pass


def validate_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        raise ValueError(
            "종목 코드를 확인해 주세요. 영문·숫자·점·하이픈만 사용할 수 있습니다."
        )
    return value


class TossMarketClient:
    def __init__(self, client_id: str, client_secret: str, opener=None, sleeper=None):
        if not client_id.strip() or not client_secret:
            raise ValueError("Toss Open API client ID와 secret이 필요합니다.")
        self.client_id = client_id.strip()
        self.client_secret = client_secret
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper or time.sleep
        self._token = None
        self._token_expires = 0.0

    def _request_json(
        self, path: str, *, method="GET", params=None, body=None, token=None
    ):
        url = BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json", "User-Agent": "AI-Trader/0.4"}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )

        for attempt in range(4):
            try:
                with self.opener(request, timeout=20) as response:
                    payload = response.read(5_000_001)
                if len(payload) > 5_000_000:
                    raise TossAPIError("Toss API 응답이 예상보다 큽니다.")
                return json.loads(payload.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After", "1")
                try:
                    exc.close()
                except Exception:
                    pass
                if status == 429 and attempt < 3:
                    try:
                        delay = min(max(float(retry_after), 0.25), 10)
                    except ValueError:
                        delay = 1
                    self.sleeper(delay)
                    continue
                if status in (401, 403):
                    raise TossAPIError(
                        "Toss 인증에 실패했습니다. 키가 유효한지, 호출 허용 IP가 등록됐는지 확인해 주세요."
                    ) from None
                if status == 404:
                    raise TossAPIError(
                        "종목 또는 Toss API 경로를 찾지 못했습니다."
                    ) from None
                if status == 429:
                    raise TossAPIError(
                        "Toss API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."
                    ) from None
                raise TossAPIError(
                    f"Toss API 요청이 실패했습니다 (HTTP {status})."
                ) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise TossAPIError(
                    "Toss API에 연결하지 못했습니다. 네트워크를 확인해 주세요."
                ) from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise TossAPIError("Toss API 응답을 읽지 못했습니다.") from exc
        raise TossAPIError(
            "Toss API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."
        )

    def get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires - 60:
            return self._token
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode()
        response = self._request_json("/oauth2/token", method="POST", body=body)
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise TossAPIError("Toss API가 access token을 반환하지 않았습니다.")
        self._token = token
        self._token_expires = now + int(response.get("expires_in", 86400))
        return token

    def test_connection(self, symbol="AAPL") -> None:
        self.fetch_minute_bars(symbol, days=1, max_pages=1)

    def fetch_minute_bars(
        self, symbol: str, days: int, max_pages=MAX_PAGES
    ) -> pd.DataFrame:
        symbol = validate_symbol(symbol)
        if not 1 <= int(days) <= 365:
            raise ValueError("조회 기간은 1~365일이어야 합니다.")
        token = self.get_token()
        start = datetime.now(timezone.utc) - timedelta(days=int(days))
        before = None
        seen = set()
        rows = []

        for page in range(max_pages):
            params = {
                "symbol": symbol,
                "interval": "1m",
                "count": PAGE_SIZE,
                "adjusted": "true",
            }
            if before:
                params["before"] = before
            response = self._request_json("/api/v1/candles", params=params, token=token)
            result = response.get("result", {})
            candles = result.get("candles", [])
            if not isinstance(candles, list):
                raise TossAPIError("Toss API의 캔들 응답 형식이 올바르지 않습니다.")
            for candle in candles:
                try:
                    timestamp = pd.Timestamp(candle["timestamp"])
                    if timestamp.tzinfo is None:
                        raise ValueError
                    row = {
                        "timestamp": timestamp,
                        "open": float(candle["openPrice"]),
                        "high": float(candle["highPrice"]),
                        "low": float(candle["lowPrice"]),
                        "close": float(candle["closePrice"]),
                        "volume": float(candle["volume"]),
                    }
                    if timestamp.tz_convert("UTC").to_pydatetime() >= start:
                        rows.append(row)
                except (KeyError, TypeError, ValueError) as exc:
                    raise TossAPIError(
                        "Toss API에 읽을 수 없는 캔들 항목이 있습니다."
                    ) from exc

            next_before = result.get("nextBefore")
            if not candles or not next_before or next_before in seen:
                break
            seen.add(next_before)
            oldest = min(pd.Timestamp(c["timestamp"]) for c in candles)
            if oldest.tz_convert("UTC").to_pydatetime() <= start:
                break
            before = next_before
            if page < max_pages - 1:
                self.sleeper(0.05)

        if not rows:
            raise TossAPIError(
                "선택한 기간의 분봉을 받지 못했습니다. 종목과 데이터 보관 범위를 확인해 주세요."
            )
        return (
            pd.DataFrame(rows)
            .drop_duplicates("timestamp")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )


def aggregate_to_five_minutes(frame: pd.DataFrame, market: str) -> pd.DataFrame:
    timezone_name, open_time, close_time = {
        "US": ("America/New_York", "09:30", "16:00"),
        "KR": ("Asia/Seoul", "09:00", "15:30"),
    }.get(market.upper(), (None, None, None))
    if timezone_name is None:
        raise ValueError("시장 코드는 US 또는 KR이어야 합니다.")
    if frame.empty:
        raise ValueError("1분봉 데이터가 없습니다.")

    bars = frame.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True).dt.tz_convert(
        timezone_name
    )
    bars = bars.sort_values("timestamp").drop_duplicates("timestamp")
    clocks = bars["timestamp"].dt.strftime("%H:%M")
    bars = bars[(clocks >= open_time) & (clocks < close_time)]
    if bars.empty:
        raise ValueError(f"선택한 기간에 {market} 정규장 분봉이 없습니다.")

    output = []
    for session, day in bars.groupby(bars["timestamp"].dt.date, sort=True):
        grouped = day.set_index("timestamp").resample(
            "5min", origin="start_day", closed="left", label="left"
        )
        candles = grouped.agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            minute_bars=("close", "count"),
        ).dropna(subset=["open", "high", "low", "close"])
        candle_clocks = candles.index.strftime("%H:%M")
        candles = candles[(candle_clocks >= open_time) & (candle_clocks < close_time)]
        candles["session"] = session
        output.append(candles.reset_index(names="timestamp"))
    return (
        pd.concat(output, ignore_index=True)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
