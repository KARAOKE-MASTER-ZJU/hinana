"""调用 yohane 进行强制对齐，返回 ASS 文本。"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# yohane 安装路径（默认用同一 .venv）
_YOHANE_DIR = Path(__file__).parent.parent.parent.parent / "yohane"


def _find_python() -> str:
    """优先使用 yohane 的 venv python，否则用当前 python。"""
    candidates = [
        _YOHANE_DIR / ".venv/bin/python",
        Path(os.environ.get("YOHANE_PYTHON", "")),
    ]
    for p in candidates:
        if p and Path(p).exists():
            return str(p)
    return "python"


def run_yohane(
    song: str,
    romaji_lines: List[str],
    output_path: str,
    forced_aligner: str = "NextFire/mms-300m-ForcedAligner-karaoke-ja-Latn",
    hf_token: str = "",
    yohane_dir: Optional[str] = None,
) -> str:
    """
    运行 yohane 强制对齐，返回生成的 ASS 文本路径。

    Args:
        song: 音频/视频文件路径或 URL
        romaji_lines: 每行的罗马音文本
        output_path: 输出 .ass 路径
        forced_aligner: HuggingFace 模型名
        hf_token: HuggingFace token（加速下载）
        yohane_dir: yohane 项目目录（默认自动检测）

    Returns:
        output_path（用于链式调用）

    Raises:
        RuntimeError: yohane 执行失败
    """
    ydir = Path(yohane_dir) if yohane_dir else _YOHANE_DIR
    run_script = ydir / "run.py"
    if not run_script.exists():
        setup_sh = Path(__file__).parent.parent.parent / "setup.sh"
        raise FileNotFoundError(
            f"yohane not found at {ydir}\n"
            f"Run setup.sh to install automatically:\n"
            f"  bash {setup_sh}\n"
            f"Or clone manually: git clone https://github.com/Japan7/yohane.git {ydir}"
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("\n".join(romaji_lines))
        romaji_file = f.name

    try:
        env = os.environ.copy()
        home = Path.home()
        env["LD_LIBRARY_PATH"] = f"{home}/miniconda3/lib:" + env.get("LD_LIBRARY_PATH", "")
        env["PATH"] = f"{home}/miniconda3/bin:" + env.get("PATH", "")
        if hf_token:
            env["HF_TOKEN"] = hf_token
            env["HUGGING_FACE_HUB_TOKEN"] = hf_token

        python = _find_python()
        cmd = [python, str(run_script), song, romaji_file,
               "--separator", "none", "--output", output_path]
        if forced_aligner:
            cmd += ["--forced-aligner", forced_aligner]

        logger.info("[yohane] running: %s", " ".join(cmd[:4]) + " ...")
        result = subprocess.run(cmd, env=env, capture_output=False)
        if result.returncode != 0:
            raise RuntimeError(f"yohane exited with code {result.returncode}")

        if not Path(output_path).exists():
            raise RuntimeError(f"yohane did not produce output at {output_path}")

        logger.info("[yohane] saved: %s", output_path)
        return output_path
    finally:
        os.unlink(romaji_file)
