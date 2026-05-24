import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import aiohttp
from bs4 import BeautifulSoup
import os

# ==========================================
# スクレイピング・データ取得ロジック
# ==========================================
# .env から取得、なければデフォルト値を使用
BASE_URL = os.getenv("BASE_URL", "https://momon-ga.com")

async def search_manga(query: str):
    """タイトル検索を行う関数"""
    url = f"{BASE_URL}/?s={query}" 
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            results = []
            # 実際のHTML構造に合わせてセレクタ（.manga-card a等）を調整してください
            for item in soup.select('.manga-card a')[:5]: 
                results.append({
                    "title": item.get_text(strip=True),
                    "url": item['href']
                })
            return results

async def get_chapters(manga_url: str):
    """作品ページからエピソード一覧を取得する関数"""
    async with aiohttp.ClientSession() as session:
        async with session.get(manga_url) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            chapters = []
            for item in soup.select('.chapter-list a'):
                chapters.append({
                    "name": item.get_text(strip=True),
                    "url": item['href']
                })
            return chapters

async def get_pages(chapter_url: str):
    """エピソードページから漫画の画像URL一覧を取得する関数"""
    async with aiohttp.ClientSession() as session:
        async with session.get(chapter_url) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            pages = []
            for img in soup.select('.manga-page img'):
                pages.append(img['src'])
            return pages


# ==========================================
# Discord UI (ボタン・ビュー) の実装
# ==========================================

class MangaReaderView(View):
    """漫画をめくるためのコンパクトなビュー"""
    def __init__(self, pages, title):
        super().__init__(timeout=180)
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
            color=0x2b2d31 # Discordの背景に馴染む色（枠線を目立たせない）
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
        # 終了時はメッセージを綺麗にクリア
        await interaction.response.edit_message(content="❌ 閲覧を終了しました。", embeds=[], view=None)
        self.stop()


class ChapterSelect(Select):
    """話数を選択するセレクトメニュー"""
    def __init__(self, chapters):
        options = [
            discord.SelectOption(label=ch['name'][:100], value=ch['url']) 
            for ch in chapters[:25]
        ]
        super().__init__(placeholder="読みたい話数を選択してください...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pages = await get_pages(self.values[0])
        
        if not pages:
            await interaction.followup.send("画像の取得に失敗しました。", ephemeral=True)
            return

        view = MangaReaderView(pages, self.options[0].label)
        await interaction.edit_original_response(embed=view.make_embed(), view=view)


class MangaSelect(Select):
    """検索結果から作品を選択するセレクトメニュー"""
    def __init__(self, results):
        options = [
            discord.SelectOption(label=res['title'][:100], value=res['url']) 
            for res in results
        ]
        super().__init__(placeholder="作品を選択してください...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chapters = await get_chapters(self.values[0])
        
        if not chapters:
            await interaction.followup.send("エピソードが見つかりませんでした。", ephemeral=True)
            return

        view = View()
        view.add_item(ChapterSelect(chapters))
        
        embed = discord.Embed(title="話数選択", description="読みたいエピソードを選んでください。", color=0x2b2d31)
        await interaction.edit_original_response(embed=embed, view=view)


# ==========================================
# Cogクラスの実装 (スラッシュコマンド)
# ==========================================
class MangaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manga", description="momon-ga.com から漫画を検索して視聴します")
    @app_commands.describe(query="検索したい漫画のタイトル")
    async def manga_search(self, interaction: discord.Interaction, query: str):
        # 応答を少し待たせる（スクレイピングの時間を稼ぐため必須）
        await interaction.response.defer()
        
        results = await search_manga(query)
        
        if not results:
            await interaction.followup.send("該当する漫画が見つかりませんでした。", ephemeral=True)
            return

        # 検索結果をセレクトメニューで提示（メッセージを上書きしていくため枠を取らない）
        view = View()
        view.add_item(MangaSelect(results))
        
        embed = discord.Embed(
            title="🔍 検索結果", 
            description=f"「{query}」の検索結果です。以下から作品を選択してください。", 
            color=0x2b2d31
        )
        await interaction.followup.send(embed=embed, view=view)

# /html コマンドの定義（ファイル送信版）
    @app_commands.command(name="html", description="指定したURLのHTMLソースをファイルとして取得します（あなただけに見えます）")
    @app_commands.describe(url="HTMLを取得したいウェブサイトのURL")
    async def get_html_source(self, interaction: discord.Interaction, url: str):
        import io  # メモリバッファを使用するためにインポート
        import urllib.parse

        # 実行した人だけに見える状態(ephemeral=True)で保留にする
        await interaction.response.defer(ephemeral=True)
        
        # 簡易的なURLチェック
        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.followup.send("❌ 有効なURL（http:// または https:// から始まるもの）を入力してください。", ephemeral=True)
            return

        try:
            async with aiohttp.ClientSession() as session:
                # 相手サーバーにBot拒否されないよう一般的なUser-Agentを設定
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"❌ HTMLの取得に失敗しました。ステータスコード: {response.status}", ephemeral=True)
                        return
                    
                    html_text = await response.text()
        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {e}", ephemeral=True)
            return

        try:
            # 取得したHTML文字列をバイトデータに変換し、インメモリファイルを作成
            html_bytes = html_text.encode('utf-8')
            file_buffer = io.BytesIO(html_bytes)
            
            # URLからドメイン名などを抽出して、ファイル名にする（例: momon-ga_com.html）
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc.replace('.', '_')
            filename = f"source_{domain if domain else 'page'}.html"
            
            # discord.File オブジェクトを作成
            discord_file = discord.File(fp=file_buffer, filename=filename)
            
            # ファイルを添付して送信（ephemeral=Trueなので本人のみ表示）
            await interaction.followup.send(
                content=f"📄 **URL:** {url}\nHTMLソースをファイルとして出力しました。ダウンロードしてご確認ください。",
                file=discord_file,
                ephemeral=True
            )
            
            # バッファを閉じる
            file_buffer.close()

        except Exception as e:
            await interaction.followup.send(f"❌ ファイル作成・送信中にエラーが発生しました: {e}", ephemeral=True)

# 自動読み込み用のセットアップ関数
async def setup(bot: commands.Bot):
    await bot.add_cog(MangaCog(bot))
