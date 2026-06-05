# HINANA: **H**ierarchical **I**nterlinear **N**ihongo  **A**nnotation via **N**eural **A**lignment for Karaoke Subtitles
<img width="225" height="225" alt="image" src="https://github.com/user-attachments/assets/c9114ce1-4651-4cb6-8940-e51a3ba5913f" />

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

## 安装

```bash
git clone https://github.com/KARAOKE-MASTER-ZJU/hinana
cd hinana
bash setup.sh
```

`setup.sh` 会自动完成：
1. clone [yohane](https://github.com/Japan7/yohane) 到 `../yohane/`
2. 创建 yohane 的 venv 并安装 torch / torchaudio 等依赖（首次约 2-3 GB）
3. 将 hinana 安装到同一 venv 中

安装完成后激活环境：

```bash
source ../yohane/activate_and_run.sh
```

## Demo：星のテリブル（スピカテリブル）

项目自带 `demo/` 目录包含示例文件（南ことり - スピカテリブル）：

```
demo/
├── spica-terrible-furigana.ass # HINANA 输出示例（振假名标注 + yohane 强制对齐）
└── spica-terrible-lyrics.txt   # 歌词文本
```

运行命令参考：

```bash
hinana /path/to/spica-terrible.mp4 \
  demo/spica-terrible-lyrics.txt \
  --mode furigana \
  -o result.ass
```

输入行示例（基础 k 时值）：
```
{\k33}迷{\k29}い{\k31}の{\k33}振{\k40}り{\k31}子{\k96}が{\k25}と{\k27}ま{\k27}ら{\k29}な{\k166}い
```

输出行示例（振假名标注后）：
```
{\k33}迷|<ま{\k29}#|<よ{\k31}い{\k33}の{\k33}振|<ふ{\k40}#|<り{\k31}子|<こ{\k96}が{\k25}と{\k27}ま{\k27}ら{\k29}な{\k166}い
```

## 快速开始

### 基本用法

```bash
hinana song.mp4 lyrics.txt
```

### 从模板 ASS 运行（保留说话人 / 非日语行）

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
  --source-ass FILE   模板 ASS（保留非日语行时间轴和说话人）
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
HF_TOKEN=hf_...           # HuggingFace token（加速模型下载）
```

## 项目结构

```
hinana/
├── setup.sh                     # 一键安装（含 yohane）
├── demo/
│   ├── spica-terrible-furigana.ass # 示例输出 ASS（南ことり - スピカテリブル）
│   └── spica-terrible-lyrics.txt
├── jpkara/
│   ├── pipeline.py              # 主流程（RL→LLM→pykakasi→yohane→ASS）
│   ├── cli.py                   # CLI 入口
│   ├── ass_reader.py            # 模板 ASS 解析
│   ├── reading/
│   │   ├── analyzer.py          # 三阶段读音分析器
│   │   ├── llm.py               # LLM 注音客户端
│   │   ├── rl_dict.py           # RhythmicaLyrics 词典
│   │   └── kana.py              # 假名/罗马音转换表
│   └── ass/
│       ├── formatter.py         # ASS 行格式化
│       ├── constants.py         # ASS 头部常量
│       └── yohane_runner.py     # yohane 子进程封装
└── tests/
```

## 致谢

- [yohane](https://github.com/Japan7/yohane) — 强制对齐引擎（Wav2Vec2）
- [RhythmicaLyrics](http://suwa.pupu.jp/RhythmicaLyrics.html) — 歌词读音词典
- [StrangeUtaGame](https://github.com/Cloudac7/StrangeUtaGame) — LLM 注音架构参考
