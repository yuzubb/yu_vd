import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

conversation_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 10

SYSTEM_PROMPT = (
    "あなたはDiscordサーバーで動く親切なAIアシスタントです。"
    "日本語で会話してください。フレンドリーで簡潔な返答を心がけてください。"
)


async def call_groq(user_id: int, user_message: str) -> str:
    history = conversation_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 1024,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"API Error {resp.status}: {text}")
            data = await resp.json()

    reply = data["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply


class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ai", description="AIと会話します")
    @app_commands.describe(message="AIへのメッセージ")
    async def ai_chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        if not GROQ_API_KEY:
            return await interaction.followup.send(
                "エラー: `.env` に `GROQ_API_KEY` が設定されていません。",
                ephemeral=True
            )

        try:
            reply = await call_groq(interaction.user.id, message)
        except Exception as e:
            return await interaction.followup.send(
                f"エラーが発生しました: {e}", ephemeral=True
            )

        embed = discord.Embed(description=reply, color=0x5865F2)
        embed.set_author(
            name=f"{interaction.user.display_name} への返答",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text="💬 /ai で続けて話しかけられます　　🗑️ /ai-reset で会話リセット")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-reset", description="AIとの会話履歴をリセットします")
    async def ai_reset(self, interaction: discord.Interaction):
        conversation_histories.pop(interaction.user.id, None)
        await interaction.response.send_message("会話履歴をリセットしました。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))