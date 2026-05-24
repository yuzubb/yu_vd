import discord
from discord.ext import commands
from discord import app_commands
import platform
import psutil
import os
import time
from datetime import datetime, timezone, timedelta

from utils import is_owner

JST = timezone(timedelta(hours=9))

# ── ヘルパー関数 ──────────────────────────────────────────────

def _bar(pct: float, width: int = 12) -> str:
    """テキストプログレスバーを生成"""
    filled = int(pct / 100 * width)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty} {pct:.1f}%"

def _bytes(b: int) -> str:
    """バイトを人間可読な文字列に変換"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def _uptime() -> str:
    """システム稼働時間を文字列で返す"""
    boot = psutil.boot_time()
    diff = int(time.time() - boot)
    d, r = divmod(diff, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}日")
    if h: parts.append(f"{h}時間")
    if m: parts.append(f"{m}分")
    parts.append(f"{s}秒")
    return " ".join(parts)

def _bot_uptime(start_time: float) -> str:
    diff = int(time.time() - start_time)
    d, r = divmod(diff, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}日")
    if h: parts.append(f"{h}時間")
    if m: parts.append(f"{m}分")
    parts.append(f"{s}秒")
    return " ".join(parts)


# ── Cog ───────────────────────────────────────────────────────

class SysinfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    # ── /サーバー情報 ─────────────────────────────────────────
    @app_commands.command(name="サーバー情報", description="サーバーのCPU・メモリ・ディスク等を表示します（オーナー専用）")
    @is_owner()
    async def sysinfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # ── CPU ──
        cpu_pct   = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq  = psutil.cpu_freq()
        freq_str  = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "不明"
        load_avg  = os.getloadavg() if hasattr(os, "getloadavg") else None
        load_str  = f"{load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}" if load_avg else "N/A"

        # ── メモリ ──
        mem  = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # ── ディスク ──
        disk = psutil.disk_usage("/")

        # ── ネットワーク ──
        net_before = psutil.net_io_counters()

        # ── プロセス ──
        proc_count = len(psutil.pids())

        # ── Bot情報 ──
        guild_count   = len(self.bot.guilds)
        bot_uptime    = _bot_uptime(self.start_time)
        sys_uptime    = _uptime()
        now_jst       = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")

        # ── Embed作成 ──
        color = discord.Color.green()
        if cpu_pct >= 90 or mem.percent >= 90:
            color = discord.Color.red()
        elif cpu_pct >= 70 or mem.percent >= 70:
            color = discord.Color.yellow()

        embed = discord.Embed(
            title="サーバーリソース情報",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        # ── システム ──
        embed.add_field(
            name="システム",
            value=(
                f"```"
                f"OS      : {platform.system()} {platform.release()}\n"
                f"アーキ  : {platform.machine()}\n"
                f"稼働時間: {sys_uptime}\n"
                f"現在時刻: {now_jst}"
                f"```"
            ),
            inline=False
        )

        # ── CPU ──
        embed.add_field(
            name="CPU",
            value=(
                f"```"
                f"使用率  : {_bar(cpu_pct)}\n"
                f"コア数  : {cpu_count} コア\n"
                f"周波数  : {freq_str}\n"
                f"負荷平均: {load_str} (1/5/15分)"
                f"```"
            ),
            inline=False
        )

        # ── メモリ ──
        swap_line = (
            f"Swap    : {_bar(swap.percent)}\n"
            f"          {_bytes(swap.used)} / {_bytes(swap.total)}"
            if swap.total > 0 else "Swap    : 未設定"
        )
        embed.add_field(
            name="メモリ",
            value=(
                f"```"
                f"RAM     : {_bar(mem.percent)}\n"
                f"          {_bytes(mem.used)} / {_bytes(mem.total)}\n"
                f"利用可能: {_bytes(mem.available)}\n"
                f"{swap_line}"
                f"```"
            ),
            inline=False
        )

        # ── ディスク ──
        embed.add_field(
            name="ディスク ( / )",
            value=(
                f"```"
                f"使用率  : {_bar(disk.percent)}\n"
                f"使用済み: {_bytes(disk.used)}\n"
                f"空き    : {_bytes(disk.free)}\n"
                f"合計    : {_bytes(disk.total)}"
                f"```"
            ),
            inline=False
        )

        # ── プロセス & Bot ──
        embed.add_field(
            name="Bot / プロセス",
            value=(
                f"```"
                f"Bot稼働 : {bot_uptime}\n"
                f"参加鯖  : {guild_count} サーバー\n"
                f"プロセス: {proc_count} 個"
                f"```"
            ),
            inline=False
        )

        # CPU使用率で絵文字を変える
        status_emoji = "🟢" if cpu_pct < 70 else ("🟡" if cpu_pct < 90 else "🔴")
        embed.set_footer(text=f"{status_emoji} CPU {cpu_pct:.1f}%  |  RAM {mem.percent:.1f}%  |  Disk {disk.percent:.1f}%")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /プロセス ─────────────────────────────────────────────
    @app_commands.command(name="プロセス", description="CPU使用率Top10プロセスを表示します（オーナー専用）")
    @is_owner()
    async def top_processes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # CPU使用率でソート
        top = sorted(procs, key=lambda x: x["cpu_percent"] or 0, reverse=True)[:10]

        lines = [f"{'PID':>6}  {'CPU%':>5}  {'MEM%':>5}  名前"]
        lines.append("─" * 40)
        for p in top:
            name = (p["name"] or "?")[:20]
            lines.append(
                f"{p['pid']:>6}  {p['cpu_percent']:>5.1f}  {p['memory_percent']:>5.1f}  {name}"
            )

        embed = discord.Embed(
            title="CPU使用率 Top10 プロセス",
            description=f"```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /ネットワーク ─────────────────────────────────────────
    @app_commands.command(name="ネットワーク", description="ネットワーク通信量を表示します（オーナー専用）")
    @is_owner()
    async def network_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        net = psutil.net_io_counters(pernic=True)
        lines = [f"{'IF名':<12}  {'受信':>10}  {'送信':>10}"]
        lines.append("─" * 38)
        for nic, stats in net.items():
            if nic == "lo":
                continue
            lines.append(f"{nic:<12}  {_bytes(stats.bytes_recv):>10}  {_bytes(stats.bytes_sent):>10}")

        embed = discord.Embed(
            title="ネットワーク通信量（起動後累計）",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.teal(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SysinfoCog(bot))
