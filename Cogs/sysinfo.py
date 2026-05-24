import discord
from discord.ext import commands
from discord import app_commands
import os
import time
import platform
import subprocess
from datetime import datetime, timezone, timedelta

from utils import is_owner

JST = timezone(timedelta(hours=9))

# ════════════════════════════════════════════════════════════
#  ヘルパー
# ════════════════════════════════════════════════════════════

def _bar(pct: float, width: int = 12) -> str:
    filled = int(pct / 100 * width)
    empty  = width - filled
    return f"{'█' * filled}{'░' * empty} {pct:.1f}%"

def _bytes(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def _fmt_seconds(sec: int) -> str:
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}日")
    if h: parts.append(f"{h}時間")
    if m: parts.append(f"{m}分")
    parts.append(f"{s}秒")
    return " ".join(parts)

def _run(cmd: list[str], timeout: int = 5) -> str:
    """コマンドを実行して stdout を返す。失敗時は空文字"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

# ════════════════════════════════════════════════════════════
#  各情報取得（subprocess / os.statvfs のみ使用）
# ════════════════════════════════════════════════════════════

def get_cpu_percent() -> float:
    """top -bn1 からCPU使用率を取得"""
    out = _run(["top", "-bn1"])
    for line in out.splitlines():
        # "Cpu(s):  3.2 us,  1.0 sy, ..." or "%Cpu(s): 3.2 us"
        if "cpu" in line.lower() and ("us" in line or "sy" in line):
            try:
                # idle を探して 100 - idle
                for part in line.replace(",", " ").split():
                    pass
                # idle値を探す
                parts = line.replace(",", " ").split()
                for i, p in enumerate(parts):
                    if "id" in p.lower() and i > 0:
                        idle = float(parts[i-1].replace("%", ""))
                        return max(0.0, 100.0 - idle)
            except Exception:
                pass
    # fallback: uptime のロードアベレージから概算
    return -1.0  # 取得失敗

def get_load_avg() -> str:
    out = _run(["uptime"])
    if "load average:" in out:
        return out.split("load average:")[-1].strip()
    if "load averages:" in out:
        return out.split("load averages:")[-1].strip()
    return "N/A"

def get_cpu_count() -> int:
    out = _run(["nproc"])
    try:
        return int(out)
    except Exception:
        pass
    # fallback
    out2 = _run(["getconf", "_NPROCESSORS_ONLN"])
    try:
        return int(out2)
    except Exception:
        return 1

def get_meminfo() -> dict:
    """free コマンドからメモリ情報を取得"""
    out = _run(["free", "-b"])
    result = {}
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0].lower().startswith("mem"):
            # Mem:  total  used  free  shared  buff/cache  available
            try:
                result["total"]     = int(parts[1])
                result["used"]      = int(parts[2])
                result["free"]      = int(parts[3])
                result["available"] = int(parts[6]) if len(parts) > 6 else int(parts[3])
            except Exception:
                pass
        elif parts and parts[0].lower().startswith("swap"):
            try:
                result["swap_total"] = int(parts[1])
                result["swap_used"]  = int(parts[2])
                result["swap_free"]  = int(parts[3])
            except Exception:
                pass
    return result

def get_disk(path: str = "/") -> dict:
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free  = st.f_frsize * st.f_bavail
        used  = total - free
        pct   = used / total * 100 if total else 0
        return {"total": total, "used": used, "free": free, "percent": pct}
    except Exception:
        pass
    # fallback: df
    out = _run(["df", "-B1", path])
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 5:
            try:
                total = int(parts[1]); used = int(parts[2]); free = int(parts[3])
                pct = used / total * 100 if total else 0
                return {"total": total, "used": used, "free": free, "percent": pct}
            except Exception:
                pass
    return {}

def get_uptime() -> str:
    out = _run(["uptime", "-p"])
    if out.startswith("up "):
        return out[3:]
    # fallback
    out2 = _run(["uptime"])
    if out2:
        return out2.split(",")[0].split("up")[-1].strip()
    return "不明"

def get_net_io() -> list[dict]:
    out = _run(["cat", "/proc/net/dev"])
    if not out:
        # ifconfig fallback
        return []
    results = []
    for line in out.splitlines()[2:]:
        parts = line.split()
        if not parts:
            continue
        nic = parts[0].rstrip(":")
        if nic == "lo":
            continue
        try:
            results.append({"nic": nic, "rx": int(parts[1]), "tx": int(parts[9])})
        except Exception:
            pass
    return results

def get_top_processes(n: int = 10) -> list[dict]:
    out = _run(["ps", "-eo", "pid,pcpu,rss,comm", "--sort=-%cpu"], timeout=8)
    if not out:
        out = _run(["ps", "-A", "-o", "pid,pcpu,rss,comm"])
    procs = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            procs.append({
                "pid":    int(parts[0]),
                "cpu":    float(parts[1]),
                "mem_kb": int(parts[2]),
                "name":   parts[3].strip()[:20],
            })
        except Exception:
            pass
    # --sort が効かない環境用
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:n]

# ════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════

class SysinfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(
        name="サーバー情報",
        description="CPU・メモリ・ディスク等を表示します（オーナー専用）"
    )
    @is_owner()
    async def sysinfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cpu_pct   = get_cpu_percent()
        load_str  = get_load_avg()
        cpu_count = get_cpu_count()

        mem = get_meminfo()
        mem_total = mem.get("total", 0)
        mem_used  = mem.get("used", 0)
        mem_avail = mem.get("available", mem.get("free", 0))
        mem_pct   = mem_used / mem_total * 100 if mem_total else 0
        swap_total = mem.get("swap_total", 0)
        swap_used  = mem.get("swap_used", 0)
        swap_pct   = swap_used / swap_total * 100 if swap_total else 0

        disk = get_disk()

        now_jst    = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        sys_uptime = get_uptime()
        bot_uptime = _fmt_seconds(int(time.time() - self.start_time))
        guild_count = len(self.bot.guilds)

        # CPUが取得できなかった場合はメモリで色判定
        ref_cpu = cpu_pct if cpu_pct >= 0 else 0
        color = discord.Color.green()
        if ref_cpu >= 90 or mem_pct >= 90:
            color = discord.Color.red()
        elif ref_cpu >= 70 or mem_pct >= 70:
            color = discord.Color.yellow()

        embed = discord.Embed(
            title="🖥️ サーバーリソース情報",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🔧 システム",
            value=(
                f"```\n"
                f"OS      : {platform.system()} {platform.release()}\n"
                f"アーキ  : {platform.machine()}\n"
                f"稼働時間: {sys_uptime}\n"
                f"現在時刻: {now_jst}\n"
                f"```"
            ),
            inline=False
        )

        cpu_bar = _bar(cpu_pct) if cpu_pct >= 0 else "取得不可"
        embed.add_field(
            name="⚙️ CPU",
            value=(
                f"```\n"
                f"使用率  : {cpu_bar}\n"
                f"コア数  : {cpu_count} コア\n"
                f"負荷平均: {load_str} (1/5/15分)\n"
                f"```"
            ),
            inline=False
        )

        swap_line = (
            f"Swap    : {_bar(swap_pct)}\n"
            f"          {_bytes(swap_used)} / {_bytes(swap_total)}"
            if swap_total > 0 else "Swap    : 未設定"
        )
        embed.add_field(
            name="💾 メモリ",
            value=(
                f"```\n"
                f"RAM     : {_bar(mem_pct)}\n"
                f"          {_bytes(mem_used)} / {_bytes(mem_total)}\n"
                f"利用可能: {_bytes(mem_avail)}\n"
                f"{swap_line}\n"
                f"```"
            ),
            inline=False
        )

        if disk:
            embed.add_field(
                name="💿 ディスク ( / )",
                value=(
                    f"```\n"
                    f"使用率  : {_bar(disk['percent'])}\n"
                    f"使用済み: {_bytes(disk['used'])}\n"
                    f"空き    : {_bytes(disk['free'])}\n"
                    f"合計    : {_bytes(disk['total'])}\n"
                    f"```"
                ),
                inline=False
            )

        embed.add_field(
            name="🤖 Bot",
            value=(
                f"```\n"
                f"Bot稼働 : {bot_uptime}\n"
                f"参加鯖  : {guild_count} サーバー\n"
                f"```"
            ),
            inline=False
        )

        cpu_str = f"{cpu_pct:.1f}%" if cpu_pct >= 0 else "N/A"
        disk_pct = disk.get("percent", 0)
        status_emoji = "🟢" if ref_cpu < 70 else ("🟡" if ref_cpu < 90 else "🔴")
        embed.set_footer(
            text=f"{status_emoji} CPU {cpu_str}  |  RAM {mem_pct:.1f}%  |  Disk {disk_pct:.1f}%"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="プロセス",
        description="CPU使用率Top10プロセスを表示します（オーナー専用）"
    )
    @is_owner()
    async def top_processes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        top = get_top_processes(10)
        lines = [f"{'PID':>6}  {'CPU%':>6}  {'RSS':>8}  名前"]
        lines.append("─" * 42)
        for p in top:
            lines.append(
                f"{p['pid']:>6}  {p['cpu']:>6.1f}  "
                f"{_bytes(p['mem_kb'] * 1024):>8}  {p['name']}"
            )
        if not top:
            lines.append("データ取得不可")

        embed = discord.Embed(
            title="📊 CPU使用率 Top10 プロセス",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="ネットワーク",
        description="ネットワーク通信量を表示します（オーナー専用）"
    )
    @is_owner()
    async def network_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        nics = get_net_io()
        lines = [f"{'IF名':<14}  {'受信':>10}  {'送信':>10}"]
        lines.append("─" * 40)
        for n in nics:
            lines.append(
                f"{n['nic']:<14}  {_bytes(n['rx']):>10}  {_bytes(n['tx']):>10}"
            )
        if not nics:
            lines.append("データ取得不可")

        embed = discord.Embed(
            title="🌐 ネットワーク通信量（起動後累計）",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.teal(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SysinfoCog(bot))
