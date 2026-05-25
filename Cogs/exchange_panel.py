import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import logging
import random
import time
import ccxt.async_support as ccxt
import paypayu
from utils import (is_allowed, mexc_not_logged_in_embed, mexc_auth_error_embed,
                   mexc_network_error_embed, create_error_embed,
                   create_success_embed, panel_owner_not_found_embed,
                   loading_embed)

logger = logging.getLogger(__name__)

MEXC_DATA_FILE = "data/mexc_data.json"
PANEL_OWNERS_FILE = "data/panel_owners.json"
EXCHANGE_SETTINGS_FILE = "data/exchange_settings.json"
PAYPAY_DATA_FILE = "data/paypay_data.json"
PAYPAY_SENDERS_FILE = "data/paypay_senders.json"
PAYPAY_VERIFICATIONS_FILE = "data/paypay_verifications.json"


# ====================== データ読み書き ======================

def load_mexc_data():
    if os.path.exists(MEXC_DATA_FILE):
        with open(MEXC_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_paypay_data():
    if os.path.exists(PAYPAY_DATA_FILE):
        with open(PAYPAY_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_paypay_senders():
    if os.path.exists(PAYPAY_SENDERS_FILE):
        with open(PAYPAY_SENDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_paypay_sender(discord_id, external_id):
    senders = load_paypay_senders()
    senders[str(discord_id)] = external_id
    os.makedirs(os.path.dirname(PAYPAY_SENDERS_FILE), exist_ok=True)
    with open(PAYPAY_SENDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(senders, f, indent=4, ensure_ascii=False)


def load_paypay_verifications():
    if os.path.exists(PAYPAY_VERIFICATIONS_FILE):
        with open(PAYPAY_VERIFICATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_paypay_verification(discord_id, amount, external_id):
    verifications = load_paypay_verifications()
    verifications[str(discord_id)] = {
        "amount": amount,
        "external_id": external_id,
        "timestamp": time.time()
    }
    os.makedirs(os.path.dirname(PAYPAY_VERIFICATIONS_FILE), exist_ok=True)
    with open(PAYPAY_VERIFICATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(verifications, f, indent=4, ensure_ascii=False)


def clear_paypay_verification(discord_id):
    verifications = load_paypay_verifications()
    if str(discord_id) in verifications:
        del verifications[str(discord_id)]
        os.makedirs(os.path.dirname(PAYPAY_VERIFICATIONS_FILE), exist_ok=True)
        with open(PAYPAY_VERIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(verifications, f, indent=4, ensure_ascii=False)


def check_paypay_sender(discord_id, external_id):
    senders = load_paypay_senders()
    registered = senders.get(str(discord_id))
    if registered is None:
        return False
    return registered == external_id


def is_paypay_sender_registered(discord_id):
    senders = load_paypay_senders()
    return str(discord_id) in senders


def load_exchange_settings():
    if os.path.exists(EXCHANGE_SETTINGS_FILE):
        with open(EXCHANGE_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "public_log_channel": None,
        "private_log_channel": None,
        "min_exchange_amount": 0,
        "exchange_rate_money": 0,
        "exchange_rate_money_light": 0
    }


def load_panel_owners():
    if os.path.exists(PANEL_OWNERS_FILE):
        with open(PANEL_OWNERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_panel_owner(message_id, owner_id):
    panel_owners = load_panel_owners()
    panel_owners[str(message_id)] = owner_id
    os.makedirs(os.path.dirname(PANEL_OWNERS_FILE), exist_ok=True)
    with open(PANEL_OWNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(panel_owners, f, indent=4, ensure_ascii=False)


def get_panel_owner(message_id):
    panel_owners = load_panel_owners()
    return panel_owners.get(str(message_id))


# ====================== Modals ======================

class FirstTimeRegistrationModal(ui.Modal, title="PayPay初回登録"):
    """初めて換金する際、PayPayのexternalIdを登録するためのModal"""

    def __init__(self, owner_id, bot, user_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.bot = bot
        self.user_id = user_id

        self.random_amount = random.randint(1, 100)
        save_paypay_verification(user_id, self.random_amount, None)
        logger.info(f"PayPay verification amount generated for user {user_id}: {self.random_amount}円")

        self.paypay_link_input = ui.TextInput(
            label=f"PayPayリンク（{self.random_amount}円）",
            placeholder=f"30秒以内に「{self.random_amount}円」のPayPayリンクを入力してください",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.paypay_link_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=loading_embed("確認中..."), ephemeral=True)

        paypay_link = self.paypay_link_input.value

        try:
            # paypayu は非同期版なので直接 await
            link_info = await paypayu.check_link(paypay_link)
            if not link_info:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="無効なPayPayリンクです。")
                )
                return

            sender_info = link_info.get("payload", {}).get("sender", {})
            external_id = sender_info.get("externalId")

            if not external_id:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="無効なPayPayリンクです。")
                )
                return

            pending_info = link_info.get("payload", {}).get("pendingP2PInfo", {})
            amount = pending_info.get("amount")
            verifications = load_paypay_verifications()
            verification = verifications.get(str(interaction.user.id))

            if not verification:
                clear_paypay_verification(interaction.user.id)
                await interaction.edit_original_response(
                    embed=create_error_embed(description="最初からやり直してください。")
                )
                return

            elapsed_time = time.time() - verification["timestamp"]
            if elapsed_time > 30:
                clear_paypay_verification(interaction.user.id)
                logger.warning(f"PayPay verification timeout for user {interaction.user.id}")
                await interaction.edit_original_response(
                    embed=create_error_embed(description="30秒以内に送信されませんでした。\n最初からやり直してください。")
                )
                return

            if amount != verification["amount"]:
                logger.warning(f"PayPay verification amount mismatch for user {interaction.user.id}: expected={verification['amount']}, got={amount}")
                await interaction.edit_original_response(
                    embed=create_error_embed(description=f"**{verification['amount']}円**のPayPayリンクを送信してください。")
                )
                return

            save_paypay_sender(interaction.user.id, external_id)
            clear_paypay_verification(interaction.user.id)
            logger.info(f"PayPay verification successful for user {interaction.user.id}, external_id={external_id}")
            await interaction.edit_original_response(
                embed=create_success_embed(description="初回登録が完了しました。\n次回から換金が可能になります。")
            )

        except Exception as e:
            logger.error(f"FirstTimeRegistrationModal error: {e}", exc_info=True)
            await interaction.edit_original_response(
                embed=create_error_embed(description="管理者にお問い合わせください。")
            )


class ExchangeModal(ui.Modal, title="換金"):
    def __init__(self, owner_id, bot):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.bot = bot

    ltc_address_input = ui.TextInput(
        label="LTCアドレス",
        placeholder="LTCアドレスを入力してください",
        required=True,
        style=discord.TextStyle.short
    )

    paypay_link_input = ui.TextInput(
        label="PayPayリンク",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=loading_embed("換金処理中..."), ephemeral=True)

        ltc_address = self.ltc_address_input.value
        paypay_link = self.paypay_link_input.value

        try:
            settings = load_exchange_settings()
            min_amount = settings.get("min_exchange_amount", 0)
            exchange_rate_money = settings.get("exchange_rate_money", 0)
            exchange_rate_money_light = settings.get("exchange_rate_money_light", 0)
            public_log_channel_id = settings.get("public_log_channel")
            private_log_channel_id = settings.get("private_log_channel")

            if exchange_rate_money <= 0 or exchange_rate_money_light <= 0:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="換金率が設定されていません。\n管理者にお問い合わせください。")
                )
                return

            # PayPayリンク確認（非同期版paypayu）
            link_info = await paypayu.check_link(paypay_link)
            if not link_info:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="無効なPayPayリンクです。")
                )
                return

            pending_info = link_info.get("payload", {}).get("pendingP2PInfo", {})
            amount = pending_info.get("amount")
            split_data = link_info.get("payload", {}).get("message", {}).get("data", {}).get("subWalletSplit", {})
            link_money = split_data.get("senderEmoneyAmount", 0)
            link_money_lite = split_data.get("senderPrepaidAmount", 0)

            if link_money_lite > 0:
                exchange_rate = exchange_rate_money_light
                money_type_name = "PayPayマネーライト"
            else:
                exchange_rate = exchange_rate_money
                money_type_name = "PayPayマネー"

            sender_info = link_info.get("payload", {}).get("sender", {})
            external_id = sender_info.get("externalId")

            if not external_id:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="無効なPayPayリンクです。")
                )
                return

            # PayPay送信者チェック（不正防止）
            if not check_paypay_sender(interaction.user.id, external_id):
                if private_log_channel_id:
                    private_channel = self.bot.get_channel(private_log_channel_id)
                    if private_channel:
                        user = interaction.user
                        alert_embed = discord.Embed(title="不正検出", color=discord.Color.red())
                        alert_embed.add_field(name="ユーザー", value=user.mention, inline=False)
                        alert_embed.add_field(name="PayPay表示名", value=sender_info.get("displayName", "不明"), inline=False)
                        alert_embed.add_field(name="金額", value=f"{amount:,.0f} 円", inline=False)
                        alert_embed.add_field(name="PayPayリンク", value=paypay_link, inline=False)
                        await private_channel.send(embed=alert_embed)

                await interaction.edit_original_response(
                    embed=create_error_embed(description="登録されているPayPayアカウントと異なります。\n別のPayPayアカウントからの送金は受け付けできません。")
                )
                return

            if amount < min_amount:
                await interaction.edit_original_response(
                    embed=create_error_embed(description=f"送金額が最低換金可能額（{min_amount:,.0f}円）未満です。\n送金額: {amount:,.0f}円")
                )
                return

            # 換金パネルオーナーのPayPayアカウントを取得
            paypay_data = load_paypay_data()
            user_paypay = None
            for entry_id, entry_data in paypay_data.items():
                if entry_data.get("discord_id") == self.owner_id:
                    user_paypay = entry_data
                    break

            if not user_paypay:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="PayPayアカウントが登録されていません。\n管理者にお問い合わせください。")
                )
                return

            # PayPayリンク受取（非同期版paypayu）
            receive_result = await paypayu.link_rev(
                paypay_link,
                user_paypay["phone"],
                user_paypay["password"],
                user_paypay["uuid"]
            )

            if receive_result == "LOGINERR":
                await interaction.edit_original_response(
                    embed=create_error_embed(description="PayPayのログインが切れています。\n管理者にお問い合わせください。")
                )
                return
            elif not receive_result:
                await interaction.edit_original_response(
                    embed=create_error_embed(description="PayPayの受取に失敗しました。")
                )
                return

            # MEXCでLTC換算・送金
            mexc_data = load_mexc_data()
            user_mexc = None
            for entry_id, entry_data in mexc_data.items():
                if entry_data.get("discord_id") == self.owner_id:
                    user_mexc = entry_data
                    break

            if not user_mexc:
                await interaction.edit_original_response(embed=mexc_not_logged_in_embed())
                return

            exchange = ccxt.mexc({
                'apiKey': user_mexc['api_key'],
                'secret': user_mexc['secret'],
                'enableRateLimit': True,
            })
            exchange.options['adjustForTimeDifference'] = True
            exchange.options['recvWindow'] = 60000

            try:
                await exchange.load_time_difference()
                await exchange.load_markets()
                balance, jpy_usdt_ticker, ltc_usdt_ticker = await asyncio.gather(
                    exchange.fetch_balance(),
                    exchange.fetch_ticker('JPY/USDT:USDT'),
                    exchange.fetch_ticker('LTC/USDT')
                )
                jpy_usdt_price = jpy_usdt_ticker.get('last', 0)
                ltc_usdt_price = ltc_usdt_ticker.get('last', 0)

                if jpy_usdt_price <= 0 or ltc_usdt_price <= 0:
                    await interaction.edit_original_response(
                        embed=create_error_embed(description="レートの取得に失敗しました。")
                    )
                    return

                exchange_amount = amount * exchange_rate
                usdt_jpy_price = 1 / jpy_usdt_price
                usdt_amount = exchange_amount / usdt_jpy_price
                ltc_amount = usdt_amount / ltc_usdt_price

                ltc_balance = balance.get('LTC', {})
                ltc_free = ltc_balance.get('free', 0)

                if ltc_free < ltc_amount:
                    ltc_free_jpy = ltc_free * ltc_usdt_price * usdt_jpy_price
                    required_jpy = ltc_amount * ltc_usdt_price * usdt_jpy_price
                    await interaction.edit_original_response(
                        embed=create_error_embed(
                            description=(
                                f"残高が不足しています。\n"
                                f"必要残高: {required_jpy:,.0f} 円 ({ltc_amount:.8f} LTC)\n"
                                f"現在残高: {ltc_free_jpy:,.0f} 円 ({ltc_free:.8f} LTC)"
                            )
                        )
                    )
                    return

                withdraw_result = await exchange.withdraw('LTC', ltc_amount, ltc_address, params={'network': 'LTC'})
                transaction_id = withdraw_result.get('id', '不明')

                # ログ送信
                user = interaction.user
                log_embed = discord.Embed(title="<管理者用>換金ログ", color=discord.Color.green())
                log_embed.add_field(name="ユーザー", value=user.mention, inline=False)
                log_embed.add_field(name="マネー種別", value=f"```{money_type_name}```", inline=False)
                log_embed.add_field(name="換金率", value=f"```{exchange_rate:.0%}```", inline=False)
                log_embed.add_field(name="受取金額", value=f"```{amount:,.0f} 円```", inline=False)
                log_embed.add_field(name="換金額", value=f"```{exchange_amount:,.0f} 円```", inline=False)
                log_embed.add_field(name="送金LTC", value=f"```{ltc_amount:.8f} LTC```", inline=False)
                log_embed.add_field(name="LTCアドレス", value=f"```{ltc_address}```", inline=False)
                log_embed.add_field(name="取引ID", value=f"```{transaction_id}```", inline=False)

                if public_log_channel_id:
                    public_channel = self.bot.get_channel(public_log_channel_id)
                    if public_channel:
                        public_embed = discord.Embed(title="換金ログ", color=discord.Color.green())
                        public_embed.add_field(name="ユーザー", value=user.mention, inline=False)
                        public_embed.add_field(name="換金率", value=f"```{exchange_rate:.0%}```", inline=False)
                        public_embed.add_field(name="受取金額", value=f"```{amount:,.0f} 円```", inline=False)
                        public_embed.add_field(name="換金額", value=f"```{exchange_amount:,.0f} 円```", inline=False)
                        await public_channel.send(embed=public_embed)

                if private_log_channel_id:
                    private_channel = self.bot.get_channel(private_log_channel_id)
                    if private_channel:
                        await private_channel.send(embed=log_embed)

                # ユーザーにDM
                try:
                    dm_embed = discord.Embed(title="換金完了", color=discord.Color.green())
                    dm_embed.add_field(name="マネー種別", value=f"```{money_type_name}```", inline=False)
                    dm_embed.add_field(name="換金率", value=f"```{exchange_rate:.0%}```", inline=False)
                    dm_embed.add_field(name="換金額", value=f"```{exchange_amount:,.0f} 円```", inline=False)
                    dm_embed.add_field(name="送金LTC", value=f"```{ltc_amount:.8f} LTC```", inline=False)
                    dm_embed.add_field(name="LTCアドレス", value=f"```{ltc_address}```", inline=False)
                    dm_embed.add_field(name="取引ID", value=f"```{transaction_id}```", inline=False)
                    await user.send(embed=dm_embed)
                except (discord.Forbidden, Exception):
                    pass

                await interaction.edit_original_response(
                    embed=create_success_embed(
                        description=f"{ltc_amount:.8f} LTCを送金しました。\n送金先: {ltc_address}\n取引ID: {transaction_id}"
                    )
                )

            except ccxt.AuthenticationError:
                await interaction.edit_original_response(embed=mexc_auth_error_embed())
            except ccxt.NetworkError:
                await interaction.edit_original_response(embed=mexc_network_error_embed())
            except ccxt.ExchangeError as e:
                error_message = str(e)
                if '16021' in error_message or 'pre-crediting' in error_message.lower():
                    await interaction.edit_original_response(
                        embed=create_error_embed(description="入金処理中の資産は出金できません。\n処理が完了するまでお待ちください。")
                    )
                else:
                    await interaction.edit_original_response(embed=create_error_embed(description=error_message))
            finally:
                await exchange.close()

        except Exception as e:
            await interaction.edit_original_response(embed=create_error_embed(description=str(e)))


