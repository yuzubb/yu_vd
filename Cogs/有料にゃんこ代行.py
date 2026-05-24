import sys
import os

# 親ディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
import importlib.util
import json
from utils import is_allowed, is_owner, OWNER_ID

# ==================== PayPay連携 ====================
PAYPAY_AVAILABLE = False
load_paypay_data = None
PAYPAY_LINK_PATTERN = None
paypayu = None

try:
    import paypayu
    
    # Cogs/paypay.py を直接読み込む
    paypay_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Cogs", "paypay.py")
    
    if os.path.exists(paypay_path):
        spec = importlib.util.spec_from_file_location("paypay_cog", paypay_path)
        paypay_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(paypay_module)
        
        load_paypay_data = paypay_module.load_paypay_data
        PAYPAY_LINK_PATTERN = paypay_module.PAYPAY_LINK_PATTERN
        PAYPAY_AVAILABLE = True
        print("[有料代行] PayPay連携を正常に読み込みました")
    else:
        print("[有料代行] Cogs/paypay.py が見つかりません")
        
except ImportError as e:
    print(f"[有料代行] paypayu.py が見つかりません: {e}")
except Exception as e:
    print(f"[有料代行] PayPay連携無効: {e}")

# ==================== Savedataedit 対応 ====================
try:
    from Savedataedit import SaveEditor, load_from_transfer
    SAVE_EDITOR_AVAILABLE = True
    print("[有料代行] Savedataedit.SaveEditor を正常に読み込みました")
except ImportError as e:
    SaveEditor = None
    load_from_transfer = None
    SAVE_EDITOR_AVAILABLE = False
    print(f"[有料代行] Savedataedit インポート失敗: {e}")

# ====================== 価格設定 ======================
ITEM_PRICES: dict[str, int] = {
    "xp": 10, "np": 10, "catfood": 10, "battle_items": 10, "vitamins": 10,
    "base_materials": 10, "catseyes": 10, "talent_orbs": 10,
    "rare": 10, "platinum": 10, "legend": 10, "event_ticket": 10, "lead": 10,
    "sub_medals": 10, "unlock_all": 10, "remove_error": 10, "levels_max": 10,
    "forms_max": 10, "talents_max": 10, "main_clear": 10,
    "zombie_clear": 10, "legend_clear": 10, "uncanny_clear": 10, "legend_quest": 10,
    "ex_clear": 10, "zero_clear": 10, "aku_clear": 10, "event_clear": 10,
    "gamatoto_max": 10, "gamatoto_hlp": 10, "ototo_max": 10, "shrine_max": 10,
    "playtime": 10, "gold_member": 10, "deck_slots": 10, "medals": 10,
    "all_medals": 10, "enemy_enc": 10, "rank_rewards": 10,
    "tutorial_skip": 10, "dojo_max": 10, "missions_clear": 10, "weekly_missions": 10,
}

# 選択肢（価格付き表示）
G1_OPTIONS = [
    ("xp", f"XP MAX ¥{ITEM_PRICES['xp']}"),
    ("np", f"NP MAX ¥{ITEM_PRICES['np']}"),
    ("catfood", f"猫缶 MAX ¥{ITEM_PRICES['catfood']}"),
    ("battle_items", f"バトルアイテム全種 MAX ¥{ITEM_PRICES['battle_items']}"),
    ("vitamins", f"ネコビタン全種 MAX ¥{ITEM_PRICES['vitamins']}"),
    ("base_materials", f"城素材全種 MAX ¥{ITEM_PRICES['base_materials']}"),
    ("catseyes", f"キャッツアイ全種 MAX ¥{ITEM_PRICES['catseyes']}"),
    ("talent_orbs", f"本能玉全種 MAX ¥{ITEM_PRICES['talent_orbs']}"),
    ("rare", f"にゃんチケ&レアチケ MAX ¥{ITEM_PRICES['rare']}"),
    ("platinum", f"プラチナチケ MAX ¥{ITEM_PRICES['platinum']}"),
    ("legend", f"レジェチケ MAX ¥{ITEM_PRICES['legend']}"),
    ("event_ticket", f"イベントチケ&福チケ MAX ¥{ITEM_PRICES['event_ticket']}"),
    ("lead", f"リーダーシップ MAX ¥{ITEM_PRICES['lead']}"),
    ("sub_medals", f"地底迷宮メダル全種 MAX ¥{ITEM_PRICES['sub_medals']}")
]

