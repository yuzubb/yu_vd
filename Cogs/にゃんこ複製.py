import discord
from discord.ext import commands
from discord import app_commands
import traceback
import asyncio
import os
import json
import time
import datetime
import io
from dotenv import load_dotenv

# --- 追加: .envファイルから特別なユーザーIDを読み込む ---
load_dotenv()
env_user_id = os.getenv("SPECIAL_USER_ID", "0")
SPECIAL_USER_ID = int(env_user_id) if env_user_id.isdigit() else 0

def is_admin_or_special():
    """管理者、または.envで指定したユーザーのみ許可するカスタムチェック"""
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.permissions.administrator or interaction.user.id == SPECIAL_USER_ID
    return app_commands.check(predicate)
# ----------------------------------------------------

# ★ PayPay決済用のインポート
import paypayu

from bcsfe import core
from bcsfe.core.server.server_handler import ServerHandler
from bcsfe.core.game.gamoto.gamatoto import Helper
from bcsfe.core.game.battle.slots import EquipSlots
from bcsfe.core.game.catbase.cat import Talent
from bcsfe.core.game.catbase.unlock_popups import Popup

# ==========================================
# BCSFE 初期化 & データファイル設定
# ==========================================
if getattr(core.core_data, "config", None) is None:
    core.set_config_path(core.Path("config.json"))
    core.set_log_path(core.Path("bcsfe.log"))
    core.core_data.init_data()

BASE_ACCOUNT_FILE = "data/base_account.json" 
DUPLICATE_PANEL_FILE = "data/duplicate_panel.json"
CONFIG_FILE = "data/daikou_config.json"
CAT_NAMES_FILE = "data/cat_names.json"

# ★ 決済・売上用のファイルパス
PAYPAY_DATA_FILE = "data/paypay_data.json"
SALES_FILE = "data/sales.json"

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: pass
    return {}

def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_valid_cat_ids():
    data = load_json(CAT_NAMES_FILE)
    if not data:
        return set()
    return {int(k) for k in data.keys() if k.isdigit()}

def record_sale(user_id: int, amount: int):
    if amount <= 0: return
    sales_data = load_json(SALES_FILE)
    if not sales_data: sales_data = {"total": 0, "users": {}}
    sales_data["users"][str(user_id)] = sales_data["users"].get(str(user_id), 0) + amount
    sales_data["total"] = sales_data.get("total", 0) + amount
    save_json(SALES_FILE, sales_data)

# ==========================================
# 全マシ用の安全な書き換え関数
# ==========================================
def super_safe_max_items(obj, max_val=9999):
    if not obj: return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if hasattr(v, "amount"): v.amount = max_val
            elif hasattr(v, "value"): v.value = max_val
            else: obj[k] = max_val
        return
    if isinstance(obj, list):
        for i in range(len(obj)):
            if hasattr(obj[i], "amount"): obj[i].amount = max_val
            elif hasattr(obj[i], "value"): obj[i].value = max_val
            else: obj[i] = max_val
        return
    if hasattr(obj, "items"): super_safe_max_items(obj.items, max_val)
    elif hasattr(obj, "materials"): super_safe_max_items(obj.materials, max_val)
    elif hasattr(obj, "orbs"): super_safe_max_items(obj.orbs, max_val)

def super_safe_clear(obj, visited=None):
    if obj is None: return
    if visited is None: visited = set()
    if id(obj) in visited: return
    visited.add(id(obj))
    if isinstance(obj, dict):
        for v in obj.values(): super_safe_clear(v, visited)
        return
    if isinstance(obj, list) or isinstance(obj, tuple):
        for v in obj: super_safe_clear(v, visited)
        return
    if isinstance(obj, (int, float, str, bool)): return
    for attr in ["clear_times", "clear_amount"]:
        if hasattr(obj, attr):
            try: setattr(obj, attr, 1)
            except: pass
    if hasattr(obj, "treasure"):
        try: obj.treasure = 3
        except: pass
    if hasattr(obj, "clear_progress"):
        try:
            if hasattr(obj, "stages") and hasattr(obj.stages, "__len__"): obj.clear_progress = len(obj.stages)
            else: obj.clear_progress = 48
        except: pass
    for attr in ["unlock_state", "chapter_unlock_state"]:
        if hasattr(obj, attr):
            try: setattr(obj, attr, 3)
            except: pass
    try: attrs = dir(obj)
    except: return
    for attr in attrs:
        if attr.startswith("__"): continue
        if attr in ["chapters", "stages", "outbreaks", "event_stages", "uncanny", "zero_legends", "aku", "sub_chapters", "gauntlets", "collab_gauntlets", "behemoth_culling", "tower", "enigma", "legend_quest", "timed_score", "missions", "login_bonuses"]:
            try: super_safe_clear(getattr(obj, attr), visited)
            except: pass

