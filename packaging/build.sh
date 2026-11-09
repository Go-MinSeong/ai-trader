#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "AI Trader .app builds require macOS."
  exit 1
fi

uv run python assets/generate_icon.py
mkdir -p assets/app_icon.iconset
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/app_icon.png --out "assets/app_icon.iconset/icon_${size}x${size}.png" >/dev/null
  doubled=$((size * 2))
  sips -z "$doubled" "$doubled" assets/app_icon.png --out "assets/app_icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns assets/app_icon.iconset -o assets/app_icon.icns
rm -rf assets/app_icon.iconset build dist/AI\ Trader.app

uv run pyinstaller --noconfirm --clean \
  --distpath dist --workpath build packaging/ai_trader.spec

codesign --force --deep --sign - "dist/AI Trader.app" || true
echo "Built: $ROOT/dist/AI Trader.app"
