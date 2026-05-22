import discord
from discord.ext import commands
from discord import app_commands
import json
import os

from utils import is_allowed

CONFIG_FILE = "data/config.json"
os.makedirs("data", exist_ok=True)


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class SettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="許可ユーザー追加", description="ユーザーを追加します")
    @app_commands.describe(user="追加するユーザー")
    @is_allowed()
    async def add_allowed_user(self, interaction: discord.Interaction, user: discord.User):
        config = load_config()
        allowed_user_ids = config.get("allowed_user_ids", [])

        if user.id not in allowed_user_ids:
            allowed_user_ids.append(user.id)
            config["allowed_user_ids"] = allowed_user_ids
            save_config(config)
            await interaction.response.send_message(f"✅ {user.mention} を許可ユーザーリストに追加しました。", ephemeral=True)
        else:
            await interaction.response.send_message(f"🚫 {user.mention} は既に許可ユーザーリストに含まれています。", ephemeral=True)

    @app_commands.command(name="許可ユーザー削除", description="リストからユーザーを削除")
    @app_commands.describe(user="削除するユーザー")
    @is_allowed()
    async def remove_allowed_user(self, interaction: discord.Interaction, user: discord.User):
        config = load_config()
        allowed_user_ids = config.get("allowed_user_ids", [])

        if user.id in allowed_user_ids:
            allowed_user_ids.remove(user.id)
            config["allowed_user_ids"] = allowed_user_ids
            save_config(config)
            await interaction.response.send_message(f"✅ {user.mention} を許可ユーザーリストから削除しました。", ephemeral=True)
        else:
            await interaction.response.send_message(f"🚫 {user.mention} は許可ユーザーリストに含まれていません。", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SettingCog(bot))

