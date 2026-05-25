import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import logging
import ccxt.async_support as ccxt
from utils import is_allowed, mexc_not_logged_in_embed, mexc_auth_error_embed, mexc_network_error_embed, create_error_embed, create_success_embed

logger = logging.getLogger(__name__)

MEXC_DATA_FILE = "data/mexc_data.json"


def load_mexc_data():
    if os.path.exists(MEXC_DATA_FILE):
        with open(MEXC_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class LtcBalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="MEXCのLTC残高を表示します")
    @is_allowed()
    async def ltc_balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Balance command invoked by user {interaction.user.id} ({interaction.user.name})")
        try:
            mexc_data = load_mexc_data()
            user_data = None

            for entry_id, entry_data in mexc_data.items():
                if entry_data.get("discord_id") == interaction.user.id:
                    user_data = entry_data
                    break

            if not user_data:
                logger.warning(f"User {interaction.user.id} attempted to check balance without MEXC login")
                await interaction.followup.send(embed=mexc_not_logged_in_embed(), ephemeral=True)
                return

            exchange = ccxt.mexc({
                'apiKey': user_data['api_key'],
                'secret': user_data['secret'],
                'enableRateLimit': True,
            })
            exchange.options['adjustForTimeDifference'] = True
            exchange.options['recvWindow'] = 60000

            try:
                await exchange.load_time_difference()
                await exchange.load_markets()
                balance, ltc_usdt_ticker, jpy_usdt_ticker = await asyncio.gather(
                    exchange.fetch_balance(),
                    exchange.fetch_ticker('LTC/USDT'),
                    exchange.fetch_ticker('JPY/USDT:USDT') if 'JPY/USDT:USDT' in exchange.markets else asyncio.sleep(0, result=None)
                )

                ltc_balance = balance.get('LTC', {})
                ltc_free = ltc_balance.get('free', 0)
                ltc_usdt_price = ltc_usdt_ticker.get('last', 0)

                try:
                    if jpy_usdt_ticker:
                        jpy_usdt_price = jpy_usdt_ticker.get('last', 0)
                        if jpy_usdt_price and jpy_usdt_price > 0:
                            usdt_jpy_price = 1 / jpy_usdt_price
                        else:
                            usdt_jpy_price = 150.0
                    else:
                        usdt_jpy_price = 150.0
                except Exception as e:
                    logger.error(f"Failed to fetch JPY rate from MEXC: {e}")
                    usdt_jpy_price = 150.0

                ltc_jpy_price = ltc_usdt_price * usdt_jpy_price
                free_jpy = ltc_free * ltc_jpy_price
                logger.info(f"User {interaction.user.id} balance: {ltc_free:.8f} LTC = {free_jpy:,.0f} JPY")

                embed = create_success_embed(title="利用可能残高", description=f"# {free_jpy:,.0f} 円")
                await interaction.followup.send(embed=embed, ephemeral=True)

            except ccxt.AuthenticationError as e:
                logger.error(f"MEXC auth error for user {interaction.user.id}: {e}")
                await interaction.followup.send(embed=mexc_auth_error_embed(), ephemeral=True)

            except ccxt.NetworkError as e:
                logger.error(f"MEXC network error for user {interaction.user.id}: {e}")
                await interaction.followup.send(embed=mexc_network_error_embed(), ephemeral=True)

            finally:
                await exchange.close()

        except Exception as e:
            logger.exception(f"Unexpected error in balance command: {e}")
            await interaction.followup.send(embed=create_error_embed(description=str(e)), ephemeral=True)


async def setup(bot):
    await bot.add_cog(LtcBalanceCog(bot))
