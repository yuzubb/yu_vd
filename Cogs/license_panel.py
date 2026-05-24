"""
license_panel.py
Bot使用権限の購入パネル管理Cog
- 日数・PayPayリンクを1枚のモーダルにまとめてパネルで完結
- 単価はオーナーが /使用権単価設定 で変更可能（デフォルト100円/日）
- 期限切れで自動的に使用不可
"""

import discord
from discord import ui, app_commands
from discord.ext import commands, tasks
import json
import os
import time
import asyncio

import paypayu
from utils import (
    OWNER_ID, load_licenses, save_licenses,
    has_valid_license, get_license_expiry_text,
    grant_license, revoke_license, is_owner
)

PANEL_FILE       = "data/license_panel.json"
UNIT_PRICE_FILE  = "data/license_unit_price.json"
PAYPAY_DATA_FILE = "data/paypay_data.json"

os.makedirs("data", exist_ok=True)

DEFAULT_UNIT_PRICE = 100  # 1日あたりのデフォルト単価（円）


# ====================== 単価管理 ======================
def load_unit_price() -> int:
    if os.path.exists(UNIT_PRICE_FILE):
        try:
            with open(UNIT_PRICE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("unit_price", DEFAULT_UNIT_PRICE)
        except Exception:
            pass
    return DEFAULT_UNIT_PRICE


def save_unit_price(price: int):
    with open(UNIT_PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump({"unit_price": price}, f, indent=4)


# ====================== パネルデータ管理 ======================
def load_panel_data() -> dict:
    if os.path.exists(PANEL_FILE):
        try:
            with open(PANEL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_panel_data(data: dict):
    with open(PANEL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_paypay_data() -> dict:
    if os.path.exists(PAYPAY_DATA_FILE):
        try:
            with open(PAYPAY_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ====================== 購入モーダル（日数＋PayPayリンクを1枚で） ======================
class PurchaseModal(ui.Modal, title="🛒 使用権の購入"):

    days_input = ui.TextInput(
        label="購入日数",
        placeholder="例: 7（1〜365の整数）",
        min_length=1,
        max_length=3,
        required=True,
    )

    pay_link = ui.TextInput(
        label="PayPayリンク",
        placeholder="https://pay.paypay.ne.jp/...",
        min_length=30,
        max_length=200,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # --- 日数バリデーション ---
        try:
            days = int(self.days_input.value.strip())
            if days < 1 or days > 365:
                raise ValueError
        except ValueError:
            return await interaction.followup.send(
                "❌ 日数は1〜365の整数で入力してください。",
                ephemeral=True
            )

        unit_price = load_unit_price()
        total      = days * unit_price
        link_url   = self.pay_link.value.strip()

        # --- オーナーのPayPay情報取得 ---
        paypay_data = load_paypay_data()
        owner_cred  = paypay_data.get(str(OWNER_ID))
        if not owner_cred:
            return await interaction.followup.send(
                "⚠️ オーナーのPayPayアカウントが未設定です。管理者にお問い合わせください。",
                ephemeral=True
            )

        # --- リンク確認 ---
        try:
            link_info = await paypayu.check_link(link_url)
        except Exception:
            link_info = None

        if not link_info:
            return await interaction.followup.send(
                "❌ PayPayリンクの確認に失敗しました。リンクが正しいか確認してください。",
                ephemeral=True
            )

        payload  = link_info.get("payload", {})
        p2p_info = payload.get("pendingP2PInfo", {})
        amount   = p2p_info.get("amount", 0)

        if p2p_info.get("isSetPasscode", False):
            return await interaction.followup.send(
                "⚠️ パスコード付きのリンクは使用できません。",
                ephemeral=True
            )

        if amount < total:
            return await interaction.followup.send(
                f"❌ 金額が不足しています。\n"
                f"📅 購入日数: **{days}日**\n"
                f"💳 必要金額: **¥{total:,}**\n"
                f"💴 リンクの金額: **¥{amount:,}**",
                ephemeral=True
            )

        # --- PayPay受け取り ---
        try:
            result = await paypayu.link_rev(
                link_url,
                owner_cred["phone"],
                owner_cred["password"],
                owner_cred["uuid"]
            )
        except Exception:
            result = None

        if result is not True:
            msg = (
                "❌ PayPayログインに失敗しました。管理者にお問い合わせください。"
                if result == "LOGINERR"
                else "❌ PayPayの受け取りに失敗しました。リンクが使用済みか期限切れの可能性があります。"
            )
            return await interaction.followup.send(msg, ephemeral=True)

        # --- ライセンス付与 ---
        grant_license(interaction.user.id, days)
        expiry_text = get_license_expiry_text(interaction.user.id)

        embed = discord.Embed(
            title="✅ 購入完了！",
            description=(
                f"🎉 **{days}日間** の使用権を付与しました！\n\n"
                f"🕐 有効期限: **{expiry_text}**\n\n"
                "Botの全機能をご利用いただけます。"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"購入金額: ¥{total:,}（{days}日 × ¥{unit_price:,}）")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ====================== パネルView ======================
class LicensePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🛒 使用権を購入する",
        style=discord.ButtonStyle.primary,
        custom_id="license_buy_open"
    )
    async def buy_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(PurchaseModal())

    @ui.button(
        label="📋 使用権を確認",
        style=discord.ButtonStyle.secondary,
        custom_id="license_check"
    )
    async def check_button(self, interaction: discord.Interaction, button: ui.Button):
        uid = interaction.user.id
        if has_valid_license(uid):
            expiry = get_license_expiry_text(uid)
            color  = discord.Color.green()
            status = f"✅ 有効\n🕐 残り: **{expiry}**"
        else:
            color  = discord.Color.red()
            status = "❌ 使用権なし\n「使用権を購入する」から購入してください。"

        embed = discord.Embed(title="使用権の確認", description=status, color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def build_panel_embed() -> discord.Embed:
    unit_price = load_unit_price()
    desc = (
        "Botの使用権をPayPayで購入できます。\n\n"
        f"💴 **料金: ¥{unit_price:,} / 日**\n"
        "好きな日数を自由に指定できます。\n\n"
        "**計算例**\n"
        f"> 1日 → ¥{unit_price:,}\n"
        f"> 7日 → ¥{unit_price * 7:,}\n"
        f"> 30日 → ¥{unit_price * 30:,}\n\n"
        "有効期限が切れると自動的に使用不可になります。\n\n"
        "📌 「使用権を購入する」を押して\n"
        "　　**日数** と **PayPayリンク** を入力してください。"
    )
    return discord.Embed(title="🤖 Bot 使用権購入", description=desc, color=0x00a0e9)


# ====================== Cog ======================
class LicensePanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._respawning = False
        self.check_expired_loop.start()

    def cog_unload(self):
        self.check_expired_loop.cancel()

    @tasks.loop(hours=1)
    async def check_expired_loop(self):
        licenses = load_licenses()
        now = time.time()
        expired = [uid for uid, exp in licenses.items() if exp != -1 and exp < now]
        if expired:
            for uid in expired:
                del licenses[uid]
            save_licenses(licenses)

    @check_expired_loop.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

    async def respawn_panel(self):
        if self._respawning:
            return
        self._respawning = True
        try:
            await self.bot.wait_until_ready()
            await asyncio.sleep(3.0)
            panel = load_panel_data()
            if not panel:
                return
            ch_id  = panel.get("channel_id")
            msg_id = panel.get("message_id")
            if not ch_id or not msg_id:
                return
            channel = self.bot.get_channel(ch_id)
            if not channel:
                return
            try:
                old = await channel.fetch_message(msg_id)
                await old.delete()
            except Exception:
                pass
            view    = LicensePanelView()
            new_msg = await channel.send(embed=build_panel_embed(), view=view)
            panel["message_id"] = new_msg.id
            save_panel_data(panel)
            self.bot.add_view(view)
        finally:
            self._respawning = False

    @app_commands.command(name="使用権パネル設置", description="Bot使用権購入パネルを設置します（オーナー専用）")
    @is_owner()
    async def setup_license_panel(self, interaction: discord.Interaction):
        panel = load_panel_data()
        if panel:
            old_ch  = panel.get("channel_id")
            old_msg = panel.get("message_id")
            if old_ch and old_msg:
                ch = self.bot.get_channel(old_ch)
                if ch:
                    try:
                        m = await ch.fetch_message(old_msg)
                        await m.delete()
                    except Exception:
                        pass
        view = LicensePanelView()
        msg  = await interaction.channel.send(embed=build_panel_embed(), view=view)
        save_panel_data({"channel_id": interaction.channel.id, "message_id": msg.id})
        await interaction.response.send_message("✅ 使用権購入パネルを設置しました！", ephemeral=True)

    @app_commands.command(name="使用権単価設定", description="1日あたりの単価を設定します（オーナー専用）")
    @app_commands.describe(price="1日あたりの金額（円）")
    @is_owner()
    async def set_unit_price(self, interaction: discord.Interaction, price: int):
        if price < 1:
            return await interaction.response.send_message("❌ 1以上の金額を設定してください。", ephemeral=True)
        save_unit_price(price)
        await self._refresh_panel()
        embed = discord.Embed(
            title="✅ 単価設定完了",
            description=(
                f"1日あたりの単価を **¥{price:,}** に設定しました。\n\n"
                f"計算例:\n> 1日 → ¥{price:,}\n> 7日 → ¥{price * 7:,}\n> 30日 → ¥{price * 30:,}"
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="使用権付与", description="ユーザーに使用権を手動付与します（オーナー専用）")
    @app_commands.describe(user="対象ユーザー", days="有効日数（0で永久、-1で取り消し）")
    @is_owner()
    async def grant_license_cmd(self, interaction: discord.Interaction, user: discord.User, days: int = 30):
        if days == -1:
            revoke_license(user.id)
            return await interaction.response.send_message(f"✅ {user.mention} の使用権を取り消しました。", ephemeral=True)
        grant_license(user.id, days if days != 0 else -1)
        expiry_text = get_license_expiry_text(user.id)
        embed = discord.Embed(
            title="✅ 使用権付与",
            description=f"{user.mention} に使用権を付与しました\n🕐 有効期限: **{expiry_text}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="使用権一覧", description="現在の使用権保持者一覧を表示します（オーナー専用）")
    @is_owner()
    async def list_licenses_cmd(self, interaction: discord.Interaction):
        licenses = load_licenses()
        now = time.time()
        lines = []
        for uid, exp in sorted(licenses.items(), key=lambda x: x[1] if x[1] != -1 else float("inf")):
            if exp == -1:
                status = "永久"
            elif exp > now:
                remain_days = int((exp - now) // 86400)
                remain_hrs  = int(((exp - now) % 86400) // 3600)
                status = f"残{remain_days}日{remain_hrs}時間"
            else:
                status = "⚠ 期限切れ"
            lines.append(f"<@{uid}>: {status}")
        desc = "\n".join(lines) if lines else "使用権保持者なし"
        embed = discord.Embed(title="🎫 使用権一覧", description=desc, color=0x9B59B6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _refresh_panel(self):
        panel = load_panel_data()
        if not panel:
            return
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id")
        if not ch_id or not msg_id:
            return
        channel = self.bot.get_channel(ch_id)
        if not channel:
            return
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=build_panel_embed())
        except Exception:
            pass


async def setup(bot: commands.Bot):
    cog = LicensePanelCog(bot)
    await bot.add_cog(cog)
    bot.loop.create_task(cog.respawn_panel())
