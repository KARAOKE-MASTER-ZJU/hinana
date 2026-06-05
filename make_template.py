"""从歌词文本生成带说话人的模板 ASS（placeholder 时间轴）。"""

import re
import sys
from pathlib import Path

LYRICS = """(さやか)星照らす大地で共に誓った
(瑠璃乃)夢は終わらない
(花帆)何度でも咲き続けよう

(花帆)ああ 本当に運命だった
私たちの出会い
(さやか)ああ 煌めく先へ伸ばした腕
(瑠璃乃)硬い殻なんて もういらない

(さやか)自由求め 自分求めて
(瑠璃乃)そして楽しいこと求めて
(花帆)咲きたい理由は みんな違うけど
同じ空見ていたね

(全員)新しい世界へ 種は蒔かれた
それは小さな
(さやか)希望のペレニアル
(全員)星照らす大地で共に誓った夢は
これから絶対に
(花帆)咲いてみせよう

(さやか)ああ 間違えてばかりだ
失望に変わる期待
(瑠璃乃)胸が苦しいのが成長痛のせいなら
(花帆)遠慮は もういらないね　全部ぶつけよう

(全員)憧れた未来へ届く気がした
雨も上がって
(瑠璃乃)芽吹いたペレニアル
(全員)星照らす大地で共に誓った夢を叶えて
ねえ 一緒に
(花帆)咲き誇ろう

(さやか)誰が求めるものではないとしても
(花帆)そう
例え褒められるものではないとしても
(瑠璃乃)何かしたいよ って
とてもあったかい気持ち
(全員)膨らんだ蕾

(花帆)四度目の桜が春を告げたら
(瑠璃乃)君は見るだろう
(さやか)満開のペレニアル

(全員)星照らす大地で共に誓った夢は終わらない
何度でも
駆け抜けた時間は永遠に枯れない
ここに残そう
ありがとう　楽しかった！！！"""

# 全員 → 多人模式
ZENIN = "さやか;瑠璃乃;花帆"

_PREFIX = re.compile(r"^\((.+?)\)(.+)$")

ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Source Han Sans Heavy,120,&H00FFFFFF,&H00FF5E00,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,11,11,11,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def make_template(out_path: str) -> None:
    lines = []
    current_actor = ""
    for raw in LYRICS.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = _PREFIX.match(raw)
        if m:
            tag, text = m.group(1), m.group(2).strip()
            current_actor = ZENIN if tag == "全員" else tag
        else:
            text = raw  # continuation line, keep current_actor
        lines.append((current_actor, text))

    out = [ASS_HEADER.rstrip("\n")]
    for actor, text in lines:
        out.append(f"Dialogue: 0,0:00:00.00,0:00:00.01,Default,{actor},0,0,0,,{text}")

    Path(out_path).write_text("\n".join(out), encoding="utf-8")
    print(f"Written {len(lines)} lines to {out_path}")


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "template.ass"
    make_template(dest)
