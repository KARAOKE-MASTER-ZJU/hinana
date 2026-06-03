"""RhythmicaLyrics 联网读音词典。

下载源：http://timetag.main.jp/RhythmicaLyrics/kakuteiyominet.php?req=get
格式：`[success]` 首行 + `word\treadings\n`
readings 为逗号分隔的 per-character RL-piece 串（＋=连词，数字=cp数无ruby）。

本模块只关心最终的平假名读音，不需要 StrangeUtaGame 的完整 annotated 格式。
"""

from __future__ import annotations

import logging
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_RL_URL = "http://timetag.main.jp/RhythmicaLyrics/kakuteiyominet.php?req=get"
_LINK_MARKER = "＋"   # ＋
_FLAG_TAIL_RE = re.compile(r"@\d+\s*$")
_DIGIT_ONLY_RE = re.compile(r"^\d+$")
_CP_OVERRIDE_RE = re.compile(r"/(\d+)$")

# ── 缓存路径 ──
def _cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "jpkara" / "rl_dictionary.txt"


# ── RL piece → 平假名 ──

def _piece_to_hira(piece: str) -> str:
    """把单个 RL piece 转成平假名字串（剥离 ＋ / @N / /N / 纯数字）。"""
    s = piece.strip()
    s = s.strip(_LINK_MARKER)
    s = _FLAG_TAIL_RE.sub("", s).rstrip()
    m = _CP_OVERRIDE_RE.search(s)
    if m:
        s = s[:m.start()].rstrip()
    if _DIGIT_ONLY_RE.match(s):
        return ""
    return s


def _readings_to_hira(readings: str) -> str:
    """comma-separated RL pieces → 完整平假名读音。"""
    pieces = [_piece_to_hira(p) for p in readings.split(",")]
    return "".join(pieces)


# ── 解析文本 ──

def parse_rl_text(text: str) -> Dict[str, str]:
    """解析 RL 词典文本 → {word: hira_reading}。"""
    result: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "[success]" or "\t" not in line:
            continue
        word, _, raw_readings = line.partition("\t")
        word = word.strip()
        raw_readings = _FLAG_TAIL_RE.sub("", raw_readings.strip())
        if not word or not raw_readings:
            continue
        # 跳过含 ASCII 字母的词条（英文词）
        if any(("a" <= c <= "z") or ("A" <= c <= "Z") for c in word):
            continue
        hira = _readings_to_hira(raw_readings)
        if hira:
            result[word] = hira
    return result


# ── 下载 & 缓存 ──

def download_rl_dict(timeout: int = 30) -> str:
    """从官方源下载词典文本，返回原始字符串。"""
    logger.info("[rl_dict] downloading from %s", _RL_URL)
    req = urllib.request.Request(_RL_URL, headers={"User-Agent": "jpkara/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_rl_dict(
    cache_ttl_days: int = 7,
    force_download: bool = False,
) -> Dict[str, str]:
    """读取词典（优先本地缓存，超时或强制时重新下载）。

    Returns:
        {word: hira} 字典，失败时返回空字典（不影响主流程）。
    """
    path = _cache_path()
    need_download = force_download

    if not need_download:
        if not path.exists():
            need_download = True
        elif time.time() - path.stat().st_mtime > cache_ttl_days * 86400:
            logger.info("[rl_dict] cache expired, refreshing")
            need_download = True

    if need_download:
        try:
            text = download_rl_dict()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            logger.info("[rl_dict] saved %d chars to %s", len(text), path)
        except Exception as e:
            logger.warning("[rl_dict] download failed: %s", e)
            if path.exists():
                logger.info("[rl_dict] using stale cache")
            else:
                return {}

    try:
        text = path.read_text(encoding="utf-8")
        d = parse_rl_text(text)
        logger.info("[rl_dict] loaded %d entries", len(d))
        return d
    except Exception as e:
        logger.warning("[rl_dict] load failed: %s", e)
        return {}


# ── 查询接口 ──

class RLDictionary:
    """线程安全的 RL 词典查询接口（延迟加载）。"""

    def __init__(self, cache_ttl_days: int = 7):
        self._ttl = cache_ttl_days
        self._data: Optional[Dict[str, str]] = None

    def _ensure_loaded(self) -> None:
        if self._data is None:
            self._data = load_rl_dict(cache_ttl_days=self._ttl)

    def get(self, word: str) -> Optional[str]:
        """查询词条，返回平假名读音；未找到返回 None。"""
        self._ensure_loaded()
        assert self._data is not None
        return self._data.get(word)

    def reload(self) -> None:
        """强制重新下载。"""
        self._data = load_rl_dict(force_download=True)

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._data or {})