# 施設をすべてMAXにするための再帰的探索プログラム
def _maximize_upgrades_in_obj(obj, visited=None):
    if obj is None: return
    if visited is None: visited = set()
    if id(obj) in visited: return
    visited.add(id(obj))
    
    if type(obj).__name__ == "Upgrade":
        obj.base = 29
        obj.plus = 10
        return
    if isinstance(obj, dict):
        for v in obj.values(): _maximize_upgrades_in_obj(v, visited)
        return
    if isinstance(obj, list) or isinstance(obj, tuple):
        for v in obj: _maximize_upgrades_in_obj(v, visited)
        return
    try:
        for attr_name in dir(obj):
            if attr_name.startswith("__"): continue
            attr = getattr(obj, attr_name)
            if type(attr).__name__ == "Upgrade":
                attr.base = 29
                attr.plus = 10
            elif isinstance(attr, (dict, list, tuple)):
                _maximize_upgrades_in_obj(attr, visited)
    except: pass

def apply_all_max(save_file):
    try:
        valid_cat_ids = get_valid_cat_ids()
        
        # 基本ステータス・アイテム
        save_file.xp = 99999999
        save_file.np = 9999
        save_file.catfood = 45000
        save_file.leadership = 9999
        save_file.normal_tickets = 999
        save_file.rare_tickets = 299
        save_file.platinum_tickets = 9
        save_file.legend_tickets = 4
        
        if hasattr(save_file, "event_capsules"):
            for i in range(len(save_file.event_capsules)): save_file.event_capsules[i] = 999
        if hasattr(save_file, "lucky_tickets"):
            for i in range(len(save_file.lucky_tickets)): save_file.lucky_tickets[i] = 999
            
        super_safe_max_items(getattr(save_file, "battle_items", None), 9999)
        super_safe_max_items(getattr(save_file, "catamins", None), 9999)
        if hasattr(save_file, "ototo"): super_safe_max_items(getattr(save_file.ototo, "base_materials", None), 9999)
        super_safe_max_items(getattr(save_file, "catseyes", None), 999)
        
        if hasattr(save_file, "catfruit"):
            for i in range(len(save_file.catfruit)): save_file.catfruit[i] = 99
        if hasattr(save_file, "talent_orbs") and hasattr(save_file.talent_orbs, "orbs"):
            for i in range(1, 150): save_file.talent_orbs.orbs[i] = core.TalentOrb(i, 99)
        if hasattr(save_file, "labyrinth_medals"):
            for i in range(len(save_file.labyrinth_medals)): save_file.labyrinth_medals[i] = 9999

        # 施設レベルMAX (青玉アップグレード)
        for upg_attr in ["upgrades", "normal_upgrades", "base_upgrades", "tech"]:
            try:
                if hasattr(save_file, upg_attr):
                    _maximize_upgrades_in_obj(getattr(save_file, upg_attr))
            except: pass

        # 施設UIレベル
        save_file.ui1 = 29; save_file.ui2 = 29; save_file.ui3 = 29; save_file.ui4 = 29
        save_file.ui5 = 29; save_file.ui6 = 29; save_file.ui7 = 29; save_file.ui8 = 29; save_file.ui9 = 29
        
        # キャラクター関連
        pic_book = None
        try: pic_book = save_file.cats.read_nyanko_picture_book(save_file)
        except: pass
        
        # 本能ゲームデータの読み込み
        talent_data = None
        try: talent_data = save_file.cats.read_talent_data(save_file)
        except: pass

        for cat in save_file.cats.cats:
            is_valid_cat = cat.id in valid_cat_ids
            if cat.id == 673: 
                is_valid_cat = False
            if pic_book and pic_book.get_cat(cat.id) is None:
                is_valid_cat = False

            if not is_valid_cat:
                cat.unlocked = 0
                cat.upgrade.base = 0
                cat.upgrade.plus = 0
                cat.current_form = 0
                cat.unlocked_forms = 0 
                cat.fourth_form = 0
                continue 

            cat.unlocked = 1
            cat.upgrade.base = 59
            cat.upgrade.plus = 90
            
            # 新規獲得フラグ(NEW)をオフ
            if hasattr(save_file.cats, "chara_new_flags"):
                save_file.cats.chara_new_flags[cat.id] = 0
            if hasattr(cat, "is_new"): cat.is_new = False
            if hasattr(cat, "new"): cat.new = False

            total_forms = 3
            if pic_book:
                pic_cat = pic_book.get_cat(cat.id)
                if pic_cat: total_forms = pic_cat.total_forms

            if total_forms >= 4:
                cat.unlocked_forms = 3; cat.current_form = 2; cat.fourth_form = 2
            elif total_forms == 3: cat.unlocked_forms = 3; cat.current_form = 2
            elif total_forms == 2: cat.unlocked_forms = 2; cat.current_form = 1
            else: cat.unlocked_forms = 1; cat.current_form = 0

            # 全キャラ本能MAX
            if talent_data is not None:
                cat_skill = talent_data.get_cat_skill(cat.id)
                if cat_skill is not None and hasattr(cat_skill, "skills"):
                    try:
                        new_talents = []
                        for skill in cat_skill.skills:
                            max_lv = getattr(skill, "max_lv", 10)
                            if max_lv <= 0: max_lv = 1
                            new_talents.append(Talent(getattr(skill, "ability_id", 0), max_lv))
                        cat.talents = new_talents
                    except: pass

        # ストーリー・ステージクリア
        if hasattr(save_file, "story"):
            for chapter in save_file.story.chapters:
                chapter.progress = 48
                for stage in chapter.stages: stage.clear_times = 1; stage.treasure = 3
        super_safe_clear(getattr(save_file, "outbreaks", None))
        super_safe_clear(getattr(save_file, "event_stages", None))
        super_safe_clear(getattr(save_file, "uncanny", None))
        super_safe_clear(getattr(save_file, "zero_legends", None))
        super_safe_clear(getattr(save_file, "aku", None))
        super_safe_clear(getattr(save_file, "gauntlets", None))
        super_safe_clear(getattr(save_file, "collab_gauntlets", None))
        super_safe_clear(getattr(save_file, "behemoth_culling", None))
        super_safe_clear(getattr(save_file, "tower", None))
        super_safe_clear(getattr(save_file, "enigma", None))
        super_safe_clear(getattr(save_file, "legend_quest", None))
        super_safe_clear(getattr(save_file, "timed_score", None))

        # ガマトト・オトート
        if hasattr(save_file, "gamatoto"): 
            save_file.gamatoto.xp = 99999999
            if hasattr(save_file.gamatoto, "helpers"):
                save_file.gamatoto.helpers.helpers = [Helper(4) for _ in range(10)]
                
        if hasattr(save_file, "ototo") and hasattr(save_file.ototo, "cannons"):
            for cannon in save_file.ototo.cannons.cannons.values():
                cannon.development = 3; cannon.levels = [30, 30, 30]
                
        # にゃんこ神社即LvMAX
        try:
            if hasattr(save_file, "cat_shrine"):
                save_file.cat_shrine.xp_offering = 99999999
                if hasattr(save_file.cat_shrine, "level"):
                    save_file.cat_shrine.level = 50
                if hasattr(save_file.cat_shrine, "unlocked"):
                    save_file.cat_shrine.unlocked = True
        except: pass
        
        try:
            medal_names = core.core_data.get_medal_names(save_file)
            if medal_names and medal_names.medal_names:
                for i, medal in enumerate(medal_names.medal_names):
                    if len(medal) > 0: save_file.medals.add_medal(i)
        except: pass
        
        # 図鑑通知(NEW)対策
        if hasattr(save_file, "enemy_guide"):
            save_file.enemy_guide = [1] * len(save_file.enemy_guide)
        try:
            if hasattr(save_file, "enemy_guide_new"):
                save_file.enemy_guide_new = [0] * len(save_file.enemy_guide_new)
        except: pass
            
        # ミッション通知(NEW)対策
        if hasattr(save_file, "missions"):
            super_safe_clear(save_file.missions)
            try:
                if hasattr(save_file.missions, "missions"):
                    for m in save_file.missions.missions:
                        if hasattr(m, "completed"): m.completed = True
                        if hasattr(m, "claimed"): m.claimed = True
                        if hasattr(m, "state"): m.state = 2
            except: pass
            
        if hasattr(save_file, "login_bonuses"): super_safe_clear(save_file.login_bonuses)
        
        if hasattr(save_file, "user_rank_rewards") and hasattr(save_file.user_rank_rewards, "rewards"):
            for reward in save_file.user_rank_rewards.rewards: 
                if hasattr(reward, "claimed"): reward.claimed = True
                
        if hasattr(save_file, "officer_pass"):
            save_file.officer_pass.play_time = 2147483647
            if hasattr(save_file.officer_pass, "gold_pass"):
                try: save_file.officer_pass.gold_pass.get_gold_pass(12345, 30, save_file)
                except: pass

        try:
            if hasattr(save_file, "item_packs") and hasattr(save_file.item_packs, "packs"):
                for i in range(len(save_file.item_packs.packs)): save_file.item_packs.packs[i] = 1
            for attr in dir(save_file):
                if "sale" in attr.lower():
                    obj = getattr(save_file, attr)
                    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
                        setattr(save_file, attr, 0)
        except: pass

        try: core.game.map.story.StoryChapters.clear_tutorial(save_file)
        except: pass

        try:
            save_file.date_3 = datetime.datetime.now()
            save_file.timestamp = datetime.datetime.now().timestamp()
            save_file.energy_penalty_timestamp = datetime.datetime.now().timestamp()
            if hasattr(save_file, "gamatoto"): save_file.gamatoto.skin = 2
            if hasattr(save_file, "ototo"): save_file.ototo.cannons = core.game.gamoto.ototo.Cannons.init(save_file.game_version)
            if hasattr(save_file, "officer_pass"):
                save_file.officer_pass.cat_id = 0
                save_file.officer_pass.cat_form = 0
        except: pass

        try:
            if hasattr(save_file, "dojo") and hasattr(save_file.dojo, "chapters"):
                stage = save_file.dojo.chapters.get_stage(0, 0)
                if stage: stage.score = 999999
        except: pass

        # 【修正】開放テロップの既読化 (安全のため、既に存在するデータのみを既読にする)
        try:
            if hasattr(save_file, "unlock_popups") and hasattr(save_file.unlock_popups, "popups"):
                for popup in save_file.unlock_popups.popups.values(): 
                    if hasattr(popup, "seen"): popup.seen = True
        except: pass

        try:
            if hasattr(save_file, "cats") and hasattr(save_file.cats, "storage_items"):
                save_file.cats.storage_items = []
        except: pass

        try: save_file.sanitize()
        except: pass
        
    except Exception as e:
        print(f"全マシ処理中にエラー: {e}")

