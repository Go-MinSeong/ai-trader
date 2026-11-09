# AI Trader

Toss Securities Open API로 미국·한국 주식의 1분봉을 모아 로컬에서 5분봉 ORB 백테스트를 실행하는 macOS 데스크톱 앱입니다. PyWebView가 번들된 HTML 화면을 띄우며 웹 서버나 브라우저를 시작하지 않습니다. 모든 거래는 가상 자금으로만 계산하고 주문 API는 사용하지 않습니다.

## 실행

```bash
uv sync --dev
uv run python desktop.py
```

일반 사용자용 앱은 `dist/AI Trader.app`입니다. Finder에서 이 앱을 열거나 다음 명령으로 바로 실행할 수 있습니다.

```bash
open "dist/AI Trader.app"
```

앱을 열면 합성 데이터 데모가 자동으로 표시됩니다. 실시간 시세 수집은 인터넷 연결과 Toss Open API 자격 증명이 필요하며, 키를 준비한 뒤 `데이터 설정`에서 연결합니다.

Toss Securities WTS에서 개인용 [Open API](https://developers.tossinvest.com/docs) 키를 발급한 뒤, 앱에서 Client ID와 Secret을 입력합니다. API 호출 허용 IP 등록이 필요할 수 있습니다. 연결이 확인되면 자격 증명은 macOS 키체인에 저장됩니다.

패키징된 앱은 다음으로 빌드합니다.

```bash
bash packaging/build.sh
open "dist/AI Trader.app"
```

## 데이터

- Toss 캔들 API의 1분봉을 로컬에서 5분봉으로 집계합니다. API가 제공하는 이력 범위가 정해져 있어 1~365일을 요청할 수 있지만, 원하는 전체 기간이 반환된다는 보장은 없습니다.
- 원본 분봉은 `~/Library/Application Support/AI Trader/market-data.sqlite3`에 저장합니다. API 키와 시세 데이터는 Git 저장소에 포함하지 않습니다.
- 시장 데이터는 개인의 자체 거래 목적으로만 사용하고 제3자에게 재배포하지 않습니다. 현재 앱은 회사 계정이나 외부 저장소로 데이터를 전송하지 않습니다.
- WorldMonitor는 선택형 뉴스 맥락 기능으로만 연결됩니다. 키 입력 후 연결 확인은 도구 목록만 읽고, 뉴스 데이터는 사용자가 `뉴스 맥락 조회`를 눌렀을 때만 요청합니다. 해당 호출은 계정의 접근 권한이나 API 할당량을 사용할 수 있습니다. WorldMonitor는 일반적인 임의 종목 OHLCV 공급자가 아니므로 Toss 시세를 대체하지 않습니다.

## 백테스트 가정

- 매일 첫 3개의 완전한 5분봉으로 15분 시가 범위를 계산합니다. 봉이 불완전하면 해당 날짜는 건너뜁니다.
- 이후 종가가 범위 고점을 넘으면 그 종가에 진입했다고 가정합니다. 하루 최대 한 번 진입하고, 손절은 시가 범위 중간값, 목표는 설정한 R 배수입니다.
- 거래당 잔고 위험 한도, 가상 초기 자금, 편도 수수료(bp), 매수·매도 슬리피지를 반영합니다. 수수료는 사용자가 입력하는 근사치이며 거래세·환전 비용 등은 포함하지 않습니다.
- 한 봉에서 손절과 목표가가 모두 닿으면 손절이 먼저 체결된 것으로 계산합니다. 장 마감까지 청산 조건이 없으면 마지막 봉 종가로 정리합니다.
- 에이전트 검토 패널은 표본 크기, 데이터 완전성, 낙폭을 확인하는 결정적 규칙 검사입니다. WorldMonitor는 요청 시 별도 뉴스 출처를 제공합니다. 이 앱은 LLM 판단을 거래 신호로 사용하지 않습니다.

승률 하나로 수익성을 판단하지 마세요. 실제 결과는 데이터 범위와 품질, 거래 수, 거래 비용 가정, 최대 낙폭과 함께 봐야 하며 과거 시뮬레이션이 미래 성과를 보장하지 않습니다.

## 참고한 프로젝트

- [`day-trader-skill`](https://github.com/Jakeschincariol/day-trader-skill): 계산기와 시뮬레이션을 분리하는 방식, 보수적 체결 가정, 결정적 테스트 아이디어를 참고했습니다. 해당 저장소는 MIT 라이선스입니다. 이 프로젝트에는 원본 코드를 복사하지 않았습니다.
- [`TradingAgents`](https://github.com/TauricResearch/TradingAgents): 분석·리스크 역할을 나눠 결과를 검토하는 개념을 참고했습니다. 이 프로젝트의 기본 검토는 재현 가능한 로컬 규칙으로 계산합니다.
- [`WorldMonitor`](https://github.com/koala73/worldmonitor): 뉴스와 거시 맥락을 위한 MCP 연동만 사용합니다. WorldMonitor 원본 저장소는 AGPL-3.0-only이고 공식 SDK는 MIT로 별도 배포되지만, 이 저장소는 SDK/플랫폼 코드를 복사하거나 번들링하지 않습니다. 호스팅 서비스와 반환 데이터에는 별도 이용 조건이 적용됩니다.

## 개발 확인

```bash
uv run python -m unittest discover -s tests -v
uv run black --check desktop.py storage.py strategy.py toss_market.py worldmonitor.py tests
```
