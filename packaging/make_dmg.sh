#!/usr/bin/env bash
# PyInstaller が生成した .app を、ドラッグ&ドロップ用の DMG に固める。
# 使い方: bash packaging/make_dmg.sh [出力名（拡張子なし）]
set -euo pipefail

APP="dist/Shiryo-Coder.app"
VOLNAME="Shiryo-Coder"
OUT_BASE="${1:-Shiryo-Coder}"
DMG="dist/${OUT_BASE}.dmg"

if [ ! -d "$APP" ]; then
  echo "エラー: $APP が見つかりません（先に PyInstaller を実行してください）。" >&2
  exit 1
fi

rm -f "$DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # ドラッグ先のショートカット

hdiutil create \
  -volname "$VOLNAME" \
  -srcfolder "$STAGE" \
  -fs HFS+ \
  -format UDZO \
  -ov \
  "$DMG"

rm -rf "$STAGE"
echo "作成しました: $DMG"
