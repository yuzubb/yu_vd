import discord
from discord.ext import commands
from discord import app_commands
import os
import traceback
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("環境変数 DISCORD_TOKEN が設定されていません。.envファイルを確認してください。")

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

# ====================== Git更新 ======================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def git_update():
    repo_dir = os.path.dirname(os.path.abspath(__file__))

    def run(cmd):
        return subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)

    log("=" * 40)
    log("Git更新を開始します")
    log("=" * 40)

    before = run(["git", "rev-parse", "HEAD"]).stdout.strip()[:7]
    log(f"更新前: {before}")

    result = run(["git", "pull", "origin", "main"])

    if result.returncode != 0:
        log("[ERROR] git pull 失敗:")
        for line in result.stderr.strip().splitlines():
            log(f"  {line}")
        log("=" * 40)
        return

    after = run(["git", "rev-parse", "HEAD"]).stdout.strip()[:7]

    if before == after:
        log("すでに最新です。更新なし")
        log("=" * 40)
        return

    log(f"更新後: {after}")

    diff = run(["git", "diff", "--name-status", before, after])
    if diff.stdout.strip():
        log("変更されたファイル:")
        for line in diff.stdout.strip().splitlines():
            parts = line.split("\t")
            label = {"M": "更新", "A": "追加", "D": "削除"}.get(parts[0], parts[0])
            log(f"  [{label}] {parts[-1]}")

    log("更新完了!")
    log("=" * 40)

# 起動時にgit更新を実行
git_update()

# ====================== Bot設定 ======================
async def setup_hook():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cogs_dir = os.path.join(base_dir, "Cogs")

    print(f"[INFO] Cogs dir: {cogs_dir}")

    if not os.path.exists(cogs_dir):
        print("[ERROR] Cogsフォルダが存在しません")
        return

    for file in os.listdir(cogs_dir):
        if file.endswith(".py") and not file.startswith("_"):
            ext = f"Cogs.{file[:-3]}"
            try:
                await bot.load_extension(ext)
                print(f"[OK] Loaded Cog: {ext}")
            except Exception as e:
                print(f"[NG] Failed Cog: {ext}")
                traceback.print_exc()

    await bot.tree.sync()
    print("[INFO] Slash commands synced")

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print("===================================")
    print(f"Bot logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("===================================")

    try:
        from Cogs.有料にゃんこ代行 import DaikoMenuView
        bot.add_view(DaikoMenuView())
        print("[INFO] Persistent view registered from main.py")
    except ImportError as e:
        print(f"[INFO] Could not import DaikoMenuView: {e}")
    except Exception as e:
        print(f"[INFO] Could not register view from main.py: {e}")

    try:
        commands_list = await bot.tree.fetch_commands()
        print(f"Registered commands: {len(commands_list)}")
        for cmd in commands_list:
            print(f"  - /{cmd.name}")
    except Exception as e:
        print(f"Failed to fetch commands: {e}")

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    print(f"Command error: {error}")
    traceback.print_exc()

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"エラーが発生しました: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"エラーが発生しました: {error}", ephemeral=True)
    except:
        pass

if __name__ == "__main__":
    bot.run(TOKEN)
