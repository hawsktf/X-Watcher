import json
import time
import sys
import os
import asyncio
import threading
import argparse
from tqdm import tqdm
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env globally
load_dotenv()

from db import init_db
from scraper import run_scraper
from generator import run_generator
from poster import run_poster as run_poster_process
from quantifier import run_quantifier
from qualifier import run_qualifier
from engagement import run_engagement

def run_automation_loop(scraper_only=False, run_quantifier_flag=False):
    """Main automation loop."""
    while True:
        try:
            print("\n" + "="*50)
            print(f"🔄 STARTING CYCLE AT {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
            print("="*50)

            asyncio.run(run_scraper())
            run_quantifier()
            
            # Run engagement monitor
            if not scraper_only:
                try:
                    with open("config_user/config.json") as f:
                        cfg = json.load(f)
                    if cfg.get("engagement_enabled", False):
                        asyncio.run(run_engagement())
                except Exception as e:
                    print(f"  ❌ Engagement Monitor Error: {e}")
            
            if not scraper_only:
                run_generator()
                run_qualifier()
                asyncio.run(run_poster_process())
            else:
                print("\n--- Scraper Only Mode: Skipping Generator, Qualifier & Poster ---")
            
        except Exception as e:
            print(f"Error in main loop: {e}")
        # Sleep for the refresh interval
        try:
            with open("config_user/config.json") as f:
                cfg = json.load(f)
            refresh = cfg.get("refresh_seconds", 3600)
        except:
            refresh = 3600
            
        # print(f"Waiting {refresh} seconds for next cycle...")
        # time.sleep(refresh)
        for _ in tqdm(range(refresh), desc="Waiting for next cycle", unit="s", ncols=75, file=sys.stdout):
            time.sleep(1)

def main():
    # PID Lock Mechanism
    lock_file = "app.lock"
    current_pid = os.getpid()
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)
                # If we get here, PID exists. But is it US or another app.py?
                # On linux we can check /proc/PID/cmdline
                try:
                    with open(f"/proc/{pid}/cmdline", "r") as f_cmd:
                        cmd = f_cmd.read()
                        if "app.py" in cmd:
                            print(f"⚠️ App is already running (PID {pid}). Exiting.")
                            sys.exit(1)
                        else:
                            print(f"⚠️ Stale lock file found (PID {pid} is a different process). Removing.")
                            os.remove(lock_file)
                except:
                    print(f"⚠️ App appears to be running (PID {pid}). Exiting for safety.")
                    sys.exit(1)
            except OSError:
                print(f"⚠️ Stale lock file found (PID {pid} not running). Removing.")
                os.remove(lock_file)
        except (ValueError, IOError):
            print("⚠️ Invalid or unreadable lock file. Removing.")
            os.remove(lock_file)

    # Create lock
    with open(lock_file, "w") as f:
        f.write(str(current_pid))
    
    try:
        parser = argparse.ArgumentParser(description="X-Watcher Hybrid Agent")
        parser.add_argument("--scraper-only", "-s", action="store_true", help="Run only the scraper in the loop, skip brain and replier.")
        parser.add_argument("--quantifier", "-q", action="store_true", help="Automatically run the quantifier after each scraper cycle.")
        args = parser.parse_args()

        print(f"Project X-Watcher: Starting Hybrid Agent{' (Scraper Only Mode)' if args.scraper_only else ''} (PID {current_pid})...")
        init_db()

        # Start the automation loop
        # We don't use a daemon thread here to ensure we handle cleanup better,
        # or we just keep the main loop simple.
        run_automation_loop(args.scraper_only, args.quantifier)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Check if WE own the lock file before removing it
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                if pid == current_pid:
                    os.remove(lock_file)
                    print("🔒 Lock file removed.")
            except:
                pass

if __name__ == "__main__":
    main()