def get_handler_sync(transfer_code, confirm_code):
    cc = core.CountryCode.from_code("jp")
    gv = core.GameVersion.from_string("13.0.0")
    handler, _ = ServerHandler.from_codes(transfer_code, confirm_code, cc, gv, print=False, save_backup=False)
    return handler

def apply_max_sync(handler):
    apply_all_max(handler.save_file)

def create_and_get_codes_sync(handler):
    success = handler.create_new_account()
    if not success: return None
    return handler.get_codes()

# ==========================================
# 通常複製 (ユーザー入力あり・PayPay対応)
# ==========================================
class DuplicateModal(discord.ui.Modal, title='アカウント複製 (決済＆コード入力)'):
    def __init__(self, unit_price: int, owner_id: str):
        super().__init__()
        self.unit_price = unit_price
        self.owner_id = owner_id

        self.transfer_code = discord.ui.TextInput(label='引き継ぎコード', placeholder='例: 1a2b3c4d5', required=True)
        self.confirm_code = discord.ui.TextInput(label='確認コード', placeholder='例: 1234', required=True)
        self.amount = discord.ui.TextInput(label='複製する数 (最大10)', placeholder='例: 5', default='1', required=True)
        
        self.add_item(self.transfer_code)
        self.add_item(self.confirm_code)
        self.add_item(self.amount)

        # 単価が設定されている場合のみPayPayリンクの入力を求めるフォームを生成
        if self.unit_price > 0:
            self.pay_link = discord.ui.TextInput(label=f'PayPayリンク (単価 {self.unit_price}円 × 個数分)', placeholder='https://pay.paypay.ne.jp/...', required=True)
            self.add_item(self.pay_link)
        else:
            self.pay_link = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            num_copies = int(self.amount.value)
            if num_copies < 1 or num_copies > 10:
                return await interaction.followup.send("エラー：作成する数は 1個から10個の間 で指定してください。", ephemeral=True)
        except ValueError:
            return await interaction.followup.send("エラー：作成する数は半角数字で入力してください。", ephemeral=True)

        total_price = num_copies * self.unit_price

        # PayPay決済チェック
        if total_price > 0:
            paypay_data = load_json(PAYPAY_DATA_FILE)
            owner_cred = next((d for d in paypay_data.values() if str(d.get("discord_id")) == str(self.owner_id)), None)
            if not owner_cred: 
                return await interaction.followup.send("エラー: 販売者のPayPayが登録されていません。", ephemeral=True)
            
            pay_link_val = self.pay_link.value.strip()
            info = await asyncio.to_thread(paypayu.check_link, pay_link_val)
            amount_received = info.get("payload", {}).get("message", {}).get("data", {}).get("amount", 0) if info else 0
            
            if amount_received < total_price: 
                return await interaction.followup.send(f"エラー: 金額が不足しています。必要金額: {total_price}円 (リンクの金額: {amount_received}円)", ephemeral=True)
                
            rev_success = await asyncio.to_thread(paypayu.link_rev, pay_link_val, owner_cred["phone"], owner_cred["password"], owner_cred["uuid"])
            if rev_success != True:
                return await interaction.followup.send("エラー: PayPayの受け取りに失敗しました。", ephemeral=True)

        guild_name = interaction.guild.name if interaction.guild else "DM"
        print(f"[LOG: 複製] 実行者: {interaction.user.display_name} (@{interaction.user.name} / ID: {interaction.user.id}) | サーバー: {guild_name} | 作成数: {num_copies}個 | 売上: {total_price}円")

        msg = await interaction.followup.send(embed=discord.Embed(
            title="処理中...", description=f"アカウントを {num_copies}個 複製しています...\n(※時間がかかります)", color=0x00aaff 
        ), wait=True, ephemeral=True)

        try:
            handler = await asyncio.to_thread(get_handler_sync, self.transfer_code.value, self.confirm_code.value)
            if handler is None:
                return await msg.edit(embed=discord.Embed(title="エラー", description="データの取得に失敗しました。コードを確認してください。", color=0xff0000))

            results = []
            for i in range(num_copies):
                codes = await asyncio.to_thread(create_and_get_codes_sync, handler)
                if codes:
                    results.append(f"【{i+1}個目】\n引き継ぎ: `{codes[0]}`\n確認: `{codes[1]}`")
                else:
                    results.append(f"【{i+1}個目】\nアカウント作成失敗")
                await asyncio.sleep(0.1)

            result_text = "\n".join(results)

            # 売上記録の保存
            if total_price > 0:
                await asyncio.to_thread(record_sale, interaction.user.id, total_price)

            try:
                if len(result_text) <= 4000:
                    await interaction.user.send(embed=discord.Embed(title="複製完了", description=f"{num_copies}個 のアカウントを複製しました！\n\n{result_text}", color=0x00aaff))
                else:
                    file_content = f"{num_copies}個の複製結果\n\n{result_text.replace('`', '').replace('**', '')}"
                    file_bytes = io.BytesIO(file_content.encode('utf-8'))
                    await interaction.user.send(
                        embed=discord.Embed(title="複製完了", description=f"{num_copies}個 のアカウントを複製しました！文字数が多いためファイルにまとめました。", color=0x00aaff),
                        file=discord.File(fp=file_bytes, filename="results.txt")
                    )
                
                await msg.edit(embed=discord.Embed(title="完了", description="複製したアカウントの情報をあなたのDMに送信しました！", color=0x00aaff))
                
                config = load_json(CONFIG_FILE)
                log_ch_id = config.get("panel_log_channel_id")
                if log_ch_id:
                    log_ch = interaction.client.get_channel(log_ch_id)
                    if log_ch:
                        log_embed = discord.Embed(title="【アカウント複製】実績ログ", color=0x00aaff)
                        log_embed.add_field(name="実行者", value=f"{interaction.user.mention} ({interaction.user.display_name})", inline=False)
                        log_embed.add_field(name="製造数", value=f"{num_copies}個", inline=False)
                        log_embed.add_field(name="売上金額", value=f"**{total_price}円**", inline=False)
                        await log_ch.send(embed=log_embed)

            except discord.Forbidden:
                await msg.edit(embed=discord.Embed(title="エラー", description="DMの送信に失敗しました。サーバー設定で「ダイレクトメッセージを許可する」をオンにしてください。", color=0xff0000))

        except Exception as e:
            error_traceback = traceback.format_exc()
            await msg.edit(
                content=None,
                embed=discord.Embed(
                    title="エラーが発生しました", 
                    description=f"処理中に予期せぬエラーが発生しました。\n```py\n{e}\n```", 
                    color=0xff0000
                )
            )
            print(f"[ERROR: 複製] 実行中にエラーが発生しました:\n{error_traceback}")

