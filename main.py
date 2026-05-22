import discord
from discord.ext import commands
from discord import app_commands
import os
import traceback

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

    # グローバルコマンドを同期
    await bot.tree.sync()
    print("[INFO] Slash commands synced")

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print("===================================")
    print(f"Bot logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("===================================")
    
    # ========== 永続Viewを直接登録（Cogがまだ読み込まれていない場合の保険） ==========
    try:
        from Cogs.有料にゃんこ代行 import DaikoMenuView
        bot.add_view(DaikoMenuView())
        print("[INFO] Persistent view registered from main.py")
    except ImportError as e:
        print(f"[INFO] Could not import DaikoMenuView: {e}")
    except Exception as e:
        print(f"[INFO] Could not register view from main.py: {e}")
    
    # 起動後に登録されているコマンドを表示
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
    
    # エラーメッセージをユーザーに送信
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"エラーが発生しました: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"エラーが発生しました: {error}", ephemeral=True)
    except:
        pass

if __name__ == "__main__":
    bot.run(TOKEN)