class TransactionStatusModal(ui.Modal, title="送金状況確認"):
    def __init__(self, owner_id, bot):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.bot = bot

    transaction_id_input = ui.TextInput(
        label="取引ID",
        placeholder="取引IDを入力してください",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=loading_embed("取引情報を取得しています..."), ephemeral=True)

        transaction_id = self.transaction_id_input.value
        logger.info(f"Transaction status check by user {interaction.user.id} for panel owner {self.owner_id}, id: {transaction_id}")

        try:
            mexc_data = load_mexc_data()
            user_mexc = None
            for entry_id, entry_data in mexc_data.items():
                if entry_data.get("discord_id") == self.owner_id:
                    user_mexc = entry_data
                    break

            if not user_mexc:
                await interaction.edit_original_response(embed=mexc_not_logged_in_embed())
                return

            exchange = ccxt.mexc({
                'apiKey': user_mexc['api_key'],
                'secret': user_mexc['secret'],
                'enableRateLimit': True,
            })
            exchange.options['adjustForTimeDifference'] = True
            exchange.options['recvWindow'] = 60000

            try:
                await exchange.load_time_difference()
                await exchange.load_markets()
                withdrawals = await exchange.fetch_withdrawals('LTC', limit=100)

                transaction = None
                for withdrawal in withdrawals:
                    if withdrawal.get('id') == transaction_id:
                        transaction = withdrawal
                        break

                if not transaction:
                    await interaction.edit_original_response(
                        embed=create_error_embed(
                            description=f"取引ID `{transaction_id}` が見つかりませんでした。\n取引IDが正しいか確認してください。"
                        )
                    )
                    return

                status = transaction.get('status', '不明')
                amount = transaction.get('amount', 0)
                currency = transaction.get('currency', 'LTC')
                address = transaction.get('address', '不明')
                txid = transaction.get('txid', '未確定')
                timestamp = transaction.get('timestamp')

                status_map = {
                    'pending': '処理中',
                    'ok': '完了',
                    'failed': '失敗',
                    'canceled': 'キャンセル済み'
                }
                status_text = status_map.get(status, str(status))

                if status == 'ok':
                    embed_color = discord.Color.green()
                elif status in ('failed', 'canceled'):
                    embed_color = discord.Color.red()
                else:
                    embed_color = discord.Color.yellow()

                embed = discord.Embed(title="送金状況", color=embed_color)
                embed.add_field(name="状態", value=f"```{status_text}```", inline=False)
                embed.add_field(name="取引ID", value=f"```{transaction_id}```", inline=False)
                embed.add_field(name="送金額", value=f"```{amount:.8f} {currency}```", inline=False)
                embed.add_field(name="送金先アドレス", value=f"```{address}```", inline=False)
                embed.add_field(name="TxID", value=f"```{txid}```", inline=False)

                if timestamp:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    embed.add_field(name="送金日時", value=f"```{dt.strftime('%Y-%m-%d %H:%M:%S')}```", inline=False)

                await interaction.edit_original_response(embed=embed)

            except ccxt.AuthenticationError as e:
                logger.error(f"MEXC auth error for owner {self.owner_id}: {e}", exc_info=True)
                await interaction.edit_original_response(embed=mexc_auth_error_embed())
            except ccxt.NetworkError as e:
                logger.warning(f"MEXC network error for owner {self.owner_id}: {e}")
                await interaction.edit_original_response(embed=mexc_network_error_embed())
            finally:
                await exchange.close()

        except Exception as e:
            logger.error(f"Transaction status check error for owner {self.owner_id}: {e}", exc_info=True)
            await interaction.edit_original_response(embed=create_error_embed(description=str(e)))