# ==========================================
# 全マシ自動作成 (PayPay対応)
# ==========================================
class AutoCreateMaxAccountModal(discord.ui.Modal, title='最強アカウント作成 (決済)'):
    def __init__(self, unit_price: int, owner_id: str):
        super().__init__()
        self.unit_price = unit_price
        self.owner_id = owner_id

        self.amount = discord.ui.TextInput(label='作成する数 (最大10)', placeholder='例: 5', default='1', required=True)
        self.add_item(self.amount)

        # 単価が設定されている場合のみPayPayリンクの入力を求めるフォームを生成
        if self.unit_price > 0:
            self.pay_link = discord.ui.TextInput(label=f'PayPayリンク (単価 {self.unit_price}円 × 個数分)', placeholder='https://pay.paypay.ne.jp/...', required=True)
            self.add_item(self.pay_link)
        else:
            self.pay_link = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        base_data = load_json(BASE_ACCOUNT_FILE)
        base_tc = base_data.get("transfer_code")
        base_cc = base_data.get("confirm_code")

        if not base_tc or not base_cc:
            return await interaction.followup.send("エラー: Botに大元のベースアカウントが登録されていません。", ephemeral=True)

        try:
            num_copies = int(self.amount.value)
            if num_copies < 1 or num_copies > 10:
                return await interaction.followup.send("エラー：作成する数は 1個から10個の間 で指定してください。", ephemeral=True)
        except ValueError:
            return await interaction.followup.send("エラー：作成する数は半角数字で入力してください。", ephemeral=True)

        total_price = num_copies * self.unit_price

        # PayPay決済チェック
        if total_price > 0:
            paypay_data = load_json(PAYPAY_DATA_FILE)
            owner_cred = next((d for d in paypay_data.values() if str(d.get("discord_id")) == str(self.owner_id)), None)
            if not owner_cred: 
                return await interaction.followup.send("エラー: 販売者のPayPayが登録されていません。", ephemeral=True)
            
            pay_link_val = self.pay_link.value.strip()
            info = await asyncio.to_thread(paypayu.check_link, pay_link_val)
            amount_received = info.get("payload", {}).get("message", {}).get("data", {}).get("amount", 0) if info else 0
            
            if amount_received < total_price: 
                return await interaction.followup.send(f"エラー: 金額が不足しています。必要金額: {total_price}円 (リンクの金額: {amount_received}円)", ephemeral=True)
                
            rev_success = await asyncio.to_thread(paypayu.link_rev, pay_link_val, owner_cred["phone"], owner_cred["password"], owner_cred["uuid"])
            if rev_success != True:
                return await interaction.followup.send("エラー: PayPayの受け取りに失敗しました。", ephemeral=True)

        guild_name = interaction.guild.name if interaction.guild else "DM"
        print(f"[LOG: 最強垢] 実行者: {interaction.user.display_name} (@{interaction.user.name} / ID: {interaction.user.id}) | サーバー: {guild_name} | 作成数: {num_copies}個 | 売上: {total_price}円")

        msg = await interaction.followup.send(embed=discord.Embed(
            title="自動作成中...", description=f"最強アカウントを {num_copies}個 量産しています...\n(※強力な処理を行うため少し時間がかかります)", color=0x00aaff 
        ), wait=True, ephemeral=True)

        try:
            handler = await asyncio.to_thread(get_handler_sync, base_tc, base_cc)
            if handler is None:
                return await msg.edit(embed=discord.Embed(title="エラー", description="ベースデータの取得に失敗しました。再登録してください。", color=0xff0000))

            await asyncio.to_thread(apply_max_sync, handler)

            results = []
            last_successful_codes = None
            for i in range(num_copies):
                codes = await asyncio.to_thread(create_and_get_codes_sync, handler)
                if codes:
                    results.append(f"【{i+1}個目】\n引き継ぎ: `{codes[0]}`\n確認: `{codes[1]}`")
                    last_successful_codes = codes
                else:
                    results.append(f"【{i+1}個目】\nアカウント作成失敗")
                await asyncio.sleep(0.1)

            # ベースアカウントを最後に作成したアカウントのコードで自動更新
            # create_new_account() を呼ぶたびに元アカウントのコードは無効になるため、
            # 最後に払い出されたコードを次回のベースとして保存する
            if last_successful_codes:
                try:
                    save_json(BASE_ACCOUNT_FILE, {
                        "transfer_code": last_successful_codes[0],
                        "confirm_code": last_successful_codes[1]
                    })
                    print(f"[LOG: ベースアカウント自動更新] 新TC: {last_successful_codes[0]} / CC: {last_successful_codes[1]}")
                except Exception as e:
                    print(f"[WARN: ベースアカウント自動更新失敗] {e}")

            result_text = "\n".join(results)

            # 売上記録の保存
            if total_price > 0:
                await asyncio.to_thread(record_sale, interaction.user.id, total_price)

            try:
                if len(result_text) <= 4000:
                    await interaction.user.send(embed=discord.Embed(title="最強アカウント作成完了", description=f"コンプリート状態のアカウントを {num_copies}個 作成しました！\n\n{result_text}", color=0x00aaff))
                else:
                    file_content = f"{num_copies}個の最強アカウント作成結果\n\n{result_text.replace('`', '').replace('**', '')}"
                    file_bytes = io.BytesIO(file_content.encode('utf-8'))
                    await interaction.user.send(
                        embed=discord.Embed(title="最強アカウント作成完了", description=f"{num_copies}個 作成しました！文字数が多いためファイルにまとめました。", color=0x00aaff),
                        file=discord.File(fp=file_bytes, filename="results_max.txt")
                    )

                await msg.edit(embed=discord.Embed(title="完了", description="作成した最強アカウントの情報をあなたのDMに送信しました！", color=0x00aaff))
                
                config = load_json(CONFIG_FILE)
                log_ch_id = config.get("panel_log_channel_id")
                if log_ch_id:
                    log_ch = interaction.client.get_channel(log_ch_id)
                    if log_ch:
                        log_embed = discord.Embed(title="【最強アカウント作成】実績ログ", color=0x00aaff)
                        log_embed.add_field(name="実行者", value=f"{interaction.user.mention} ({interaction.user.display_name})", inline=False)
                        log_embed.add_field(name="製造数", value=f"{num_copies}個", inline=False)
                        log_embed.add_field(name="売上金額", value=f"**{total_price}円**", inline=False)
                        await log_ch.send(embed=log_embed)

            except discord.Forbidden:
                await msg.edit(embed=discord.Embed(title="エラー", description="DMの送信に失敗しました。サーバー設定で「ダイレクトメッセージを許可する」をオンにしてください。", color=0xff0000))

        except Exception as e:
            error_traceback = traceback.format_exc()
            await msg.edit(
                content=None,
                embed=discord.Embed(
                    title="エラーが発生しました", 
                    description=f"処理中に予期せぬエラーが発生しました。\n```py\n{e}\n```", 
                    color=0xff0000
                )
            )
            print(f"[ERROR: 最強垢] 実行中にエラーが発生しました:\n{error_traceback}")

