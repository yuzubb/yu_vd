import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta

import paypayu
from utils import is_owner, is_allowed, OWNER_ID

JST = timezone(timedelta(hours=9))

SALES_FILE      = "data/sales.json"
PAYPAY_DATA_FILE = "data/paypay_data.json"
PAYOUT_FILE     = "data/payouts.json"       # 送金申請履歴

REVENUE_RATE    = 0.7   # 購入者への還元率 70%
MIN_PAYOUT      = 500   # 送金申請の最低金額（円）


# ════════════════════════════════════════════════════════════
#  JSON ユーティリティ
# ════════════════════════════════════════════════════════════

def load_json(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ════════════════════════════════════════════════════════════
#  送金申請ボタン View
# ════════════════════════════════════════════════════════════

class PayoutRequestView(discord.ui.View):
    """送金申請フォームを開くボタン"""

    def __init__(self, user_id: int, payout_amount: int):
        super().__init__(timeout=300)
        self.user_id      = user_id
        self.payout_amount = payout_amount

    @discord.ui.button(label="📤 PayPayリンクで送金申請", style=discord.ButtonStyle.green, custom_id="payout_request_btn")
    async def request_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("あなたは使用できません。", ephemeral=True)
            return
        await interaction.response.send_modal(
            PayoutModal(payout_amount=self.payout_amount)
        )


class PayoutModal(discord.ui.Modal, title="送金申請"):
    paypay_link = discord.ui.TextInput(
        label="PayPayリンク（受け取り用）",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True
    )

    def __init__(self, payout_amount: int):
        super().__init__()
        self.payout_amount = payout_amount

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = self.paypay_link.value.strip()

        # リンク検証
        info = await asyncio.to_thread(paypayu.check_link, link)
        if not info:
            await interaction.followup.send("❌ PayPayリンクの確認に失敗しました。リンクを確認してください。", ephemeral=True)
            return

        amount_in_link = (
            info.get("payload", {})
                .get("pendingP2PInfo", {})
                .get("amount", 0)
        )

        if amount_in_link < self.payout_amount:
            await interaction.followup.send(
                f"❌ リンクの金額が不足しています。\n"
                f"必要金額: **{self.payout_amount}円** / リンク金額: **{amount_in_link}円**",
                ephemeral=True
            )
            return

        # 申請を保存
        payouts = load_json(PAYOUT_FILE)
        uid = str(interaction.user.id)
        if uid not in payouts:
            payouts[uid] = []

        now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        payouts[uid].append({
            "amount":     self.payout_amount,
            "link":       link,
            "status":     "pending",  # pending / approved / rejected
            "requested_at": now_str
        })
        save_json(PAYOUT_FILE, payouts)

        # オーナーにDM通知
        try:
            owner = await interaction.client.fetch_user(OWNER_ID)
            owner_dm = await owner.create_dm()

            embed = discord.Embed(
                title="💸 送金申請が届きました",
                color=discord.Color.gold(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="申請者",   value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="金額",     value=f"**{self.payout_amount}円**", inline=True)
            embed.add_field(name="申請日時", value=now_str, inline=True)
            embed.add_field(name="PayPayリンク", value=link, inline=False)
            embed.set_footer(text="✅ 承認する場合は /送金承認 コマンドを使用してください")

            await owner_dm.send(embed=embed)
        except Exception as e:
            print(f"[WARN] オーナーへのDM送信失敗: {e}")

        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ 送金申請を送りました",
                description=f"**{self.payout_amount}円** の送金申請をBOT作成者に送信しました。\n承認され次第、PayPayで受け取れます。",
                color=discord.Color.green()
            ),
            ephemeral=True
        )


# ════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════

class SalesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ────────────────────────────────────────────────────────
    #  /売上確認  （ライセンス保持者が自分の鯖の売上を見る）
    # ────────────────────────────────────────────────────────
    @app_commands.command(
        name="売上確認",
        description="あなたのサーバーの売上と受け取り可能額を表示します"
    )
    @is_allowed()
    async def check_sales(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sales = load_json(SALES_FILE)
        uid   = str(interaction.user.id)

        my_sales   = sales.get("users", {}).get(uid, 0)          # 自分の売上合計
        total_sales = sales.get("total", 0)                       # Bot全体の売上

        payout_amount = int(my_sales * REVENUE_RATE)             # 70%
        can_apply     = payout_amount >= MIN_PAYOUT

        # 申請済みの履歴
        payouts = load_json(PAYOUT_FILE)
        my_payouts = payouts.get(uid, [])
        pending_total = sum(p["amount"] for p in my_payouts if p["status"] == "pending")
        approved_total = sum(p["amount"] for p in my_payouts if p["status"] == "approved")

        color = discord.Color.green() if can_apply else discord.Color.blurple()
        embed = discord.Embed(
            title="📊 売上確認",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="💰 あなたの売上",
            value=(
                f"```yaml\n"
                f"総売上       : {my_sales:,} 円\n"
                f"受取額 (70%) : {payout_amount:,} 円\n"
                f"申請済み     : {pending_total:,} 円 (審査中)\n"
                f"受取済み     : {approved_total:,} 円\n"
                f"```"
            ),
            inline=False
        )
        embed.add_field(
            name="📈 Bot全体の売上",
            value=f"```{total_sales:,} 円```",
            inline=False
        )

        if can_apply:
            embed.add_field(
                name="✅ 送金申請できます",
                value=f"**{payout_amount:,}円** の送金申請が可能です。\n下のボタンから申請してください。",
                inline=False
            )
        else:
            remaining = MIN_PAYOUT - payout_amount
            embed.add_field(
                name="⏳ 申請条件 未達成",
                value=f"あと **{remaining:,}円分** の売上で申請可能になります。\n（最低申請額: {MIN_PAYOUT:,}円）",
                inline=False
            )

        embed.set_footer(text=f"還元率: {int(REVENUE_RATE*100)}%  |  最低申請額: {MIN_PAYOUT}円")

        # 申請ボタン
        if can_apply and pending_total == 0:
            view = PayoutRequestView(
                user_id=interaction.user.id,
                payout_amount=payout_amount
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            if pending_total > 0:
                embed.set_footer(text="⚠️ 審査中の申請があります。承認をお待ちください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ────────────────────────────────────────────────────────
    #  /売上一覧  （オーナーが全ユーザーの売上を確認）
    # ────────────────────────────────────────────────────────
    @app_commands.command(
        name="売上一覧",
        description="全ユーザーの売上と70%分を一覧表示します（オーナー専用）"
    )
    @is_owner()
    async def sales_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sales = load_json(SALES_FILE)
        users_data = sales.get("users", {})
        total_sales = sales.get("total", 0)

        if not users_data:
            await interaction.followup.send("まだ売上データがありません。", ephemeral=True)
            return

        # 売上順にソート
        sorted_users = sorted(users_data.items(), key=lambda x: x[1], reverse=True)

        lines = [f"{'ユーザーID':<20} {'売上':>8} {'70%':>7}"]
        lines.append("─" * 42)

        for uid, amount in sorted_users:
            payout = int(amount * REVENUE_RATE)
            # ユーザー名取得を試みる
            try:
                user = self.bot.get_user(int(uid)) or await self.bot.fetch_user(int(uid))
                name = user.name[:14]
            except Exception:
                name = uid[:14]
            lines.append(f"{name:<20} {amount:>7,}円 {payout:>6,}円")

        lines.append("─" * 42)
        lines.append(f"{'合計':<20} {total_sales:>7,}円 {int(total_sales * REVENUE_RATE):>6,}円")

        # 申請状況も追加
        payouts = load_json(PAYOUT_FILE)
        pending_list = []
        for uid, plist in payouts.items():
            for p in plist:
                if p["status"] == "pending":
                    try:
                        user = self.bot.get_user(int(uid)) or await self.bot.fetch_user(int(uid))
                        uname = user.name
                    except Exception:
                        uname = uid
                    pending_list.append(f"  {uname}: {p['amount']:,}円 ({p['requested_at']})")

        embed = discord.Embed(
            title="📋 売上一覧",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        if pending_list:
            embed.add_field(
                name="⏳ 送金申請中",
                value="\n".join(pending_list[:10]),
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ────────────────────────────────────────────────────────
    #  /送金承認  （オーナーが申請を承認してPayPayを受け取る）
    # ────────────────────────────────────────────────────────
    @app_commands.command(
        name="送金承認",
        description="送金申請を承認してPayPayリンクを受け取ります（オーナー専用）"
    )
    @app_commands.describe(user="承認するユーザー")
    @is_owner()
    async def approve_payout(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)

        payouts = load_json(PAYOUT_FILE)
        uid = str(user.id)
        user_payouts = payouts.get(uid, [])

        # pending のものを取得
        pending = [p for p in user_payouts if p["status"] == "pending"]
        if not pending:
            await interaction.followup.send(f"❌ {user.mention} に審査中の申請はありません。", ephemeral=True)
            return

        target = pending[0]   # 最古の申請から処理

        # PayPayリンクを受け取る
        paypay_data = load_json(PAYPAY_DATA_FILE)
        owner_cred  = paypay_data.get(str(OWNER_ID))
        if not owner_cred:
            await interaction.followup.send("❌ オーナーのPayPayが登録されていません。`/paypayログイン` で登録してください。", ephemeral=True)
            return

        link = target["link"]
        result = await asyncio.to_thread(
            paypayu.link_rev,
            link,
            owner_cred["phone"],
            owner_cred["password"],
            owner_cred["uuid"]
        )

        if result is True:
            # ステータス更新
            for p in payouts[uid]:
                if p["link"] == link and p["status"] == "pending":
                    p["status"] = "approved"
                    p["approved_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                    break
            save_json(PAYOUT_FILE, payouts)

            # 申請者にDM通知
            try:
                dm = await user.create_dm()
                await dm.send(embed=discord.Embed(
                    title="✅ 送金申請が承認されました",
                    description=f"**{target['amount']:,}円** の送金申請が承認され、PayPayリンクが受け取られました。",
                    color=discord.Color.green()
                ))
            except Exception:
                pass

            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ 承認完了",
                    description=f"{user.mention} の **{target['amount']:,}円** の申請を承認し、PayPayリンクを受け取りました。",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )

        elif result == "LOGINERR":
            await interaction.followup.send("❌ PayPayログインに失敗しました。`/paypayログイン` で再登録してください。", ephemeral=True)
        else:
            await interaction.followup.send("❌ PayPayリンクの受け取りに失敗しました。リンクの有効期限が切れている可能性があります。", ephemeral=True)

    # ────────────────────────────────────────────────────────
    #  /売上リセット  （オーナーが特定ユーザーの売上をリセット）
    # ────────────────────────────────────────────────────────
    @app_commands.command(
        name="売上リセット",
        description="指定ユーザーの売上をリセットします（オーナー専用）"
    )
    @app_commands.describe(user="リセットするユーザー")
    @is_owner()
    async def reset_sales(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)

        sales = load_json(SALES_FILE)
        uid   = str(user.id)

        before = sales.get("users", {}).get(uid, 0)
        if before == 0:
            await interaction.followup.send(f"❌ {user.mention} の売上データがありません。", ephemeral=True)
            return

        sales["users"][uid] = 0
        sales["total"]      = max(0, sales.get("total", 0) - before)
        save_json(SALES_FILE, sales)

        await interaction.followup.send(
            embed=discord.Embed(
                title="🔄 売上リセット完了",
                description=f"{user.mention} の売上 **{before:,}円** をリセットしました。",
                color=discord.Color.orange()
            ),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SalesCog(bot))
