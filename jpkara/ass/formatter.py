"""ASS 行格式化器：把 (orig_char, hira_mora) + k值 → 各种注音格式。"""

from __future__ import annotations

import re
from typing import List, Tuple

from jpkara.reading.kana import is_kanji

# [(k_value, mora_text)]
KFlat = List[Tuple[int, str]]

_K_RE = re.compile(r"\{\\k(\d+)\}([^{]*)")


def parse_k_flat(ass_text: str) -> KFlat:
    """从 ASS k-tag 文本提取 [(k_val, mora)] —— 去掉空格、空 mora。"""
    return [
        (int(m.group(1)), m.group(2).strip())
        for m in _K_RE.finditer(ass_text)
        if m.group(2).strip()
    ]


def build_furigana(char_moras: List[Tuple[str, str]], k_flat: KFlat) -> str:
    """
    生成 aegisub-tools 兼容的振仮名格式：

    - 漢字首 mora → {\\kN}字|<よみ
    - 漢字续 mora → {\\kN}#|<よみ
    - 假名 mora    → {\\kN}か
    """
    n = min(len(char_moras), len(k_flat))
    parts = []
    prev_char = None
    for i in range(n):
        ch, hm = char_moras[i]
        k = k_flat[i][0]
        if len(ch) == 1 and is_kanji(ch):
            if ch != prev_char:
                parts.append(f"{{\\k{k}}}{ch}|<{hm}")
            else:
                parts.append(f"{{\\k{k}}}#|<{hm}")
        else:
            parts.append(f"{{\\k{k}}}{ch}")
        prev_char = ch
    return "".join(parts)


def build_kana(char_moras: List[Tuple[str, str]], k_flat: KFlat) -> str:
    """平假名注音格式：每个 mora 换成对应的假名。"""
    n = min(len(char_moras), len(k_flat))
    return "".join(f"{{\\k{k_flat[i][0]}}}{char_moras[i][1]}" for i in range(n))


def build_romaji(k_flat: KFlat) -> str:
    """重建 yohane 原始罗马音输出（保留空格分词）。"""
    return "".join(f"{{\\k{k}}}{m}" for k, m in k_flat)
