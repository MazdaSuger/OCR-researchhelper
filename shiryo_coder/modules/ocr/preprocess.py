"""画像前処理（OpenCV）: グレースケール化・傾き補正・ノイズ除去・二値化。

仕様書 3.1「前処理: 傾き補正・二値化・ノイズ除去（OpenCV）」に対応。
すべて numpy 配列（OpenCV の BGR またはグレースケール）を入出力とする。
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessConfig:
    """前処理パイプラインの設定。各ステップは個別に無効化できる。"""

    grayscale: bool = True
    deskew: bool = True
    denoise: bool = True
    binarize: bool = True
    max_skew_deg: float = 15.0   # この角度を超える推定は誤検出として無視
    denoise_strength: int = 10

    @classmethod
    def none(cls) -> "PreprocessConfig":
        """前処理を一切行わない設定。"""
        return cls(grayscale=False, deskew=False, denoise=False, binarize=False)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """カラー画像をグレースケールに変換する（既にグレーならそのまま）。"""
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def estimate_skew(gray: np.ndarray) -> float:
    """テキストの傾き角（度）を推定する。正なら反時計回りに回転して水平化。"""
    thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 10:
        return 0.0
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    if angle < -45:
        angle = 90 + angle
    return float(angle)


def deskew(image: np.ndarray, *, max_skew_deg: float = 15.0) -> tuple[np.ndarray, float]:
    """傾きを補正した画像と、適用した角度を返す。"""
    gray = to_grayscale(image)
    angle = estimate_skew(gray)
    if abs(angle) < 0.1 or abs(angle) > max_skew_deg:
        return image, 0.0
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, angle


def denoise(gray: np.ndarray, *, strength: int = 10) -> np.ndarray:
    """非局所平均によるノイズ除去（グレースケール）。"""
    return cv2.fastNlMeansDenoising(gray, None, h=strength)


def binarize(gray: np.ndarray) -> np.ndarray:
    """大津の二値化。"""
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]


def preprocess(image: np.ndarray, config: PreprocessConfig | None = None) -> np.ndarray:
    """設定に従って前処理パイプラインを適用する。

    順序: グレースケール → 傾き補正 → ノイズ除去 → 二値化。
    """
    config = config or PreprocessConfig()
    out = image
    if config.deskew:
        out, _ = deskew(out, max_skew_deg=config.max_skew_deg)
    if config.grayscale:
        out = to_grayscale(out)
    if config.denoise:
        out = denoise(to_grayscale(out), strength=config.denoise_strength)
    if config.binarize:
        out = binarize(to_grayscale(out))
    return out
