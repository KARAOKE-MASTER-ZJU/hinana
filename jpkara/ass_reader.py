"""从 .ass 文件解析歌词，用于重新标注时间轴。"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import List

_TAG_RE = re.compile(r"\{[^}]*\}")

# 只保留可发音字符：平/片假名、CJK、拉丁、数字、空格和冒号
_KEEP_RE = re.compile(
    r"[^぀-ゟ゠-ヿ"  # 平假名 + 片假名
    r"一-鿿㐀-䶿豈-﫿"  # CJK 统一汉字
    r"A-Za-z0-9 :]"
)


def _clean(text: str) -> str:
    """剥离 ASS 标签 → NFKC 标准化 → 去掉非可发音字符。"""
    text = _TAG_RE.sub("", text)           # 去 {\k...} 等标签
    text = unicodedata.normalize("NFKC", text)  # ⽚→片, ⽿→耳, 全角→半角
    text = _KEEP_RE.sub("", text)          # 保留可发音字符
    return text.strip()


def extract_lyrics_from_ass(path: str) -> List[str]:
    """
    从 .ass 文件的 Dialogue 行提取纯歌词（去 k 标签、标点，NFKC 规范化）。
    保持行数与原 Dialogue 行一致，空行保留为空字符串。
    """
    lines: List[str] = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        parts = raw.split(",", 9)
        text = parts[9] if len(parts) == 10 else ""
        lines.append(_clean(text))
    return lines
