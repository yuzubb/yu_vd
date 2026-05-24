import discord
from discord import app_commands
import json
import os
import time

CONFIG_FILE = "data/config.json"
LICENSE_FILE = "data/bot_licenses.json"

# ====================== オーナーID ======================
OWNER_ID = 1455012819291340862


def load_allowed_users() -> list:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("allowed_user_ids", [])
        except json.JSONDecodeError:
            return []
    return []


# ====================== ライセンス管理 ======================
def load_licenses() -> dict:
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_licenses(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def has_valid_license(user_id: int) -> bool:
    """ユーザーが有効なライセンスを持っているか確認"""
    if user_id == OWNER_ID:
        return True

    licenses = load_licenses()
    uid = str(user_id)
    if uid not in licenses:
        return False

    expiry = licenses[uid]
    if expiry == -1:  # 永久ライセンス
        return True
    return time.time() < expiry


def get_license_expiry_text(user_id: int) -> str:
    """ライセンスの有効期限テキストを返す"""
    if user_id == OWNER_ID:
        return "永久（オーナー）"

    licenses = load_licenses()
    uid = str(user_id)
    if uid not in licenses:
        return "なし"

    expiry = licenses[uid]
    if expiry == -1:
        return "永久"

    remain = expiry - time.time()
    if remain <= 0:
        return "期限切れ"

    days = int(remain // 86400)
    hours = int((remain % 86400) // 3600)
    if days > 0:
        return f"残{days}日{hours}時間"
    return f"残{hours}時間"


def grant_license(user_id: int, days: int):
    """ライセンスを付与する（days=-1で永久）"""
    licenses = load_licenses()
    uid = str(user_id)

    if days == -1:
        licenses[uid] = -1
    else:
        current = licenses.get(uid, 0)
        now = time.time()
        # 既に有効なライセンスがあれば延長
        base = max(current, now)
        licenses[uid] = base + days * 86400

    save_licenses(licenses)


def revoke_license(user_id: int):
    """ライセンスを削除する"""
    licenses = load_licenses()
    licenses.pop(str(user_id), None)
    save_licenses(licenses)


# ====================== 権限チェック ======================
def is_owner():
    """オーナーのみ許可するデコレータ"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("🚫 このコマンドはオーナーのみ使用できます", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


def is_allowed():
    """ライセンスを持つユーザーのみ許可するデコレータ"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not has_valid_license(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Botの使用権限がありません。購入パネルから利用権を購入してください。",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)