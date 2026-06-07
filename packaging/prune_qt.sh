#!/usr/bin/env bash
# 未使用の Qt ライブラリ/プラグインをビルド済みバンドルから削除してサイズを削減する。
# モジュール除外（spec の excludes）では Qt の共有ライブラリ本体は残るため、後処理で消す。
# 本アプリが使うのは QtCore / QtGui / QtWidgets（＋プラットフォーム/画像プラグイン）のみ。
# 使い方: bash packaging/prune_qt.sh [対象ディレクトリ（.app か dist/Shiryo-Coder）]
set -euo pipefail

TARGET="${1:-dist/Shiryo-Coder.app}"
[ -e "$TARGET" ] || { echo "対象が見つかりません: $TARGET" >&2; exit 1; }

before=$(du -sm "$TARGET" 2>/dev/null | cut -f1 || echo "?")

# 削除して安全な Qt モジュール（QtWidgets/Gui/Core から参照されない）
NAMES="
Qml Qml.network QmlModels QmlWorkerScript QmlMeta QmlLocalStorage QmlXmlListModel
QmlCompiler QmlCore QmlAsset
Quick Quick3D QuickControls2 QuickControls2Impl QuickWidgets QuickTemplates2
QuickShapes2 QuickParticles QuickLayouts QuickTimeline QuickDialogs2 QuickDialogs2Utils
QuickDialogs2QuickImpl QuickEffects QuickControls2Basic QuickControls2Material
QuickControls2Fusion QuickControls2Imagine QuickControls2Universal
VirtualKeyboard VirtualKeyboardQml VirtualKeyboardSettings
3DCore 3DRender 3DExtras 3DInput 3DAnimation 3DLogic 3DQuick 3DQuickRender
Charts ChartsQml DataVisualization DataVisualizationQml Graphs GraphsWidgets
Multimedia MultimediaWidgets MultimediaQuick SpatialAudio
Pdf PdfQuick Designer DesignerComponents Help UiTools
Bluetooth Nfc Positioning PositioningQuick Location Sensors SensorsQuick
SerialPort SerialBus RemoteObjects RemoteObjectsQml Scxml ScxmlQml TextToSpeech
StateMachine StateMachineQml WebEngineCore WebEngineQuick WebEngineWidgets
WebSockets WebChannel WebChannelQuick WebView WebViewQuick NetworkAuth Sql Test
"

for name in $NAMES; do
  # Linux (.so) / macOS (.dylib) の共有ライブラリ
  find "$TARGET" -type f \
    \( -name "libQt6${name}.so*" -o -name "libQt6${name}.*.dylib" -o -name "libQt6${name}.dylib" \) \
    -delete 2>/dev/null || true
  # macOS framework
  find "$TARGET" -type d -name "Qt${name}.framework" -exec rm -rf {} + 2>/dev/null || true
done

# 不要なプラグイン/ディレクトリ（platforms・imageformats・styles は残す）
for d in qml \
         plugins/sqldrivers plugins/multimedia plugins/position plugins/sensors \
         plugins/qmltooling plugins/webview plugins/platforminputcontexts \
         plugins/texttospeech plugins/playlistformats plugins/renderers \
         plugins/geometryloaders plugins/sceneparsers plugins/assetimporters; do
  find "$TARGET" -type d -path "*/$d" -exec rm -rf {} + 2>/dev/null || true
done

after=$(du -sm "$TARGET" 2>/dev/null | cut -f1 || echo "?")
echo "Qt prune: ${before}MB -> ${after}MB  ($TARGET)"
