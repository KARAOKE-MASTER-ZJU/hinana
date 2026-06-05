#!/usr/bin/env bash
# HINANA 一键安装脚本
# 自动 clone yohane（强制对齐引擎）并安装全部依赖
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YOHANE_DIR="$(dirname "$SCRIPT_DIR")/yohane"

echo "=== HINANA setup ==="
echo "hinana dir : $SCRIPT_DIR"
echo "yohane dir : $YOHANE_DIR"
echo ""

# 1. Clone yohane
if [ ! -d "$YOHANE_DIR" ]; then
    echo "→ Cloning yohane..."
    git clone https://github.com/Japan7/yohane.git "$YOHANE_DIR"
else
    echo "→ yohane already present, pulling latest..."
    git -C "$YOHANE_DIR" pull --ff-only
fi

# 2. Install yohane deps（含 torch，首次约 2-3 GB，耐心等待）
echo ""
echo "→ Installing yohane + torch (this may take several minutes)..."
cd "$YOHANE_DIR"
uv sync --extra cli

# 3. Install hinana into the same venv
echo ""
echo "→ Installing hinana..."
cd "$SCRIPT_DIR"
uv pip install -e . --python "$YOHANE_DIR/.venv/bin/python"

echo ""
echo "✓ 安装完成！"
echo ""
echo "运行方式："
echo "  source $YOHANE_DIR/activate_and_run.sh"
echo "  hinana song.mp4 lyrics.txt --mode furigana -o result.ass"
echo ""
echo "Demo（需准备音频文件）："
echo "  hinana /path/to/spica-terrible.mp4 \\"
echo "    $SCRIPT_DIR/demo/spica-terrible-lyrics.txt \\"
echo "    --source-ass $SCRIPT_DIR/demo/spica-terrible.ass \\"
echo "    -o result.ass"