# ====================== パネルView ======================

class PersistentPanel(ui.View):
    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="換金する", style=discord.ButtonStyle.primary, custom_id="exchange_panel:exchange", row=0)
    async def exchange_button(self, interaction: discord.Interaction, button: ui.Button):
        owner_id = get_panel_owner(interaction.message.id)
        if not owner_id:
            await interaction.response.send_message(embed=panel_owner_not_found_embed(), ephemeral=True)
            return

        if is_paypay_sender_registered(interaction.user.id):
            modal = ExchangeModal(owner_id, self.bot)
        else:
            modal = FirstTimeRegistrationModal(owner_id, self.bot, interaction.user.id)

        await interaction.response.send_modal(modal)

    @ui.button(label="送金状況確認", style=discord.ButtonStyle.secondary, custom_id="exchange_panel:transaction_status", row=1)
    async def transaction_status_button(self, interaction: discord.Interaction, button: ui.Button):
        owner_id = get_panel_owner(interaction.message.id)
        if not owner_id:
            await interaction.response.send_message(embed=panel_owner_not_found_embed(), ephemeral=True)
            return
        modal = TransactionStatusModal(owner_id, self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="残高表示", style=discord.ButtonStyle.success, custom_id="exchange_panel:balance", row=0)
    async def balance_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(embed=loading_embed("残高を取得しています..."), ephemeral=True)

        try:
            owner_id = get_panel_owner(interaction.message.id)
            if not owner_id:
                await interaction.edit_original_response(embed=panel_owner_not_found_embed())
                return

            mexc_data = load_mexc_data()
            user_data = None
            for entry_id, entry_data in mexc_data.items():
                if entry_data.get("discord_id") == owner_id:
                    user_data = entry_data
                    break

            if not user_data:
                await interaction.edit_original_response(embed=mexc_not_logged_in_embed())
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

                ltc_free = balance.get('LTC', {}).get('free', 0)
                ltc_usdt_price = ltc_usdt_ticker.get('last', 0)

                try:
                    if jpy_usdt_ticker:
                        jpy_usdt_price = jpy_usdt_ticker.get('last', 0)
                        usdt_jpy_price = 1 / jpy_usdt_price if jpy_usdt_price > 0 else 150.0
                    else:
                        usdt_jpy_price = 150.0
                except Exception:
                    usdt_jpy_price = 150.0

                free_jpy = ltc_free * ltc_usdt_price * usdt_jpy_price
                await interaction.edit_original_response(
                    embed=create_success_embed(title="利用可能残高", description=f"# {free_jpy:,.0f} 円")
                )

            except ccxt.AuthenticationError:
                await interaction.edit_original_response(embed=mexc_auth_error_embed())
            except ccxt.NetworkError:
                await interaction.edit_original_response(embed=mexc_network_error_embed())
            finally:
                await exchange.close()

        except Exception as e:
            await interaction.edit_original_response(embed=create_error_embed(description=str(e)))


