import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
import ccxt.async_support as ccxt
from utils import is_allowed, create_success_embed, create_error_embed, create_warning_embed

logger = logging.getLogger(__name__)

MEXC_DATA_FILE = "data/mexc_data.json"


def load_mexc_data():
    if os.path.exists(MEXC_DATA_FILE):
        with open(MEXC_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_mexc_data(data):
    os.makedirs(os.path.dirname(MEXC_DATA_FILE), exist_ok=True)
    with open(MEXC_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class MEXCLoginModal(ui.Modal, title="MEXC ログイン"):
    def __init__(self):
        super().__init__(timeout=300)

    api_key_input = ui.TextInput(
        label="Access Key",
        placeholder="MEXCのAccessKeyを入力してください",
        required=True,
        style=discord.TextStyle.short
    )

    secret_input = ui.TextInput(
        label="Secret Key",
        placeholder="MEXCのSecretKeyを入力してください",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        api_key = self.api_key_input.value
        secret = self.secret_input.value
        logger.info(f"MEXC login attempt by user {interaction.user.id} ({interaction.user.name})")

        try:
            exchange = ccxt.mexc({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
            })
            exchange.options['adjustForTimeDifference'] = True
            exchange.options['recvWindow'] = 60000

            try:
                await exchange.load_time_difference()
                await exchange.load_markets()
                await exchange.fetch_balance()

                mexc_data = load_mexc_data()
                existing_id = None
                for entry_id, entry_data in mexc_data.items():
                    if entry_data.get("discord_id") == interaction.user.id:
                        existing_id = entry_id
                        break

                new_data_payload = {
                    "discord_id": interaction.user.id,
                    "api_key": api_key,
                    "secret": secret
                }

                if existing_id:
                    mexc_data[existing_id] = new_data_payload
                    success_message = "MEXCアカウント情報を更新しました。"
                    logger.info(f"MEXC account updated for user {interaction.user.id}")
                else:
                    max_id = max([int(k) for k in mexc_data.keys()] or [0], default=0)
                    next_id = max_id + 1
                    mexc_data[str(next_id)] = new_data_payload
                    success_message = "MEXCアカウントにログインしました。"
                    logger.info(f"MEXC account registered for user {interaction.user.id}")

                save_mexc_data(mexc_data)

                embed = create_success_embed(description=success_message)
                await interaction.followup.send(embed=embed, ephemeral=True)

            except ccxt.AuthenticationError as e:
                logger.warning(f"MEXC authentication failed for user {interaction.user.id}: {e}")
                embed = create_error_embed(description="AccessKeyまたはSecretKeyが正しくありません。")
                await interaction.followup.send(embed=embed, ephemeral=True)

            except ccxt.NetworkError as e:
                logger.warning(f"MEXC network error for user {interaction.user.id}: {e}")
                embed = create_warning_embed(description="しばらく待ってから再試行してください。")
                await interaction.followup.send(embed=embed, ephemeral=True)

            finally:
                await exchange.close()

        except Exception as e:
            logger.error(f"MEXC login error for user {interaction.user.id}: {e}", exc_info=True)
            embed = create_error_embed(description=f"{str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)


class MexcGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="mexc", description="MEXC関連のコマンド")

    @app_commands.command(name="login", description="MEXCアカウントにログインします")
    @is_allowed()
    async def login(self, interaction: discord.Interaction):
        logger.debug(f"User {interaction.user.id} ({interaction.user.name}) invoked /mexc login")
        modal = MEXCLoginModal()
        await interaction.response.send_modal(modal)


class MexcLoginCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(MEXC_DATA_FILE):
            save_mexc_data({})

        self.mexc_group = MexcGroup()
        self.bot.tree.add_command(self.mexc_group)


async def setup(bot):
    await bot.add_cog(MexcLoginCog(bot))
