#!/usr/bin/env bash
# tesseract 本体・依存 dylib・tessdata を .app に同梱する（macOS 専用）。
# 前提: brew install tesseract tesseract-lang dylibbundler
# 使い方: bash packaging/bundle_tesseract.sh [dist/Shiryo-Coder.app]
set -euo pipefail

APP="${1:-dist/Shiryo-Coder.app}"
if [ ! -d "$APP" ]; then
  echo "エラー: $APP が見つかりません。" >&2
  exit 1
fi

TESS_BIN="$(command -v tesseract || true)"
if [ -z "$TESS_BIN" ]; then
  echo "tesseract が見つからないため同梱をスキップします（brew install tesseract）。" >&2
  exit 0
fi

MACOS="$APP/Contents/MacOS"
RES="$APP/Contents/Resources"
LIBS="$APP/Contents/libs"
mkdir -p "$MACOS" "$RES" "$LIBS"

# 本体
cp -f "$TESS_BIN" "$MACOS/tesseract"
chmod +x "$MACOS/tesseract"

# 依存 dylib を収集し install_name を @executable_path/../libs/ に書き換え
if command -v dylibbundler >/dev/null; then
  dylibbundler -of -cd -b \
    -x "$MACOS/tesseract" \
    -d "$LIBS" \
    -p "@executable_path/../libs/"
else
  echo "警告: dylibbundler が無いため依存 dylib が解決されない可能性があります。" >&2
fi

# tessdata（言語データ）。jpn/jpn_vert は tesseract-lang が提供。
TESSDATA_DIR="$(dirname "$TESS_BIN")/../share/tessdata"
if [ -d "$TESSDATA_DIR" ]; then
  mkdir -p "$RES/tessdata"
  cp -f "$TESSDATA_DIR"/*.traineddata "$RES/tessdata/" 2>/dev/null || true
  echo "同梱した tessdata:"
  ls "$RES/tessdata" | sed 's/\.traineddata$//' | paste -sd' ' -
else
  echo "警告: tessdata が見つかりません（$TESSDATA_DIR）。" >&2
fi

echo "tesseract を $APP に同梱しました。"
