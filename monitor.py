"""
OT Bot Log Monitor
Tampilkan log secara real-time
Optimized for performance
"""

import os
import sys
from datetime import datetime

DAILY_LOG_DIR = "logs"


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def show_logs(lines=30):
    """Tampilkan log terakhir"""
    clear_screen()

    print("=" * 70)
    print("  OT APPROVAL BOT - LOG MONITOR")
    print("=" * 70)
    print(f"  Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Get today's log file
    today_log = os.path.join(DAILY_LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

    if os.path.exists(today_log):
        print(f"\n📄 {today_log} (terakhir {lines} baris):")
        print("-" * 70)

        with open(today_log, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                # Color by type
                if "| CMD" in line:
                    color = "\033[92m"  # Green
                elif "| CB" in line:
                    color = "\033[96m"  # Cyan
                elif "| MSG" in line:
                    color = "\033[93m"  # Yellow
                elif "| SYS" in line:
                    color = "\033[94m"  # Blue
                elif "| ERROR" in line:
                    color = "\033[91m"  # Red
                else:
                    color = "\033[0m"   # White

                print(f"{color}{line.strip()}\033[0m")
    else:
        print(f"\n⚠️  File log belum ada. Jalankan bot dulu!")

    # Show daily logs summary
    print("\n" + "=" * 70)
    print("📁 Daily Logs:")
    print("-" * 70)

    if os.path.exists(DAILY_LOG_DIR):
        log_files = sorted(os.listdir(DAILY_LOG_DIR), reverse=True)[:7]
        if log_files:
            for f in log_files:
                size = os.path.getsize(os.path.join(DAILY_LOG_DIR, f))
                date = f.replace("bot_", "").replace(".log", "")
                print(f"  📄 {date} | {size} bytes")
        else:
            print("  (tidak ada log harian)")
    else:
        print("  (tidak ada log harian)")

    print("\n" + "=" * 70)
    print("  Tekan Ctrl+C untuk keluar")
    print("=" * 70)


def show_stats():
    """Tampilkan statistik dari logs"""
    print("=" * 70)
    print("  OT APPROVAL BOT - STATISTICS")
    print("=" * 70 + "\n")

    stats = {
        "commands": 0,
        "callbacks": 0,
        "messages": 0,
        "errors": 0,
        "system": 0,
        "total": 0
    }

    today_log = os.path.join(DAILY_LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

    if os.path.exists(today_log):
        with open(today_log, "r", encoding="utf-8") as f:
            for line in f:
                stats["total"] += 1
                if "| CMD" in line:
                    stats["commands"] += 1
                elif "| CB" in line:
                    stats["callbacks"] += 1
                elif "| MSG" in line:
                    stats["messages"] += 1
                elif "| SYS" in line:
                    stats["system"] += 1
                elif "| ERROR" in line:
                    stats["errors"] += 1

    print(f"  Total events     : {stats['total']}")
    print(f"  Commands         : {stats['commands']}")
    print(f"  Callbacks        : {stats['callbacks']}")
    print(f"  Messages         : {stats['messages']}")
    print(f"  System           : {stats['system']}")
    print(f"  Errors           : {stats['errors']}")

    # User count
    users = set()
    if os.path.exists(today_log):
        with open(today_log, "r", encoding="utf-8") as f:
            for line in f:
                if "U:" in line:
                    try:
                        user_id = line.split("U:")[1].split()[0]
                        users.add(user_id)
                    except:
                        pass

    print(f"  Unique users     : {len(users)}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            show_stats()
        else:
            print("Usage: python monitor.py [--stats]")
    else:
        show_logs()