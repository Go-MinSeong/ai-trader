import json
import unittest

from worldmonitor import WorldMonitorClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        return self.payload


class WorldMonitorTests(unittest.TestCase):
    def test_tool_list_connection_does_not_call_data_tools(self):
        calls = []

        def opener(request, timeout):
            body = json.loads(request.data)
            calls.append(body)
            return FakeResponse({"result": {"tools": []}})

        client = WorldMonitorClient("test-key", opener=opener)
        client.test_connection()
        self.assertEqual(calls[0]["method"], "tools/list")

    def test_news_context_extracts_headlines(self):
        def opener(request, timeout):
            return FakeResponse(
                {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "stale": False,
                                        "insights": {
                                            "generatedAt": "2026-11-09T00:00:00Z",
                                            "topStories": [
                                                {
                                                    "title": "A company headline",
                                                    "primarySource": "Example News",
                                                }
                                            ],
                                        },
                                    }
                                ),
                            }
                        ]
                    }
                }
            )

        result = WorldMonitorClient("test-key", opener=opener).get_news_context("AAPL")
        self.assertEqual(result["stories"][0]["source"], "Example News")
        self.assertFalse(result["stale"])


if __name__ == "__main__":
    unittest.main()
