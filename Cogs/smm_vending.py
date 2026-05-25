"""
smm_vending.py  ―  SMMフォロ爆自販機 Cog
配置場所: Cogs/smm_vending.py

.env に追記:
    SMM_API_KEY=SMMのAPIキー
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import aiohttp
import json
import os
import re
import datetime
import pytz
from collections import defaultdict

from utils import is_allowed, OWNER_ID
import paypayu

# ─── 設定 ──────────────────────────────────────────────────────────────────────
SMM_API_URL  = "https://smmjp.com/api/v2"
SMM_API_KEY  = os.getenv("SMM_API_KEY", "")

SMM_ORDER_FILE  = "data/smm_orders.json"
SMM_MENU_FILE   = "data/smm_menu.json"
PAYPAY_FILE     = "paypay_data.json"   # vending.py と共有
VENDING_FILE    = "data/smm_vending_data.json"
PENDING_FILE    = "data/paypay_pending_smm.json"

JST = pytz.timezone("Asia/Tokyo")

SNS_CATEGORIES = [
    {"key": "instagram",  "label": "Instagram",   "emoji": "📷"},
    {"key": "tiktok",     "label": "TikTok",       "emoji": "🎵"},
    {"key": "twitter",    "label": "X (Twitter)",  "emoji": "🐦"},
    {"key": "threads",    "label": "Threads",      "emoji": "🧵"},
    {"key": "youtube",    "label": "YouTube",      "emoji": "▶️"},
    {"key": "spotify",    "label": "Spotify",      "emoji": "🟢"},
    {"key": "facebook",   "label": "Facebook",     "emoji": "🔵"},
    {"key": "line",       "label": "LINE",         "emoji": "💬"},
    {"key": "twitch",     "label": "Twitch",       "emoji": "💜"},
    {"key": "reddit",     "label": "Reddit",       "emoji": "🟠"},
    {"key": "discord",    "label": "Discord",      "emoji": "🎮"},
    {"key": "telegram",   "label": "Telegram",     "emoji": "✈️"},
    {"key": "kick",       "label": "Kick",         "emoji": "🟩"},
    {"key": "pinterest",  "label": "Pinterest",    "emoji": "📌"},
    {"key": "clubhouse",  "label": "Clubhouse",    "emoji": "🏠"},
    {"key": "whatsapp",   "label": "WhatsApp",     "emoji": "📱"},
    {"key": "bluesky",    "label": "BlueSky",      "emoji": "🦋"},
    {"key": "googleplay", "label": "Google Play",  "emoji": "▶"},
    {"key": "googlemaps", "label": "Google Maps",  "emoji": "🗺️"},
    {"key": "quora",      "label": "Quora",        "emoji": "❓"},
]
CATEGORY_EMOJI   = {c["key"]: c["emoji"]  for c in SNS_CATEGORIES}
CATEGORY_LABEL   = {c["key"]: c["label"]  for c in SNS_CATEGORIES}
CATEGORY_CHOICES = [app_commands.Choice(name=c["label"], value=c["key"]) for c in SNS_CATEGORIES]

# ─── 初期メニューテンプレート（自販機作成時に自動登録する人気サービス） ────────────
# service_name_keyword: SMMサービス名に含まれるキーワード（小文字）で自動マッチング
# margin_rate: 原価に掛ける倍率（例 3.0 = 原価の3倍で販売）
DEFAULT_MENU_TEMPLATES = [
    # Instagram
    {"category": "instagram", "keyword": "instagram followers",        "name": "Instagramフォロワー",          "margin_rate": 3.0, "min_qty": 100,  "max_qty": 10000},
    {"category": "instagram", "keyword": "instagram likes",            "name": "Instagramいいね",              "margin_rate": 3.0, "min_qty": 50,   "max_qty": 5000},
    {"category": "instagram", "keyword": "instagram views",            "name": "Instagram動画再生数",          "margin_rate": 3.0, "min_qty": 1000, "max_qty": 100000},
    # TikTok
    {"category": "tiktok",    "keyword": "tiktok followers",           "name": "TikTokフォロワー",             "margin_rate": 3.0, "min_qty": 100,  "max_qty": 10000},
    {"category": "tiktok",    "keyword": "tiktok likes",               "name": "TikTokいいね",                 "margin_rate": 3.0, "min_qty": 100,  "max_qty": 10000},
    {"category": "tiktok",    "keyword": "tiktok views",               "name": "TikTok動画再生数",             "margin_rate": 3.0, "min_qty": 1000, "max_qty": 500000},
    # X (Twitter)
    {"category": "twitter",   "keyword": "twitter followers",          "name": "Xフォロワー",                  "margin_rate": 3.0, "min_qty": 100,  "max_qty": 10000},
    {"category": "twitter",   "keyword": "twitter likes",              "name": "Xいいね",                      "margin_rate": 3.0, "min_qty": 50,   "max_qty": 5000},
    # YouTube
    {"category": "youtube",   "keyword": "youtube subscribers",        "name": "YouTubeチャンネル登録",        "margin_rate": 3.0, "min_qty": 100,  "max_qty": 5000},
    {"category": "youtube",   "keyword": "youtube views",              "name": "YouTube再生回数",              "margin_rate": 3.0, "min_qty": 1000, "max_qty": 500000},
    # Threads
    {"category": "threads",   "keyword": "threads followers",          "name": "Threadsフォロワー",            "margin_rate": 3.5, "min_qty": 100,  "max_qty": 5000},
]

# SMMサービスのrateはUSD/1000件単位。円換算レート（適宜更新）
SMM_USD_TO_JPY = 155.0

# ─── JSON ヘルパー ──────────────────────────────────────────────────────────────
def _ensure_data_dir():
    os.makedirs("data", exist_ok=True)

def load_json(path: str):
    _ensure_data_dir()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_json(path: str, data):
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_smm_menu() -> list:
    _ensure_data_dir()
    if os.path.exists(SMM_MENU_FILE):
        with open(SMM_MENU_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_smm_menu(data: list):
    _ensure_data_dir()
    with open(SMM_MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_vending_data() -> dict:
    return load_json(VENDING_FILE)

def save_vending_data(data: dict):
    save_json(VENDING_FILE, data)

def load_paypay_data() -> dict:
    return load_json(PAYPAY_FILE)

# ─── SMM API ───────────────────────────────────────────────────────────────────
async def smm_request(payload: dict) -> dict:
    payload["key"] = SMM_API_KEY
    async with aiohttp.ClientSession() as session:
        async with session.post(SMM_API_URL, data=payload) as resp:
            text = await resp.text()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"error": f"APIレスポンス解析失敗: {text[:200]}"}

async def smm_add_order(service_id: int, link: str, quantity: int) -> dict:
    return await smm_request({"action": "add", "service": service_id, "link": link, "quantity": quantity})

async def smm_get_status(order_id) -> dict:
    return await smm_request({"action": "status", "order": order_id})

async def smm_get_balance() -> dict:
    return await smm_request({"action": "balance"})

async def smm_get_services() -> list:
    result = await smm_request({"action": "services"})
    return result if isinstance(result, list) else []

def _calc_price_jpy(rate_str, margin_rate: float) -> float:
    """SMMのrate（USD/1000件）を円換算して利益マージンを乗せ、1件あたりの円価格を返す"""
    try:
        rate_usd_per_1000 = float(rate_str)
        cost_jpy_per_1    = rate_usd_per_1000 * SMM_USD_TO_JPY / 1000
        return round(cost_jpy_per_1 * margin_rate, 2)
    except (TypeError, ValueError):
        return 0.0

def _match_service(services: list, keyword: str) -> dict | None:
    """キーワードでSMMサービスリストを検索し最初にヒットしたものを返す"""
    kw = keyword.lower()
    for svc in services:
        if kw in svc.get("name", "").lower():
            return svc
    return None

# ─── PayPay 自動受取 UI ────────────────────────────────────────────────────────
def _fmt_ts(ts) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(int(ts) / 1000, tz=JST)
        return dt.strftime("%Y年%m月%d日  %H時%M分%S秒")
    except:
        return str(ts)

def _build_paypay_embed(sender, amount, money, money_light,
                        transaction_id, created_at, expires_at,
                        received=False) -> discord.Embed:
    embed = discord.Embed(
        title="PayPay Auto Receive",
        description=f"{sender}から受け取る",
        color=0xE8343A,
    )
    embed.add_field(name="送信者",       value=sender,             inline=False)
    embed.add_field(name="合計金額",     value=f"{amount}円",      inline=False)
    embed.add_field(name="マネー",       value=f"{money}円",       inline=False)
    embed.add_field(name="マネーライト", value=f"{money_light}円", inline=False)
    embed.add_field(name="取引番号",     value=transaction_id,     inline=False)
    embed.add_field(name="作成日時",     value=created_at,         inline=False)
    embed.add_field(name="有効期限",     value=expires_at,         inline=False)
    embed.set_footer(text="受け取り済み" if received else "SMM自販機")
    return embed


class PayPayReceiveView(ui.View):
    def __init__(self, link, amount, sender, money, money_light,
                 transaction_id, created_at, expires_at):
        super().__init__(timeout=None)
        self.link           = link
        self.amount         = amount
        self.sender         = sender
        self.money          = money
        self.money_light    = money_light
        self.transaction_id = transaction_id
        self.created_at     = created_at
        self.expires_at     = expires_at

    @ui.button(label="受け取る", style=discord.ButtonStyle.danger, custom_id="smm_paypay_receive_btn")
    async def receive_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ このボタンはオーナーのみ操作できます。", ephemeral=True
            )
        await interaction.response.defer()

        info = load_paypay_data().get(str(OWNER_ID))
        if not info:
            return await interaction.followup.send(
                "❌ オーナーのPayPayアカウントが未登録です。`/smm_paypay登録` で登録してください。", ephemeral=True
            )

        result = await paypayu.link_rev(self.link, info["phone"], info["password"], info["uuid"])

        if result is True:
            button.label    = "受け取り済み"
            button.style    = discord.ButtonStyle.secondary
            button.disabled = True
            embed = _build_paypay_embed(
                sender=self.sender, amount=self.amount,
                money=self.money, money_light=self.money_light,
                transaction_id=self.transaction_id,
                created_at=self.created_at, expires_at=self.expires_at,
                received=True,
            )
            await interaction.message.edit(embed=embed, view=self)
        elif result == "LOGINERR":
            await interaction.followup.send("❌ PayPayログインに失敗しました。", ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ 受け取りに失敗しました。リンクが無効または受取済みの可能性があります。", ephemeral=True
            )

# ─── 購入フロー UI ────────────────────────────────────────────────────────────
class SmmQuantityModal(ui.Modal, title="購入情報入力"):
    url_input = ui.TextInput(
        label="SNSのURL",
        placeholder="https://instagram.com/your_account",
        required=True, max_length=500,
    )
    qty_input = ui.TextInput(
        label="購入数",
        placeholder="例: 100",
        required=True, max_length=6,
    )

    def __init__(self, menu_item: dict, vm_id: str, bot: commands.Bot):
        super().__init__()
        self.menu_item = menu_item
        self.vm_id     = vm_id
        self.bot       = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ 数量には整数を入力してください。", ephemeral=True)

        mi    = self.menu_item
        min_q = mi.get("min_qty", 1)
        max_q = mi.get("max_qty", 100000)

        if qty < min_q or qty > max_q:
            return await interaction.response.send_message(
                f"❌ 購入数は {min_q:,}〜{max_q:,} の範囲で入力してください。", ephemeral=True
            )

        total_price = round(mi.get("price", 0) * qty)
        sns_url     = self.url_input.value.strip()

        embed = discord.Embed(title="購入確認", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.add_field(name="サービス", value=f"```{mi['name']}```",     inline=False)
        embed.add_field(name="URL",      value=f"```{sns_url}```",         inline=False)
        embed.add_field(name="数量",     value=f"```{qty:,}個```",        inline=True)
        embed.add_field(name="合計金額", value=f"```¥{total_price:,}```", inline=True)
        embed.set_footer(text="SMM自販機")

        view = SmmPurchaseConfirmView(
            vm_id=self.vm_id, menu_item=mi, sns_url=sns_url,
            quantity=qty, total_price=total_price, bot=self.bot,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SmmPayPayModal(ui.Modal, title="PayPay決済"):
    paypay_input = ui.TextInput(
        label="PayPayリンク",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True,
    )

    def __init__(self, confirm_view):
        super().__init__()
        self.confirm_view = confirm_view

    async def on_submit(self, interaction: discord.Interaction):
        await self.confirm_view.process_purchase(interaction, self.paypay_input.value.strip())


class SmmPurchaseConfirmView(ui.View):
    def __init__(self, vm_id, menu_item, sns_url, quantity, total_price, bot):
        super().__init__(timeout=300)
        self.vm_id       = vm_id
        self.menu_item   = menu_item
        self.sns_url     = sns_url
        self.quantity    = quantity
        self.total_price = total_price
        self.bot         = bot

    @ui.button(label="購入確定", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if self.total_price == 0:
            await self.process_purchase(interaction, None)
        else:
            await interaction.response.send_modal(SmmPayPayModal(self))

    @ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("❌ 購入をキャンセルしました。", ephemeral=True)

    async def process_purchase(self, interaction: discord.Interaction, pay_link):
        await interaction.response.defer(ephemeral=True)

        if self.total_price > 0:
            if not pay_link:
                return await interaction.followup.send("❌ PayPayリンクが入力されていません。", ephemeral=True)

            payment_info = await paypayu.check_link(pay_link)
            if not payment_info:
                return await interaction.followup.send(
                    "❌ 有効なPayPayリンクを入力してください（受取待ち状態のみ使用可）。", ephemeral=True
                )

            amount = payment_info.get("payload", {}).get("pendingP2PInfo", {}).get("amount", 0)
            if amount < self.total_price:
                return await interaction.followup.send(
                    f"❌ 金額不足。必要: ¥{self.total_price:,} / 送金額: ¥{amount:,}", ephemeral=True
                )

            vd          = load_vending_data()
            vm          = vd.get(self.vm_id, {})
            paypay_data = load_paypay_data()
            owner_id    = vm.get("owner_id")
            owner_creds = paypay_data.get(str(owner_id))

            if not owner_creds:
                return await interaction.followup.send(
                    "❌ 販売者のPayPayアカウントが設定されていません。", ephemeral=True
                )

            result = await paypayu.link_rev(
                pay_link,
                owner_creds["phone"],
                owner_creds["password"],
                owner_creds["uuid"],
            )
            if result is not True:
                return await interaction.followup.send(
                    "❌ PayPay決済の処理に失敗しました。リンクを確認してください。", ephemeral=True
                )

        mi       = self.menu_item
        smm_resp = await smm_add_order(mi["service_id"], self.sns_url, self.quantity)

        if "error" in smm_resp or "order" not in smm_resp:
            return await interaction.followup.send(
                f"❌ SMM注文に失敗しました。\n```{smm_resp.get('error', str(smm_resp))}```", ephemeral=True
            )

        smm_order_id = smm_resp["order"]

        orders = load_json(SMM_ORDER_FILE)
        orders[str(smm_order_id)] = {
            "discord_user_id": str(interaction.user.id),
            "vm_id":           self.vm_id,
            "service_id":      mi["service_id"],
            "service_name":    mi["name"],
            "sns_url":         self.sns_url,
            "quantity":        self.quantity,
            "total_price":     self.total_price,
            "smm_order_id":    smm_order_id,
            "status":          "Pending",
            "created_at":      datetime.datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
        }
        save_json(SMM_ORDER_FILE, orders)

        price_disp = f"¥{self.total_price:,}" if self.total_price > 0 else "¥0（無料）"
        embed = discord.Embed(title="✅ 注文完了", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="サービス", value=f"```{mi['name']}```",       inline=False)
        embed.add_field(name="URL",      value=f"```{self.sns_url}```",       inline=False)
        embed.add_field(name="数量",     value=f"```{self.quantity:,}個```", inline=True)
        embed.add_field(name="支払金額", value=f"```{price_disp}```",         inline=True)
        embed.add_field(name="注文ID",   value=f"```{smm_order_id}```",       inline=True)
        embed.set_footer(text="注文IDは「状況確認」ボタンで使えます。 | SMM自販機")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # ログチャンネルへ送信
        try:
            vd        = load_vending_data()
            vm        = vd.get(self.vm_id, {})
            log_ch_id = vm.get("log_channel_id")
            if log_ch_id:
                log_ch = self.bot.get_channel(log_ch_id)
                if log_ch:
                    log_embed = discord.Embed(title="📋 購入ログ", color=0x2b2d31, timestamp=discord.utils.utcnow())
                    log_embed.add_field(name="購入者",  value=interaction.user.mention,        inline=True)
                    log_embed.add_field(name="内容",    value=f"{mi['name']} ({price_disp})",  inline=True)
                    log_embed.add_field(name="数量",    value=f"{self.quantity:,} 件",         inline=True)
                    log_embed.add_field(name="OrderID", value=str(smm_order_id),               inline=False)
                    log_embed.set_footer(text="SMM自販機")
                    await log_ch.send(embed=log_embed)
        except Exception as e:
            print(f"[smm_log_channel] error: {e}")

        # 購入ロール付与
        try:
            vd      = load_vending_data()
            role_id = vd.get(self.vm_id, {}).get("purchase_role_id")
            if role_id and interaction.guild:
                role = interaction.guild.get_role(role_id)
                if role and role not in interaction.user.roles:
                    await interaction.user.add_roles(role)
        except Exception as e:
            print(f"[smm_role_grant] error: {e}")

        # 購入者へDM通知
        try:
            now_jst = datetime.datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S(JST)")
            dm_embed = discord.Embed(title="購入が完了しました", color=0x2b2d31)
            dm_embed.add_field(name="購入日",       value=f"```{now_jst}```",                                                                                                    inline=True)
            dm_embed.add_field(name="購入サーバー", value=f"```{interaction.guild.name if interaction.guild else 'DM'}```",                                                       inline=True)
            dm_embed.add_field(name="商品名",       value=f"```{mi['name']}```",                                                                                                 inline=True)
            dm_embed.add_field(name="購入数",       value=f"```{self.quantity:,}個```",                                                                                          inline=True)
            dm_embed.add_field(name="支払金額",     value=f"```{price_disp}```",                                                                                                 inline=True)
            dm_embed.add_field(name="注文ID",       value=f"```{smm_order_id}```",                                                                                               inline=True)
            dm_embed.set_footer(text="SMM自販機")
            await interaction.user.send(embed=dm_embed)
        except:
            pass

        # オーナーへDM通知
        try:
            owner_user = await self.bot.fetch_user(OWNER_ID)
            if owner_user:
                owner_embed = discord.Embed(title="💰 新しい購入がありました", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                owner_embed.add_field(name="購入者",   value=f"```{interaction.user} ({interaction.user.id})```", inline=False)
                owner_embed.add_field(name="商品名",   value=f"```{mi['name']}```",                               inline=True)
                owner_embed.add_field(name="購入数",   value=f"```{self.quantity:,}個```",                        inline=True)
                owner_embed.add_field(name="支払金額", value=f"```{price_disp}```",                               inline=True)
                owner_embed.add_field(name="注文ID",   value=f"```{smm_order_id}```",                             inline=True)
                owner_embed.add_field(name="サーバー", value=f"```{interaction.guild.name if interaction.guild else 'DM'}```", inline=True)
                owner_embed.set_footer(text="SMM自販機")
                await owner_user.send(embed=owner_embed)
        except:
            pass


# ─── パネル UI ────────────────────────────────────────────────────────────────
class SmmCategorySelect(ui.Select):
    def __init__(self, vm_id: str, bot: commands.Bot):
        self.vm_id = vm_id
        self.bot   = bot

        menu = load_smm_menu()
        used = {m.get("category") for m in menu if m.get("vm_id") == vm_id}
        options = [
            discord.SelectOption(label=c["label"], value=c["key"])
            for c in SNS_CATEGORIES if c["key"] in used
        ]
        if not options:
            options = [discord.SelectOption(label="サービスなし", value="none")]

        super().__init__(
            placeholder="カテゴリーを選択して購入手続きへお進みください。",
            options=options,
            custom_id=f"smm_cat_{vm_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("現在サービスが登録されていません。", ephemeral=True)

        category = self.values[0]
        items    = [m for m in load_smm_menu() if m.get("vm_id") == self.vm_id and m.get("category") == category]

        if not items:
            return await interaction.response.send_message("このカテゴリーにサービスがありません。", ephemeral=True)

        embed = discord.Embed(
            title=f"{CATEGORY_LABEL.get(category, '')} ― サービス選択",
            description="購入するサービスを選んでください。",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="SMM自販機")

        for opt in self.options:
            opt.default = False
        await interaction.response.edit_message(view=self.view)

        await interaction.followup.send(
            embed=embed,
            view=SmmServiceSelectView(self.vm_id, items, self.bot),
            ephemeral=True,
        )


class SmmServiceSelectView(ui.View):
    def __init__(self, vm_id, items, bot):
        super().__init__(timeout=120)
        self.add_item(SmmServiceSelectInner(vm_id, items, bot))


class SmmServiceSelectInner(ui.Select):
    def __init__(self, vm_id, items, bot):
        self.vm_id = vm_id
        self.items = items
        self.bot   = bot
        options = [
            discord.SelectOption(
                label=item["name"][:100],
                value=str(item["service_id"]),
                description=f"¥{item.get('price', 0)}/単価  {item.get('min_qty', 1):,}〜{item.get('max_qty', 100000):,}個"[:100],
            )
            for item in items
        ]
        super().__init__(placeholder="サービスを選択...", options=options)

    async def callback(self, interaction: discord.Interaction):
        item = next((m for m in self.items if str(m["service_id"]) == self.values[0]), None)
        if not item:
            return await interaction.response.send_message("サービスが見つかりません。", ephemeral=True)
        await interaction.response.send_modal(SmmQuantityModal(item, self.vm_id, self.bot))


class SmmOrderCheckModal(ui.Modal, title="注文状況の照会"):
    order_id_input = ui.TextInput(
        label="注文ID (OrderID)",
        placeholder="例: 12345",
        required=True, max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            order_id = int(self.order_id_input.value.strip())
        except ValueError:
            return await interaction.followup.send("❌ 注文IDには数字を入力してください。", ephemeral=True)

        result = await smm_get_status(order_id)

        STATUS_JP = {
            "Pending":     "⏳ 処理待ち",
            "In progress": "🔄 処理中",
            "Completed":   "✅ 完了",
            "Partial":     "⚠️ 一部完了",
            "Canceled":    "❌ キャンセル",
        }

        if "error" in result:
            embed = discord.Embed(
                title="❌ 照会エラー",
                description=f"注文IDが見つかりません。\n```{result['error']}```",
                color=discord.Color.red(),
            )
        else:
            raw       = result.get("status", "不明")
            orders    = load_json(SMM_ORDER_FILE)
            local_rec = orders.get(str(order_id), {})

            embed = discord.Embed(
                title=f"📦 注文 #{order_id} の状況",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow(),
            )
            if local_rec.get("service_name"):
                embed.add_field(name="サービス", value=f"```{local_rec['service_name']}```", inline=False)
            if local_rec.get("sns_url"):
                embed.add_field(name="URL",      value=f"```{local_rec['sns_url']}```",      inline=False)

            embed.add_field(name="ステータス",  value=f"```{STATUS_JP.get(raw, raw)}```",       inline=True)
            embed.add_field(name="残数",         value=f"```{result.get('remains', '-')}```",     inline=True)
            embed.add_field(name="開始時残数",   value=f"```{result.get('start_count', '-')}```", inline=True)
            if local_rec.get("quantity"):
                embed.add_field(name="注文数",   value=f"```{local_rec['quantity']:,}個```",      inline=True)
            if local_rec.get("total_price") is not None:
                embed.add_field(name="支払金額", value=f"```¥{local_rec['total_price']:,}```",    inline=True)
            if local_rec.get("created_at"):
                embed.add_field(name="注文日時", value=f"```{local_rec['created_at']}```",         inline=False)

            if str(order_id) in orders:
                orders[str(order_id)]["status"] = raw
                save_json(SMM_ORDER_FILE, orders)

        embed.set_footer(text="SMM自販機")
        await interaction.followup.send(embed=embed, ephemeral=True)


class SmmStatusButton(ui.Button):
    def __init__(self):
        super().__init__(label="状況確認", style=discord.ButtonStyle.secondary, custom_id="smm_status_btn", row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SmmOrderCheckModal())


class SmmHistoryView(ui.View):
    ITEMS_PER_PAGE = 5

    def __init__(self, records: list, user_id: int):
        super().__init__(timeout=120)
        self.records = records
        self.user_id = user_id
        self.page    = 0
        self.total   = max(1, (len(records) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self._refresh()

    def _refresh(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total - 1

    def build_embed(self) -> discord.Embed:
        STATUS_ICON = {
            "Completed":   "✅",
            "In progress": "🔄",
            "Pending":     "⏳",
            "Partial":     "⚠️",
            "Canceled":    "❌",
        }
        start  = self.page * self.ITEMS_PER_PAGE
        chunk  = self.records[start:start + self.ITEMS_PER_PAGE]
        embed  = discord.Embed(
            title="🧾  購入履歴",
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{self.page + 1} / {self.total} ページ　|　SMM自販機")
        for rec in chunk:
            icon  = STATUS_ICON.get(rec.get("status", "Pending"), "❓")
            name  = rec.get("service_name", "不明")
            qty   = rec.get("quantity", 0)
            price = rec.get("total_price", 0)
            oid   = rec.get("smm_order_id", "-")
            date  = rec.get("created_at", "")[:16]
            embed.add_field(
                name=f"{icon}  {date}　OrderID: {oid}",
                value=f"```{name}\n数量: {qty:,}個　支払: ¥{price:,}```",
                inline=False,
            )
        if not chunk:
            embed.description = "履歴がありません。"
        return embed

    @ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, btn: ui.Button):
        self.page -= 1
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, btn: ui.Button):
        self.page += 1
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class SmmHistoryButton(ui.Button):
    def __init__(self):
        super().__init__(label="購入履歴", style=discord.ButtonStyle.primary, custom_id="smm_history_btn", row=1)

    async def callback(self, interaction: discord.Interaction):
        orders  = load_json(SMM_ORDER_FILE)
        records = sorted(
            [r for r in orders.values() if r.get("discord_user_id") == str(interaction.user.id)],
            key=lambda r: r.get("created_at", ""),
            reverse=True,
        )
        view  = SmmHistoryView(records, interaction.user.id)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SmmPanelView(ui.View):
    def __init__(self, vm_id: str, bot: commands.Bot):
        super().__init__(timeout=None)
        self.vm_id = vm_id
        self.bot   = bot
        self.add_item(SmmCategorySelect(vm_id, bot))
        self.add_item(SmmStatusButton())
        self.add_item(SmmHistoryButton())


# ─── 売上集計 ─────────────────────────────────────────────────────────────────
class SalesPagingView(ui.View):
    ITEMS_PER_PAGE = 8

    def __init__(self, target, period_label, total_revenue, total_qty, total_orders,
                 avg_price, peak_hour, service_revenue, service_qty, recent_days, hour_revenue):
        super().__init__(timeout=120)
        self.target          = target
        self.period_label    = period_label
        self.total_revenue   = total_revenue
        self.total_qty       = total_qty
        self.total_orders    = total_orders
        self.avg_price       = avg_price
        self.peak_hour       = peak_hour
        self.service_revenue = service_revenue
        self.service_qty     = service_qty
        self.recent_days     = recent_days
        self.hour_revenue    = hour_revenue
        self.main_page       = 0
        self.buyer_page      = 0
        self.buyer_total     = max(1, (len(target) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)

    def current_embed(self):
        if self.main_page == 0:
            return self._overview_embed()
        elif self.main_page == 1:
            return self._hourly_embed()
        else:
            return self._buyers_embed()

    def refresh_buttons(self):
        self.prev_main.disabled  = self.main_page == 0
        self.next_main.disabled  = self.main_page == 2
        self.prev_buyer.disabled = self.main_page != 2 or self.buyer_page == 0
        self.next_buyer.disabled = self.main_page != 2 or self.buyer_page >= self.buyer_total - 1

    def _overview_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📊  売上レポート  ―  {self.period_label}",
            color=0xFFD700,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="💴  総売上",   value=f"```¥{self.total_revenue:,}```",  inline=True)
        embed.add_field(name="🛒  総注文数", value=f"```{self.total_orders:,} 件```",  inline=True)
        embed.add_field(name="📦  総数量",   value=f"```{self.total_qty:,} 個```",     inline=True)
        embed.add_field(name="💡  平均単価", value=f"```¥{self.avg_price:,.0f}```",    inline=True)
        if self.peak_hour is not None:
            embed.add_field(
                name="⏰  ピーク時間帯",
                value=f"```{self.peak_hour:02d}:00 〜 {self.peak_hour:02d}:59```",
                inline=True,
            )
        ranking = sorted(self.service_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
        if ranking:
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            lines  = []
            for i, (name, rev) in enumerate(ranking):
                qty   = self.service_qty.get(name, 0)
                share = rev / self.total_revenue * 100 if self.total_revenue else 0
                lines.append(f"{medals[i]} **{name}**\n　└ ¥{rev:,}  /  {qty:,}個  ({share:.1f}%)")
            embed.add_field(name="🏆  サービス別ランキング", value="\n".join(lines), inline=False)
        if self.recent_days:
            embed.add_field(name="📅  直近の日別売上", value="\n".join(f"`{d}`　¥{r:,}" for d, r in self.recent_days), inline=False)
        embed.set_footer(text="1/3 ページ　|　SMM自販機")
        return embed

    def _hourly_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"⏰  時間帯別売上  ―  {self.period_label}", color=0x5865F2, timestamp=discord.utils.utcnow())
        if self.hour_revenue:
            max_rev = max(self.hour_revenue.values()) or 1
            lines   = []
            for h in range(24):
                rev = self.hour_revenue.get(h, 0)
                if rev == 0:
                    continue
                bar = "█" * int(rev / max_rev * 10)
                lines.append(f"`{h:02d}時`  {bar:<10}  ¥{rev:,}")
            embed.add_field(name="売上バー", value="\n".join(lines) if lines else "データなし", inline=False)
        else:
            embed.description = "時間帯データがありません。"
        embed.set_footer(text="2/3 ページ　|　SMM自販機")
        return embed

    def _buyers_embed(self) -> discord.Embed:
        STATUS_ICON = {"Completed": "✅", "In progress": "🔄", "Pending": "⏳", "Partial": "⚠️", "Canceled": "❌"}
        start = self.buyer_page * self.ITEMS_PER_PAGE
        chunk = self.target[start:start + self.ITEMS_PER_PAGE]
        embed = discord.Embed(title=f"👥  購入者一覧  ―  {self.period_label}", color=0x57F287, timestamp=discord.utils.utcnow())
        for rec in chunk:
            uid    = rec.get("discord_user_id", "不明")
            status = rec.get("status", "Pending")
            icon   = STATUS_ICON.get(status, "❓")
            price  = rec.get("total_price", 0)
            qty    = rec.get("quantity", 0)
            name   = rec.get("service_name", "不明")
            date   = rec.get("created_at", "")[:16]
            embed.add_field(
                name=f"{icon}  <@{uid}>  ―  {date}",
                value=f"```{name}  /  {qty:,}個  /  ¥{price:,}```",
                inline=False,
            )
        embed.set_footer(text=f"3/3 ページ ({self.buyer_page+1}/{self.buyer_total})　|　SMM自販機")
        return embed

    @ui.button(label="◀ 前へ", style=discord.ButtonStyle.secondary, row=0)
    async def prev_main(self, itx: discord.Interaction, btn: ui.Button):
        self.main_page = max(0, self.main_page - 1)
        self.refresh_buttons()
        await itx.response.edit_message(embed=self.current_embed(), view=self)

    @ui.button(label="次へ ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_main(self, itx: discord.Interaction, btn: ui.Button):
        self.main_page = min(2, self.main_page + 1)
        self.refresh_buttons()
        await itx.response.edit_message(embed=self.current_embed(), view=self)

    @ui.button(label="< 購入者", style=discord.ButtonStyle.primary, row=1)
    async def prev_buyer(self, itx: discord.Interaction, btn: ui.Button):
        self.buyer_page = max(0, self.buyer_page - 1)
        self.refresh_buttons()
        await itx.response.edit_message(embed=self.current_embed(), view=self)

    @ui.button(label="購入者 >", style=discord.ButtonStyle.primary, row=1)
    async def next_buyer(self, itx: discord.Interaction, btn: ui.Button):
        self.buyer_page = min(self.buyer_total - 1, self.buyer_page + 1)
        self.refresh_buttons()
        await itx.response.edit_message(embed=self.current_embed(), view=self)


# ─── Cog ─────────────────────────────────────────────────────────────────────
class SmmVendingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        vending_data = load_vending_data()
        for vm_id in vending_data.keys():
            self.bot.add_view(SmmPanelView(vm_id, self.bot))
        self.bot.add_view(PayPayReceiveView(
            link="", amount=0, sender="", money=0, money_light=0,
            transaction_id="", created_at="", expires_at="",
        ))
        self.panel_refresh.start()
        self.order_status_check.start()

    def cog_unload(self):
        self.panel_refresh.cancel()
        self.order_status_check.cancel()

    @tasks.loop(hours=1)
    async def panel_refresh(self):
        vending_data = load_vending_data()
        for vm_id, vm in vending_data.items():
            msg_info = vm.get("panel_message")
            if not msg_info:
                continue
            try:
                ch = self.bot.get_channel(msg_info["channel_id"])
                if not ch:
                    continue
                msg        = await ch.fetch_message(msg_info["message_id"])
                menu_items = [m for m in load_smm_menu() if m.get("vm_id") == vm_id]
                old_embed  = msg.embeds[0] if msg.embeds else None
                title      = old_embed.title       if old_embed else "24時間フォロ爆自販機"
                desc       = old_embed.description if old_embed else "PayPay決済対応 | 24時間稼働中"

                embed = discord.Embed(title=title, description=desc, color=0x2b2d31)
                embed.set_footer(text="SMM自販機")
                for cat in SNS_CATEGORIES:
                    items = [m for m in menu_items if m.get("category") == cat["key"]]
                    if not items:
                        continue
                    lines = [f"{m['name']}：¥{m.get('price', 0)}/単価" for m in items]
                    embed.add_field(name=cat["label"], value="\n".join(lines), inline=False)

                view = SmmPanelView(vm_id, self.bot)
                await msg.edit(embed=embed, view=view)
            except Exception as e:
                print(f"[smm_panel_refresh] vm_id={vm_id} error: {e}")

    @panel_refresh.before_loop
    async def before_panel_refresh(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=30)
    async def order_status_check(self):
        orders  = load_json(SMM_ORDER_FILE)
        changed = False
        STATUS_JP = {
            "Pending":     "⏳ 処理待ち",
            "In progress": "🔄 処理中",
            "Completed":   "✅ 完了",
            "Partial":     "⚠️ 一部完了",
            "Canceled":    "❌ キャンセル",
        }
        NOTIFY_STATUSES = {"Completed", "Partial", "Canceled"}

        for order_id, rec in list(orders.items()):
            prev_status = rec.get("status", "Pending")
            if prev_status in NOTIFY_STATUSES:
                continue
            try:
                result     = await smm_get_status(int(order_id))
                new_status = result.get("status", prev_status)
                if new_status == prev_status:
                    continue

                orders[order_id]["status"] = new_status
                changed = True
                if new_status not in NOTIFY_STATUSES:
                    continue

                try:
                    user_id = int(rec.get("discord_user_id", 0))
                    user    = await self.bot.fetch_user(user_id)
                    if user:
                        color = discord.Color.green() if new_status == "Completed" else discord.Color.red()
                        embed = discord.Embed(
                            title=f"注文ステータス更新: {STATUS_JP.get(new_status, new_status)}",
                            color=color, timestamp=discord.utils.utcnow(),
                        )
                        embed.add_field(name="注文ID",   value=f"```{order_id}```",                        inline=True)
                        embed.add_field(name="サービス", value=f"```{rec.get('service_name', '不明')}```", inline=True)
                        embed.add_field(name="数量",     value=f"```{rec.get('quantity', '-'):,}個```",    inline=True)
                        embed.add_field(name="URL",      value=f"```{rec.get('sns_url', '-')}```",         inline=False)
                        embed.set_footer(text="SMM自販機")
                        await user.send(embed=embed)
                except Exception as e:
                    print(f"[smm_order_status_check] user dm error: {e}")
            except Exception as e:
                print(f"[smm_order_status_check] order={order_id} error: {e}")

        if changed:
            save_json(SMM_ORDER_FILE, orders)

    @order_status_check.before_loop
    async def before_order_status_check(self):
        await self.bot.wait_until_ready()

    # PayPayリンク自動検知（SMM専用チャンネル）
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        links = re.findall(r'https://pay\.paypay\.ne\.jp/[A-Za-z0-9_\-]+', message.content)
        if not links:
            return

        # SMM自販機のログチャンネル内のみ反応
        vd = load_vending_data()
        smm_log_channels = {vm.get("paypay_detect_channel_id") for vm in vd.values() if vm.get("paypay_detect_channel_id")}
        if message.channel.id not in smm_log_channels:
            return

        for link in links:
            try:
                link_info = await paypayu.check_link(link)
                if not link_info:
                    continue

                payload     = link_info.get("payload", {})
                msg_data    = payload.get("message", {}).get("data", {})
                p2p_info    = payload.get("pendingP2PInfo", {})

                amount      = msg_data.get("amount", 0)
                money       = p2p_info.get("prepaidMoney", {}).get("amount", 0)
                money_light = p2p_info.get("prepaidMoneyLight", {}).get("amount", 0)
                sender_name = payload.get("sender", {}).get("displayName", "不明")
                trans_id    = msg_data.get("requestId") or link.split("/")[-1]
                created_at  = _fmt_ts(msg_data.get("createdAt") or payload.get("createdAt"))
                expires_at  = _fmt_ts(msg_data.get("expiredAt") or payload.get("expiredAt"))

                embed = _build_paypay_embed(
                    sender=sender_name, amount=amount,
                    money=money, money_light=money_light,
                    transaction_id=trans_id,
                    created_at=created_at, expires_at=expires_at,
                )
                view = PayPayReceiveView(
                    link=link, amount=amount, sender=sender_name,
                    money=money, money_light=money_light,
                    transaction_id=trans_id,
                    created_at=created_at, expires_at=expires_at,
                )
                await message.channel.send(embed=embed, view=view)
            except Exception as e:
                print(f"[smm_on_message paypay] error: {e}")

    # ─── オートコンプリート ────────────────────────────────────────────────────
    async def _vm_id_ac(self, interaction: discord.Interaction, current: str):
        vending_data = load_vending_data()
        return [
            app_commands.Choice(name=vm["name"], value=vm_id)
            for vm_id, vm in vending_data.items()
            if vm.get("owner_id") == str(interaction.user.id) and current.lower() in vm["name"].lower()
        ][:25]

    async def _service_ac(self, interaction: discord.Interaction, current: str):
        vm_id = getattr(interaction.namespace, "vm_id", "") or ""
        return [
            app_commands.Choice(name=f"[{m['service_id']}] {m['name']}"[:100], value=str(m["service_id"]))
            for m in load_smm_menu()
            if m.get("vm_id") == vm_id and current.lower() in m["name"].lower()
        ][:25]

    # ─── コマンド群 ────────────────────────────────────────────────────────────
    @app_commands.command(name="フォロ爆自販機作成", description="SMMフォロ爆自販機を新規作成します（人気サービスを自動登録）")
    @is_allowed()
    @app_commands.describe(
        name="自販機の名前",
        auto_menu="作成時に人気サービスを自動登録するか（デフォルト: はい）",
        margin_rate="自動登録時の利益マージン倍率（例: 3.0 = 原価の3倍）",
    )
    @app_commands.choices(auto_menu=[
        app_commands.Choice(name="はい（自動登録する）", value="yes"),
        app_commands.Choice(name="いいえ（手動で追加する）", value="no"),
    ])
    async def vm_create(
        self, interaction: discord.Interaction,
        name: str,
        auto_menu: str = "yes",
        margin_rate: float = 3.0,
    ):
        import uuid
        await interaction.response.defer(ephemeral=True)

        vending_data        = load_vending_data()
        vm_id               = str(uuid.uuid4())
        vending_data[vm_id] = {"name": name, "owner_id": str(interaction.user.id)}
        save_vending_data(vending_data)

        has_paypay = str(interaction.user.id) in load_paypay_data()
        lines_msg = [f"✅ フォロ爆自販機「{name}」を作成しました。", f"**自販機ID:** `{vm_id}`"]
        if not has_paypay:
            lines_msg.append("⚠️ PayPayアカウントが未登録です。`/smm_paypay登録` を先に実行してください。")

        if auto_menu == "no":
            lines_msg.append("\n💡 `/smmサービス追加` または `/smm自動メニュー追加` でサービスを登録してください。")
            return await interaction.followup.send("\n".join(lines_msg), ephemeral=True)

        await interaction.followup.send("\n".join(lines_msg) + "\n\n⏳ SMMサービスを取得して初期メニューを自動登録中...", ephemeral=True)

        services = await smm_get_services()
        if not services:
            await interaction.followup.send(
                "⚠️ SMMサービスの取得に失敗しました。APIキーを確認するか、"
                "`/smm自動メニュー追加` で後から自動登録できます。",
                ephemeral=True,
            )
            return

        menu    = load_smm_menu()
        added   = []
        skipped = []
        for tmpl in DEFAULT_MENU_TEMPLATES:
            svc = _match_service(services, tmpl["keyword"])
            if not svc:
                skipped.append(f"❓ {tmpl['name']}（キーワード未ヒット: {tmpl['keyword']}）")
                continue
            service_id = int(svc.get("service", 0))
            if any(m["service_id"] == service_id and m.get("vm_id") == vm_id for m in menu):
                skipped.append(f"⚠️ {tmpl['name']}（ID:{service_id} 既登録）")
                continue
            actual_margin = tmpl["margin_rate"] * (margin_rate / 3.0)
            sell_price    = _calc_price_jpy(svc.get("rate", "0"), actual_margin)
            if sell_price <= 0:
                skipped.append(f"⚠️ {tmpl['name']}（価格計算失敗）")
                continue
            menu.append({
                "vm_id":       vm_id,
                "owner_id":    str(interaction.user.id),
                "category":    tmpl["category"],
                "service_id":  service_id,
                "name":        tmpl["name"],
                "price":       sell_price,
                "min_qty":     int(max(tmpl["min_qty"], int(svc.get("min", tmpl["min_qty"])))),
                "max_qty":     int(min(tmpl["max_qty"], int(svc.get("max", tmpl["max_qty"])))),
                "cost_rate":   svc.get("rate", "0"),
                "margin_rate": actual_margin,
            })
            added.append(f"✅ {tmpl['name']}（ID:{service_id}  ¥{sell_price}/件）")

        save_smm_menu(menu)

        result_embed = discord.Embed(
            title=f"📦 初期メニュー自動登録結果 — {name}",
            color=discord.Color.green() if added else discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        if added:
            result_embed.add_field(name=f"登録成功 {len(added)}件", value="\n".join(added)[:1024], inline=False)
        if skipped:
            result_embed.add_field(name=f"スキップ {len(skipped)}件", value="\n".join(skipped)[:1024], inline=False)
        result_embed.add_field(
            name="次のステップ",
            value="`/フォロ爆パネル設置` でパネルを設置するとすぐに販売開始できます。\n"
                  "価格は `/smmサービス削除` → `/smmサービス追加` で個別に変更できます。",
            inline=False,
        )
        result_embed.set_footer(text=f"マージン倍率: {margin_rate}x | SMM自販機")
        await interaction.followup.send(embed=result_embed, ephemeral=True)

    @app_commands.command(name="フォロ爆パネル設置", description="フォロ爆自販機パネルをこのチャンネルに設置します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(
        vm_id="設置する自販機ID",
        title="パネルタイトル",
        description="パネル説明文",
    )
    async def smm_setup(
        self, interaction: discord.Interaction,
        vm_id: str,
        title: str = "24時間フォロ爆自販機",
        description: str = "PayPay決済対応 | 24時間稼働中",
    ):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)

        menu_items = [m for m in load_smm_menu() if m.get("vm_id") == vm_id]
        embed      = discord.Embed(title=title, description=description, color=0x2b2d31)
        embed.set_footer(text="SMM自販機")
        for cat in SNS_CATEGORIES:
            items = [m for m in menu_items if m.get("category") == cat["key"]]
            if not items:
                continue
            lines = [f"{m['name']}：¥{m.get('price', 0)}/単価" for m in items]
            embed.add_field(name=cat["label"], value="\n".join(lines), inline=False)
        if not menu_items:
            embed.description += "\n\n**/smmサービス追加** でサービスを登録してください。"

        view = SmmPanelView(vm_id, self.bot)
        self.bot.add_view(view)
        await interaction.response.send_message("✅ フォロ爆自販機パネルを設置しました。", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        vending_data[vm_id]["panel_message"] = {
            "channel_id": interaction.channel.id,
            "message_id": msg.id,
        }
        save_vending_data(vending_data)

    @app_commands.command(name="smmサービス追加", description="SMMサービスをフォロ爆自販機に追加します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(
        vm_id="自販機ID",
        category="SNSカテゴリー",
        service_id="SMMのサービスID（/smmサービス検索で確認）",
        name="表示名（例: Instagramフォロワー/1日3万人）",
        price_per_unit="1個あたりの価格（円）",
        min_qty="最小購入数",
        max_qty="最大購入数",
    )
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def smm_add_service(
        self, interaction: discord.Interaction,
        vm_id: str, category: str, service_id: int,
        name: str, price_per_unit: float,
        min_qty: int = 100, max_qty: int = 10000,
    ):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        menu = load_smm_menu()
        if any(m["service_id"] == service_id and m.get("vm_id") == vm_id for m in menu):
            return await interaction.response.send_message("⚠️ そのサービスIDは既に登録されています。", ephemeral=True)
        menu.append({
            "vm_id": vm_id, "owner_id": str(interaction.user.id),
            "category": category, "service_id": service_id,
            "name": name, "price": price_per_unit,
            "min_qty": min_qty, "max_qty": max_qty,
        })
        save_smm_menu(menu)
        await interaction.response.send_message(
            f"✅ [{CATEGORY_LABEL.get(category)}] 「{name}」(ID:{service_id}) を追加しました。\n"
            f"`/フォロ爆パネル設置` でパネルを再設置すると反映されます。",
            ephemeral=True,
        )

    @app_commands.command(name="smmサービス削除", description="SMMサービスをメニューから削除します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac, service_id=_service_ac)
    @app_commands.describe(vm_id="自販機ID", service_id="削除するサービスID")
    async def smm_remove_service(self, interaction: discord.Interaction, vm_id: str, service_id: str):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        menu     = load_smm_menu()
        new_menu = [m for m in menu if not (str(m["service_id"]) == service_id and m.get("vm_id") == vm_id)]
        if len(new_menu) == len(menu):
            return await interaction.response.send_message("⚠️ そのサービスは見つかりません。", ephemeral=True)
        save_smm_menu(new_menu)
        await interaction.response.send_message(f"✅ サービスID {service_id} を削除しました。", ephemeral=True)

    @app_commands.command(name="smmサービス一覧", description="登録済みのSMMサービスを一覧表示します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機（省略で全件）")
    async def smm_list_services(self, interaction: discord.Interaction, vm_id: str = None):
        menu = load_smm_menu()
        if vm_id:
            menu = [m for m in menu if m.get("vm_id") == vm_id]
        menu = [m for m in menu if m.get("owner_id") == str(interaction.user.id)]
        if not menu:
            return await interaction.response.send_message("登録済みのサービスがありません。", ephemeral=True)
        embed = discord.Embed(title="📋 SMMサービス一覧", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_footer(text="SMM自販機")
        for cat in SNS_CATEGORIES:
            items = [m for m in menu if m.get("category") == cat["key"]]
            if not items:
                continue
            lines = [f"`[ID:{m['service_id']}]` {m['name']}  ¥{m['price']}/単価  {m['min_qty']:,}〜{m['max_qty']:,}個" for m in items]
            embed.add_field(name=cat["label"], value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="smm実績チャンネル設定", description="フォロ爆購入ログを送信するチャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機ID", channel="ログを送信するチャンネル")
    async def set_log_channel(self, interaction: discord.Interaction, vm_id: str, channel: discord.TextChannel):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        vending_data[vm_id]["log_channel_id"] = channel.id
        save_vending_data(vending_data)
        await interaction.response.send_message(f"✅ ログチャンネルを {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="smmpaypay検知チャンネル設定", description="PayPayリンク自動検知チャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機ID", channel="PayPayリンクを検知するチャンネル")
    async def set_paypay_detect_channel(self, interaction: discord.Interaction, vm_id: str, channel: discord.TextChannel):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        vending_data[vm_id]["paypay_detect_channel_id"] = channel.id
        save_vending_data(vending_data)
        await interaction.response.send_message(f"✅ PayPay検知チャンネルを {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="smmロール設定", description="フォロ爆購入時に付与するロールを設定します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機ID", role="購入時に付与するロール")
    async def set_purchase_role(self, interaction: discord.Interaction, vm_id: str, role: discord.Role):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        vending_data[vm_id]["purchase_role_id"] = role.id
        save_vending_data(vending_data)
        await interaction.response.send_message(f"✅ 購入時付与ロールを {role.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="smmロール解除", description="フォロ爆購入時のロール付与設定を解除します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機ID")
    async def remove_purchase_role(self, interaction: discord.Interaction, vm_id: str):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)
        vending_data[vm_id].pop("purchase_role_id", None)
        save_vending_data(vending_data)
        await interaction.response.send_message("✅ ロール付与設定を解除しました。", ephemeral=True)

    @app_commands.command(name="smmバランス確認", description="SMMアカウントの残高を確認します")
    @is_allowed()
    async def smm_balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await smm_get_balance()
        embed  = discord.Embed(title="💰 SMMアカウント残高", color=discord.Color.gold(), timestamp=discord.utils.utcnow())
        embed.add_field(name="残高", value=f"```{result.get('balance', '取得失敗')} {result.get('currency', '')}```")
        embed.set_footer(text="SMM自販機")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="smmサービス検索", description="SMMから利用可能なサービスをキーワード検索します")
    @is_allowed()
    @app_commands.describe(keyword="キーワード（例: Instagram Followers）")
    async def smm_search_services(self, interaction: discord.Interaction, keyword: str = ""):
        await interaction.response.defer(ephemeral=True)
        services = await smm_get_services()
        if not services:
            return await interaction.followup.send("❌ 取得失敗。APIキーを確認してください。", ephemeral=True)
        kw       = keyword.lower()
        filtered = [s for s in services if kw in s.get("name", "").lower()] if kw else services
        filtered = filtered[:10]
        embed = discord.Embed(
            title=f"🔍 SMM検索: {keyword or '全件（先頭10件）'}",
            color=discord.Color.blurple(), timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="サービスIDを /smmサービス追加 で登録 | SMM自販機")
        for svc in filtered:
            embed.add_field(
                name=f"[ID:{svc.get('service')}] {svc.get('name', '不明')[:80]}",
                value=f"```最小: {svc.get('min', '-')}  最大: {svc.get('max', '-')}  料金: {svc.get('rate', '-')}```",
                inline=False,
            )
        if not filtered:
            embed.description = "該当するサービスが見つかりませんでした。"
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="smm売上集計", description="フォロ爆自販機の売上・注文統計を表示します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(period="集計期間", vm_id="自販機（省略で全件）")
    @app_commands.choices(period=[
        app_commands.Choice(name="今日",   value="today"),
        app_commands.Choice(name="今週",   value="week"),
        app_commands.Choice(name="今月",   value="month"),
        app_commands.Choice(name="全期間", value="all"),
    ])
    async def sales_summary(self, interaction: discord.Interaction, period: str = "all", vm_id: str = None):
        await interaction.response.defer(ephemeral=True)

        orders = load_json(SMM_ORDER_FILE)
        now    = datetime.datetime.now(JST)

        def in_period(rec):
            if period == "all":
                return True
            created = rec.get("created_at", "")
            if not created:
                return False
            try:
                dt = JST.localize(datetime.datetime.strptime(created, "%Y/%m/%d %H:%M:%S"))
                if period == "today":
                    return dt.date() == now.date()
                elif period == "week":
                    return (now - dt).days < 7
                elif period == "month":
                    return dt.year == now.year and dt.month == now.month
            except:
                return True
            return True

        my_vms = {
            vid for vid, vm in load_vending_data().items()
            if vm.get("owner_id") == str(interaction.user.id)
        }
        if vm_id:
            my_vms = {vm_id} if vm_id in my_vms else set()

        target = sorted(
            [r for r in orders.values() if r.get("vm_id") in my_vms and in_period(r)],
            key=lambda r: r.get("created_at", ""), reverse=True,
        )

        if not target:
            return await interaction.followup.send("📊 該当する注文データがありません。", ephemeral=True)

        period_label  = {"today": "今日", "week": "今週", "month": "今月", "all": "全期間"}.get(period, period)
        total_revenue = sum(r.get("total_price", 0) for r in target)
        total_qty     = sum(r.get("quantity", 0)    for r in target)
        total_orders  = len(target)
        avg_price     = total_revenue / total_orders if total_orders else 0

        service_revenue: dict = {}
        service_qty: dict     = {}
        for rec in target:
            name = rec.get("service_name", "不明")
            service_revenue[name] = service_revenue.get(name, 0) + rec.get("total_price", 0)
            service_qty[name]     = service_qty.get(name, 0)     + rec.get("quantity", 0)

        hour_revenue = defaultdict(int)
        for rec in target:
            try:
                h = datetime.datetime.strptime(rec["created_at"], "%Y/%m/%d %H:%M:%S").hour
                hour_revenue[h] += rec.get("total_price", 0)
            except:
                pass
        peak_hour = max(hour_revenue, key=hour_revenue.get) if hour_revenue else None

        day_revenue = defaultdict(int)
        for rec in target:
            try:
                d = rec["created_at"][:10]
                day_revenue[d] += rec.get("total_price", 0)
            except:
                pass
        recent_days = sorted(day_revenue.items(), reverse=True)[:5]

        view = SalesPagingView(
            target=target, period_label=period_label,
            total_revenue=total_revenue, total_qty=total_qty,
            total_orders=total_orders, avg_price=avg_price,
            peak_hour=peak_hour, service_revenue=service_revenue,
            service_qty=service_qty, recent_days=recent_days,
            hour_revenue=hour_revenue,
        )
        view.refresh_buttons()
        await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)

    @app_commands.command(name="smm_paypay登録", description="SMM自販機用PayPayアカウントを登録します")
    @is_allowed()
    @app_commands.describe(phone="電話番号（090...）", password="パスワード")
    async def paypay_register(self, interaction: discord.Interaction, phone: str, password: str):
        await interaction.response.defer(ephemeral=True)
        import uuid
        set_uuid = str(uuid.uuid4())
        result   = await paypayu.login(phone, password, set_uuid)

        if result.get("response_type") == "ErrorResponse":
            info    = result.get("result_info", {})
            code    = info.get("result_code", "")
            msg     = info.get("result_msg", "")
            ec      = result.get("error_code", "")
            desc    = f"```\ncode: {code}\nmsg : {msg}\nec  : {ec}\n```"
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ PayPayログインエラー", description=desc, color=discord.Color.red()),
                ephemeral=True,
            )

        if "otp_reference_id" in result:
            pending = load_json(PENDING_FILE)
            pending[str(interaction.user.id)] = {
                "phone": phone, "password": password, "uuid": set_uuid,
                "otpid": result["otp_reference_id"],
                "otp_pre": result.get("otp_prefix", "")
            }
            save_json(PENDING_FILE, pending)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📱 SMS認証コードを入力してください",
                    description="SMSに届いた**4桁の認証コード**を `/smm_paypay認証 コード` で入力してください。",
                    color=discord.Color.blue(),
                ),
                ephemeral=True,
            )
        elif "access_token" in result:
            data = load_paypay_data()
            data[str(interaction.user.id)] = {"phone": phone, "password": password, "uuid": set_uuid}
            save_json(PAYPAY_FILE, data)
            await interaction.followup.send(
                embed=discord.Embed(title="✅ PayPay登録完了", description="ログイン成功しました。", color=discord.Color.green()),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(title="⚠️ 予期しない応答", description=f"```{str(result)[:300]}```", color=discord.Color.orange()),
                ephemeral=True,
            )

    @app_commands.command(name="smm_paypay認証", description="SMSに届いた認証コードを入力します")
    @is_allowed()
    @app_commands.describe(code="SMSに届いた4桁のコード")
    async def paypay_otp(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)
        pending = load_json(PENDING_FILE)
        info    = pending.get(str(interaction.user.id))
        if not info:
            return await interaction.followup.send(
                "❌ 認証待ちデータがありません。先に `/smm_paypay登録` を実行してください。", ephemeral=True
            )
        result = await paypayu.login_otp(info["uuid"], code, info["otpid"], info["otp_pre"])
        if result == "OK":
            data = load_paypay_data()
            data[str(interaction.user.id)] = {"phone": info["phone"], "password": info["password"], "uuid": info["uuid"]}
            save_json(PAYPAY_FILE, data)
            del pending[str(interaction.user.id)]
            save_json(PENDING_FILE, pending)
            await interaction.followup.send(
                embed=discord.Embed(title="✅ PayPay登録完了", description="認証成功！アカウントを登録しました。", color=discord.Color.green()),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(title="❌ 認証エラー", description="コードが正しくないか期限切れです。\n`/smm_paypay登録` からやり直してください。", color=discord.Color.red()),
                ephemeral=True,
            )

    @app_commands.command(name="smm_paypay確認", description="登録済みのPayPayアカウントを確認します")
    @is_allowed()
    async def paypay_check(self, interaction: discord.Interaction):
        info = load_paypay_data().get(str(interaction.user.id))
        if not info:
            return await interaction.response.send_message("❌ PayPayアカウントが登録されていません。`/smm_paypay登録` で登録してください。", ephemeral=True)
        embed = discord.Embed(title="✅ PayPay登録情報", color=discord.Color.green())
        embed.add_field(name="電話番号", value=f"```{info['phone']}```", inline=True)
        embed.set_footer(text="SMM自販機")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="smm自動メニュー追加", description="SMMサービス一覧から利益マージンを付けて既存の自販機にまとめて追加します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(
        vm_id="追加先の自販機ID",
        margin_rate="利益マージン倍率（例: 3.0 = 原価の3倍）",
        keyword="絞り込みキーワード（空白=全テンプレート）",
    )
    async def smm_auto_add_menu(
        self, interaction: discord.Interaction,
        vm_id: str,
        margin_rate: float = 3.0,
        keyword: str = "",
    ):
        vending_data = load_vending_data()
        vm = vending_data.get(vm_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("❌ 指定された自販機が見つかりません。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        services = await smm_get_services()
        if not services:
            return await interaction.followup.send("❌ SMMサービスの取得に失敗しました。APIキーを確認してください。", ephemeral=True)

        menu    = load_smm_menu()
        added   = []
        skipped = []
        kw_filter = keyword.lower()

        for tmpl in DEFAULT_MENU_TEMPLATES:
            if kw_filter and kw_filter not in tmpl["keyword"] and kw_filter not in tmpl["name"].lower():
                continue
            svc = _match_service(services, tmpl["keyword"])
            if not svc:
                skipped.append(f"❓ {tmpl['name']}（キーワード未ヒット）")
                continue
            service_id = int(svc.get("service", 0))
            if any(m["service_id"] == service_id and m.get("vm_id") == vm_id for m in menu):
                skipped.append(f"⚠️ {tmpl['name']}（ID:{service_id} 既登録）")
                continue
            actual_margin = tmpl["margin_rate"] * (margin_rate / 3.0)
            sell_price    = _calc_price_jpy(svc.get("rate", "0"), actual_margin)
            if sell_price <= 0:
                skipped.append(f"⚠️ {tmpl['name']}（価格計算失敗）")
                continue
            menu.append({
                "vm_id":       vm_id,
                "owner_id":    str(interaction.user.id),
                "category":    tmpl["category"],
                "service_id":  service_id,
                "name":        tmpl["name"],
                "price":       sell_price,
                "min_qty":     int(max(tmpl["min_qty"], int(svc.get("min", tmpl["min_qty"])))),
                "max_qty":     int(min(tmpl["max_qty"], int(svc.get("max", tmpl["max_qty"])))),
                "cost_rate":   svc.get("rate", "0"),
                "margin_rate": actual_margin,
            })
            added.append(f"✅ {tmpl['name']}（ID:{service_id}  ¥{sell_price}/件）")

        save_smm_menu(menu)

        embed = discord.Embed(
            title=f"📦 自動メニュー追加結果 — {vm['name']}",
            color=discord.Color.green() if added else discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        if added:
            embed.add_field(name=f"追加成功 {len(added)}件", value="\n".join(added)[:1024], inline=False)
        if skipped:
            embed.add_field(name=f"スキップ {len(skipped)}件", value="\n".join(skipped)[:1024], inline=False)
        embed.add_field(
            name="反映方法",
            value="`/フォロ爆パネル設置` でパネルを再設置すると反映されます。",
            inline=False,
        )
        embed.set_footer(text=f"マージン倍率: {margin_rate}x | SMM自販機")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="smm利益確認", description="登録済みサービスの原価・販売価格・利益率を一覧表示します")
    @is_allowed()
    @app_commands.autocomplete(vm_id=_vm_id_ac)
    @app_commands.describe(vm_id="自販機（省略で全件）")
    async def smm_profit_check(self, interaction: discord.Interaction, vm_id: str = None):
        menu = load_smm_menu()
        if vm_id:
            menu = [m for m in menu if m.get("vm_id") == vm_id]
        menu = [m for m in menu if m.get("owner_id") == str(interaction.user.id)]
        if not menu:
            return await interaction.response.send_message("登録済みのサービスがありません。", ephemeral=True)

        embed = discord.Embed(
            title="💹 原価・利益確認",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="※原価はSMMのUSD/1000件レートをJPY換算 | SMM自販機")

        for m in menu:
            cost_rate  = m.get("cost_rate")
            sell_price = m.get("price", 0)
            margin     = m.get("margin_rate", 0)
            if cost_rate:
                cost_jpy = round(float(cost_rate) * SMM_USD_TO_JPY / 1000, 4)
                profit   = round(sell_price - cost_jpy, 4)
                margin_pct = round((profit / sell_price * 100) if sell_price else 0, 1)
                value = (
                    f"原価: ¥{cost_jpy}/件  →  販売: ¥{sell_price}/件\n"
                    f"利益: ¥{profit}/件  利益率: {margin_pct}%  倍率: {round(margin, 2)}x"
                )
            else:
                value = f"販売: ¥{sell_price}/件（原価データなし）"
            embed.add_field(
                name=f"[ID:{m['service_id']}] {m['name']}",
                value=f"```{value}```",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(SmmVendingCog(bot))
