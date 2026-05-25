import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import json
import os
import logging
from utils import is_allowed, create_error_embed, create_success_embed
from utils import is_owner

logger = logging.getLogger(__name__)

SETTINGS_FILE = "data/exchange_settings.json"


def load_exchange_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "public_log_channel": None,
        "private_log_channel": None,
        "min_exchange_amount": 0,
        "exchange_rate_money": 0,
        "exchange_rate_money_light": 0
    }


def save_exchange_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


class ExchangeSettingsModal(ui.Modal, title="換金設定"):
    def __init__(self):
        super().__init__(timeout=None)

    min_amount_input = ui.TextInput(
        label="最低換金可能額",
        placeholder="最低換金可能額を入力してください",
        required=True,
        style=discord.TextStyle.short
    )

    rate_money_input = ui.TextInput(
        label="PayPayマネー換金率(%)",
        placeholder="PayPayマネーの換金率を入力してください (例: 85)",
        required=True,
        style=discord.TextStyle.short
    )

    rate_money_light_input = ui.TextInput(
        label="PayPayマネーライト換金率(%)",
        placeholder="PayPayマネーライトの換金率を入力してください (例: 80)",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            min_amount = float(self.min_amount_input.value)
            rate_money_percent = float(self.rate_money_input.value)
            rate_money_light_percent = float(self.rate_money_light_input.value)

            if min_amount < 0:
                await interaction.followup.send(
                    embed=create_error_embed(description="最低換金可能額は0以上である必要があります。"),
                    ephemeral=True
                )
                return

            if rate_money_percent <= 0 or rate_money_percent > 100:
                await interaction.followup.send(
                    embed=create_error_embed(description="PayPayマネー換金率は0より大きく100以下である必要があります。"),
                    ephemeral=True
                )
                return

            if rate_money_light_percent <= 0 or rate_money_light_percent > 100:
                await interaction.followup.send(
                    embed=create_error_embed(description="PayPayマネーライト換金率は0より大きく100以下である必要があります。"),
                    ephemeral=True
                )
                return

            rate_money = rate_money_percent / 100
            rate_money_light = rate_money_light_percent / 100

            settings = load_exchange_settings()
            settings["min_exchange_amount"] = min_amount
            settings["exchange_rate_money"] = rate_money
            settings["exchange_rate_money_light"] = rate_money_light
            save_exchange_settings(settings)

            embed = create_success_embed(
                description=(
                    f"換金設定を更新しました。\n"
                    f"• 最低換金可能額: {min_amount:,.0f} 円\n"
                    f"• PayPayマネー換金率: {rate_money:.0%}\n"
                    f"• PayPayマネーライト換金率: {rate_money_light:.0%}"
                )
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Exchange settings updated by {interaction.user.id}: min={min_amount}, money={rate_money}, light={rate_money_light}")

        except ValueError:
            await interaction.followup.send(
                embed=create_error_embed(description="数値の形式が正しくありません。"),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed(description="設定を保存できませんでした。"),
                ephemeral=True
            )
            logger.error(f"Failed to save exchange settings: {e}")


class ExchangeLogChannelGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="換金ログ", description="換金ログチャンネル設定")

    @app_commands.command(name="公開", description="公開ログチャンネルを設定します")
    @is_allowed()
    async def set_public(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = load_exchange_settings()
        settings["public_log_channel"] = channel.id
        save_exchange_settings(settings)
        embed = create_success_embed(description=f"公開ログチャンネルを {channel.mention} に設定しました。")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Set public log channel to {channel.id}")

    @app_commands.command(name="非公開", description="非公開ログチャンネルを設定します")
    @is_allowed()
    async def set_private(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = load_exchange_settings()
        settings["private_log_channel"] = channel.id
        save_exchange_settings(settings)
        embed = create_success_embed(description=f"非公開ログチャンネルを {channel.mention} に設定しました。")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Set private log channel to {channel.id}")


class ExchangeSettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_group = ExchangeLogChannelGroup()
        self.bot.tree.add_command(self.log_group)

    @app_commands.command(name="換金設定", description="換金率・最低換金額を設定します")
    @is_allowed()
    async def exchange_settings(self, interaction: discord.Interaction):
        modal = ExchangeSettingsModal()
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(ExchangeSettingCog(bot))
