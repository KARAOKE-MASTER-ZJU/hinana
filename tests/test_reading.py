"""基础读音功能测试（无网络依赖）。"""

import pytest
from jpkara.reading.kana import hira_to_moras, kata_to_hira, is_kanji, is_kana
from jpkara.reading.rl_dict import parse_rl_text, _readings_to_hira
from jpkara.ass.formatter import parse_k_flat, build_furigana, build_kana


# ── kana utils ──

def test_kata_to_hira():
    assert kata_to_hira("カゼ") == "かぜ"
    assert kata_to_hira("みまもる") == "みまもる"  # already hira


def test_hira_to_moras_simple():
    moras = hira_to_moras("かぜ")
    assert [(h, r) for h, r in moras] == [("か", "ka"), ("ぜ", "ze")]


def test_hira_to_moras_digraph():
    moras = hira_to_moras("きょう")
    assert moras[0] == ("きょ", "kyo")
    assert moras[1] == ("う", "u")


def test_hira_to_moras_double_consonant():
    moras = hira_to_moras("まって")
    assert moras[0] == ("ま", "ma")
    assert moras[1] == ("っ", "t")
    assert moras[2][1] == "te"


# ── RL dictionary parsing ──

def test_parse_rl_piece_simple():
    assert _readings_to_hira("き,ょ,う") == "きょう"


def test_parse_rl_piece_linked():
    # ＋ markers stripped
    assert _readings_to_hira("み,ま,も,る") == "みまもる"


def test_parse_rl_text():
    sample = "[success]\n今日\tき,ょ,う\n見守る\tみ,ま,も,る\n"
    d = parse_rl_text(sample)
    assert d.get("今日") == "きょう"
    assert d.get("見守る") == "みまもる"


def test_parse_rl_text_skips_ascii():
    sample = "[success]\nhello\the,ro\n今日\tき,ょ,う\n"
    d = parse_rl_text(sample)
    assert "hello" not in d
    assert "今日" in d


# ── formatter ──

def test_parse_k_flat():
    text = r"{\k18}ka{\k16}ze {\k28}ga"
    flat = parse_k_flat(text)
    assert flat[0] == (18, "ka")
    assert flat[1] == (16, "ze")
    assert flat[2] == (28, "ga")


def test_build_furigana_simple():
    # 風(か,ぜ) → {\k18}風|<か{\k16}#|<ぜ
    char_moras = [("風", "か"), ("風", "ぜ"), ("が", "が")]
    k_flat = [(18, "ka"), (16, "ze"), (28, "ga")]
    result = build_furigana(char_moras, k_flat)
    assert "{\\k18}風|<か" in result
    assert "{\\k16}#|<ぜ" in result
    assert "{\\k28}が" in result


def test_build_kana_simple():
    char_moras = [("風", "か"), ("風", "ぜ")]
    k_flat = [(18, "ka"), (16, "ze")]
    result = build_kana(char_moras, k_flat)
    assert result == "{\\k18}か{\\k16}ぜ"
