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

# 「壊れているので開けません」と出た場合の対処を同梱（未署名／未公証アプリ向け）
cat > "$STAGE/はじめにお読みください.txt" <<'TXT'
Shiryō-Coder（史料コーダー）

インストール:
  Shiryo-Coder.app を Applications フォルダにドラッグしてください。

「"Shiryo-Coder" は壊れているため開けません」と表示される場合:
  これはアプリが Apple の公証（notarization）を受けていないためです（中身は壊れていません）。
  ターミナルで次を 1 回実行すると開けるようになります:

      xattr -dr com.apple.quarantine /Applications/Shiryo-Coder.app

  もしくは Finder でアプリを右クリック →「開く」→「開く」を選択してください。

OCR:
  tesseract と日本語データ（jpn/jpn_vert/osd）はアプリに同梱済みです。別途インストール不要。
TXT

# LZFSE 圧縮（ULFO）でサイズ削減。失敗時は UDZO にフォールバック。
if ! hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -fs HFS+ -format ULFO -ov "$DMG"; then
  hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
fi

rm -rf "$STAGE"
echo "作成しました: $DMG"
ls -lh "$DMG"
