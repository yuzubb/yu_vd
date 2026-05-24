"""
license_panel.py
Bot使用権限の購入パネル管理Cog
- パネル設置はオーナー（OWNER_ID）のみ
- 価格は微調整可能
- PayPay決済で使用権を購入
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

PANEL_FILE      = "data/license_panel.json"
PRICES_FILE     = "data/license_prices.json"
PAYPAY_DATA_FILE = "data/paypay_data.json"

os.makedirs("data", exist_ok=True)

# ====================== デフォルト価格 ======================
DEFAULT_PRICES = {
    "1day":   {"label": "1日",   "days": 1,  "price": 100},
    "7days":  {"label": "7日",   "days": 7,  "price": 500},
    "30days": {"label": "1ヶ月", "days": 30, "price": 3000},
}


def load_prices() -> dict:
    if os.path.exists(PRICES_FILE):
        try:
            with open(PRICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return DEFAULT_PRICES.copy()


def save_prices(data: dict):
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_panel_data() -> dict:
    if os.path.exists(PANEL_FILE):
        try:
            with open(PANEL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
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
        except json.JSONDecodeError:
            pass
    return {}


# ====================== 購入モーダル ======================
class PurchaseModal(ui.Modal):
    def __init__(self, plan_key: str, plan_info: dict):
        super().__init__(
            title=f"使用権購入 - {plan_info['label']}（¥{plan_info['price']}）",
            timeout=180
        )
        self.plan_key  = plan_key
        self.plan_info = plan_info

        self.pay_link = ui.TextInput(
            label=f"PayPayリンク（¥{plan_info['price']} 分）",
            placeholder="https://pay.paypay.ne.jp/...",
            required=True,
            min_length=30,
            max_length=200,
        )
        self.add_item(self.pay_link)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link_url = self.pay_link.value.strip()
        required_amount = self.plan_info["price"]

        # --- PayPay情報をオーナーから取得 ---
        paypay_data = load_paypay_data()
        owner_cred = paypay_data.get(str(OWNER_ID))
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

        if amount < required_amount:
            return await interaction.followup.send(
                f"❌ 金額が不足しています。\n必要金額: **¥{required_amount:,}**\nリンクの金額: **¥{amount:,}**",
                ephemeral=True
            )

        # パスコードチェック
        if p2p_info.get("isSetPasscode", False):
            return await interaction.followup.send(
                "⚠️ パスコード付きのリンクは使用できません。",
                ephemeral=True
            )

        # --- 受け取り ---
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
            if result == "LOGINERR":
                msg = "❌ PayPayログインに失敗しました。管理者にお問い合わせください。"
            else:
                msg = "❌ PayPayの受け取りに失敗しました。リンクが使用済みか期限切れの可能性があります。"
            return await interaction.followup.send(msg, ephemeral=True)

        # --- ライセンス付与 ---
        grant_license(interaction.user.id, self.plan_info["days"])
        expiry_text = get_license_expiry_text(interaction.user.id)

        embed = discord.Embed(
            title="✅ 購入完了！",
            description=(
                f"**{self.plan_info['label']}プラン** の使用権を付与しました！\n\n"
                f"🕐 有効期限: **{expiry_text}**\n\n"
                "Botの全機能をご利用いただけます。"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"購入金額: ¥{required_amount:,}")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ====================== 購入パネルView ======================
class LicensePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self._rebuild_buttons()

    def _rebuild_buttons(self):
        # 既存ボタンをクリア
        self.clear_items()
        prices = load_prices()

        for key, info in prices.items():
            btn = ui.Button(
                label=f"🛒 {info['label']} ¥{info['price']:,}",
                style=discord.ButtonStyle.primary,
                custom_id=f"license_buy_{key}",
            )

            async def callback(interaction: discord.Interaction, k=key, i=info):
                modal = PurchaseModal(plan_key=k, plan_info=i)
                await interaction.response.send_modal(modal)

            btn.callback = callback
            self.add_item(btn)

        # 有効期限確認ボタン
        check_btn = ui.Button(
            label="📋 使用権を確認",
            style=discord.ButtonStyle.secondary,
            custom_id="license_check",
            row=1,
        )

        async def check_callback(interaction: discord.Interaction):
            uid = interaction.user.id
            if has_valid_license(uid):
                expiry = get_license_expiry_text(uid)
                color = discord.Color.green()
                status = f"✅ 有効\n🕐 残り: **{expiry}**"
            else:
                color = discord.Color.red()
                status = "❌ 使用権なし\n上のボタンから購入してください。"

            embed = discord.Embed(
                title="使用権の確認",
                description=status,
                color=color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        check_btn.callback = check_callback
        self.add_item(check_btn)


def build_panel_embed(prices: dict) -> discord.Embed:
    lines = []
    for key, info in prices.items():
        lines.append(f"**{info['label']}プラン** ▸ ¥{info['price']:,}")

    desc = (
        "Botの使用権をPayPayで購入できます。\n\n"
        "**料金プラン**\n"
        + "\n".join(lines)
        + "\n\n"
        "購入後はBotの全機能を利用できます。\n"
        "有効期限が切れると自動的に使用不可になります。\n\n"
        "📌 ボタンを押してPayPayリンクを入力してください。"
    )
    embed = discord.Embed(
        title="🤖 Bot 使用権購入",
        description=desc,
        color=0x00a0e9
    )
    return embed


# ====================== Cog ======================
class LicensePanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._respawning = False
        self.check_expired_loop.start()

    def cog_unload(self):
        self.check_expired_loop.cancel()

    # 期限切れチェック（1時間ごと）
    @tasks.loop(hours=1)
    async def check_expired_loop(self):
        """期限切れライセンスを自動削除する"""
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
        """Bot起動時にパネルを再設置"""
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

            prices = load_prices()
            view   = LicensePanelView()
            new_msg = await channel.send(embed=build_panel_embed(prices), view=view)

            panel["message_id"] = new_msg.id
            save_panel_data(panel)
            self.bot.add_view(view)
        finally:
            self._respawning = False

    # ── /使用権パネル設置 ─────────────────────────────────
    @app_commands.command(name="使用権パネル設置", description="Bot使用権購入パネルを設置します（オーナー専用）")
    @is_owner()
    async def setup_license_panel(self, interaction: discord.Interaction):
        """使用権購入パネルを現在のチャンネルに設置する"""
        panel = load_panel_data()

        # 古いパネルを削除
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

        prices  = load_prices()
        view    = LicensePanelView()
        msg     = await interaction.channel.send(embed=build_panel_embed(prices), view=view)

        save_panel_data({"channel_id": interaction.channel.id, "message_id": msg.id})
        await interaction.response.send_message("✅ 使用権購入パネルを設置しました！", ephemeral=True)

    # ── /使用権価格設定 ──────────────────────────────────
    @app_commands.command(name="使用権価格設定", description="使用権の価格プランを変更します（オーナー専用）")
    @app_commands.describe(
        plan="変更するプラン（1day / 7days / 30days）",
        price="新しい価格（円）",
        days="有効日数（変更する場合）",
        label="プラン名（変更する場合）"
    )
    @is_owner()
    async def set_license_price(
        self,
        interaction: discord.Interaction,
        plan: str,
        price: int,
        days: int = 0,
        label: str = ""
    ):
        prices = load_prices()
        if plan not in prices:
            keys = ", ".join(prices.keys())
            return await interaction.response.send_message(
                f"❌ 不明なプラン: `{plan}`\n使えるプラン: `{keys}`",
                ephemeral=True
            )

        if price < 0:
            return await interaction.response.send_message("❌ 価格は0以上にしてください", ephemeral=True)

        prices[plan]["price"] = price
        if days > 0:
            prices[plan]["days"] = days
        if label:
            prices[plan]["label"] = label

        save_prices(prices)

        # パネルを更新
        await self._refresh_panel()

        embed = discord.Embed(
            title="✅ 価格設定完了",
            description=f"**{prices[plan]['label']}プラン** を更新しました\n"
                        f"▸ 価格: ¥{price:,}\n"
                        f"▸ 有効日数: {prices[plan]['days']}日",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /使用権付与 ──────────────────────────────────────
    @app_commands.command(name="使用権付与", description="ユーザーに使用権を手動付与します（オーナー専用）")
    @app_commands.describe(
        user="対象ユーザー",
        days="有効日数（0で永久、-1で取り消し）"
    )
    @is_owner()
    async def grant_license_cmd(self, interaction: discord.Interaction, user: discord.User, days: int = 30):
        if days == -1:
            revoke_license(user.id)
            return await interaction.response.send_message(
                f"✅ {user.mention} の使用権を取り消しました。", ephemeral=True
            )

        grant_license(user.id, days if days != 0 else -1)
        expiry_text = get_license_expiry_text(user.id)

        embed = discord.Embed(
            title="✅ 使用権付与",
            description=f"{user.mention} に使用権を付与しました\n🕐 有効期限: **{expiry_text}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /使用権一覧 ──────────────────────────────────────
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
        embed = discord.Embed(
            title="🎫 使用権一覧",
            description=desc,
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _refresh_panel(self):
        """パネルのEmbedを価格変更後に更新する"""
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
            prices = load_prices()
            await msg.edit(embed=build_panel_embed(prices))
        except Exception:
            pass


async def setup(bot: commands.Bot):
    cog = LicensePanelCog(bot)
    await bot.add_cog(cog)
    bot.loop.create_task(cog.respawn_panel())