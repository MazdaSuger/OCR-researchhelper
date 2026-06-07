"""OCR エンジンの共通インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from shiryo_coder.modules.ocr.result import OcrResult


class EngineUnavailable(RuntimeError):
    """エンジンの依存（バイナリ・SDK・認証情報）が揃っていない。"""


class OcrEngine(ABC):
    """OCR エンジンの基底クラス。

    `recognize` は前処理済みの画像（numpy 配列）またはファイルパスを受け取り、
    `OcrResult`（テキスト＋座標付きトークン）を返す。
    """

    #: UI・メタデータで使う識別名
    name: str = "base"
    #: 縦書きをサポートするか
    vertical_supported: bool = False

    @abstractmethod
    def recognize(
        self,
        image,
        *,
        vertical: bool = False,
        language: str | None = None,
    ) -> OcrResult:
        ...

    def is_available(self) -> bool:
        """このエンジンが実行可能かを返す（既定は True）。"""
        return True

    def ensure_available(self) -> None:
        if not self.is_available():
            raise EngineUnavailable(
                f"エンジン '{self.name}' は利用できません（依存が不足しています）。"
            )
