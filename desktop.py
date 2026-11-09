from __future__ import annotations

import sys
from pathlib import Path

import webview


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return root / relative


class DesktopAPI:
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


def main() -> None:
    html = resource_path("ui/index.html").read_text(encoding="utf-8")
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
