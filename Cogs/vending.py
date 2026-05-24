import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from typing import List, Optional
from utils import is_allowed
import paypayu

VENDING_DATA_DIR = "data/vending_machines"
os.makedirs(VENDING_DATA_DIR, exist_ok=True)

def get_vending_dir(guild_id):
    path = os.path.join(VENDING_DATA_DIR, str(guild_id))
    os.makedirs(path, exist_ok=True)
    return path

def get_vending_path(guild_id, vending_id):
    return os.path.join(get_vending_dir(guild_id), f"{vending_id}.json")

def load_vending(guild_id, vending_id):
    path = get_vending_path(guild_id, vending_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None

def save_vending(guild_id, vending_id, data):
    path = get_vending_path(guild_id, vending_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_all_vendings(guild_id):
    path = get_vending_dir(guild_id)
    if not os.path.exists(path):
        return []
    files = [f for f in os.listdir(path) if f.endswith(".json")]
    results = []
    for f in files:
        vid = f.replace(".json", "")
        data = load_vending(guild_id, vid)
        if data:
            results.append((vid, data.get("name", "No Name")))
    return results

async def vending_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    vendings = get_all_vendings(interaction.guild.id)
    choices = []
    for vid, name in vendings:
        label = f"{name} ({vid})"
        if current.lower() in label.lower():
            choices.append(app_commands.Choice(name=label, value=vid))
    return choices[:25]

async def product_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    vending_id = interaction.namespace.id
    if not vending_id:
        return []
    data = load_vending(interaction.guild.id, vending_id)
    if not data:
        return []
    choices = []
    for pid, pdata in data.get("products", {}).items():
        label = f"{pdata['name']} ({pid})"
        if current.lower() in label.lower():
            choices.append(app_commands.Choice(name=label, value=pid))
    return choices[:25]

def generate_vending_embed(data):
    embed = discord.Embed(
        title=data["name"],
        description="下記ボタンを押して購入したい商品を選択してください",
        color=discord.Color.blue()
    )
    products = data.get("products", {})
    if products:
        for pid, product in products.items():
            infinite = product.get("infinite_stock", False)
            stock_text = "∞" if infinite else str(len(product.get("stock", [])))
            embed.add_field(
                name=f"**{product['name']}**",
                value=f"```値段: {product['price']}円\n在庫: {stock_text}```",
                inline=False
            )
    else:
        embed.add_field(name="お知らせ", value="現在販売中の商品はありません。", inline=False)
    embed.set_footer(text=f"ID: {data['id']} | created by @{data.get('owner_name', 'Unknown')}")
    return embed

async def update_public_panel(bot, guild_id, vending_id, data):
    for loc in data.get("panel_locations", []):
        channel_id = loc.get("channel_id")
        message_id = loc.get("message_id")
        if channel_id and message_id:
            try:
                channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                await message.edit(embed=generate_vending_embed(data), view=VendingPanelView(bot))
            except Exception:
                pass

class ProductSelectView(ui.View):
    def __init__(self, bot, guild_id, vending_id):
        super().__init__(timeout=300)
        data = load_vending(guild_id, vending_id)
        self.add_item(ProductSelect(bot, guild_id, vending_id, data))

class ProductSelect(ui.Select):
    def __init__(self, bot, guild_id, vending_id, data):
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id

        options = []
        for pid, product in data.get("products", {}).items():
            infinite = product.get("infinite_stock", False)
            stock_count = len(product.get("stock", []))
            if infinite:
                desc_text = f"値段: {product['price']}円 | 在庫: ∞"
            elif stock_count > 0:
                desc_text = f"値段: {product['price']}円 | 在庫: {stock_count}個"
            else:
                desc_text = f"値段: {product['price']}円 | ❌ 在庫切れ"
            options.append(discord.SelectOption(label=product["name"], value=pid, description=desc_text))

        super().__init__(
            placeholder="購入する商品を選択...",
            min_values=1, max_values=1,
            options=options if options else [discord.SelectOption(label="商品未登録", value="dummy")]
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "dummy":
            return await interaction.response.defer()

        data = load_vending(self.guild_id, self.vending_id)
        product = data["products"][self.values[0]]
        infinite = product.get("infinite_stock", False)
        stock = product.get("stock", [])

        if not infinite and len(stock) == 0:
            return await interaction.response.send_message("❌ この商品は在庫切れです。", ephemeral=True)

        embed = discord.Embed(title="購入確認", color=discord.Color.blue())
        embed.add_field(name="商品名", value=product["name"], inline=False)
        embed.add_field(name="価格", value=f"¥{product['price']}", inline=True)
        embed.add_field(name="在庫", value="∞個" if infinite else f"{len(stock)}個", inline=True)
        if product.get("description"):
            embed.add_field(name="説明", value=product["description"], inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=PurchaseConfirmView(self.bot, self.guild_id, self.vending_id, self.values[0]),
            ephemeral=True
        )

class PurchaseConfirmView(ui.View):
    def __init__(self, bot, guild_id, vending_id, product_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id
        self.product_id = product_id

    @ui.button(label="購入する", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        data = load_vending(self.guild_id, self.vending_id)
        if not data or self.product_id not in data.get("products", {}):
            return await interaction.response.send_message("自販機または商品が見つかりません。", ephemeral=True)

        product = data["products"][self.product_id]
        infinite = product.get("infinite_stock", False)
        stock = product.get("stock", [])

        if not infinite and len(stock) == 0:
            return await interaction.response.send_message("在庫切れです。", ephemeral=True)

        paypay_id = data.get("paypay_id")
        if not paypay_id:
            return await interaction.response.send_message("PayPayアカウントが設定されていません。", ephemeral=True)

        modal = PaymentLinkModal(self.bot, self.guild_id, self.vending_id, self.product_id, product, infinite)
        await interaction.response.send_modal(modal)

    @ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="購入をキャンセルしました。", embed=None, view=None)

class PaymentLinkModal(ui.Modal, title="PayPayリンク入力"):
    count_input = ui.TextInput(label="購入個数", placeholder="購入する個数を入力", max_length=3, required=True)
    link_input = ui.TextInput(label="PayPayリンク", placeholder="PayPayリンクを入力してください(0円の場合は空白)", required=False)
    password_input = ui.TextInput(label="パスワード", placeholder="パスワードがある場合のみ入力", required=False, max_length=4)

    def __init__(self, bot, guild_id, vending_id, product_id, product, infinite):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id
        self.product_id = product_id
        self.product = product
        self.infinite = infinite

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            count = int(self.count_input.value.strip())
            if count <= 0:
                raise ValueError
        except ValueError:
            return await interaction.followup.send("個数は1以上の半角数字で入力してください。", ephemeral=True)

        total_price = self.product["price"] * count

        if total_price == 0:
            data = load_vending(self.guild_id, self.vending_id)
            if not data or self.product_id not in data.get("products", {}):
                return await interaction.followup.send("自販機または商品が見つかりません。", ephemeral=True)

            product = data["products"][self.product_id]
            stock = product.get("stock", [])

            if not self.infinite and len(stock) < count:
                return await interaction.followup.send(
                    f"在庫が不足しています。現在の在庫: {len(stock)}個", ephemeral=True
                )

            if self.infinite:
                product_content = product.get("infinite_content", "")
                if not product_content:
                    return await interaction.followup.send(
                        "❌ 商品内容が設定されていません。管理者に連絡してください。", ephemeral=True
                    )
            else:
                product_content = stock[:count]
                product["stock"] = stock[count:]
                data["products"][self.product_id] = product

            save_vending(self.guild_id, self.vending_id, data)
            await update_public_panel(self.bot, self.guild_id, self.vending_id, data)

            if isinstance(product_content, list):
                delivery_text = "\n".join(product_content)
            else:
                delivery_text = str(product_content)

            dm_embed = discord.Embed(title="購入明細", color=0x57F287)
            dm_embed.add_field(name="商品名", value=product["name"], inline=False)
            dm_embed.add_field(name="購入個数", value=f"{count}個", inline=False)
            dm_embed.add_field(name="合計", value="0円", inline=False)
            dm_embed.set_footer(text="※ 商品の内容は上のコードブロックをご確認ください")

            try:
                await interaction.user.send(content=f"```\n{delivery_text}\n```", embed=dm_embed)
                await interaction.followup.send("✅ 無料で購入完了しました！詳細はDMをご確認ください。", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(content=f"```\n{delivery_text}\n```", embed=dm_embed, ephemeral=True)

            log_channel_id = data.get("log_channel_id")
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    log_embed = discord.Embed(title="🛒 購入ログ", color=discord.Color.purple())
                    log_embed.add_field(name="購入者", value=interaction.user.mention, inline=False)
                    log_embed.add_field(name="商品", value=f"```{product['name']}```", inline=False)
                    log_embed.add_field(name="購入個数", value=f"{count}個", inline=False)
                    log_embed.add_field(name="合計金額", value="0円 (無料)", inline=False)
                    try:
                        await log_channel.send(embed=log_embed)
                    except Exception:
                        pass
            return

        link = self.link_input.value.strip()
        if not link:
            return await interaction.followup.send("有料商品のため、PayPayリンクを入力してください。", ephemeral=True)

        password = self.password_input.value.strip() or None

        check_result = await paypayu.check_link(link)
        if not check_result:
            return await interaction.followup.send("無効なPayPayリンクです。", ephemeral=True)

        link_amount = check_result.get("payload", {}).get("pendingP2PInfo", {}).get("amount", 0)
        if link_amount != total_price:
            return await interaction.followup.send(
                f"リンクの金額(¥{link_amount})が合計金額(¥{total_price})と一致しません。", ephemeral=True
            )

        data = load_vending(self.guild_id, self.vending_id)
        paypay_id = data.get("paypay_id")
        paypay_data_path = "paypay_data.json"
        paypay_info = {}
        if os.path.exists(paypay_data_path):
            try:
                with open(paypay_data_path, "r", encoding="utf-8") as f:
                    all_paypay = json.load(f)
                    paypay_info = all_paypay.get(paypay_id, {})
            except Exception:
                pass

        if not paypay_info:
            return await interaction.followup.send("PayPayアカウント情報が見つかりません。", ephemeral=True)

        result = await paypayu.link_rev(link, paypay_info["phone"], paypay_info["password"], paypay_info["uuid"], password)

        if result == "LOGINERR":
            return await interaction.followup.send("PayPayログインエラーが発生しました。", ephemeral=True)
        if not result:
            return await interaction.followup.send("PayPayリンクの受取に失敗しました。", ephemeral=True)

        data = load_vending(self.guild_id, self.vending_id)
        product = data["products"][self.product_id]
        stock = product.get("stock", [])

        if self.infinite:
            product_content = product.get("infinite_content", "")
            if not product_content:
                return await interaction.followup.send(
                    "❌ 商品内容が設定されていません。管理者に連絡してください。", ephemeral=True
                )
        else:
            if len(stock) < count:
                return await interaction.followup.send(
                    "在庫が不足しています。PayPayリンクは受け取られましたが、商品を配送できません。管理者に連絡してください。", ephemeral=True
                )
            product_content = stock[:count]
            product["stock"] = stock[count:]

        data["products"][self.product_id] = product
        save_vending(self.guild_id, self.vending_id, data)
        await update_public_panel(self.bot, self.guild_id, self.vending_id, data)

        if isinstance(product_content, list):
            delivery_text = "\n".join(product_content)
        else:
            delivery_text = str(product_content)

        dm_embed = discord.Embed(title="購入明細", color=0x57F287)
        dm_embed.add_field(name="商品名", value=product["name"], inline=False)
        dm_embed.add_field(name="購入個数", value=f"{count}個", inline=False)
        dm_embed.add_field(name="合計", value=f"{total_price}円", inline=False)
        dm_embed.set_footer(text="※ 商品の内容は上のコードブロックをご確認ください")
        try:
            await interaction.user.send(content=f"```\n{delivery_text}\n```", embed=dm_embed)
            await interaction.followup.send("✅ 購入完了！商品情報はDMをご確認ください。", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(content=f"```\n{delivery_text}\n```", embed=dm_embed, ephemeral=True)

        log_channel_id = data.get("log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(title="🛒 購入ログ", color=discord.Color.purple())
                log_embed.add_field(name="購入者", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="商品", value=f"```{product['name']}```", inline=False)
                log_embed.add_field(name="購入個数", value=f"{count}個", inline=False)
                log_embed.add_field(name="合計金額", value=f"{total_price}円", inline=False)
                try:
                    await log_channel.send(embed=log_embed)
                except Exception:
                    pass

class VendingPanelView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    def get_vending_id(self, interaction: discord.Interaction):
        if not interaction.message or not interaction.message.embeds:
            return None
        footer = interaction.message.embeds[0].footer.text or ""
        if footer.startswith("ID: "):
            return footer.split(" | ")[0].replace("ID: ", "")
        return None

    @ui.button(label="購入する", style=discord.ButtonStyle.green, custom_id="vending:buy", emoji="🛒")
    async def buy_button(self, interaction: discord.Interaction, button: ui.Button):
        vending_id = self.get_vending_id(interaction)
        if not vending_id:
            return await interaction.response.send_message("❌ 自販機IDの取得に失敗しました。", ephemeral=True)

        data = load_vending(interaction.guild.id, vending_id)
        if not data or not data.get("products"):
            return await interaction.response.send_message("❌ 現在販売中の商品がありません。", ephemeral=True)

        embed = discord.Embed(
            title=f"{data['name']} - 商品選択",
            description="購入したい商品を以下から選択してください。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=ProductSelectView(self.bot, interaction.guild.id, vending_id), ephemeral=True)

    @ui.button(label="在庫確認", style=discord.ButtonStyle.secondary, custom_id="vending:stock", emoji="📦")
    async def stock_button(self, interaction: discord.Interaction, button: ui.Button):
        vending_id = self.get_vending_id(interaction)
        if not vending_id:
            return await interaction.response.send_message("❌ 自販機IDの取得に失敗しました。", ephemeral=True)

        data = load_vending(interaction.guild.id, vending_id)
        if not data:
            return await interaction.response.send_message("❌ 自販機データが見つかりません。", ephemeral=True)

        embed = generate_vending_embed(data)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ProductEditModal(ui.Modal, title="商品情報変更"):
    name_input = ui.TextInput(label="商品名", placeholder="商品名", max_length=100, required=True)
    price_input = ui.TextInput(label="価格", placeholder="価格(0=無料)", max_length=10, required=True)
    description_input = ui.TextInput(label="説明", placeholder="商品の説明", style=discord.TextStyle.paragraph, required=False, max_length=500)
    infinite_input = ui.TextInput(label="在庫無限", placeholder="はい いいえ", max_length=3, required=True)

    def __init__(self, bot, guild_id, vending_id, product_id, current_product):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id
        self.product_id = product_id
        self.name_input.default = current_product.get("name", "")
        self.price_input.default = str(current_product.get("price", 0))
        self.description_input.default = current_product.get("description", "")
        self.infinite_input.default = "はい" if current_product.get("infinite_stock", False) else "いいえ"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price = int(self.price_input.value)
            if price < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ 価格は0以上の整数で入力してください。", ephemeral=True)

        infinite = self.infinite_input.value.strip() in ["はい", "yes", "y"]
        data = load_vending(self.guild_id, self.vending_id)
        if not data or self.product_id not in data.get("products", {}):
            return await interaction.response.send_message("❌ 自販機または商品が見つかりません。", ephemeral=True)

        product = data["products"][self.product_id]
        product["name"] = self.name_input.value
        product["price"] = price
        product["description"] = self.description_input.value
        product["infinite_stock"] = infinite
        save_vending(self.guild_id, self.vending_id, data)
        await update_public_panel(self.bot, self.guild_id, self.vending_id, data)

        embed = discord.Embed(title="✅ 商品情報を変更しました", color=discord.Color.green())
        embed.add_field(name="商品名", value=product["name"], inline=False)
        embed.add_field(name="価格", value=f"¥{product['price']}", inline=True)
        embed.add_field(name="在庫無限", value="はい" if product["infinite_stock"] else "いいえ", inline=True)
        if product["description"]:
            embed.add_field(name="説明", value=product["description"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class StockAddModal(ui.Modal, title="在庫追加"):
    stock_input = ui.TextInput(
        label="商品内容",
        placeholder="有限在庫: 1行に1つずつ入力\n在庫無限: 購入時に送る内容を入力",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    def __init__(self, bot, guild_id, vending_id, product_id, is_infinite=False):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id
        self.product_id = product_id
        self.is_infinite = is_infinite

        data = load_vending(guild_id, vending_id)
        if data and product_id in data.get("products", {}):
            product = data["products"][product_id]
            if is_infinite:
                self.stock_input.default = product.get("infinite_content", "")
            else:
                current_stock = product.get("stock", [])
                self.stock_input.default = "\n".join(current_stock)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        new_content_raw = self.stock_input.value

        data = load_vending(self.guild_id, self.vending_id)
        if not data or self.product_id not in data.get("products", {}):
            return await interaction.followup.send("❌ 自販機または商品が見つかりません。", ephemeral=True)

        product = data["products"][self.product_id]

        if self.is_infinite:
            old_content = product.get("infinite_content", "")
            if old_content:
                try:
                    await interaction.user.send(
                        content=f"📦 **{product['name']}** の旧在庫内容:\n```\n{old_content}\n```"
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        f"⚠️ DMを送信できませんでした。旧在庫内容:\n```\n{old_content[:1000]}\n```", ephemeral=True
                    )

            product["infinite_content"] = new_content_raw
            stock_count_text = "∞"
        else:
            lines = [line.strip() for line in new_content_raw.split("\n") if line.strip()]
            if not lines:
                return await interaction.followup.send("❌ 有効な在庫が入力されていません。", ephemeral=True)
            product["stock"] = lines
            stock_count_text = f"{len(lines)}件"

        save_vending(self.guild_id, self.vending_id, data)
        await update_public_panel(self.bot, self.guild_id, self.vending_id, data)

        embed = discord.Embed(title="✅ 在庫を更新しました", color=discord.Color.green())
        embed.add_field(name="商品名", value=product["name"], inline=False)
        embed.add_field(name="現在の在庫数", value=stock_count_text, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

        notif_ch_id = data.get("stock_notification_channel_id")
        notif_role_id = data.get("stock_notification_role_id")
        if notif_ch_id:
            notif_ch = interaction.guild.get_channel(notif_ch_id)
            if notif_ch:
                notif_embed = discord.Embed(
                    title="🔔 在庫追加通知",
                    description=f"@{interaction.user.name} が在庫を更新しました",
                    color=discord.Color.blue()
                )
                notif_embed.add_field(name="商品名", value=product["name"], inline=False)
                notif_embed.add_field(name="在庫数", value=stock_count_text, inline=False)
                notif_embed.set_footer(text=f"更新者: {interaction.user.name}")
                try:
                    if notif_role_id:
                        role = interaction.guild.get_role(notif_role_id)
                        await notif_ch.send(content=role.mention if role else None, embed=notif_embed)
                    else:
                        await notif_ch.send(embed=notif_embed)
                except Exception:
                    pass

class VendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    vm = app_commands.Group(
        name="vm",
        description="自販機システム",
    )

    @vm.command(name="create", description="新しい自販機を作成します")
    @is_allowed()
    @app_commands.describe(id="自販機ID(半角英数字)", name="自販機名")
    async def create(self, interaction: discord.Interaction, id: str, name: str):
        if load_vending(interaction.guild.id, id):
            return await interaction.response.send_message(f"ID `{id}` は既に存在します。", ephemeral=True)

        data = {
            "id": id,
            "name": name,
            "owner_id": interaction.user.id,
            "owner_name": interaction.user.name,
            "paypay_id": str(interaction.user.id),
            "products": {},
            "panel_locations": [],
            "stock_notification_channel_id": None,
            "stock_notification_role_id": None,
            "log_channel_id": None,
        }
        save_vending(interaction.guild.id, id, data)

        embed = discord.Embed(title="✅ 自販機を作成しました", color=discord.Color.green())
        embed.add_field(name="ID", value=f"`{id}`", inline=True)
        embed.add_field(name="自販機名", value=name, inline=True)
        embed.add_field(name="次のステップ", value="`/vm product_add` で商品を登録し、`/vm panel_set` でパネルを設置してください。", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="delete", description="自販機のデータを削除します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="削除する自販機のID")
    async def delete(self, interaction: discord.Interaction, id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)

        for loc in data.get("panel_locations", []):
            ch = self.bot.get_channel(loc["channel_id"])
            if ch:
                try:
                    msg = await ch.fetch_message(loc["message_id"])
                    await msg.delete()
                except Exception:
                    pass

        path = get_vending_path(interaction.guild.id, id)
        os.remove(path)

        embed = discord.Embed(title="自販機を削除しました", color=discord.Color.green())
        embed.add_field(name="削除した自販機", value=f"{data['name']} (`{id}`)", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="panel_set", description="自販機パネルをこのチャンネルに設置します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID")
    async def panel_set(self, interaction: discord.Interaction, id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"❌ ID `{id}` が見つかりません。", ephemeral=True)
        if not data.get("products"):
            return await interaction.response.send_message("❌ 商品が登録されていません。先に `/vm product_add` で商品を追加してください。", ephemeral=True)

        embed = generate_vending_embed(data)
        view = VendingPanelView(self.bot)
        try:
            message = await interaction.channel.send(embed=embed, view=view)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ チャンネルへの送信権限がありません。", ephemeral=True)

        data.setdefault("panel_locations", [])
        data["panel_locations"].append({"channel_id": interaction.channel.id, "message_id": message.id})
        save_vending(interaction.guild.id, id, data)
        await interaction.response.send_message("✅ パネルを設置しました。", ephemeral=True)

    @vm.command(name="panel_remove", description="設置された自販機パネルを削除します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID", message_id="削除するパネルのメッセージID")
    async def panel_remove(self, interaction: discord.Interaction, id: str, message_id: str = None):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"❌ ID `{id}` が見つかりません。", ephemeral=True)

        locations = data.get("panel_locations", [])
        if not locations:
            return await interaction.response.send_message("❌ 設置されているパネルがありません。", ephemeral=True)

        removed = 0
        new_locations = []
        for loc in locations:
            if message_id is None or str(loc["message_id"]) == message_id:
                ch = self.bot.get_channel(loc["channel_id"])
                if ch:
                    try:
                        msg = await ch.fetch_message(loc["message_id"])
                        await msg.delete()
                        removed += 1
                    except Exception:
                        pass
            else:
                new_locations.append(loc)

        data["panel_locations"] = new_locations
        save_vending(interaction.guild.id, id, data)
        await interaction.response.send_message(f"✅ {removed}件のパネルを削除しました。", ephemeral=True)

    @vm.command(name="panel_update", description="パネルを最新の情報に更新します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID")
    async def panel_update(self, interaction: discord.Interaction, id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        await update_public_panel(self.bot, interaction.guild.id, id, data)
        await interaction.response.send_message("✅ パネルを更新しました。", ephemeral=True)

    @vm.command(name="product_add", description="自販機に商品を追加します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(
        id="自販機のID",
        product_name="商品名",
        price="価格(0=無料)",
        description="商品説明(任意)",
        infinite_stock="在庫無限(はい/いいえ)"
    )
    async def product_add(
        self, interaction: discord.Interaction,
        id: str, product_name: str, price: int,
        description: str = "", infinite_stock: str = "いいえ"
    ):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        if price < 0:
            return await interaction.response.send_message("価格は0以上の整数で指定してください。", ephemeral=True)

        products = data.setdefault("products", {})
        product_id = f"prod_{len(products) + 1}"
        is_infinite = infinite_stock.strip() in ["はい", "yes", "y"]

        products[product_id] = {
            "name": product_name,
            "price": price,
            "description": description,
            "stock": [],
            "infinite_stock": is_infinite,
            "infinite_content": "",
        }
        save_vending(interaction.guild.id, id, data)
        await update_public_panel(self.bot, interaction.guild.id, id, data)

        embed = discord.Embed(title="✅ 商品を追加しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=False)
        embed.add_field(name="商品ID", value=product_id, inline=True)
        embed.add_field(name="商品名", value=product_name, inline=True)
        embed.add_field(name="価格", value=f"¥{price}", inline=True)
        embed.add_field(name="在庫無限", value="はい" if is_infinite else "いいえ", inline=True)
        if description:
            embed.add_field(name="説明", value=description, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="product_delete", description="商品を削除します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete, product_id=product_autocomplete)
    @app_commands.describe(id="自販機のID", product_id="削除する商品のID")
    async def product_delete(self, interaction: discord.Interaction, id: str, product_id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        if product_id not in data.get("products", {}):
            return await interaction.response.send_message(f"商品 `{product_id}` が見つかりません。", ephemeral=True)

        product_name = data["products"][product_id]["name"]
        del data["products"][product_id]
        save_vending(interaction.guild.id, id, data)
        await update_public_panel(self.bot, interaction.guild.id, id, data)

        embed = discord.Embed(title="商品を削除しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=True)
        embed.add_field(name="商品", value=f"{product_name} (`{product_id}`)", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="product_edit", description="商品の情報を変更します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete, product_id=product_autocomplete)
    @app_commands.describe(id="自販機のID", product_id="編集する商品のID")
    async def product_edit(self, interaction: discord.Interaction, id: str, product_id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        if product_id not in data.get("products", {}):
            return await interaction.response.send_message(f"商品 `{product_id}` が見つかりません。", ephemeral=True)

        modal = ProductEditModal(self.bot, interaction.guild.id, id, product_id, data["products"][product_id])
        await interaction.response.send_modal(modal)

    @vm.command(name="stock_add", description="商品に在庫を追加します(在庫無限の場合は現在の在庫をDMに送信してから追加します)")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete, product_id=product_autocomplete)
    @app_commands.describe(id="自販機のID", product_id="在庫を追加する商品のID")
    async def stock_add(self, interaction: discord.Interaction, id: str, product_id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        if product_id not in data.get("products", {}):
            return await interaction.response.send_message(f"商品 `{product_id}` が見つかりません。", ephemeral=True)
        
        is_infinite = data["products"][product_id].get("infinite_stock", False)
        
        if is_infinite:
            embed = discord.Embed(
                title="⚠️ 在庫無限商品の在庫追加",
                description="この商品は在庫無限に設定されています。\n"
                            "在庫を追加すると、**現在の在庫をすべてDMに送信してから**新しい在庫を追加します。\n\n"
                            "よろしければ下のボタンを押してください。",
                color=discord.Color.yellow()
            )
            view = InfiniteStockConfirmView(self.bot, interaction.guild.id, id, product_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            modal = StockAddModal(self.bot, interaction.guild.id, id, product_id, is_infinite=False)
            await interaction.response.send_modal(modal)

    @vm.command(name="stock_withdraw", description="商品の在庫を引き出します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete, product_id=product_autocomplete)
    @app_commands.describe(
        id="自販機のID",
        product_id="在庫を引き出す商品のID",
        count="引き出す個数",
        infinite_mode="在庫無限の場合0=在庫なし 1=在庫継続"
    )
    async def stock_withdraw(self, interaction: discord.Interaction, id: str, product_id: str, count: int, infinite_mode: int = 0):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)
        if product_id not in data.get("products", {}):
            return await interaction.response.send_message(f"商品 `{product_id}` が見つかりません。", ephemeral=True)

        product = data["products"][product_id]
        is_infinite = product.get("infinite_stock", False)

        if is_infinite:
            if infinite_mode not in (0, 1):
                return await interaction.response.send_message("`infinite_mode` は 0 または 1 を指定してください。", ephemeral=True)

            infinite_content = product.get("infinite_content", "")

            if infinite_mode == 0:
                product["infinite_stock"] = False
                product["infinite_content"] = ""
                save_vending(interaction.guild.id, id, data)
                await update_public_panel(self.bot, interaction.guild.id, id, data)

                embed = discord.Embed(title="✅ 在庫無限を解除しました", color=discord.Color.orange())
                embed.add_field(name="商品名", value=product["name"], inline=False)
                embed.add_field(name="在庫無限", value="OFF", inline=True)
                embed.add_field(name="在庫数", value=f"{len(product.get('stock', []))}個", inline=True)
                if infinite_content:
                    embed.add_field(name="削除した内容", value=f"```{infinite_content[:500]}```", inline=False)
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            else:  
                if not infinite_content:
                    return await interaction.response.send_message("在庫無限の内容が設定されていません。", ephemeral=True)

                try:
                    await interaction.user.send(content=f"```\n{infinite_content}\n```")
                    embed = discord.Embed(title="✅ 在庫無限の内容をDMに送信しました", color=discord.Color.green())
                    embed.add_field(name="商品名", value=product["name"], inline=False)
                    embed.add_field(name="在庫無限", value="ON", inline=True)
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                except discord.Forbidden:
                    return await interaction.response.send_message(
                        f"DMを送信できませんでした。\n```\n{infinite_content[:500]}\n```", ephemeral=True
                    )

        if count <= 0:
            return await interaction.response.send_message("個数は1以上で指定してください。", ephemeral=True)

        stock = product.get("stock", [])
        if count > len(stock):
            return await interaction.response.send_message(
                f"在庫が不足しています。現在の在庫: {len(stock)}個", ephemeral=True
            )

        withdrawn = stock[:count]
        product["stock"] = stock[count:]
        save_vending(interaction.guild.id, id, data)
        await update_public_panel(self.bot, interaction.guild.id, id, data)

        withdrawn_text = "\n".join(withdrawn)
        embed = discord.Embed(title="✅ 在庫を引き出しました", color=discord.Color.green())
        embed.add_field(name="商品名", value=product["name"], inline=False)
        embed.add_field(name="引き出した個数", value=f"{len(withdrawn)}個", inline=True)
        embed.add_field(name="残りの在庫", value=f"{len(product['stock'])}個", inline=True)

        try:
            await interaction.user.send(content=f"```\n{withdrawn_text}\n```")
            embed.add_field(name="内容", value="DMに送信しました", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed.add_field(name="引き出した内容", value=f"```{withdrawn_text[:1000]}```", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="notif_set", description="在庫追加通知チャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID", channel="通知を送信するチャンネル", role="メンションするロール")
    async def notif_set(
        self, interaction: discord.Interaction,
        id: str, channel: discord.TextChannel, role: discord.Role = None
    ):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)

        data["stock_notification_channel_id"] = channel.id
        data["stock_notification_role_id"] = role.id if role else None
        save_vending(interaction.guild.id, id, data)

        embed = discord.Embed(title="✅ 在庫追加通知を設定しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=True)
        embed.add_field(name="チャンネル", value=channel.mention, inline=True)
        if role:
            embed.add_field(name="メンションロール", value=role.mention, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="notif_remove", description="在庫追加通知の設定を削除します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID")
    async def notif_remove(self, interaction: discord.Interaction, id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)

        data["stock_notification_channel_id"] = None
        data["stock_notification_role_id"] = None
        save_vending(interaction.guild.id, id, data)

        embed = discord.Embed(title="在庫追加通知を削除しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="log_set", description="購入ログを送信するチャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID", channel="ログを送信するチャンネル")
    async def log_set(self, interaction: discord.Interaction, id: str, channel: discord.TextChannel):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)

        data["log_channel_id"] = channel.id
        save_vending(interaction.guild.id, id, data)

        embed = discord.Embed(title="✅ 購入ログチャンネルを設定しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=True)
        embed.add_field(name="チャンネル", value=channel.mention, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @vm.command(name="log_remove", description="購入ログチャンネルの設定を削除します")
    @is_allowed()
    @app_commands.autocomplete(id=vending_autocomplete)
    @app_commands.describe(id="自販機のID")
    async def log_remove(self, interaction: discord.Interaction, id: str):
        data = load_vending(interaction.guild.id, id)
        if not data:
            return await interaction.response.send_message(f"ID `{id}` が見つかりません。", ephemeral=True)

        data["log_channel_id"] = None
        save_vending(interaction.guild.id, id, data)

        embed = discord.Embed(title="購入ログチャンネルを削除しました", color=discord.Color.green())
        embed.add_field(name="自販機", value=data["name"], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VendingPanelView(self.bot))

class InfiniteStockConfirmView(ui.View):
    def __init__(self, bot, guild_id, vending_id, product_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.vending_id = vending_id
        self.product_id = product_id

    @ui.button(label="はい、在庫を追加する", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = StockAddModal(self.bot, self.guild_id, self.vending_id, self.product_id, is_infinite=True)
        await interaction.response.send_modal(modal)

    @ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="キャンセルしました。", embed=None, view=None)

async def setup(bot):
    await bot.add_cog(VendingCog(bot))
    bot.add_view(VendingPanelView(bot))