# ====================== Cog ======================

class ExchangePanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(PersistentPanel(bot))

    @app_commands.command(name="換金パネル", description="LTC換金パネルを表示します")
    @is_allowed()
    async def create_panel(self, interaction: discord.Interaction):
        settings = load_exchange_settings()
        min_amount = settings.get("min_exchange_amount", 0)
        rate_money = settings.get("exchange_rate_money", 0)
        rate_money_light = settings.get("exchange_rate_money_light", 0)

        embed = discord.Embed(
            title="自動換金",
            description=(
                f"PayPayでLTCを24時間いつでも購入できます。\n\n"
                f"```最低換金額:{min_amount:,.0f}円〜```\n"
                f"```PayPayマネー換金率:{rate_money * 100:.0f}%```\n"
                f"```PayPayマネーライト換金率:{rate_money_light * 100:.0f}%```\n\n"
                f"⚠️注意事項⚠️\n"
                f"・アドレスの間違いによる返金はできません。\n"
                f"・マネーロンダリング対策のためDiscordアカウントとPayPayアカウントが紐づけられます。\n"
                f"__**・送金エラーだった場合管理者にお問い合わせください。問い合わせされなかった場合の返金は行いません。**__"
            ),
            color=discord.Color.blue()
        )

        view = PersistentPanel(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

        message = await interaction.original_response()
        save_panel_owner(message.id, interaction.user.id)
        logger.info(f"Exchange panel created by user {interaction.user.id}, message_id={message.id}")


async def setup(bot):
    await bot.add_cog(ExchangePanelCog(bot))