G2_OPTIONS = [
    ("unlock_all", f"全キャラ開放 ¥{ITEM_PRICES['unlock_all']}"),
    ("remove_error", f"エラーキャラ削除 ¥{ITEM_PRICES['remove_error']}"),
    ("levels_max", f"全キャラ/施設 LvMAX ¥{ITEM_PRICES['levels_max']}"),
    ("forms_max", f"全キャラ最高形態 ¥{ITEM_PRICES['forms_max']}"),
    ("talents_max", f"全キャラ本能全開放 ¥{ITEM_PRICES['talents_max']}")
]

G3_OPTIONS = [
    ("main_clear", f"メインステージ全クリア+金お宝 ¥{ITEM_PRICES['main_clear']}"),
    ("zombie_clear", f"メインゾンビステージ全クリア ¥{ITEM_PRICES['zombie_clear']}"),
    ("legend_clear", f"レジェンド全クリア ¥{ITEM_PRICES['legend_clear']}"),
    ("uncanny_clear", f"旧レジェンド全クリア ¥{ITEM_PRICES['uncanny_clear']}"),
    ("legend_quest", f"レジェンドクエスト全クリア ¥{ITEM_PRICES['legend_quest']}"),
    ("ex_clear", f"真レジェンド全クリア ¥{ITEM_PRICES['ex_clear']}"),
    ("zero_clear", f"零レジェンド全クリア ¥{ITEM_PRICES['zero_clear']}"),
    ("aku_clear", f"魔界編全クリア ¥{ITEM_PRICES['aku_clear']}"),
    ("event_clear", f"イベントステージ全クリア ¥{ITEM_PRICES['event_clear']}")
]

G4_OPTIONS = [
    ("gamatoto_max", f"ガマトト LvMAX ¥{ITEM_PRICES['gamatoto_max']}"),
    ("gamatoto_hlp", f"ガマトト助手 全員レジェンド化 ¥{ITEM_PRICES['gamatoto_hlp']}"),
    ("ototo_max", f"オトート全城強化 LvMAX ¥{ITEM_PRICES['ototo_max']}"),
    ("shrine_max", f"にゃんこ神社 LvMAX ¥{ITEM_PRICES['shrine_max']}"),
    ("playtime", f"プレイ時間カンスト ¥{ITEM_PRICES['playtime']}"),
    ("gold_member", f"ゴールド会員化 ¥{ITEM_PRICES['gold_member']}"),
    ("deck_slots", f"編成スロット数最大拡張 ¥{ITEM_PRICES['deck_slots']}"),
    ("medals", f"にゃんこメダル全開放 ¥{ITEM_PRICES['medals']}"),
    ("all_medals", f"全メダル獲得 ¥{ITEM_PRICES['all_medals']}"),
    ("enemy_enc", f"敵キャラ図鑑全開放 ¥{ITEM_PRICES['enemy_enc']}"),
    ("rank_rewards", f"ユーザーランク報酬全受取 ¥{ITEM_PRICES['rank_rewards']}"),
    ("tutorial_skip", f"チュートリアルスキップ ¥{ITEM_PRICES['tutorial_skip']}"),
    ("dojo_max", f"道場スコア MAX ¥{ITEM_PRICES['dojo_max']}"),
    ("missions_clear", f"全ミッションクリア ¥{ITEM_PRICES['missions_clear']}"),
    ("weekly_missions", f"ウィークリーミッション全クリア ¥{ITEM_PRICES['weekly_missions']}")
]

# 表示名（価格なし、金額確認画面用）
ALL_OPTIONS = {val: label.split(' ¥')[0] for val, label in G1_OPTIONS + G2_OPTIONS + G3_OPTIONS + G4_OPTIONS}

def calc_total(selected: list[str]) -> int:
    prices = _load_prices() if os.path.exists(PRICES_FILE) else ITEM_PRICES
    return sum(prices.get(k, ITEM_PRICES.get(k, 0)) for k in selected)


