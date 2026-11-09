from __future__ import annotations

import json
import urllib.error
import urllib.request

MCP_URL = "https://worldmonitor.app/mcp"


class WorldMonitorError(Exception):
    pass


class WorldMonitorClient:
    def __init__(self, api_key: str, opener=None):
        if not api_key.strip():
            raise ValueError("WorldMonitor API key가 필요합니다.")
        self.api_key = api_key.strip()
        self.opener = opener or urllib.request.urlopen

    def _call(self, method: str, params: dict) -> dict:
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode()
        request = urllib.request.Request(
            MCP_URL,
            data=payload,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "X-WorldMonitor-Key": self.api_key,
                "User-Agent": "AI-Trader/0.2",
            },
        )
        try:
            with self.opener(request, timeout=20) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise WorldMonitorError("WorldMonitor 응답이 예상보다 큽니다.")
            result = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise WorldMonitorError(
                    "WorldMonitor 인증 또는 이용 권한을 확인해 주세요."
                ) from None
            raise WorldMonitorError(
                f"WorldMonitor 요청이 실패했습니다 (HTTP {exc.code})."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise WorldMonitorError("WorldMonitor에 연결하지 못했습니다.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorldMonitorError("WorldMonitor 응답을 읽지 못했습니다.") from exc
        if "error" in result:
            message = result["error"].get("message", "MCP 요청 오류")
            raise WorldMonitorError(f"WorldMonitor MCP: {message}")
        return result.get("result", {})

    def test_connection(self) -> None:
        result = self._call("tools/list", {})
        if not isinstance(result.get("tools"), list):
            raise WorldMonitorError("WorldMonitor 도구 목록을 확인하지 못했습니다.")

    def get_news_context(self, symbol: str) -> dict:
        result = self._call(
            "tools/call",
            {
                "name": "get_news_intelligence",
                "arguments": {"query": symbol, "limit": 5},
            },
        )
        content = result.get("content", [])
        if not content or content[0].get("type") != "text":
            raise WorldMonitorError("뉴스 맥락 응답이 비어 있습니다.")
        try:
            data = json.loads(content[0]["text"])
        except json.JSONDecodeError as exc:
            raise WorldMonitorError("뉴스 맥락 데이터를 읽지 못했습니다.") from exc
        if "_budget_exceeded" in data:
            raise WorldMonitorError("WorldMonitor API 응답 한도를 넘었습니다.")
        insights = data.get("insights", data)
        stories = insights.get("topStories", []) if isinstance(insights, dict) else []
        return {
            "symbol": symbol,
            "stale": bool(data.get("stale", False)),
            "generated_at": (
                insights.get("generatedAt") if isinstance(insights, dict) else None
            ),
            "stories": [
                {
                    "title": story.get("title", "제목 없음"),
                    "source": story.get("primarySource", "출처 미상"),
                    "url": story.get("url"),
                }
                for story in stories[:5]
            ],
        }