# ==========================================
# パネルのView
# ==========================================
class MainPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="アカウント複製", style=discord.ButtonStyle.blurple, custom_id="btn_duplicate_only")
    async def btn_duplicate(self, interaction: discord.Interaction, button: discord.ui.Button):
        panel_data = load_json(DUPLICATE_PANEL_FILE)
        owner_id = str(panel_data.get("owner_id", interaction.user.id))
        duplicate_price = panel_data.get("duplicate_price", 0)
        
        await interaction.response.send_modal(DuplicateModal(unit_price=duplicate_price, owner_id=owner_id))

    @discord.ui.button(label="最強アカウント作成", style=discord.ButtonStyle.red, custom_id="btn_create_max")
    async def btn_create_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        panel_data = load_json(DUPLICATE_PANEL_FILE)
        owner_id = str(panel_data.get("owner_id", interaction.user.id))
        max_price = panel_data.get("max_price", 0)
        
        await interaction.response.send_modal(AutoCreateMaxAccountModal(unit_price=max_price, owner_id=owner_id))


class PanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._respawning_channels = set() 
        self._is_respawning = False 
        self.panel_data = load_json(DUPLICATE_PANEL_FILE)
        self.bot.loop.create_task(self.respawn_panel())

    def save_panel_data(self):
        save_json(DUPLICATE_PANEL_FILE, self.panel_data)

    # ★ パネルの見た目と価格表示を結合
    def get_embed(self):
        duplicate_price = self.panel_data.get("duplicate_price", 0) if self.panel_data else 0
        max_price = self.panel_data.get("max_price", 0) if self.panel_data else 0
        
        desc = (
            "【アカウント複製】\n入力したアカウントを、そのままの状態で好きな数だけ複製します。\n"
            f"> 単価: **{duplicate_price}円** / 1アカウント\n\n"
            "【最強アカウント作成】\n完全コンプリート状態にして好きな数だけ自動作成します。\n"
            f"> 単価: **{max_price}円** / 1アカウント\n\n"
            "下のボタンを選んでください。"
        )
        
        # どちらかに金額が設定されている場合は、PayPay対応の注意書きを追加する
        if duplicate_price > 0 or max_price > 0:
            desc += "\n\n※PayPay自動決済に対応しています。\n※ボタンを押した後の画面で、指定した「作成数 × 単価」の金額分のPayPayリンクを入力してください。"
        
        return discord.Embed(title="アカウント複製 ＆ 作成ツール", description=desc, color=0x2b2d31)

    async def respawn_panel(self):
        if self._is_respawning: return
        self._is_respawning = True
        try:
            await self.bot.wait_until_ready()
            await asyncio.sleep(2.0)
            
            if not self.panel_data: return
            
            channel_id = self.panel_data.get("channel_id")
            message_id = self.panel_data.get("message_id")
            
            if not channel_id or not message_id: return
            channel = self.bot.get_channel(channel_id)
            if not channel: return

            try:
                old_msg = await channel.fetch_message(message_id)
                await old_msg.delete()
            except: pass

            view = MainPanelView()
            new_msg = await channel.send(embed=self.get_embed(), view=view)
            
            self.panel_data["message_id"] = new_msg.id
            self.save_panel_data()
            self.bot.add_view(view)
        finally:
            self._is_respawning = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if not self.panel_data: return

        channel_id = self.panel_data.get("channel_id")
        message_id = self.panel_data.get("message_id")

        if not channel_id or message.channel.id != channel_id: return
        
        if channel_id in self._respawning_channels: return

        self._respawning_channels.add(channel_id)
        try:
            await asyncio.sleep(2.0) 

            try:
                old_msg = await message.channel.fetch_message(message_id)
                await old_msg.delete()
            except: pass

            view = MainPanelView()
            new_msg = await message.channel.send(embed=self.get_embed(), view=view)
            
            self.panel_data["message_id"] = new_msg.id
            self.save_panel_data()
            self.bot.add_view(view)
        except Exception as e:
            print(f"パネル再設置中にエラー: {e}")
        finally:
            self._respawning_channels.discard(channel_id)

    @app_commands.command(name="set_base", description="最強垢のベースを登録します")
    @app_commands.describe(transfer_code="適当な初期垢の引き継ぎコード", confirm_code="確認コード")
    @is_admin_or_special()
    async def set_base_account(self, interaction: discord.Interaction, transfer_code: str, confirm_code: str):
        save_json(BASE_ACCOUNT_FILE, {"transfer_code": transfer_code, "confirm_code": confirm_code})
        await interaction.response.send_message(f"登録完了: ベースアカウントを登録しました。", ephemeral=True)

    @set_base_account.error
    async def set_base_account_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)

    @app_commands.command(name="にゃんこ大戦争複製パネル", description="複製・作成パネルを設置します（管理者用）")
    @app_commands.describe(duplicate_price="アカウント複製の単価(円)", max_price="最強垢作成の単価(円)")
    @is_admin_or_special()
    async def setup_panel(self, interaction: discord.Interaction, duplicate_price: int = 0, max_price: int = 0):
        if self.panel_data:
            old_channel_id = self.panel_data.get("channel_id")
            old_message_id = self.panel_data.get("message_id")
            if old_channel_id and old_message_id:
                old_channel = self.bot.get_channel(old_channel_id)
                if old_channel:
                    try:
                        old_msg = await old_channel.fetch_message(old_message_id)
                        await old_msg.delete()
                    except: pass

        self.panel_data = {
            "channel_id": interaction.channel.id, 
            "message_id": None, # 後で上書き
            "owner_id": str(interaction.user.id),
            "duplicate_price": duplicate_price,
            "max_price": max_price
        }

        msg = await interaction.channel.send(embed=self.get_embed(), view=MainPanelView())
        
        self.panel_data["message_id"] = msg.id
        self.save_panel_data()
        await interaction.response.send_message("パネルを設置しました！", ephemeral=True)

    @setup_panel.error
    async def setup_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)

    @app_commands.command(name="price3", description="複製と最強垢作成の単価を設定します")
    @app_commands.describe(duplicate_price="アカウント複製の単価(円)", max_price="最強垢作成の単価(円)")
    @is_admin_or_special()
    async def set_price3(self, interaction: discord.Interaction, duplicate_price: int, max_price: int):
        if not self.panel_data:
            self.panel_data = {}
        self.panel_data["duplicate_price"] = duplicate_price
        self.panel_data["max_price"] = max_price
        self.save_panel_data()

        # パネルのメッセージも更新を試みる
        channel_id = self.panel_data.get("channel_id")
        message_id = self.panel_data.get("message_id")
        if channel_id and message_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=self.get_embed())
                except: pass

        await interaction.response.send_message(f"値段を設定しました！\n複製: {duplicate_price}円\n最強垢: {max_price}円", ephemeral=True)

    @set_price3.error
    async def set_price3_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)

    @app_commands.command(name="set_panel_log", description="複製と最強垢作成の実績ログを送信するチャンネルを設定します")
    @app_commands.describe(channel="ログを送信するチャンネル")
    @is_admin_or_special()
    async def set_panel_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_json(CONFIG_FILE)
        config["panel_log_channel_id"] = channel.id
        save_json(CONFIG_FILE, config)
        await interaction.response.send_message(f"設定完了: 複製・作成のログを {channel.mention} に送信します。", ephemeral=True)

    @set_panel_log.error
    async def set_panel_log_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PanelCog(bot))
    # ★ ここにあった bot.tree.sync() は削除しました