# ====================== UI ======================
class DaikoMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="ログインして注文する", 
        style=discord.ButtonStyle.success, 
        emoji="🛒",
        custom_id="daiko_paid_login_button:v3"
    )
    async def login(self, interaction: discord.Interaction, button: ui.Button):
        # 直接モーダルを送信、エラー時は新しくメッセージを送信
        try:
            await interaction.response.send_modal(DaikoLoginModal())
        except (discord.errors.NotFound, discord.errors.InteractionResponded) as e:
            print(f"ログインボタンエラー: {e}")
            # 期限切れの場合は新しくメッセージを送信
            embed = discord.Embed(
                title="にゃんこ大戦争 代行自販機",
                description="ボタンの有効期限が切れました。もう一度 `/にゃんこ代行` コマンドを実行してください。",
                color=0xF5A623
            )
            # フォローアップで送信を試みる
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                # フォローアップもダメなら元のレスポンスで送信
                await interaction.response.send_message(embed=embed, ephemeral=True)


class DaikoLoginModal(ui.Modal, title="アカウントログイン"):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ui.TextInput(label="引き継ぎコード", placeholder="引き継ぎコードを入力してください", style=discord.TextStyle.short))
        self.add_item(ui.TextInput(label="認証コード", placeholder="4桁の認証コード", min_length=4, max_length=4, style=discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not SAVE_EDITOR_AVAILABLE:
            return await interaction.followup.send("SaveEditorが利用できません", ephemeral=True)

        try:
            editor = await load_from_transfer(self.children[0].value, self.children[1].value, "jp")
            embed = discord.Embed(
                title="代行内容を選択",
                description="カテゴリから項目を選んでください",
                color=0x5865F2
            )
            await interaction.followup.send(embed=embed, view=DaikoPaidSelectView(editor), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"ログイン失敗: {str(e)}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"モーダルエラー: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("エラーが発生しました。もう一度お試しください。", ephemeral=True)
            else:
                await interaction.followup.send("エラーが発生しました。もう一度お試しください。", ephemeral=True)
        except:
            pass

class DaikoPaidSelectView(ui.View):
    def __init__(self, editor):
        super().__init__(timeout=300)
        self.editor = editor
        self.sel1 = []
        self.sel2 = []
        self.sel3 = []
        self.sel4 = []

        self.add_item(_GroupSelect(self, G1_OPTIONS, "アイテム系を選択", 0))
        self.add_item(_GroupSelect(self, G2_OPTIONS, "キャラ系を選択", 1))
        self.add_item(_GroupSelect(self, G3_OPTIONS, "ステージ系を選択", 2))
        self.add_item(_GroupSelect(self, G4_OPTIONS, "施設・その他を選択", 3))

        btn = ui.Button(label="確定して金額確認", style=discord.ButtonStyle.success, emoji="✅", row=4)
        btn.callback = self._confirm
        self.add_item(btn)

    def _all_selected(self):
        return self.sel1 + self.sel2 + self.sel3 + self.sel4

    async def _confirm(self, interaction: discord.Interaction):
        selected = self._all_selected()
        if not selected:
            return await interaction.response.send_message("何も選択されていません。", ephemeral=True)

        total = calc_total(selected)
        lines = "\n".join(f"・{ALL_OPTIONS.get(k,k)} ¥{ITEM_PRICES.get(k,0)}" for k in selected)
        embed = discord.Embed(
            title="金額確認",
            description=f"{lines}\n\n**合計 ¥{total}**",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, view=_PayConfirmView(self.editor, selected, total), ephemeral=True)


class _GroupSelect(ui.Select):
    def __init__(self, parent_view, opts, placeholder, row):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=label, value=val) for val, label in opts]
        super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options, row=row, custom_id=f"group_select_{placeholder}_{row}")

    async def callback(self, interaction: discord.Interaction):
        ph = self.placeholder
        if "アイテム" in ph:
            self.parent_view.sel1 = self.values
        elif "キャラ" in ph:
            self.parent_view.sel2 = self.values
        elif "ステージ" in ph:
            self.parent_view.sel3 = self.values
        else:
            self.parent_view.sel4 = self.values
        try:
            await interaction.response.edit_message()
        except:
            pass


class _PayConfirmView(ui.View):
    def __init__(self, editor, selected, total):
        super().__init__(timeout=180)
        self.editor = editor
        self.selected = selected
        self.total = total
        btn = ui.Button(label=f"¥{total} PayPayで支払う", style=discord.ButtonStyle.primary, emoji="💳", custom_id="paypay_button")
        btn.callback = self.open_modal
        self.add_item(btn)

    async def open_modal(self, interaction: discord.Interaction):
        # ライセンス保持者は無料
        actual_total = 0 if _has_license(interaction.user.id) else self.total
        await interaction.response.send_modal(PayPayLinkModal(self.editor, self.selected, actual_total, interaction))


