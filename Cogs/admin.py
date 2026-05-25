import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import time
import subprocess
import zipfile
import asyncio
from datetime import datetime, timezone, timedelta

from utils import is_owner, OWNER_ID

JST = timezone(timedelta(hours=9))
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # main.py のあるディレクトリ
DATA_DIR  = os.path.join(REPO_DIR, "data")


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ════════════════════════════════════════════════════════
    #  /ping
    # ════════════════════════════════════════════════════════
    @app_commands.command(name="ping", description="Botのレイテンシを表示します")
    async def ping(self, interaction: discord.Interaction):
        ws_latency = round(self.bot.latency * 1000)

        # REST レイテンシ計測
        before = time.monotonic()
        await interaction.response.defer(ephemeral=True)
        after  = time.monotonic()
        rest_latency = round((after - before) * 1000)

        # 色分け
        color = discord.Color.green()
        if ws_latency > 200:
            color = discord.Color.red()
        elif ws_latency > 100:
            color = discord.Color.yellow()

        emoji = "🟢" if ws_latency <= 100 else ("🟡" if ws_latency <= 200 else "🔴")

        embed = discord.Embed(title=f"{emoji} Pong!", color=color,
                              timestamp=datetime.now(timezone.utc))
        embed.add_field(name="📡 WebSocket", value=f"```{ws_latency} ms```",  inline=True)
        embed.add_field(name="🌐 REST",      value=f"```{rest_latency} ms```", inline=True)
        embed.set_footer(text=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"))

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ════════════════════════════════════════════════════════
    #  /git更新
    # ════════════════════════════════════════════════════════
    @app_commands.command(name="git更新", description="git pull して最新コードに更新します（オーナー専用）")
    @is_owner()
    async def git_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # 更新前のコミット
        before = _run_git(["git", "rev-parse", "HEAD"]).stdout.strip()[:7]

        result = _run_git(["git", "pull", "origin", "main"])

        # 失敗
        if result.returncode != 0:
            embed = discord.Embed(title="❌ git pull 失敗", color=discord.Color.red(),
                                  timestamp=datetime.now(timezone.utc))
            err = result.stderr.strip()[:1000] or "（エラー詳細なし）"
            embed.add_field(name="エラー", value=f"```\n{err}\n```", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        after = _run_git(["git", "rev-parse", "HEAD"]).stdout.strip()[:7]

        # 最新だった
        if before == after:
            embed = discord.Embed(title="✅ すでに最新です", color=discord.Color.green(),
                                  timestamp=datetime.now(timezone.utc))
            embed.add_field(name="コミット", value=f"`{before}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # 変更されたファイル一覧
        diff = _run_git(["git", "diff", "--name-status", before, after])
        label_map = {"M": "📝 更新", "A": "➕ 追加", "D": "🗑️ 削除"}
        changed_lines = []
        for line in diff.stdout.strip().splitlines():
            parts = line.split("\t")
            label = label_map.get(parts[0], parts[0])
            changed_lines.append(f"{label}  {parts[-1]}")

        embed = discord.Embed(title="🔄 git pull 完了", color=discord.Color.blurple(),
                              timestamp=datetime.now(timezone.utc))
        embed.add_field(name="コミット", value=f"`{before}` → `{after}`", inline=False)
        if changed_lines:
            changes_text = "\n".join(changed_lines)[:1000]
            embed.add_field(name="変更ファイル", value=f"```\n{changes_text}\n```", inline=False)
        embed.add_field(name="⚠️ 注意", value="変更を反映するには `/再起動` が必要です", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ════════════════════════════════════════════════════════
    #  /再起動
    # ════════════════════════════════════════════════════════
    @app_commands.command(name="再起動", description="Botを再起動します（オーナー専用）")
    @is_owner()
    async def restart(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔄 再起動します...",
                description="数秒後にBotが再起動されます。",
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            ),
            ephemeral=True
        )

        await asyncio.sleep(1)
        await self.bot.close()

        sys.exit(0) 

    # ════════════════════════════════════════════════════════
    #  /バックアップ
    # ════════════════════════════════════════════════════════
    @app_commands.command(name="バックアップ", description="data/ フォルダをzipにしてDMに送ります（オーナー専用）")
    @is_owner()
    async def backup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not os.path.exists(DATA_DIR):
            await interaction.followup.send("❌ `data/` フォルダが見つかりません。", ephemeral=True)
            return

        # zip 作成
        now_str  = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(REPO_DIR, f"backup_{now_str}.zip")

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(DATA_DIR):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname   = os.path.relpath(full_path, REPO_DIR)
                        zf.write(full_path, arcname)

            zip_size = os.path.getsize(zip_path)

            # 8MB 以下なら Discord に添付（上限）
            if zip_size <= 8 * 1024 * 1024:
                owner = await self.bot.fetch_user(OWNER_ID)
                dm    = await owner.create_dm()

                embed = discord.Embed(
                    title="📦 バックアップ完了",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="ファイル名", value=f"`backup_{now_str}.zip`", inline=False)
                embed.add_field(name="サイズ",     value=f"`{zip_size / 1024:.1f} KB`",    inline=True)
                embed.set_footer(text="DMに送信しました")

                with open(zip_path, "rb") as f:
                    await dm.send(
                        embed=embed,
                        file=discord.File(f, filename=f"backup_{now_str}.zip")
                    )

                await interaction.followup.send(
                    embed=discord.Embed(
                        title="✅ バックアップをDMに送信しました",
                        color=discord.Color.green()
                    ),
                    ephemeral=True
                )
            else:
                # 大きすぎる場合はサーバーに保存してパスを通知
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="⚠️ ファイルが大きすぎます",
                        description=(
                            f"サイズ: `{zip_size / 1024 / 1024:.1f} MB`\n"
                            f"保存先: `{zip_path}`"
                        ),
                        color=discord.Color.yellow()
                    ),
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ バックアップ失敗",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
        finally:
            # zip ファイルを削除（送信済みなら不要）
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
