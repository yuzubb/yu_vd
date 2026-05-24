import discord
from discord import app_commands, ui
from discord.ext import commands
from discord.ui import Button, View, Select
import aiohttp
from bs4 import BeautifulSoup
import os
import io
import json
import urllib.parse
import asyncio
import paypayu
from utils import is_allowed, is_owner

# ==========================================
# 設定
# ==========================================
BASE_URL = os.getenv("BASE_URL", "https://momon-ga.com")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

MANGA_PRICE = 50  # 閲覧料金（円）
PAYPAY_DATA_FILE = "paypay_data.json"
MANGA_PAYPAY_OWNER_FILE = "manga_paypay_owner.json"
MANGA_PANEL_FILE = "manga_panel.json"  # パネル設置場所の保存


# ==========================================
# データ管理
# ==========================================

def load_paypay_data():
    if os.path.exists(PAYPAY_DATA_FILE):
        with open(PAYPAY_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_manga_paypay_owner():
    if os.path.exists(MANGA_PAYPAY_OWNER_FILE):
        with open(MANGA_PAYPAY_OWNER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manga_paypay_owner(data):
    with open(MANGA_PAYPAY_OWNER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_manga_panels():
    if os.path.exists(MANGA_PANEL_FILE):
        with open(MANGA_PANEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_manga_panels(data):
    with open(MANGA_PANEL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ==========================================
# スクレイピング・データ取得ロジック
# ==========================================

async def search_manga(query: str):
    """タイトル検索を行う関数"""
    encoded_query = urllib.parse.quote(query)
    url = f"{BASE_URL}/?s={encoded_query}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            results = []
            items = soup.select('.post-list > a')

            for item in items:
                span_tag = item.find('span')
                if span_tag:
                    title = span_tag.get_text(strip=True)
                else:
                    img_tag = item.find('img')
                    title = img_tag.get('alt', '').strip() if img_tag else "無題の作品"

                href = item.get('href')

                if title and href:
                    results.append({"title": title, "url": href})

            return results[:25]


async def get_pages(manga_url: str):
    """作品ページからすべての漫画画像URLを取得する関数"""
    async with aiohttp.ClientSession() as session:
        async with session.get(manga_url, headers=HEADERS) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            pages = []
            main_area = soup.select_one('.main-area')
            target_soup = main_area if main_area else soup

            for img in target_soup.find_all('img'):
                src = img.get('data-src') or img.get('src')
                if src:
                    src_lower = src.lower()
                    if any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if 'logo' not in src_lower and 'icon' not in src_lower and 'avatar' not in src_lower:
                            if src not in pages:
                                pages.append(src)

            return pages


# ==========================================
# パネル Embed 生成
# ==========================================

def generate_manga_panel_embed():
    embed = discord.Embed(
        title="📚 漫画ビューア",
        description=(
            "漫画を検索して閲覧できます。\n\n"
            "🔍 **検索は無料**\n"
            f"📖 **閲覧は¥{MANGA_PRICE}（1回ごと）**\n\n"
            "下のボタンを押して漫画を検索してください。"
        ),
        color=0x2b2d31
    )
    embed.set_footer(text="manga-panel | Powered by momon-ga.com")
    return embed


# ==========================================
# Discord UI
# ==========================================

class MangaReaderView(View):
    """漫画をめくるためのビュー"""
    def __init__(self, pages, title):
        super().__init__(timeout=300)
        self.pages = pages
        self.title = title
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page == len(self.pages) - 1

    def make_embed(self):
        embed = discord.Embed(
            title=self.title,
            description=f"ページ: **{self.current_page + 1}** / {len(self.pages)}",
            color=0x2b2d31
        )
        embed.set_image(url=self.pages[self.current_page])
        return embed

    @discord.ui.button(label="◀ 前へ", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="次へ ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="終了", style=discord.ButtonStyle.danger, row=0)
    async def close_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ 閲覧を終了しました。", embeds=[], view=None)
        self.stop()


class MangaPaymentModal(ui.Modal, title="PayPay支払い"):
    """PayPayリンクを受け取るモーダル"""
    link_input = ui.TextInput(
        label="PayPayリンク",
        placeholder="https://pay.paypay.ne.jp/XXXXXXXXXX",
        required=True
    )
    password_input = ui.TextInput(
        label="パスワード（設定されている場合のみ）",
        placeholder="パスワードがある場合のみ入力",
        required=False,
        max_length=4
    )

    def __init__(self, manga_url: str, manga_title: str):
        super().__init__()
        self.manga_url = manga_url
        self.manga_title = manga_title

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = self.link_input.value.strip()
        password = self.password_input.value.strip() or None

        check_result = await paypayu.check_link(link)
        if not check_result:
            await interaction.followup.send("❌ 無効なPayPayリンクです。有効なリンクを貼り付けてください。", ephemeral=True)
            return

        link_amount = check_result.get("payload", {}).get("pendingP2PInfo", {}).get("amount", 0)
        if link_amount != MANGA_PRICE:
            await interaction.followup.send(
                f"❌ リンクの金額（¥{link_amount}）が正しくありません。¥{MANGA_PRICE}のPayPayリンクを送ってください。",
                ephemeral=True
            )
            return

        is_passcode = check_result.get("payload", {}).get("pendingP2PInfo", {}).get("isSetPasscode", False)
        if is_passcode and password is None:
            await interaction.followup.send(
                "⚠️ このリンクにはパスコードが設定されています。パスワード欄に入力してください。",
                ephemeral=True
            )
            return

        owner_data = load_manga_paypay_owner()
        owner_id = owner_data.get("owner_id")
        if not owner_id:
            await interaction.followup.send(
                "❌ 管理者がPayPayアカウントを設定していません。`/manga支払い設定` で設定が必要です。",
                ephemeral=True
            )
            return

        paypay_data = load_paypay_data()
        paypay_info = paypay_data.get(str(owner_id))
        if not paypay_info:
            await interaction.followup.send("❌ PayPayアカウント情報が見つかりません。管理者に連絡してください。", ephemeral=True)
            return

        result = await paypayu.link_rev(
            link,
            paypay_info["phone"],
            paypay_info["password"],
            paypay_info["uuid"],
            password
        )

        if result == "LOGINERR":
            await interaction.followup.send("❌ PayPayログインエラーが発生しました。管理者に連絡してください。", ephemeral=True)
            return

        if not result:
            await interaction.followup.send(
                "❌ PayPayリンクの受け取りに失敗しました。リンクの有効期限が切れているか、すでに使用済みの可能性があります。",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ **¥{MANGA_PRICE}の支払いを確認しました！**\n「{self.manga_title}」を読み込んでいます...",
            ephemeral=True
        )

        pages = await get_pages(self.manga_url)

        if not pages:
            await interaction.followup.send("⚠️ 漫画画像の取得に失敗しました。URLが正しいか確認してください。", ephemeral=True)
            return

        view = MangaReaderView(pages, self.manga_title)
        await interaction.followup.send(embed=view.make_embed(), view=view, ephemeral=True)


class MangaPaymentView(View):
    """支払いボタンを表示するビュー"""
    def __init__(self, manga_url: str, manga_title: str):
        super().__init__(timeout=300)
        self.manga_url = manga_url
        self.manga_title = manga_title

    @discord.ui.button(label="💴 50円を支払って読む", style=discord.ButtonStyle.success)
    async def pay_button(self, interaction: discord.Interaction, button: Button):
        modal = MangaPaymentModal(self.manga_url, self.manga_title)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ キャンセルしました。", embeds=[], view=None)
        self.stop()


class MangaSelect(Select):
    """検索結果から作品を選択するセレクトメニュー"""
    def __init__(self, results):
        options = [
            discord.SelectOption(label=res['title'][:100], value=res['url'])
            for res in results
        ]
        super().__init__(placeholder="読みたい作品を選択してください...", options=options)

    async def callback(self, interaction: discord.Interaction):
        from utils import OWNER_ID
        selected_title = "無題"
        for option in self.options:
            if option.value == self.values[0]:
                selected_title = option.label
                break

        manga_url = self.values[0]

        # オーナーは支払いなしで直接閲覧
        if interaction.user.id == OWNER_ID:
            await interaction.response.defer(ephemeral=True)
            pages = await get_pages(manga_url)
            if not pages:
                await interaction.followup.send("⚠️ 漫画画像の取得に失敗しました。URLが正しいか確認してください。", ephemeral=True)
                return
            view = MangaReaderView(pages, selected_title)
            await interaction.followup.send(embed=view.make_embed(), view=view, ephemeral=True)
            return

        embed = discord.Embed(
            title="📖 漫画閲覧 - 支払い確認",
            color=0xf7a800
        )
        embed.add_field(name="作品名", value=f"**{selected_title}**", inline=False)
        embed.add_field(name="閲覧料金", value=f"**¥{MANGA_PRICE}**（1回限り）", inline=False)
        embed.add_field(
            name="支払い方法",
            value=(
                "1. PayPayアプリで **¥50のリンク** を作成してください\n"
                "2. 「💴 50円を支払って読む」ボタンを押す\n"
                "3. 表示されるフォームにリンクを貼り付けてください\n"
                "4. 支払い確認後、すぐに閲覧できます"
            ),
            inline=False
        )
        embed.set_footer(text="⚠️ 支払いは1回の閲覧のみ有効です。次回また¥50が必要です。")

        view = MangaPaymentView(manga_url, selected_title)
        await interaction.response.edit_message(embed=embed, view=view)


class MangaSearchModal(ui.Modal, title="漫画検索"):
    """パネルから検索するためのモーダル"""
    query_input = ui.TextInput(
        label="タイトル",
        placeholder="検索したい漫画のタイトルを入力...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        from utils import OWNER_ID
        await interaction.response.defer(ephemeral=True)

        results = await search_manga(self.query_input.value)

        if not results:
            await interaction.followup.send("❌ 該当する漫画が見つかりませんでした。", ephemeral=True)
            return

        view = View()
        view.add_item(MangaSelect(results))

        is_owner_user = interaction.user.id == OWNER_ID
        description = (
            f"「{self.query_input.value}」の検索結果です。\n\n🆓 **オーナー権限：完全無料で閲覧できます**"
            if is_owner_user else
            f"「{self.query_input.value}」の検索結果です。\n以下から作品を選ぶと**¥{MANGA_PRICE}**で閲覧できます。\n\n🆓 検索は無料です"
        )
        embed = discord.Embed(
            title="🔍 検索結果",
            description=description,
            color=0x2b2d31
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class MangaPanelView(ui.View):
    """常設パネル用ビュー（timeout=None でBot再起動後も有効）"""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔍 漫画を検索する", style=discord.ButtonStyle.primary, custom_id="manga_panel:search")
    async def search_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = MangaSearchModal()
        await interaction.response.send_modal(modal)


# ==========================================
# Cogクラス (スラッシュコマンド)
# ==========================================
class MangaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Bot起動時にパネルのViewを永続化登録"""
        self.bot.add_view(MangaPanelView())

    # ---- パネル更新ヘルパー ----
    async def update_all_panels(self):
        panels = load_manga_panels()
        new_panels = []
        for loc in panels:
            try:
                channel = self.bot.get_channel(loc["channel_id"]) or await self.bot.fetch_channel(loc["channel_id"])
                message = await channel.fetch_message(loc["message_id"])
                await message.edit(embed=generate_manga_panel_embed(), view=MangaPanelView())
                new_panels.append(loc)
            except Exception:
                pass  # メッセージが消えていた場合はリストから除外
        save_manga_panels(new_panels)

    # ---- 検索コマンド ----
    @app_commands.command(name="漫画", description="momon-ga.com から漫画を検索して視聴します（閲覧は¥50）")
    @is_allowed()
    @app_commands.describe(query="検索したい漫画のタイトル")
    async def manga_search(self, interaction: discord.Interaction, query: str):
        from utils import OWNER_ID
        await interaction.response.defer(ephemeral=True)

        results = await search_manga(query)

        if not results:
            await interaction.followup.send("❌ 該当する漫画が見つかりませんでした。", ephemeral=True)
            return

        view = View()
        view.add_item(MangaSelect(results))

        is_owner_user = interaction.user.id == OWNER_ID
        description = (
            f"「{query}」の検索結果です。\n\n🆓 **オーナー権限：完全無料で閲覧できます**"
            if is_owner_user else
            f"「{query}」の検索結果です。\n以下から作品を選ぶと**¥{MANGA_PRICE}**で閲覧できます。\n\n🆓 検索は無料です"
        )
        embed = discord.Embed(
            title="🔍 検索結果",
            description=description,
            color=0x2b2d31
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # ---- パネル管理コマンドグループ（設置・削除は管理者のみ、パネル自体は全員が使用可能）----
    manga_panel = app_commands.Group(
        name="漫画パネル",
        description="漫画パネルの管理（設置・削除は管理者のみ）",
        default_permissions=discord.Permissions(administrator=True)
    )

    @manga_panel.command(name="set", description="このチャンネルに漫画検索パネルを設置します（誰でも使えるパネルが設置されます）")
    async def panel_set(self, interaction: discord.Interaction):
        try:
            message = await interaction.channel.send(
                embed=generate_manga_panel_embed(),
                view=MangaPanelView()
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ チャンネルへの送信権限がありません。", ephemeral=True)
            return

        panels = load_manga_panels()
        panels.append({
            "channel_id": interaction.channel.id,
            "message_id": message.id,
            "guild_id": interaction.guild.id
        })
        save_manga_panels(panels)

        await interaction.response.send_message(
            f"✅ 漫画パネルを設置しました。\nチャンネル: {interaction.channel.mention}",
            ephemeral=True
        )

    @manga_panel.command(name="remove", description="設置済みの漫画パネルを削除します")
    @app_commands.describe(message_id="削除するパネルのメッセージID（省略すると全パネルを削除）")
    async def panel_remove(self, interaction: discord.Interaction, message_id: str = None):
        panels = load_manga_panels()
        if not panels:
            await interaction.response.send_message("❌ 設置されているパネルがありません。", ephemeral=True)
            return

        removed = 0
        new_panels = []
        for loc in panels:
            if message_id is None or str(loc["message_id"]) == message_id:
                try:
                    channel = self.bot.get_channel(loc["channel_id"]) or await self.bot.fetch_channel(loc["channel_id"])
                    msg = await channel.fetch_message(loc["message_id"])
                    await msg.delete()
                    removed += 1
                except Exception:
                    removed += 1  # すでに消えていてもカウント
            else:
                new_panels.append(loc)

        save_manga_panels(new_panels)
        await interaction.response.send_message(f"✅ {removed}件のパネルを削除しました。", ephemeral=True)

    @manga_panel.command(name="update", description="設置済みの全パネルを最新の表示に更新します")
    async def panel_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.update_all_panels()
        await interaction.followup.send("✅ パネルを更新しました。", ephemeral=True)

    @manga_panel.command(name="list", description="設置済みのパネル一覧を表示します")
    async def panel_list(self, interaction: discord.Interaction):
        panels = load_manga_panels()
        if not panels:
            await interaction.response.send_message("現在パネルは設置されていません。", ephemeral=True)
            return

        lines = []
        for loc in panels:
            ch = self.bot.get_channel(loc["channel_id"])
            ch_str = ch.mention if ch else f"(ID: {loc['channel_id']})"
            lines.append(f"• {ch_str} — メッセージID: `{loc['message_id']}`")

        embed = discord.Embed(
            title="📋 設置済み漫画パネル一覧",
            description="\n".join(lines),
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- PayPay受取設定 ----
    @app_commands.command(name="manga支払い設定", description="漫画閲覧料金の受取PayPayアカウントを設定します（オーナー専用）")
    @is_owner()
    async def manga_paypay_setup(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        paypay_data = load_paypay_data()

        if user_id_str not in paypay_data:
            await interaction.response.send_message(
                "❌ PayPayアカウントが登録されていません。先に `/paypayログイン` でPayPayアカウントを登録してください。",
                ephemeral=True
            )
            return

        save_manga_paypay_owner({"owner_id": user_id_str})

        await interaction.response.send_message(
            f"✅ 漫画閲覧料金の受取PayPayアカウントを設定しました。\n"
            f"ユーザー: {interaction.user.mention}\n"
            f"閲覧料金: ¥{MANGA_PRICE}/回",
            ephemeral=True
        )

    # ---- HTML取得 ----
    @app_commands.command(name="html", description="指定したURLのHTMLソースをファイルとして取得します（あなただけに見えます）")
    @is_allowed()
    @app_commands.describe(url="HTMLを取得したいウェブサイトのURL")
    async def get_html_source(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)

        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.followup.send("❌ 有効なURL（http:// または https:// から始まるもの）を入力してください。", ephemeral=True)
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS, timeout=10) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"❌ HTMLの取得に失敗しました。ステータスコード: {response.status}", ephemeral=True)
                        return
                    html_text = await response.text()
        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {e}", ephemeral=True)
            return

        try:
            html_bytes = html_text.encode('utf-8')
            file_buffer = io.BytesIO(html_bytes)
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc.replace('.', '_')
            filename = f"source_{domain if domain else 'page'}.html"
            discord_file = discord.File(fp=file_buffer, filename=filename)
            await interaction.followup.send(
                content=f"📄 **URL:** {url}\nHTMLソースをファイルとして出力しました。ダウンロードしてご確認ください。",
                file=discord_file,
                ephemeral=True
            )
            file_buffer.close()
        except Exception as e:
            await interaction.followup.send(f"❌ ファイル作成・送信中にエラーが発生しました: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MangaCog(bot))
