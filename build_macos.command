#!/bin/zsh
set -e
cd "$(dirname "$0")"

# 仅用于构建；生成的 .app 可在没有 Python 的 Mac 上运行。
python3 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name "论文截图工具" app.py

echo ""
echo "构建完成：dist/论文截图工具.app"
echo "把这个 .app 复制给最终使用者即可，无需安装 Python。"
read -n 1 -s -r "?按任意键退出…"

