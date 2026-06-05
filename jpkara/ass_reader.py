"""从 .ass 文件解析歌词，用于重新标注时间轴。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List

_TAG_RE = re.compile(r"\{[^}]*\}")

# 只保留可发音字符：平/片假名、CJK、拉丁、数字、空格和冒号
_KEEP_RE = re.compile(
    "["
    "^぀-ゟ"   # 平假名
    "゠-ヿ"    # 片假名
    "一-鿿"    # CJK 统一汉字
    "㐀-䶿"    # CJK 扩展 A
    "A-Za-z0-9 :"
    "]"
)

# 含有平假名 / 片假名 / CJK 才算日文行
_JP_RE = re.compile(
    "["
    "぀-ゟ"
    "゠-ヿ"
    "一-鿿"
    "㐀-䶿"
    "]"
)


def _clean(text: str) -> str:
    """剥离 ASS 标签 → NFKC 标准化（⽚→片）→ 去掉非可发音字符。"""
    text = _TAG_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = _KEEP_RE.sub("", text)
    return text.strip()


def _has_japanese(text: str) -> bool:
    return bool(_JP_RE.search(text))


@dataclass
class AssDialogue:
    raw: str           # 原始行（含完整时间轴）
    text: str          # 清理后歌词文本
    actor: str         # Name 字段（说话人）
    is_japanese: bool  # False → 不送 yohane，保留原始时间轴


def parse_ass_dialogues(path: str) -> List[AssDialogue]:
    """
    解析 .ass Dialogue 行，返回结构化列表。
    is_japanese=False 的行（3:38 pm 等纯数字/英文）保留原始时间轴，不送 yohane。
    """
    result: List[AssDialogue] = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        parts = raw.split(",", 9)
        actor = parts[4].strip() if len(parts) >= 5 else ""
        text = _clean(parts[9] if len(parts) == 10 else "")
        result.append(AssDialogue(raw=raw, text=text, actor=actor, is_japanese=_has_japanese(text)))
    return result


def extract_lyrics_from_ass(path: str) -> List[str]:
    """仅返回歌词文本列表（兼容旧接口）。"""
    return [d.text for d in parse_ass_dialogues(path)]
