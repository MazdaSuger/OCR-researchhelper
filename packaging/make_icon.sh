#!/usr/bin/env bash
# packaging/icon.png から macOS の .icns を生成する（sips/iconutil 必須＝macOS 専用）。
# 出力: packaging/Shiryo-Coder.icns
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/icon.png"
ICONSET="$HERE/Shiryo-Coder.iconset"
ICNS="$HERE/Shiryo-Coder.icns"

if [ ! -f "$SRC" ]; then
  echo "エラー: $SRC が見つかりません（python packaging/make_icon.py を実行）。" >&2
  exit 1
fi
if ! command -v iconutil >/dev/null || ! command -v sips >/dev/null; then
  echo "iconutil/sips が無いため .icns 生成をスキップ（macOS 以外）。" >&2
  exit 0
fi

rm -rf "$ICONSET" "$ICNS"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size"        "$SRC" --out "$ICONSET/icon_${size}x${size}.png"   >/dev/null
  sips -z $((size*2)) $((size*2)) "$SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"
echo "作成しました: $ICNS"
