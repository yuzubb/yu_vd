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
#  /proc 直読みヘルパー（psutil不要・Termux対応）
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

# ── CPU 使用率（0.5秒間隔で2回読んで差分）────────────────────
def _read_cpu_stat():
    with open("/proc/stat") as f:
        line = f.readline()          # "cpu  ..."
    vals = list(map(int, line.split()[1:]))
    idle  = vals[3] + (vals[4] if len(vals) > 4 else 0)   # idle + iowait
    total = sum(vals)
    return idle, total

def get_cpu_percent(interval: float = 0.5) -> float:
    idle1, total1 = _read_cpu_stat()
    time.sleep(interval)
    idle2, total2 = _read_cpu_stat()
    d_total = total2 - total1
    d_idle  = idle2  - idle1
    if d_total == 0:
        return 0.0
    return (1 - d_idle / d_total) * 100

# ── CPU コア数 ────────────────────────────────────────────────
def get_cpu_count() -> int:
    count = 0
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("processor"):
                    count += 1
    except Exception:
        pass
    return count or 1

# ── CPU 周波数（kHz → MHz）────────────────────────────────────
def get_cpu_freq_mhz() -> str:
    paths = [
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq",
        "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq",
    ]
    for p in paths:
        try:
            with open(p) as f:
                khz = int(f.read().strip())
            return f"{khz / 1000:.0f} MHz"
        except Exception:
            pass
    # /proc/cpuinfo fallback
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "cpu MHz" in line or "BogoMIPS" in line:
                    val = line.split(":")[1].strip()
                    return f"{float(val):.0f} MHz"
    except Exception:
        pass
    return "不明"

# ── ロードアベレージ ──────────────────────────────────────────
def get_load_avg() -> str:
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        return f"{parts[0]} / {parts[1]} / {parts[2]}"
    except Exception:
        return "N/A"

# ── メモリ（/proc/meminfo, kB → bytes）───────────────────────
def get_meminfo() -> dict:
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":")
                info[key.strip()] = int(val.split()[0]) * 1024
    except Exception:
        pass
    return info

# ── ディスク（os.statvfs）────────────────────────────────────
def get_disk(path: str = "/") -> dict:
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free  = st.f_frsize * st.f_bavail
        used  = total - free
        pct   = used / total * 100 if total else 0
        return {"total": total, "used": used, "free": free, "percent": pct}
    except Exception:
        return {}

# ── システム稼働時間（/proc/uptime）──────────────────────────
def get_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        return _fmt_seconds(int(secs))
    except Exception:
        return "不明"

# ── ネットワーク（/proc/net/dev）──────────────────────────────
def get_net_io() -> list[dict]:
    results = []
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]        # ヘッダー2行スキップ
        for line in lines:
            parts = line.split()
            nic = parts[0].rstrip(":")
            if nic == "lo":
                continue
            rx = int(parts[1])
            tx = int(parts[9])
            results.append({"nic": nic, "rx": rx, "tx": tx})
    except Exception:
        pass
    return results

# ── プロセス Top10（/proc/<pid>/stat）────────────────────────
def get_top_processes(n: int = 10) -> list[dict]:
    procs = []
    try:
        hz = os.sysconf("SC_CLK_TCK")
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])

        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                stat_path = f"/proc/{pid}/stat"
                status_path = f"/proc/{pid}/status"
                with open(stat_path) as f:
                    raw = f.read()
                # プロセス名は括弧内
                name_start = raw.index("(") + 1
                name_end   = raw.rindex(")")
                name = raw[name_start:name_end][:16]
                fields = raw[name_end + 2:].split()
                utime  = int(fields[11])
                stime  = int(fields[12])
                starttime = int(fields[19])
                total_time = utime + stime
                proc_age = uptime_sec - starttime / hz
                cpu_pct = (total_time / hz / proc_age * 100) if proc_age > 0 else 0

                # メモリ（VmRSS）
                mem_kb = 0
                with open(status_path) as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            mem_kb = int(line.split()[1])
                            break

                procs.append({"pid": int(pid), "name": name,
                              "cpu": cpu_pct, "mem_kb": mem_kb})
            except Exception:
                pass
    except Exception:
        pass

    return sorted(procs, key=lambda x: x["cpu"], reverse=True)[:n]


# ════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════

class SysinfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    # ── /サーバー情報 ─────────────────────────────────────────
    @app_commands.command(
        name="サーバー情報",
        description="CPU・メモリ・ディスク等を表示します（オーナー専用）"
    )
    @is_owner()
    async def sysinfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cpu_pct   = get_cpu_percent()
        cpu_count = get_cpu_count()
        cpu_freq  = get_cpu_freq_mhz()
        load_str  = get_load_avg()

        mem       = get_meminfo()
        mem_total = mem.get("MemTotal", 0)
        mem_avail = mem.get("MemAvailable", 0)
        mem_used  = mem_total - mem_avail
        mem_pct   = mem_used / mem_total * 100 if mem_total else 0
        swap_total = mem.get("SwapTotal", 0)
        swap_free  = mem.get("SwapFree", 0)
        swap_used  = swap_total - swap_free
        swap_pct   = swap_used / swap_total * 100 if swap_total else 0

        disk = get_disk()

        now_jst     = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        sys_uptime  = get_uptime()
        bot_uptime  = _fmt_seconds(int(time.time() - self.start_time))
        guild_count = len(self.bot.guilds)

        color = discord.Color.green()
        if cpu_pct >= 90 or mem_pct >= 90:
            color = discord.Color.red()
        elif cpu_pct >= 70 or mem_pct >= 70:
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

        embed.add_field(
            name="⚙️ CPU",
            value=(
                f"```\n"
                f"使用率  : {_bar(cpu_pct)}\n"
                f"コア数  : {cpu_count} コア\n"
                f"周波数  : {cpu_freq}\n"
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

        status_emoji = "🟢" if cpu_pct < 70 else ("🟡" if cpu_pct < 90 else "🔴")
        disk_pct = disk.get("percent", 0)
        embed.set_footer(
            text=f"{status_emoji} CPU {cpu_pct:.1f}%  |  RAM {mem_pct:.1f}%  |  Disk {disk_pct:.1f}%"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /プロセス ─────────────────────────────────────────────
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
                f"{_bytes(p['mem_kb']*1024):>8}  {p['name']}"
            )

        embed = discord.Embed(
            title="📊 CPU使用率 Top10 プロセス",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /ネットワーク ─────────────────────────────────────────
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
            lines.append("データなし")

        embed = discord.Embed(
            title="🌐 ネットワーク通信量（起動後累計）",
            description="```\n" + "\n".join(lines) + "\n```",
            color=discord.Color.teal(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SysinfoCog(bot))
