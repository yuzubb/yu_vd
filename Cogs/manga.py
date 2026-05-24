import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import aiohttp
from bs4 import BeautifulSoup
import os
import io
import urllib.parse
import asyncio

# ==========================================
# スクレイピング・データ取得ロジック
# ==========================================
# .env から取得、なければデフォルト値を使用
BASE_URL = os.getenv("BASE_URL", "https://momon-ga.com")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

async def search_manga(query: str):
    """タイトル検索を行う関数 (修正版)"""
    encoded_query = urllib.parse.quote(query)
    url = f"{BASE_URL}/?s={encoded_query}" 
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            results = []
            # 検索結果のコンテナ構造: .post-list > a
            items = soup.select('.post-list > a')
            
            for item in items:
                # spanタグ内のテキストを優先取得、なければimgのaltから取得
                span_tag = item.find('span')
                if span_tag:
                    title = span_tag.get_text(strip=True)
                else:
                    img_tag = item.find('img')
                    title = img_tag.get('alt', '').strip() if img_tag else "無題の作品"
                
                href = item.get('href')
                
                if title and href:
                    results.append({
                        "title": title,
                        "url": href
                    })
            
            # Discordのセレクトメニュー上限(25件)に合わせる
            return results[:25]


async def get_pages(manga_url: str):
    """作品ページからすべての漫画画像URLを取得する関数 (個別ページ構造に最適化)"""
    async with aiohttp.ClientSession() as session:
        async with session.get(manga_url, headers=HEADERS) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            pages = []
            
            # 1. main-area内を探索
            main_area = soup.select_one('.main-area')
            target_soup = main_area if main_area else soup
            
            # 2. 遅延読み込み(lazyload)対策を含めてimgタグから画像URLを抽出
            for img in target_soup.find_all('img'):
                # data-src 属性があれば優先（遅延読み込みサイトで有効）
                src = img.get('data-src') or img.get('src')
                if src:
                    # 拡張子が画像ファイルっぽく、かつアバターやアイコン用の画像を除外
                    src_lower = src.lower()
                    if any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if 'logo' not in src_lower and 'icon' not in src_lower and 'avatar' not in src_lower:
                            # 重複を防ぎつつ追加
                            if src not in pages:
                                pages.append(src)
            
            return pages


# ==========================================
# Discord UI (ボタン・ビュー) の実装
# ==========================================

class MangaReaderView(View):
    """漫画をめくるためのコンパクトなビュー"""
    def __init__(self, pages, title):
        super().__init__(timeout=300) # 5分でタイムアウト
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
            color=0x2b2d31 # Discord背景に馴染む色
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


class MangaSelect(Select):
    """検索結果から作品を選択するセレクトメニュー"""
    def __init__(self, results):
        options = [
            discord.SelectOption(label=res['title'][:100], value=res['url']) 
            for res in results
        ]
        super().__init__(placeholder="読みたい作品を選択してください...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 読み込み中表示
        await interaction.response.defer()
        
        # 選択された作品の画像一覧を直接取得（話数選択をスキップしてスリム化）
        pages = await get_pages(self.values[0])
        
        if not pages:
            await interaction.followup.send("⚠️ 漫画画像の取得に失敗したか、ページ内に画像が見つかりませんでした。", ephemeral=True)
            return

        # 選択した選択肢のタイトルを取得
        selected_title = "無題"
        for option in self.options:
            if option.value == self.values[0]:
                selected_title = option.label
                break

        # ビューアを表示
        view = MangaReaderView(pages, selected_title)
        await interaction.edit_original_response(embed=view.make_embed(), view=view)


# ==========================================
# Cogクラスの実装 (スラッシュコマンド)
# ==========================================
class MangaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manga", description="momon-ga.com から漫画を検索して視聴します")
    @app_commands.describe(query="検索したい漫画のタイトル")
    async def manga_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        results = await search_manga(query)
        
        if not results:
            await interaction.followup.send("❌ 該当する漫画が見つかりませんでした。", ephemeral=True)
            return

        # 検索結果をセレクトメニューで提示
        view = View()
        view.add_item(MangaSelect(results))
        
        embed = discord.Embed(
            title="🔍 検索結果", 
            description=f"「{query}」の検索結果です。以下から作品を選択してすぐに閲覧できます。", 
            color=0x2b2d31
        )
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="html", description="指定したURLのHTMLソースをファイルとして取得します（あなただけに見えます）")
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


# 自動読み込み用のセットアップ関数
async def setup(bot: commands.Bot):
    await bot.add_cog(MangaCog(bot))
