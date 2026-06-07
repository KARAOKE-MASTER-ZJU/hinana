"""MeCab 分词封装（fugashi + unidic-lite），返回与 pykakasi 兼容的 token list。

如果 fugashi/unidic-lite 未安装，is_available() 返回 False，
上层代码自动回退到 pykakasi。
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

_tagger = None
_available: bool | None = None


def is_available() -> bool:
    global _available
    if _available is None:
        try:
            _get_tagger()
            _available = True
        except Exception as e:
            logger.debug("[mecab] unavailable: %s", e)
            _available = False
    return _available


def _get_tagger():
    global _tagger
    if _tagger is None:
        import fugashi
        import unidic_lite
        _tagger = fugashi.Tagger(f"-d {unidic_lite.DICDIR}")
    return _tagger


def tokenize(text: str) -> List[Dict[str, str]]:
    """分词，返回 [{"orig": surface, "hira": katakana_reading}]。"""
    result = []
    for word in _get_tagger()(text):
        surface = word.surface
        try:
            kana = str(word.feature.kana)
            if not kana or kana == "*":
                kana = surface
        except (AttributeError, TypeError):
            kana = surface
        result.append({"orig": surface, "hira": kana})
    return result
