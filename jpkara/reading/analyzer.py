"""三层读音分析器：(MeCab|pykakasi)+RL词典 → LLM（仅未覆盖行） → pykakasi兜底。

输出：每个日语行拆成 [(orig_char, hira_mora)] 的 flat mora 列表，
供 ass/formatter.py 与 k-时值配对。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .kana import is_kanji, is_kana, kata_to_hira, hira_to_moras, SMALL_KANA, HIRA_DIGRAPHS

logger = logging.getLogger(__name__)

# 逐行 mora 对：[(orig_char, hira_mora)]
CharMoras = List[Tuple[str, str]]


# ─────────────────────────────────────────────────────────
# pykakasi 封装
# ─────────────────────────────────────────────────────────

_kks = None

def _kakasi():
    global _kks
    if _kks is None:
        from pykakasi import kakasi
        _kks = kakasi()
    return _kks


# ─────────────────────────────────────────────────────────
# 分词（MeCab 优先，pykakasi 兜底）
# ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[Dict]:
    """返回 [{"orig": str, "hira": str}]，优先 MeCab，否则 pykakasi。"""
    from .mecab_tokenizer import is_available as mecab_ok, tokenize as mecab_tok
    if mecab_ok():
        return mecab_tok(text)
    return _kakasi().convert(text)


# ─────────────────────────────────────────────────────────
# 字符→mora 分配（kana 锚点法）
# ─────────────────────────────────────────────────────────

def _distribute(orig: str, hira: str, out: List[Tuple[str, str]]) -> None:
    """把 hira 按 kana 锚点分配到 orig 各字符，结果 append 到 out。"""
    hira = kata_to_hira(hira)
    hi = list(hira)
    oi = 0
    while oi < len(orig):
        c = orig[oi]
        if is_kana(c):
            next_c = orig[oi + 1] if oi + 1 < len(orig) else ""
            if next_c and next_c in SMALL_KANA and is_kana(next_c):
                pair_hira = kata_to_hira(c) + kata_to_hira(next_c)
                if pair_hira in HIRA_DIGRAPHS:
                    if len(hi) >= 2 and kata_to_hira(hi[0]) + kata_to_hira(hi[1]) == pair_hira:
                        hi.pop(0); hi.pop(0)
                    elif hi and kata_to_hira(hi[0]) == kata_to_hira(c):
                        hi.pop(0)
                    pair_str = c + next_c
                    for hm, _ in hira_to_moras(pair_hira):
                        out.append((pair_str, hm))
                    oi += 2
                    continue
            hc = kata_to_hira(c)
            if hi and kata_to_hira(hi[0]) == hc:
                hi.pop(0)
            for hm, _ in hira_to_moras(hc):
                out.append((c, hm))
            oi += 1
        elif is_kanji(c):
            end = oi + 1
            while end < len(orig) and is_kanji(orig[end]):
                end += 1
            kanji_block = orig[oi:end]

            if end < len(orig):
                next_hc = kata_to_hira(orig[end])
                anchor = next((j for j, h in enumerate(hi) if kata_to_hira(h) == next_hc), None)
                consumed = hi[:anchor] if anchor is not None else hi[:len(kanji_block)]
                hi = hi[anchor:] if anchor is not None else hi[len(kanji_block):]
            else:
                consumed = hi[:]
                hi = []

            reading = "".join(consumed)
            moras = hira_to_moras(reading)

            if len(kanji_block) == 1:
                for hm, _ in moras:
                    out.append((kanji_block[0], hm))
            else:
                weights = []
                for ki in kanji_block:
                    sub = _kakasi().convert(ki)
                    n = len(hira_to_moras(kata_to_hira(sub[0]["hira"]))) if sub else 1
                    weights.append(max(1, n))
                total_w = sum(weights)
                total_m = len(moras)
                allocated = 0
                mi = 0
                for wi, (ki, w) in enumerate(zip(kanji_block, weights)):
                    if wi == len(kanji_block) - 1:
                        cnt = total_m - allocated
                    else:
                        cnt = max(1, round(w / total_w * total_m))
                        allocated += cnt
                    for j in range(cnt):
                        out.append((ki, moras[mi][0] if mi < len(moras) else ""))
                        mi += 1
            oi = end
        else:
            oi += 1


def _pairs_to_char_moras(pairs: List[Tuple[str, str]]) -> CharMoras:
    """LLM/RL 返回的 (surface, hira) 序列 → flat (orig_char, hira_mora)。"""
    out: List[Tuple[str, str]] = []
    for surface, hira in pairs:
        _distribute(surface, hira, out)
    return out


# ─────────────────────────────────────────────────────────
# pykakasi 回退
# ─────────────────────────────────────────────────────────

def _pykakasi_char_moras(jp_line: str) -> CharMoras:
    tokens = _kakasi().convert(jp_line)
    out: List[Tuple[str, str]] = []
    for tok in tokens:
        _distribute(tok["orig"], kata_to_hira(tok["hira"]), out)
    return out


def _pykakasi_line_romaji(jp_line: str) -> str:
    tokens = _kakasi().convert(jp_line)
    return " ".join(t["hepburn"].strip() for t in tokens if t["hepburn"].strip())


# ─────────────────────────────────────────────────────────
# 三层分析器
# ─────────────────────────────────────────────────────────

class ReadingAnalyzer:
    """
    分析整首歌词读音，优先级：(MeCab|pykakasi)+RL词典 → LLM（仅未覆盖行）→ pykakasi。

    用法：
        analyzer = ReadingAnalyzer(llm_client=..., rl_dict=...)
        char_moras_list = analyzer.analyze_lines(jp_lines)
        romaji_lines = analyzer.to_romaji_lines(jp_lines)
    """

    def __init__(
        self,
        llm_client=None,
        rl_dict=None,
        use_llm: bool = True,
        use_rl: bool = True,
    ):
        self._llm = llm_client
        self._rl = rl_dict
        self._use_llm = use_llm and llm_client is not None
        self._use_rl = use_rl and rl_dict is not None

    def _tokenize_and_rl(self, jp_line: str) -> Tuple[List[Tuple[str, str]], bool]:
        """
        用 MeCab/pykakasi 分词，RL 词典覆盖读音。
        返回 (pairs, all_kanji_covered)。
        """
        tokens = _tokenize(jp_line)
        pairs: List[Tuple[str, str]] = []
        all_covered = True
        for tok in tokens:
            orig = tok["orig"]
            has_kanji = any(is_kanji(c) for c in orig)
            rl_reading = self._rl.get(orig) if self._use_rl else None
            if rl_reading:
                pairs.append((orig, rl_reading))
            else:
                pairs.append((orig, kata_to_hira(tok["hira"])))
                if has_kanji:
                    all_covered = False
        return pairs, all_covered

    def analyze_lines(self, jp_lines: List[str]) -> List[CharMoras]:
        """
        返回每行的 [(orig_char, hira_mora)]。

        Pass 1: MeCab/pykakasi + RL 词典（速度快，无副作用）
        Pass 2: 对 RL 未覆盖行调用 LLM（批量，仅在需要时）
        """
        # Pass 1
        pass1: List[Tuple[List[Tuple[str, str]], bool]] = [
            self._tokenize_and_rl(line) for line in jp_lines
        ]

        # Pass 2: LLM 仅对未完全覆盖的行
        llm_override: Dict[int, CharMoras] = {}
        if self._use_llm and self._llm.is_configured():
            uncov_idx = [i for i, (_, cov) in enumerate(pass1) if not cov]
            if uncov_idx:
                uncov_lines = [jp_lines[i] for i in uncov_idx]
                logger.info(
                    "[analyzer] RL uncovered %d/%d lines, calling LLM...",
                    len(uncov_idx), len(jp_lines),
                )
                mapping, err = self._llm.annotate_lines(uncov_lines)
                if err:
                    logger.warning("[analyzer] LLM error: %s", err)
                else:
                    for local_j, pairs in mapping.items():
                        global_i = uncov_idx[local_j]
                        llm_override[global_i] = _pairs_to_char_moras(pairs)
                    logger.info("[analyzer] LLM covered %d lines", len(llm_override))

        return [
            llm_override[i] if i in llm_override else _pairs_to_char_moras(pairs)
            for i, (pairs, _) in enumerate(pass1)
        ]

    def to_romaji_lines(self, jp_lines: List[str]) -> List[str]:
        """生成对应每行的罗马音字符串（yohane 输入格式）。"""
        result = []
        for line in jp_lines:
            tokens = _tokenize(line)
            words = []
            for tok in tokens:
                orig = tok["orig"]
                rl = self._rl.get(orig) if self._use_rl else None
                hira = kata_to_hira(rl if rl else tok["hira"])
                rom = "".join(r for _, r in hira_to_moras(hira))
                if rom:
                    words.append(rom)
            result.append(" ".join(words) if words else _pykakasi_line_romaji(line))
        return result
