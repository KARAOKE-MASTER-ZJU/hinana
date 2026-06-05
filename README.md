# HINANA

**Hierarchical Interlinear Nihongo Annotation via Neural Alignment**

日语卡拉 OK 注音工具：输入日语歌词 + 音频，输出带振假名注音的 Aegisub `.ass` 文件。

## 功能

- **强制对齐**：基于 [yohane](https://github.com/Japan7/yohane)（Wav2Vec2），自动生成每个音节的 k 时值
- **三阶段读音引擎**：

```
日语歌词
  ↓ ① RhythmicaLyrics 词典（歌词专用，7天缓存）
  ↓ ② LLM 注音（OpenAI 兼容 API，整首批量请求）
  ↓ ③ pykakasi 兜底
平假名读音 → yohane 强制对齐 → k 时值 ASS
```

- **多种输出格式**：

| 模式 | 说明 | 示例 |
|------|------|------|
| `furigana` | 汉字上方标注振假名（默认） | `{\k18}風\|<か{\k16}#\|<ぜ` |
| `kana` | 替换为平假名 | `{\k18}か{\k16}ぜ` |
| `romaji` | 汉字上方标注罗马音 | `{\k18}風\|<ka{\k16}#\|<ze` |

- **说话人保留**：从模板 ASS 读取 Name 字段，输出时原样写回

## 快速开始

```bash
# 1. 克隆并安装（需要已安装 yohane）
git clone https://github.com/KARAOKE-MASTER-ZJU/hinana
cd hinana
uv pip install -e . --python ~/yohane/.venv/bin/python

# 2. 配置 LLM（可选，推荐）
cp .env.example .env
# 编辑 .env：OPENAI_BASE_URL、OPENAI_API_KEY、OPENAI_MODEL

# 3. 运行
hinana song.mp4 lyrics.txt --mode furigana -o output.ass
```

## 使用方式

### 基本用法

```bash
hinana song.mp4 lyrics.txt
```

### 从模板 ASS 运行（保留时间轴结构和说话人）

```bash
hinana song.mp4 lyrics.txt --source-ass template.ass -o result.ass
```

### 已有罗马音，跳过自动转换

```bash
hinana song.mp4 lyrics_jp.txt --romaji lyrics_romaji.txt
```

### 同时输出多种格式

```bash
hinana song.mp4 lyrics.txt --mode furigana romaji
```

## CLI 参数

```
hinana <song> <lyrics> [选项]

选项：
  --source-ass FILE   模板 ASS（用于保留非日语行时间轴和说话人）
  --romaji FILE       罗马音文件（跳过自动转换）
  --mode MODE         furigana / kana / romaji，可多选  [默认: furigana]
  --output FILE       输出 .ass 路径
  --no-rl             禁用 RhythmicaLyrics 词典
  --no-llm            禁用 LLM，仅用 pykakasi
  --rl-refresh        强制重新下载 RL 词典
  --forced-aligner    HuggingFace 模型 ID
  --hf-token          HuggingFace token
  --yohane-dir        yohane 目录路径
```

## 环境变量

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
HF_TOKEN=hf_...
```

## 项目结构

```
hinana/
├── jpkara/
│   ├── pipeline.py          # 主流程（RL→LLM→pykakasi→yohane→ASS）
│   ├── cli.py               # CLI 入口
│   ├── ass_reader.py        # 模板 ASS 解析
│   ├── reading/
│   │   ├── analyzer.py      # 三阶段读音分析器
│   │   ├── llm.py           # LLM 注音客户端
│   │   ├── rl_dict.py       # RhythmicaLyrics 词典
│   │   └── kana.py          # 假名/罗马音转换表
│   └── ass/
│       ├── formatter.py     # ASS 行格式化（furigana/kana/romaji）
│       ├── constants.py     # ASS 头部常量
│       └── yohane_runner.py # yohane 子进程封装
└── tests/
```

## 致谢

- [yohane](https://github.com/Japan7/yohane) — 强制对齐引擎（Wav2Vec2）
- [RhythmicaLyrics](http://suwa.pupu.jp/RhythmicaLyrics.html) — 歌词读音词典
- [StrangeUtaGame](https://github.com/Cloudac7/StrangeUtaGame) — LLM 注音架构参考
