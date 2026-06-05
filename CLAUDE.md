# jpkara — 开发说明

## 项目目的

日语卡拉 OK 注音工具：输入日语歌词 + 音频，输出带振假名/假名/罗马音注音的 Aegisub `.ass` 文件。
yohane 负责强制对齐（罗马音 → k 时值），本项目负责日语注音层和 ASS 格式化。

## 本地环境

- 项目目录：`~/jpkara/`
- Python venv：`~/yohane/.venv`（与 yohane 共用）
- yohane 目录：`~/yohane/`
- GPU：NVIDIA RTX 2050，WSL2 直通，CUDA 13.3
- ffmpeg：`~/miniconda3/bin/ffmpeg`（需 `LD_LIBRARY_PATH=$HOME/miniconda3/lib:$LD_LIBRARY_PATH`）

## 开发流程

```bash
# 激活环境（用 yohane 的 venv）
source ~/yohane/activate_and_run.sh
cd ~/jpkara
pip install -e .        # 或 uv pip install -e . --python ~/yohane/.venv/bin/python

# 运行测试
pytest tests/

# 运行 CLI
jpkara song.mp4 lyrics.txt --mode furigana
```

## 注意事项

### LLM 配置
- `~/.env` 或 `~/jpkara/.env` 里设置 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL`
- LLM 对整首歌词发一次批量请求，结果缓存到内存（不写磁盘）

### RL 词典
- 首次运行自动从 `http://timetag.main.jp/RhythmicaLyrics/kakuteiyominet.php?req=get` 下载
- 缓存到 `~/.cache/jpkara/rl_dictionary.txt`，7天自动刷新
- 强制刷新：`jpkara --rl-refresh ...` 或 `RLDictionary().reload()`

### yohane 集成
- `yohane_runner.py` 通过子进程调用 `~/yohane/run.py`
- 自动检测 `~/yohane/.venv/bin/python`
- 可通过 `YOHANE_PYTHON` 环境变量或 `--yohane-dir` 参数覆盖

### ASS 格式
- furigana 格式与 aegisub-tools 的 KaraTemplater 兼容
  - 汉字首 mora：`{\kN}字|<よみ`
  - 汉字续 mora：`{\kN}#|<よみ`
  - 假名 mora：`{\kN}か`
- mora 数量不匹配时截断（WARNING 日志）

## 参考项目

- **StrangeUtaGame**：https://github.com/Cloudac7/StrangeUtaGame
  - 同类型卡拉 OK 注音工具，有 GUI（PyQt6 + Fluent Design）
  - 注音层：FugashiAnalyzer（MeCab + unidic_lite）为基础，`llm_ruby.py` 作为独立引擎覆盖整首
  - RL 词典通过 `network_dictionary.py` 管理，`source_order` 用户可配置，是**可叠加资源层**而非串联 fallback
  - 关键参考文件：`src/strange_uta_game/backend/infrastructure/parsers/` 下的 `ruby_analyzer.py` / `llm_ruby.py` / `rl_dictionary.py`

## 已知问题

- 复合词的汉字 mora 分配（如 見守る みまもる）在字典读音与词典读音不同时可能有偏差
  → RL 词典命中后准确率提升，LLM 更准确
- pykakasi 纯回退质量差（歌词特有读音），建议总是配置 LLM

## 主要文件

| 文件 | 职责 |
|------|------|
| `jpkara/pipeline.py` | 主流程编排（RL→LLM→pykakasi→yohane→ASS格式化） |
| `jpkara/cli.py` | argparse CLI |
| `jpkara/reading/kana.py` | 假名/罗马音转换表，mora 拆分 |
| `jpkara/reading/rl_dict.py` | RhythmicaLyrics 词典下载、解析、缓存 |
| `jpkara/reading/llm.py` | LLM 注音客户端（OpenAI 兼容） |
| `jpkara/reading/analyzer.py` | 三层分析器，输出 CharMoras |
| `jpkara/ass/formatter.py` | furigana/kana/romaji ASS 行格式化 |
| `jpkara/ass/yohane_runner.py` | yohane 子进程调用封装 |
| `tests/test_reading.py` | 单元测试（无网络依赖） |
