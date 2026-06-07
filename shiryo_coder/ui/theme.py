"""アプリ共通の見た目（白・オレンジ・黒のモダンテーマ）。

グローバル QSS を QApplication に適用し、全ウィジェットへ一括反映する。色は
`PALETTE` を一元管理し、コード上の配色（コーダー色など）とは独立。
"""

from __future__ import annotations

# 配色（白＝背景 / オレンジ＝アクセント / 黒＝文字）
PALETTE = {
    "bg": "#FFFFFF",          # 背景（白）
    "panel": "#FAFAFA",       # わずかに沈めた面
    "border": "#E6E6E6",      # 罫線
    "text": "#1A1A1A",        # 文字（黒）
    "muted": "#6B7280",       # 補助文字
    "accent": "#F97316",      # オレンジ（主アクセント）
    "accent_dark": "#EA580C", # ホバー/押下
    "accent_2": "#FFF1E6",    # 選択の淡いオレンジ
    "accent_3": "#FFE0C2",    # 選択（濃いめ）
    "disabled_bg": "#F0F0F0",
    "disabled_fg": "#A0A0A0",
}


def stylesheet() -> str:
    """テーマの QSS を返す。"""
    p = PALETTE
    return f"""
* {{
    font-family: "Noto Sans CJK JP", "Hiragino Sans", "Yu Gothic UI", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {p['text']};
}}
QWidget {{ background: {p['bg']}; }}
QMainWindow, QDialog {{ background: {p['bg']}; }}

/* 見出し・補助 */
QLabel {{ background: transparent; }}

/* メニューバー */
QMenuBar {{ background: {p['bg']}; border-bottom: 1px solid {p['border']}; padding: 2px; }}
QMenuBar::item {{ background: transparent; padding: 6px 12px; border-radius: 6px; }}
QMenuBar::item:selected {{ background: {p['accent_2']}; color: {p['accent_dark']}; }}
QMenu {{ background: {p['bg']}; border: 1px solid {p['border']}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['accent_2']}; color: {p['accent_dark']}; }}

/* ボタン（オレンジを主アクセントに） */
QPushButton {{
    background: {p['accent']};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {p['accent_dark']}; }}
QPushButton:pressed {{ background: {p['accent_dark']}; padding-top: 8px; }}
QPushButton:disabled {{ background: {p['disabled_bg']}; color: {p['disabled_fg']}; }}

/* 入力系 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {p['bg']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: {p['accent_3']};
    selection-color: {p['text']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p['bg']};
    border: 1px solid {p['border']};
    selection-background-color: {p['accent_2']};
    selection-color: {p['accent_dark']};
}}

/* 表 */
QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget, QListView {{
    background: {p['bg']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    alternate-background-color: {p['panel']};
    outline: 0;
}}
QTableWidget::item:selected, QTableView::item:selected,
QTreeWidget::item:selected, QTreeView::item:selected,
QListWidget::item:selected, QListView::item:selected {{
    background: {p['accent_2']};
    color: {p['accent_dark']};
}}
QHeaderView::section {{
    background: {p['panel']};
    color: {p['text']};
    border: none;
    border-bottom: 2px solid {p['accent']};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {p['panel']}; border: none; }}

/* タブ */
QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {p['muted']};
    padding: 8px 16px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {p['accent_dark']}; border-bottom: 2px solid {p['accent']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {p['text']}; }}

/* チェックボックス */
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {p['border']}; border-radius: 4px; background: {p['bg']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border: 1px solid {p['accent']}; }}

/* グループ枠 */
QGroupBox {{
    border: 1px solid {p['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
    font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {p['accent_dark']}; }}

/* 進捗バー */
QProgressBar {{
    border: 1px solid {p['border']};
    border-radius: 8px;
    text-align: center;
    background: {p['panel']};
    height: 16px;
}}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 7px; }}

/* スプリッタ・スクロールバー */
QSplitter::handle {{ background: {p['border']}; }}
QSplitter::handle:hover {{ background: {p['accent']}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D4D4D4; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p['accent']}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #D4D4D4; border-radius: 5px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {p['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ステータスバー・ツールチップ */
QStatusBar {{ background: {p['panel']}; color: {p['muted']}; border-top: 1px solid {p['border']}; }}
QToolTip {{ background: {p['text']}; color: #FFFFFF; border: none; padding: 4px 8px; border-radius: 6px; }}
"""


def apply_theme(app) -> None:
    """QApplication にテーマを適用する。"""
    app.setStyleSheet(stylesheet())
