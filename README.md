# jpkara

Japanese lyrics → k-timed furigana karaoke ASS, powered by [yohane](https://github.com/Japan7/yohane).

## What it does

Takes a song file and Japanese lyrics, and produces an Aegisub `.ass` file with:
- Accurate k-timing via **forced alignment** (yohane / Wav2Vec2)
- **Furigana annotations** on kanji (`{\k17}風|<か{\k17}#|<ぜ`)
- Or **hiragana** / plain **romaji** output modes

Reading accuracy is achieved by a three-layer engine:

```
日本語歌詞
  ↓ ① RhythmicaLyrics 词典（歌词专用，7天缓存）
  ↓ ② LLM 注音（OpenAI-compatible API，整首批量）
  ↓ ③ pykakasi 兜底
平假名读音 → yohane 强制对齐 → k 时值 ASS
```

## Quick start

```bash
# 1. Clone and set up (requires yohane already installed)
git clone https://github.com/yourname/jpkara
cd jpkara
uv venv && source .venv/bin/activate
uv pip install -e .
uv pip install -e /path/to/yohane[cli]   # yohane as dependency

# 2. Configure LLM (optional but recommended)
cp .env.example .env
# edit .env: OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL

# 3. Run
jpkara song.mp4 lyrics.txt --mode furigana -o output.ass
```

## Output modes

| Mode | Description | Example |
|------|-------------|---------|
| `furigana` | Kanji + ruby annotation (default) | `{\k18}風\|<か{\k16}#\|<ぜ` |
| `kana` | Hiragana with k-timing | `{\k18}か{\k16}ぜ` |
| `romaji` | Romaji (plain yohane output) | `{\k18}ka{\k16}ze` |

## Simple pairing mode

If you have the romaji already, skip auto-conversion:

```bash
jpkara song.mp4 lyrics_jp.txt --romaji lyrics_romaji.txt --mode furigana
```

## CLI reference

```
jpkara <song> <lyrics> [options]

Options:
  --romaji FILE       Romaji lyrics file (simple pairing mode)
  --mode MODE         furigana / kana / romaji  [default: furigana]
  --output FILE       Output .ass path
  --no-rl             Disable RhythmicaLyrics dictionary
  --no-llm            Disable LLM, use pykakasi only
  --rl-refresh        Force re-download RL dictionary
  --forced-aligner    HuggingFace model ID
  --hf-token          HuggingFace token
  --yohane-dir        Path to yohane directory
```

## Environment variables

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
HF_TOKEN=hf_...
```

## Project structure

```
jpkara/
├── jpkara/
│   ├── pipeline.py          # Main orchestrator
│   ├── cli.py               # CLI entry point
│   ├── reading/
│   │   ├── kana.py          # Kana/romaji tables, mora splitting
│   │   ├── rl_dict.py       # RhythmicaLyrics dictionary
│   │   ├── llm.py           # LLM reading client
│   │   └── analyzer.py      # Three-layer reading analyzer
│   └── ass/
│       ├── formatter.py     # ASS line formatters
│       └── yohane_runner.py # yohane subprocess wrapper
└── tests/
```

## Acknowledgements

- [yohane](https://github.com/Japan7/yohane) — forced alignment engine
- [RhythmicaLyrics](http://suwa.pupu.jp/RhythmicaLyrics.html) — lyrics reading dictionary
- [StrangeUtaGame](https://github.com/Xuan-cc/StrangeUtaGame) — LLM ruby annotation design reference
