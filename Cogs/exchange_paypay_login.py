"""
exchange_paypay_login.py
換金パネル用 PayPay ログイン Cog
（data/paypay_data.json に discord_id をキーとして保存）
"""
import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import json
import os
import uuid
import logging
import paypayu
from utils import is_allowed, create_success_embed, create_error_embed, create_warning_embed

logger = logging.getLogger(__name__)

PAYPAY_DATA_FILE = "data/paypay_data.json"


def load_paypay_data():
    if os.path.exists(PAYPAY_DATA_FILE):
        with open(PAYPAY_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_paypay_data(data):
    os.makedirs(os.path.dirname(PAYPAY_DATA_FILE), exist_ok=True)
    with open(PAYPAY_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class ExchangePayPayOTPModal(ui.Modal, title="PayPay OTP認証"):
    def __init__(self, phone, password, set_uuid, otpid, otp_pre):
        super().__init__(timeout=120)
        self.phone = phone
        self.password = password
        self.set_uuid = set_uuid
        self.otpid = otpid
        self.otp_pre = otp_pre

    otp_input = ui.TextInput(
        label="ワンタイムパスワード",
        placeholder="SMSに届いた4桁の認証コードを入力",
        min_length=4,
        max_length=4,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Exchange PayPay OTP verification attempt by user {interaction.user.id}")

        otp_result = await paypayu.login_otp(self.set_uuid, self.otp_input.value, self.otpid, self.otp_pre)

        if otp_result == "OK":
            paypay_data = load_paypay_data()

            # 既存エントリを確認（discord_idで検索）
            existing_id = None
            for entry_id, entry_data in paypay_data.items():
                if entry_data.get("discord_id") == interaction.user.id:
                    existing_id = entry_id
                    break

            new_data_payload = {
                "discord_id": interaction.user.id,
                "phone": self.phone,
                "password": self.password,
                "uuid": self.set_uuid
            }

            if existing_id:
                paypay_data[existing_id] = new_data_payload
                success_message = "換金用PayPayアカウントを更新しました。"
                logger.info(f"Exchange PayPay account updated for user {interaction.user.id}")
            else:
                keys = [int(k) for k in paypay_data.keys() if k.isdigit()]
                next_id = max(keys, default=0) + 1
                paypay_data[str(next_id)] = new_data_payload
                success_message = "換金用PayPayアカウントを登録しました。"
                logger.info(f"Exchange PayPay account registered for user {interaction.user.id}")

            save_paypay_data(paypay_data)
            await interaction.followup.send(
                embed=create_success_embed(description=success_message),
                ephemeral=True
            )

        elif otp_result == "ERR":
            logger.warning(f"Exchange PayPay OTP failed for user {interaction.user.id}: Invalid OTP")
            await interaction.followup.send(
                embed=create_error_embed(description="OTPコードが正しくありません。"),
                ephemeral=True
            )
        else:
            logger.error(f"Exchange PayPay OTP error for user {interaction.user.id}: {otp_result}")
            await interaction.followup.send(
                embed=create_warning_embed(description="開発者にお問い合わせください。"),
                ephemeral=True
            )


class ExchangePayPayGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="換金paypay", description="換金用PayPay管理")

    @app_commands.command(name="ログイン", description="換金パネル用のPayPayアカウントを登録します")
    @is_allowed()
    @app_commands.describe(phone="電話番号", password="パスワード")
    async def login(self, interaction: discord.Interaction, phone: str, password: str):
        logger.debug(f"User {interaction.user.id} invoked /換金paypay ログイン")
        set_uuid = str(uuid.uuid4())
        result = await paypayu.login(phone, password, set_uuid)

        if result.get("response_type") == "ErrorResponse":
            logger.warning(f"Exchange PayPay login failed for user {interaction.user.id}")
            await interaction.response.send_message(
                embed=create_error_embed(description="電話番号・パスワードが正しくありません。"),
                ephemeral=True
            )
            return

        otpid = result.get("otp_reference_id")
        otp_pre = result.get("otp_prefix")

        if not otpid or not otp_pre:
            await interaction.response.send_message(
                embed=create_error_embed(description="予期せぬエラーが発生しました。もう一度お試しください。"),
                ephemeral=True
            )
            return

        modal = ExchangePayPayOTPModal(phone, password, set_uuid, otpid, otp_pre)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="確認", description="換金パネル用のPayPayアカウントの登録状況を確認します")
    @is_allowed()
    async def check(self, interaction: discord.Interaction):
        paypay_data = load_paypay_data()
        registered = any(
            entry_data.get("discord_id") == interaction.user.id
            for entry_data in paypay_data.values()
        )
        if registered:
            embed = create_success_embed(description="換金用PayPayアカウントが登録されています。")
        else:
            embed = create_error_embed(description="換金用PayPayアカウントが登録されていません。\n`/換金paypay ログイン` で登録してください。")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ExchangePayPayLoginCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(PAYPAY_DATA_FILE):
            save_paypay_data({})

        self.group = ExchangePayPayGroup()
        self.bot.tree.add_command(self.group)


async def setup(bot):
    await bot.add_cog(ExchangePayPayLoginCog(bot))
