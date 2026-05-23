import subprocess
import sys
import os
from datetime import datetime

REPO_DIR = os.path.expanduser("~/yu_vd")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run(cmd, cwd=REPO_DIR):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result

def update():
    log("=" * 40)
    log("Git更新を開始します")
    log("=" * 40)

    # 現在のコミットハッシュを取得
    before = run(["git", "rev-parse", "HEAD"])
    before_hash = before.stdout.strip()[:7]
    log(f"更新前のコミット: {before_hash}")

    # pull
    log("git pull を実行中...")
    result = run(["git", "pull", "origin", "main"])

    if result.returncode != 0:
        log(f"[ERROR] git pull 失敗:")
        log(result.stderr.strip())
        return False

    # 更新後のコミットハッシュ
    after = run(["git", "rev-parse", "HEAD"])
    after_hash = after.stdout.strip()[:7]

    if before_hash == after_hash:
        log("すでに最新です。更新なし")
        return True

    log(f"更新後のコミット: {after_hash}")

    # 変更されたファイル一覧を表示
    diff = run(["git", "diff", "--name-status", before_hash, after_hash])
    if diff.stdout.strip():
        log("-" * 40)
        log("変更されたファイル:")
        for line in diff.stdout.strip().splitlines():
            status, *filename = line.split("\t")
            label = {"M": "更新", "A": "追加", "D": "削除"}.get(status, status)
            log(f"  [{label}] {' '.join(filename)}")
        log("-" * 40)
    else:
        log("変更ファイルなし")

    log("更新完了!")
    return True

if __name__ == "__main__":
    success = update()
    if not success:
        sys.exit(1)
