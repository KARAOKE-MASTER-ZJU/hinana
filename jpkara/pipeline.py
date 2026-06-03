"""主流程编排：日语歌词 → k时值注音 ASS。

流程：
  1. ReadingAnalyzer（RL→LLM→pykakasi）→ 每行 CharMoras + 罗马音
  2. yohane 强制对齐（罗马音 → k时值 ASS）
  3. ASS 后处理：furigana / kana / romaji 格式化
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Literal, Optional, Union

from .reading.analyzer import ReadingAnalyzer
from .reading.llm import LLMReadingClient
from .reading.rl_dict import RLDictionary
from .ass.formatter import build_furigana, build_kana, build_romaji, parse_k_flat
from .ass.yohane_runner import run_yohane

logger = logging.getLogger(__name__)

OutputMode = Literal["furigana", "kana", "romaji"]


class Pipeline:
    """
    jpkara 主流程入口。

    Args:
        use_rl: 启用 RhythmicaLyrics 词典
        use_llm: 启用 LLM 注音
        llm_base_url/api_key/model: LLM 配置（空时从环境变量读取）
        rl_cache_ttl_days: RL 词典缓存天数
        forced_aligner: yohane 使用的 HF 模型
        hf_token: HuggingFace token
        yohane_dir: yohane 项目目录（None=自动检测）
    """

    def __init__(
        self,
        use_rl: bool = True,
        use_llm: bool = True,
        llm_base_url: str = "",
        llm_api_key: str = "",
        llm_model: str = "",
        rl_cache_ttl_days: int = 7,
        forced_aligner: str = "NextFire/mms-300m-ForcedAligner-karaoke-ja-Latn",
        hf_token: str = "",
        yohane_dir: Optional[str] = None,
    ):
        self.forced_aligner = forced_aligner
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.yohane_dir = yohane_dir

        rl_dict = RLDictionary(cache_ttl_days=rl_cache_ttl_days) if use_rl else None
        llm_client = (
            LLMReadingClient(
                base_url=llm_base_url,
                api_key=llm_api_key,
                model=llm_model,
            )
            if use_llm
            else None
        )
        self.analyzer = ReadingAnalyzer(
            llm_client=llm_client,
            rl_dict=rl_dict,
            use_llm=use_llm,
            use_rl=use_rl,
        )

    def run(
        self,
        song: str,
        jp_lines: List[str],
        output_path: str,
        mode: Union[OutputMode, List[OutputMode]] = "furigana",
        romaji_lines: Optional[List[str]] = None,
        source_ass: Optional[str] = None,
    ) -> List[str]:
        """
        完整运行管线。

        Args:
            song: 音频/视频文件或 URL
            jp_lines: 日语歌词（每行一个）
            output_path: 输出 .ass 路径（多 mode 时加 _furigana/_kana/_romaji 后缀）
            mode: 输出格式，支持单个或列表，如 ["furigana", "romaji"]
            romaji_lines: 用户提供的罗马音（simple pairing 模式）

        Returns:
            实际写出的文件路径列表
        """
        modes: List[OutputMode] = [mode] if isinstance(mode, str) else list(mode)
        multi = len(modes) > 1

        # --- pass-through 支持：从 source_ass 识别非日文行，不送 yohane ---
        # passthrough_map: {全局index: 原始 Dialogue 行}（非日文行，保留原始时间轴）
        # jp_indices: 需要 yohane 重新对齐的行的全局 index 列表
        passthrough_map: dict = {}
        jp_indices: List[int] = list(range(len(jp_lines)))

        if source_ass:
            from .ass_reader import parse_ass_dialogues
            dialogues = parse_ass_dialogues(source_ass)
            passthrough_map = {
                i: d.raw for i, d in enumerate(dialogues) if not d.is_japanese
            }
            jp_indices = [i for i, d in enumerate(dialogues) if d.is_japanese]
            skipped = len(passthrough_map)
            if skipped:
                logger.info(
                    "[pipeline] %d non-Japanese lines kept as pass-through (e.g. timestamps, English)",
                    skipped,
                )
            # 只把日文行送给后续处理
            jp_lines = [jp_lines[i] for i in jp_indices]

        # 1. 分析读音（RL→LLM→pykakasi）
        logger.info("[pipeline] analyzing readings (%d lines)...", len(jp_lines))
        char_moras_list = self.analyzer.analyze_lines(jp_lines)

        # 2. 确定罗马音
        if romaji_lines:
            if len(romaji_lines) != len(jp_lines):
                n = min(len(romaji_lines), len(jp_lines))
                logger.warning("[pipeline] line count mismatch, truncating to %d", n)
                jp_lines = jp_lines[:n]
                romaji_lines = romaji_lines[:n]
                char_moras_list = char_moras_list[:n]
        else:
            logger.info("[pipeline] generating romaji from analyzer...")
            romaji_lines = self.analyzer.to_romaji_lines(jp_lines)

        # 3. yohane 强制对齐（只对日文行）
        stem = output_path[:-4] if output_path.endswith(".ass") else output_path
        tmp_ass = stem + "_tmp.ass"
        run_yohane(
            song=song,
            romaji_lines=romaji_lines,
            output_path=tmp_ass,
            forced_aligner=self.forced_aligner,
            hf_token=self.hf_token,
            yohane_dir=self.yohane_dir,
        )

        # 4. 读取 yohane 输出，预计算 k_flat
        yohane_ass = Path(tmp_ass).read_text(encoding="utf-8")
        yohane_dialogues = [l for l in yohane_ass.splitlines() if l.startswith("Dialogue:")]

        n = min(len(yohane_dialogues), len(jp_lines))
        if len(yohane_dialogues) != len(jp_lines):
            logger.warning(
                "[pipeline] dialogue count %d != line count %d, truncating to %d",
                len(yohane_dialogues), len(jp_lines), n,
            )

        k_flats = []
        for i in range(n):
            parts = yohane_dialogues[i].split(",", 9)
            yohane_text = parts[9].strip() if len(parts) == 10 else ""
            k_flats.append(parse_k_flat(yohane_text))

        written: List[str] = []

        # 5. 对每个 mode 写出文件
        for m in modes:
            out = (stem + f"_{m}.ass") if multi else output_path

            # romaji 模式：直接用 yohane 输出，但仍需插回 pass-through 行
            if m == "romaji" and not passthrough_map:
                import shutil
                shutil.copy(tmp_ass, out)
                logger.info("[pipeline] romaji mode, saved: %s", out)
                written.append(out)
                continue

            # 计算每行新文本（yohane 重新对齐的行）
            new_texts: List[str] = []
            for i in range(n):
                cm = char_moras_list[i]
                kf = k_flats[i]
                if len(cm) != len(kf):
                    logger.debug(
                        "[pipeline] line %d mora mismatch chars=%d k=%d",
                        i, len(cm), len(kf),
                    )
                if m == "romaji":
                    new_texts.append(yohane_dialogues[i].split(",", 9)[9] if len(yohane_dialogues[i].split(",", 9)) == 10 else "")
                elif m == "furigana":
                    new_texts.append(build_furigana(cm, kf))
                else:  # kana
                    new_texts.append(build_kana(cm, kf))

            # 重写 ASS：从 yohane 输出的非 Dialogue 行取头部，
            # 然后按原始顺序插入 pass-through 行和 yohane 行
            header_lines = [l for l in yohane_ass.splitlines() if not l.startswith("Dialogue:")]
            out_lines = list(header_lines)

            yohane_idx = 0  # 指向 new_texts / yohane_dialogues
            total = (len(jp_indices) + len(passthrough_map)) if source_ass else n

            for global_i in range(total):
                if global_i in passthrough_map:
                    # 非日文行：用原始 Dialogue 行（原始时间轴 + 清理后文本）
                    raw = passthrough_map[global_i]
                    p = raw.split(",", 9)
                    if len(p) == 10:
                        from .ass_reader import _clean
                        p[9] = _clean(p[9])
                    out_lines.append(",".join(p))
                elif yohane_idx < len(new_texts):
                    # 日文行：用 yohane 时间轴 + 新注音文本
                    p = yohane_dialogues[yohane_idx].split(",", 9)
                    if len(p) == 10:
                        p[9] = new_texts[yohane_idx]
                    out_lines.append(",".join(p))
                    yohane_idx += 1

            Path(out).write_text("\n".join(out_lines), encoding="utf-8")
            logger.info("[pipeline] %s mode, saved: %s", m, out)
            written.append(out)

        # 6. 清理临时文件
        if Path(tmp_ass).exists():
            Path(tmp_ass).unlink()

        return written
