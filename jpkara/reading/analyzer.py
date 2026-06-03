"""三层读音分析器：RL词典 → LLM → pykakasi。

输出：每个日语行拆成 [(orig_char, hira_mora)] 的 flat mora 列表，
供 ass/formatter.py 与 k-时值配对。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .kana import is_kanji, is_kana, kata_to_hira, hira_to_moras

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
            hc = kata_to_hira(c)
            if hi and kata_to_hira(hi[0]) == hc:
                hi.pop(0)
            for hm, _ in hira_to_moras(hc):
                out.append((c, hm))
            oi += 1
        elif is_kanji(c):
            # 找下一个 kana 锚点确定汉字块的边界
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
                # 用各字单独读音的 mora 数作权重，按比例切分
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
            oi += 1  # 跳过标点/空格


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
    分析整首歌词的读音，优先级：RL词典 → LLM → pykakasi。

    用法：
        analyzer = ReadingAnalyzer(llm_client=..., rl_dict=...)
        char_moras_list = analyzer.analyze_lines(jp_lines)
        romaji_lines = analyzer.to_romaji_lines(jp_lines)
    """

    def __init__(
        self,
        llm_client=None,   # LLMReadingClient | None
        rl_dict=None,      # RLDictionary | None
        use_llm: bool = True,
        use_rl: bool = True,
    ):
        self._llm = llm_client
        self._rl = rl_dict
        self._use_llm = use_llm and llm_client is not None
        self._use_rl = use_rl and rl_dict is not None

        # LLM cache: line_text → Pairs
        self._llm_cache: Dict[str, List[Tuple[str, str]]] = {}
        self._llm_prewarmed = False

    def _prewarm_llm(self, lines: List[str]) -> None:
        """一次性批量 LLM 注音整首歌词并缓存。"""
        if self._llm_prewarmed or not self._use_llm:
            return
        self._llm_prewarmed = True
        if not self._llm.is_configured():
            logger.warning("[analyzer] LLM not configured, skipping")
            return
        logger.info("[analyzer] calling LLM for %d lines", len(lines))
        mapping, err = self._llm.annotate_lines(lines)
        if err:
            logger.warning("[analyzer] LLM error: %s", err)
            return
        for idx, pairs in mapping.items():
            self._llm_cache[lines[idx]] = pairs
        logger.info("[analyzer] LLM cached %d/%d lines", len(self._llm_cache), len(lines))

    def analyze_lines(self, jp_lines: List[str]) -> List[CharMoras]:
        """返回每行的 [(orig_char, hira_mora)] 列表。"""
        # 批量预热 LLM（单次 HTTP 请求）
        if self._use_llm:
            self._prewarm_llm(jp_lines)

        return [self._analyze_one(line) for line in jp_lines]

    def _analyze_one(self, jp_line: str) -> CharMoras:
        # 1. LLM cache
        if self._use_llm and jp_line in self._llm_cache:
            logger.debug("[analyzer] LLM hit: %s", jp_line[:20])
            return _pairs_to_char_moras(self._llm_cache[jp_line])

        # 2. RL 词典：逐 token 查询（pykakasi 分词 + RL 读音覆盖）
        if self._use_rl:
            tokens = _kakasi().convert(jp_line)
            pairs: List[Tuple[str, str]] = []
            all_rl = True
            for tok in tokens:
                orig = tok["orig"]
                rl_reading = self._rl.get(orig)
                if rl_reading:
                    logger.debug("[analyzer] RL hit: %s→%s", orig, rl_reading)
                    pairs.append((orig, rl_reading))
                else:
                    all_rl = False
                    pairs.append((orig, kata_to_hira(tok["hira"])))
            if all_rl:
                return _pairs_to_char_moras(pairs)
            # 部分命中也用（RL覆盖了正确的，pykakasi 兜底其余）
            return _pairs_to_char_moras(pairs)

        # 3. pykakasi 纯回退
        logger.debug("[analyzer] pykakasi fallback: %s", jp_line[:20])
        return _pykakasi_char_moras(jp_line)

    def to_romaji_lines(self, jp_lines: List[str]) -> List[str]:
        """生成对应每行的罗马音字符串（用于 yohane 输入）。"""
        # 预热 LLM
        if self._use_llm:
            self._prewarm_llm(jp_lines)

        result = []
        for line in jp_lines:
            # 从 LLM 缓存生成罗马音（更准确）
            if self._use_llm and line in self._llm_cache:
                pairs = self._llm_cache[line]
                from .kana import hira_to_moras as _h2m
                words = []
                for surface, hira in pairs:
                    moras = _h2m(kata_to_hira(hira))
                    words.append("".join(rom for _, rom in moras))
                result.append(" ".join(w for w in words if w))
            else:
                result.append(_pykakasi_line_romaji(line))
        return result
