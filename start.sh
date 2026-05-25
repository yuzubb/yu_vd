#!/data/data/com.termux/files/usr/bin/bash
# yu_vd Bot 起動スクリプト (Termux用)
# このスクリプトを使ってBotを起動してください: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN="$SCRIPT_DIR/main.py"

echo "=============================="
echo "  yu_vd Bot 起動スクリプト"
echo "=============================="

while true; do
    echo "[$(date '+%H:%M:%S')] Botを起動します..."
    python "$MAIN"
    EXIT_CODE=$?

    # 終了コード 0 = 再起動リクエスト
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] 再起動します... (3秒後)"
        sleep 3
        continue
    fi

    # 終了コード 1 以外の異常終了も自動再起動
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[$(date '+%H:%M:%S')] 異常終了 (code=$EXIT_CODE)。10秒後に再起動します..."
        sleep 10
        continue
    fi
done
