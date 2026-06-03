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
from typing import List, Literal, Optional

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
        mode: OutputMode = "furigana",
        romaji_lines: Optional[List[str]] = None,
    ) -> str:
        """
        完整运行管线。

        Args:
            song: 音频/视频文件或 URL
            jp_lines: 日语歌词（每行一个）
            output_path: 输出 .ass 路径
            mode: 输出格式 furigana / kana / romaji
            romaji_lines: 用户提供的罗马音（simple pairing 模式）

        Returns:
            output_path
        """
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

        # 3. yohane 强制对齐
        tmp_ass = output_path if mode == "romaji" else output_path.replace(".ass", "_tmp.ass")
        run_yohane(
            song=song,
            romaji_lines=romaji_lines,
            output_path=tmp_ass,
            forced_aligner=self.forced_aligner,
            hf_token=self.hf_token,
            yohane_dir=self.yohane_dir,
        )

        if mode == "romaji":
            logger.info("[pipeline] romaji mode, done: %s", output_path)
            return output_path

        # 4. 读取 yohane 输出并重写为目标格式
        yohane_ass = Path(tmp_ass).read_text(encoding="utf-8")
        dialogue_lines = [l for l in yohane_ass.splitlines() if l.startswith("Dialogue:")]

        n = min(len(dialogue_lines), len(jp_lines))
        if len(dialogue_lines) != len(jp_lines):
            logger.warning(
                "[pipeline] dialogue count %d != line count %d, truncating to %d",
                len(dialogue_lines), len(jp_lines), n,
            )

        new_texts: List[str] = []
        for i in range(n):
            dl = dialogue_lines[i]
            parts = dl.split(",", 9)
            yohane_text = parts[9].strip() if len(parts) == 10 else ""
            k_flat = parse_k_flat(yohane_text)
            cm = char_moras_list[i]

            if len(cm) != len(k_flat):
                logger.debug(
                    "[pipeline] line %d mora mismatch chars=%d k=%d",
                    i, len(cm), len(k_flat),
                )

            if mode == "furigana":
                new_texts.append(build_furigana(cm, k_flat))
            else:  # kana
                new_texts.append(build_kana(cm, k_flat))

        # 5. 重写 ASS
        out_lines = []
        text_idx = 0
        for line in yohane_ass.splitlines():
            if line.startswith("Dialogue:") and text_idx < len(new_texts):
                p = line.split(",", 9)
                if len(p) == 10:
                    p[9] = new_texts[text_idx]
                    line = ",".join(p)
                    text_idx += 1
            out_lines.append(line)

        Path(output_path).write_text("\n".join(out_lines), encoding="utf-8")

        # 清理临时文件
        if tmp_ass != output_path and Path(tmp_ass).exists():
            Path(tmp_ass).unlink()

        logger.info("[pipeline] done: %s", output_path)
        return output_path