class PayPayLinkModal(ui.Modal, title="PayPay送金リンク入力"):
    link = ui.TextInput(
        label="PayPay送金リンク",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True,
        style=discord.TextStyle.short
    )
    link_pass = ui.TextInput(
        label="パスワード（ある場合のみ）",
        required=False,
        placeholder="リンクにパスワードが設定されている場合のみ入力",
        style=discord.TextStyle.short
    )

    def __init__(self, editor, selected, total, original_interaction):
        super().__init__(timeout=180)
        self.editor = editor
        self.selected = selected
        self.total = total
        self.original_interaction = original_interaction

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not PAYPAY_AVAILABLE:
            await interaction.followup.send(
                "PayPay自動連携が設定されていません。管理者が手動で確認後、代行を実行します。",
                ephemeral=True
            )
            if interaction.client.application.owner:
                owner = interaction.client.application.owner
                embed = discord.Embed(
                    title="新規注文",
                    description=f"ユーザー: {interaction.user.mention}\n金額: ¥{self.total}\nPayPayリンク: {self.link.value}",
                    color=discord.Color.orange()
                )
                await owner.send(embed=embed)
            return

        link_url = self.link.value
        if PAYPAY_LINK_PATTERN and not PAYPAY_LINK_PATTERN.match(link_url):
            return await interaction.followup.send(
                "正しいPayPayリンクの形式ではありません。\n例: https://pay.paypay.ne.jp/XXXXXX",
                ephemeral=True
            )

        link_info = await paypayu.check_link(link_url)
        if not link_info:
            return await interaction.followup.send(
                "リンクの確認に失敗しました。リンクが無効か期限切れの可能性があります。",
                ephemeral=True
            )

        payload = link_info.get("payload", {})
        p2p_info = payload.get("pendingP2PInfo", {})
        link_amount = p2p_info.get("amount", 0)

        if link_amount != self.total:
            return await interaction.followup.send(
                f"金額が一致しません。\n請求金額: ¥{self.total}\n送金金額: ¥{link_amount}\n\n正しい金額で送金してください。",
                ephemeral=True
            )

        is_passcode = p2p_info.get("isSetPasscode", False)
        link_password = self.link_pass.value if self.link_pass.value else None

        if is_passcode and not link_password:
            return await interaction.followup.send(
                "このリンクにはパスワードが設定されています。パスワードを入力してください。",
                ephemeral=True
            )

        # ========== 修正箇所: 動的にオーナーIDを取得 ==========
        # Botのオーナー情報を取得
        app_info = await interaction.client.application_info()
        owner = app_info.owner
        OWNER_ID = str(owner.id)
        
        paypay_data_path = "paypay_data.json"
        paypay_info = {}
        
        if os.path.exists(paypay_data_path):
            try:
                with open(paypay_data_path, "r", encoding="utf-8") as f:
                    all_paypay = json.load(f)
                    # 文字列キーで検索
                    paypay_info = all_paypay.get(OWNER_ID, {})
                    # 見つからなければ数値キーでも試す
                    if not paypay_info:
                        try:
                            owner_id_int = int(OWNER_ID)
                            paypay_info = all_paypay.get(owner_id_int, {})
                        except:
                            pass
                    # デバッグ用: 保存されているキーを表示
                    if not paypay_info:
                        print(f"[DEBUG] paypay_data.json のキー: {list(all_paypay.keys())}")
                        print(f"[DEBUG] 探しているオーナーID: {OWNER_ID}")
            except Exception as e:
                print(f"PayPayデータ読み込みエラー: {e}")

        if not paypay_info:
            return await interaction.followup.send(
                f"Bot管理者 ({owner.display_name}) のPayPayアカウントが登録されていません。\n管理者が `/paypayログイン` を実行してください。",
                ephemeral=True
            )
        # ====================================================

        phone = paypay_info.get("phone")
        password = paypay_info.get("password")
        user_uuid = paypay_info.get("uuid")

        result = await paypayu.link_rev(link_url, phone, password, user_uuid, link_password)

        if result is True:
            await interaction.followup.send(
                "PayPayでのお支払いを確認しました。代行を実行しています...",
                ephemeral=True
            )
            actions = await _execute_daiko(self.editor, self.selected)
            await _send_daiko_result(interaction, self.editor, actions, self.total)
        elif result == "LOGINERR":
            await interaction.followup.send(
                "PayPayへのログインに失敗しました。管理者に連絡してください。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "送金の受け取りに失敗しました。リンクの有効期限が切れていないか、パスワードが正しいか確認してください。",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"PayPayリンクモーダルエラー: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("エラーが発生しました。もう一度お試しください。", ephemeral=True)
            else:
                await interaction.followup.send("エラーが発生しました。もう一度お試しください。", ephemeral=True)
        except:
            pass


# ====================== 代行実行 ======================
async def _execute_daiko(editor, selected):
    actions = []
    for key in selected:
        try:
            if key == "unlock_all":
                await asyncio.to_thread(editor.unlock_all_cats)
            elif key == "remove_error":
                await asyncio.to_thread(editor.remove_ban_flags)
            elif key == "levels_max":
                await asyncio.to_thread(editor.max_level_all_cats)
            elif key == "forms_max":
                await asyncio.to_thread(editor.max_all_cats)
            elif key == "main_clear":
                await asyncio.to_thread(editor.clear_all_stages)
            elif key == "talents_max":
                cats = editor.get_all_cats()
                for cat in cats:
                    if cat.unlocked:
                        await asyncio.to_thread(cat.max_talents, 10)
            elif key == "zombie_clear":
                await asyncio.to_thread(editor.clear_all_outbreaks)
            elif key == "legend_clear":
                await asyncio.to_thread(editor.clear_all_zero_legends)
            elif key == "uncanny_clear":
                await asyncio.to_thread(editor.clear_all_uncanny)
            elif key == "legend_quest":
                await asyncio.to_thread(editor.clear_all_legend_quest)
            elif key == "ex_clear":
                await asyncio.to_thread(editor.clear_all_ex_stages)
            elif key == "zero_clear":
                await asyncio.to_thread(editor.clear_all_zero_legends)
            elif key == "aku_clear":
                await asyncio.to_thread(editor.clear_all_aku)
            elif key == "event_clear":
                await asyncio.to_thread(editor.clear_all_events)
            elif key == "gamatoto_max":
                editor.gamatoto_xp = 9999999
                await asyncio.to_thread(editor.max_gamatoto_helpers)
            elif key == "gamatoto_hlp":
                await asyncio.to_thread(editor.max_gamatoto_helpers)
            elif key == "ototo_max":
                await asyncio.to_thread(editor.max_facilities)
            elif key == "shrine_max":
                editor.set_cat_shrine(30, 9999999)
            elif key == "playtime":
                editor.set_play_time(99999, 0)
            elif key == "gold_member":
                editor.set_gold_pass(365)
            elif key == "deck_slots":
                editor.equip_slots = 50
            elif key == "medals":
                editor.unlock_all_medals()
            elif key == "all_medals":
                editor.unlock_all_medals()
            elif key == "enemy_enc":
                editor.unlock_enemy_guide()
            elif key == "tutorial_skip":
                editor.set_tutorial_cleared()
                editor.unlock_equip_menu()
            elif key == "dojo_max":
                editor.set_dojo_score(0, 999999)
            elif key == "missions_clear":
                editor.clear_all_missions()
            elif key == "weekly_missions":
                editor.clear_all_missions()
            elif key == "rank_rewards":
                try:
                    if hasattr(editor, "user_rank_rewards") and hasattr(editor.user_rank_rewards, "rewards"):
                        for r in editor.user_rank_rewards.rewards:
                            if hasattr(r, "claimed"): r.claimed = True
                    elif hasattr(editor, "claim_all_rank_rewards"):
                        editor.claim_all_rank_rewards()
                except Exception:
                    pass
            elif key == "xp":
                editor.xp = 999999999
            elif key == "np":
                editor.np = 999999
            elif key == "catfood":
                editor.catfood = 50000
            elif key == "battle_items":
                editor.set_all_battle_items(999)
            elif key == "vitamins":
                editor.set_all_catamins(999)
            elif key == "base_materials":
                editor.max_base_materials(9999)
            elif key == "catseyes":
                editor.set_all_catseyes(999)
            elif key == "talent_orbs":
                editor.max_all_talent_orbs()
            elif key == "rare":
                editor.rare_tickets = 999
                editor.normal_tickets = 29
            elif key == "platinum":
                editor.platinum_tickets = 29
            elif key == "legend":
                editor.legend_tickets = 29
            elif key == "event_ticket":
                editor.hundred_million_ticket = 99
            elif key == "lead":
                editor.leadership = 999
            elif key == "sub_medals":
                editor.set_all_labyrinth_medals(99)
            else:
                actions.append(f"⚠ {ALL_OPTIONS.get(key, key)} (未実装)")
                continue
            actions.append(f"✓ {ALL_OPTIONS.get(key, key)}")
        except Exception as e:
            print(f"エラー {key}: {e}")
            actions.append(f"✗ {ALL_OPTIONS.get(key, key)}")
    return actions


async def send_jisseki_to_channel(interaction, actions, paid):
    """指定されたチャンネルに実績を送信（注文内容・金額・アイコン・名前のみ、コードは含まない）"""
    config_file = "daiko_config.json"
    if not os.path.exists(config_file):
        return
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    channel_id = config.get("jisseki_channel_id")
    if not channel_id:
        return
    
    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        return
    
    # 注文内容を整形（✓がついているものだけ表示）
    order_items = [a.replace("✓ ", "") for a in actions if a.startswith("✓")]
    order_text = "\n".join(f"・{item}" for item in order_items)
    
    # シンプルなEmbed（コードは含まない）
    embed = discord.Embed(
        title="代行実績",
        description=f"```\n{order_text}\n```",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    
    # アイコンと名前
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.avatar.url if interaction.user.avatar else None
    )
    
    # 合計金額のみ（コードは入れない）
    embed.add_field(name="合計金額", value=f"¥{paid}", inline=False)
    
    await channel.send(embed=embed)


async def _send_daiko_result(interaction, editor, actions, paid):
    try:
        result = editor.issue_transfer_codes()
        if asyncio.iscoroutine(result):
            tc, pin = await result
        else:
            tc, pin = await asyncio.to_thread(editor.issue_transfer_codes)

        if tc and pin:
            # DM送信（既存）
            embed_dm = discord.Embed(
                title="代行完了",
                description=f"お支払い金額: ¥{paid}",
                color=0x2ECC71
            )
            embed_dm.add_field(name="引き継ぎコード", value=f"`{tc}`", inline=False)
            embed_dm.add_field(name="認証コード", value=f"`{pin}`", inline=False)
            embed_dm.add_field(name="実行内容", value="\n".join(actions), inline=False)
            embed_dm.set_footer(text="代行が完了しました。アプリ内でコードを入力してください")
            await interaction.user.send(embed=embed_dm)
            await interaction.followup.send("DMに新しい引き継ぎコードを送信しました", ephemeral=True)
            
            # 売上記録
            _record_sale(interaction.user.id, paid)
            
            # 実績チャンネル送信
            await send_jisseki_to_channel(interaction, actions, paid)
            
            return
    except Exception as e:
        print(f"コード発行エラー: {e}")

    await interaction.followup.send("コード発行に失敗しました。もう一度お試しください", ephemeral=True)


class DaikoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.view_registered = False

    @commands.Cog.listener()
    async def on_ready(self):
        # 二重登録を防ぐ
        if not self.view_registered:
            try:
                self.bot.add_view(DaikoMenuView())
                self.view_registered = True
                print("[DaikoCog] 永続Viewを登録しました")
            except Exception as e:
                print(f"[DaikoCog] 永続View登録エラー: {e}")
        print("[DaikoCog] 読み込み完了")

    @app_commands.command(name="にゃんこ代行", description="有料のにゃんこ大戦争代行サービス")
    @is_allowed()
    async def daiko(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("サーバー内のみ使用できます", ephemeral=True)
        
        # 価格付きリスト表示のEmbed
        embed = discord.Embed(
            title="にゃんこ大戦争 代行自販機",
            description="カテゴリで選択 → 確定 → PayPayで支払い → 代行実行",
            color=0xF5A623
        )
        
        # アイテム系
        items_list = []
        for _, label in G1_OPTIONS:
            items_list.append(f"・{label}")
        items = "\n".join(items_list)
        embed.add_field(name="アイテム系", value=f"```{items}```", inline=False)
        
        # キャラ系
        chars_list = []
        for _, label in G2_OPTIONS:
            chars_list.append(f"・{label}")
        chars = "\n".join(chars_list)
        embed.add_field(name="キャラ系", value=f"```{chars}```", inline=False)
        
        # ステージ系
        stages_list = []
        for _, label in G3_OPTIONS:
            stages_list.append(f"・{label}")
        stages = "\n".join(stages_list)
        embed.add_field(name="ステージ系", value=f"```{stages}```", inline=False)
        
        # 施設・その他系
        facilities_list = []
        for _, label in G4_OPTIONS:
            facilities_list.append(f"・{label}")
        facilities = "\n".join(facilities_list)
        embed.add_field(name="施設・その他系", value=f"```{facilities}```", inline=False)
        
        embed.set_footer(text="代行後は新しい引き継ぎコードがDMに送られます")
        
        await interaction.response.send_message(embed=embed, view=DaikoMenuView())

    @app_commands.command(name="にゃんこ実績チャンネル", description="代行実績を送信するチャンネルを設定します（オーナー専用）")
    @is_owner()
    @app_commands.describe(channel="送信先のチャンネル")
    async def set_jisseki_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        
        config = {}
        if os.path.exists("daiko_config.json"):
            with open("daiko_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        
        config["jisseki_channel_id"] = channel.id
        
        with open("daiko_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        embed = discord.Embed(
            title="✅ 設定完了",
            description=f"代行完了時に {channel.mention} に実績を送信します。",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="にゃんこ実績チャンネル解除", description="実績送信チャンネル解除（オーナー専用）")
    @is_owner()
    async def unset_jisseki_channel(self, interaction: discord.Interaction):
        if os.path.exists("daiko_config.json"):
            with open("daiko_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            
            if "jisseki_channel_id" in config:
                del config["jisseki_channel_id"]
                
                with open("daiko_config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                await interaction.response.send_message("実績送信チャンネルを解除しました。", ephemeral=True)
            else:
                await interaction.response.send_message("設定されていません。", ephemeral=True)
        else:
            await interaction.response.send_message("設定されていません。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DaikoCog(bot))
    await bot.add_cog(DaikoPricesCog(bot))


# ====================== 追加コマンド群 ======================
# ※ DaikoCog のメソッドとして定義するため、クラス外に独立したヘルパーを先に定義

PRICES_FILE = "daiko_prices.json"
SALES_FILE  = "daiko_sales.json"
LICENSE_FILE = "daiko_licenses.json"

def _load_prices() -> dict:
    if os.path.exists(PRICES_FILE):
        try:
            with open(PRICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(ITEM_PRICES)  # デフォルト値

def _save_prices(data: dict):
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_sales() -> dict:
    if os.path.exists(SALES_FILE):
        try:
            with open(SALES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total": 0, "users": {}}

def _record_sale(user_id: int, amount: int):
    if amount <= 0:
        return
    data = _load_sales()
    uid = str(user_id)
    data["users"][uid] = data["users"].get(uid, 0) + amount
    data["total"] = data.get("total", 0) + amount
    with open(SALES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_licenses() -> dict:
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_licenses(data: dict):
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _has_license(user_id: int) -> bool:
    import time
    data = _load_licenses()
    expiry = data.get(str(user_id), 0)
    return expiry == -1 or expiry > time.time()


class DaikoPricesCog(commands.Cog):
    """価格設定・売上・ライセンス管理コマンド群"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        from utils import OWNER_ID
        return interaction.user.id == OWNER_ID

    # ── 価格設定 ──────────────────────────────────────────
    @app_commands.command(name="にゃんこ価格設定", description="各代行メニューの価格を設定します（管理者専用）")
    @app_commands.describe(
        item="変更するメニューのキー（例: xp, catfood, main_clear）",
        price="新しい価格（円、0で無料）"
    )
    async def set_price(self, interaction: discord.Interaction, item: str, price: int):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)
        if item not in ITEM_PRICES:
            keys = ", ".join(sorted(ITEM_PRICES.keys()))
            return await interaction.response.send_message(
                f"不明なキー: `{item}`\n\n使えるキー一覧:\n```{keys}```", ephemeral=True
            )
        if price < 0:
            return await interaction.response.send_message("0以上の値を入力してください", ephemeral=True)

        prices = _load_prices()
        old = prices.get(item, ITEM_PRICES.get(item, 0))
        prices[item] = price
        _save_prices(prices)

        label = ALL_OPTIONS.get(item, item)
        embed = discord.Embed(
            title="✅ 価格変更完了",
            description=f"**{label}**\n¥{old} → ¥{price}",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 価格一覧 ──────────────────────────────────────────
    @app_commands.command(name="にゃんこ価格一覧", description="現在の代行メニュー価格一覧を表示します")
    async def list_prices(self, interaction: discord.Interaction):
        prices = _load_prices()

        def block(opts):
            lines = []
            for val, _ in opts:
                label = ALL_OPTIONS.get(val, val)
                p = prices.get(val, ITEM_PRICES.get(val, 0))
                lines.append(f"{label}: ¥{p}")
            return "\n".join(lines)

        embed = discord.Embed(title="💴 代行メニュー価格一覧", color=0x3498DB)
        embed.add_field(name="アイテム系",   value=f"```{block(G1_OPTIONS)}```", inline=False)
        embed.add_field(name="キャラ系",     value=f"```{block(G2_OPTIONS)}```", inline=False)
        embed.add_field(name="ステージ系",   value=f"```{block(G3_OPTIONS)}```", inline=False)
        embed.add_field(name="施設・その他", value=f"```{block(G4_OPTIONS)}```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 売上確認 ──────────────────────────────────────────
    @app_commands.command(name="にゃんこ売上", description="代行サービスの売上を確認します（管理者専用）")
    async def show_sales(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)

        data = _load_sales()
        total = data.get("total", 0)
        users = data.get("users", {})

        sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, amount) in enumerate(sorted_users[:15]):
            icon = medals[i] if i < 3 else f"**{i+1}位**"
            lines.append(f"{icon} <@{uid}>: ¥{amount}")

        desc = "\n".join(lines) if lines else "まだ売上データがありません"
        desc += f"\n\n{'='*20}\n💰 **売上合計: ¥{total}**"

        embed = discord.Embed(
            title="🏆 売上ランキング",
            description=desc,
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── ライセンス（無料枠）付与 ──────────────────────────
    @app_commands.command(name="にゃんこ無料付与", description="指定ユーザーを無料枠（ライセンス）に設定します（管理者専用）")
    @app_commands.describe(
        user="対象ユーザー",
        days="有効日数（0で永久、-1で解除）"
    )
    async def grant_free(self, interaction: discord.Interaction, user: discord.Member, days: int = 30):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)

        import time
        data = _load_licenses()
        uid = str(user.id)

        if days == -1:
            data.pop(uid, None)
            _save_licenses(data)
            return await interaction.response.send_message(
                f"{user.mention} の無料ライセンスを解除しました", ephemeral=True
            )

        expiry = -1 if days == 0 else int(time.time()) + days * 86400
        data[uid] = expiry
        _save_licenses(data)

        expiry_text = "永久" if days == 0 else f"{days}日間"
        embed = discord.Embed(
            title="✅ 無料ライセンス付与",
            description=f"{user.mention} に **{expiry_text}** の無料枠を付与しました",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── ライセンス一覧 ──────────────────────────────────────
    @app_commands.command(name="にゃんこライセンス一覧", description="無料枠ユーザーの一覧を表示します（管理者専用）")
    async def list_licenses(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)

        import time
        data = _load_licenses()
        now = time.time()

        lines = []
        for uid, expiry in data.items():
            if expiry == -1:
                status = "永久"
            elif expiry > now:
                remain = int((expiry - now) / 86400)
                status = f"残{remain}日"
            else:
                status = "⚠ 期限切れ"
            lines.append(f"<@{uid}>: {status}")

        desc = "\n".join(lines) if lines else "登録なし"
        embed = discord.Embed(title="🎫 無料ライセンス一覧", description=desc, color=0x9B59B6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 価格一括変更 ──────────────────────────────────────
    @app_commands.command(name="にゃんこ価格一括設定", description="全メニューの価格を一括で変更します（管理者専用）")
    @app_commands.describe(price="全アイテムに設定する価格（円、0で全部無料）")
    async def set_all_prices(self, interaction: discord.Interaction, price: int):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)
        if price < 0:
            return await interaction.response.send_message("0以上の値を入力してください", ephemeral=True)

        prices = {key: price for key in ITEM_PRICES}
        _save_prices(prices)

        embed = discord.Embed(
            title="✅ 価格一括変更完了",
            description=f"全{len(prices)}項目の価格を **¥{price}** に設定しました",
            color=0x2ECC71
        )
        embed.set_footer(text="個別に変更したい場合は /にゃんこ価格設定 を使用してください")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 売上リセット（管理者専用） ─────────────────────────
    @app_commands.command(name="にゃんこ売上リセット", description="売上データをリセットします（管理者専用・取消不可）")
    async def reset_sales(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)

        with open(SALES_FILE, "w", encoding="utf-8") as f:
            json.dump({"total": 0, "users": {}}, f)

        await interaction.response.send_message("売上データをリセットしました", ephemeral=True)
