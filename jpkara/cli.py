"""jpkara CLI 入口。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
        prog="jpkara",
        description="Japanese lyrics → k-timed annotated karaoke ASS via yohane",
    )
    parser.add_argument("song", help="Audio/video file path or URL (yt-dlp supported)")
    parser.add_argument("lyrics", help="Japanese lyrics file (UTF-8, one line per lyric line)")
    parser.add_argument(
        "--romaji", "-r", default=None,
        help="Optional romaji lyrics file for simple pairing mode (auto-generate if omitted)",
    )
    parser.add_argument(
        "--mode", "-m", default="furigana",
        help="Output annotation mode(s), comma-separated: furigana,kana,romaji (default: furigana)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output .ass path (default: song filename with .ass extension)",
    )
    parser.add_argument(
        "--no-rl", action="store_true",
        help="Disable RhythmicaLyrics dictionary lookup",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable LLM reading annotation (fall back to pykakasi only)",
    )
    parser.add_argument(
        "--rl-refresh", action="store_true",
        help="Force re-download of RhythmicaLyrics dictionary",
    )
    parser.add_argument(
        "--forced-aligner", "-a",
        default="NextFire/mms-300m-ForcedAligner-karaoke-ja-Latn",
        help="HuggingFace Wav2Vec2 model for forced alignment",
    )
    parser.add_argument(
        "--hf-token", default=os.getenv("HF_TOKEN", ""),
        help="HuggingFace token (or set HF_TOKEN env var)",
    )
    parser.add_argument(
        "--yohane-dir", default=None,
        help="Path to yohane project directory (auto-detected if omitted)",
    )
    args = parser.parse_args()

    # Determine output path
    output = args.output
    if not output:
        if args.song.startswith(("http://", "https://")):
            output = "output.ass"
        else:
            output = str(Path(args.song).with_suffix(".ass"))

    # Read input files
    jp_lines = [
        l for l in Path(args.lyrics).read_text("utf-8").splitlines() if l.strip()
    ]
    romaji_lines = None
    if args.romaji:
        romaji_lines = [
            l for l in Path(args.romaji).read_text("utf-8").splitlines() if l.strip()
        ]

    # Handle RL refresh
    if args.rl_refresh and not args.no_rl:
        from jpkara.reading.rl_dict import RLDictionary
        logging.getLogger(__name__).info("Refreshing RL dictionary...")
        RLDictionary().reload()

    # Parse mode(s)
    valid = {"furigana", "kana", "romaji"}
    modes = [m.strip() for m in args.mode.split(",") if m.strip()]
    bad = [m for m in modes if m not in valid]
    if bad:
        parser.error(f"Unknown mode(s): {bad!r}. Choose from: furigana, kana, romaji")

    # Run pipeline
    from jpkara.pipeline import Pipeline
    pipeline = Pipeline(
        use_rl=not args.no_rl,
        use_llm=not args.no_llm,
        forced_aligner=args.forced_aligner or "",
        hf_token=args.hf_token,
        yohane_dir=args.yohane_dir,
    )
    written = pipeline.run(
        song=args.song,
        jp_lines=jp_lines,
        output_path=output,
        mode=modes[0] if len(modes) == 1 else modes,
        romaji_lines=romaji_lines,
    )
    for f in written:
        print(f"Saved: {f}")


if __name__ == "__main__":
    main()
