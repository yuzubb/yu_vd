import discord
from discord import app_commands
import json
import os

CONFIG_FILE = "data/config.json"


def load_allowed_users() -> list:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("allowed_user_ids", [])
        except json.JSONDecodeError:
            return []
    return []


def is_allowed():
    async def predicate(interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True

        allowed_ids = load_allowed_users()
        if interaction.user.id not in allowed_ids:
            await interaction.response.send_message("🚫 あなたは使用できません", ephemeral=True)
            return False

        return True
    return app_commands.check(predicate)
