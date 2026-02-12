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

def run_automation_loop(scraper_only=False, run_quantifier_flag=False):
    """Main automation loop."""
    while True:
        try:
            print("\n" + "="*50)
            print(f"🔄 STARTING CYCLE AT {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
            print("="*50)

            print("\n🚀 Starting Scraper Cycle ---")
            asyncio.run(run_scraper())
            print("✅ Scraper Cycle Complete ---")
            
            # Run quantifier by default
            print("\n🧠 Starting Post Quantification ---")
            run_quantifier()
            print("✅ Post Quantification Complete ---")
            
            if not scraper_only:
                print("\n🎨 Starting Generator (Creation) ---")
                run_generator()
                print("✅ Generator Complete ---")
                
                print("\n🛡️ Starting Qualifier (Safety) ---")
                run_qualifier()
                print("✅ Qualifier Complete ---")
                
                print("\n📢 Starting Poster (Execution) ---")
                asyncio.run(run_poster_process())
                print("✅ Poster Complete ---")
            else:
                print("\n--- Scraper Only Mode: Skipping Generator, Qualifier & Poster ---")
            
        except Exception as e:
            print(f"Error in main loop: {e}")
        # Sleep for the refresh interval
        try:
            with open("config.json") as f:
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
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)
                print(f"⚠️ App is already running (PID {pid}). Exiting.")
                sys.exit(1)
            except OSError:
                print(f"⚠️ Stale lock file found (PID {pid} not running). Removing.")
                os.remove(lock_file)
        except ValueError:
            print("⚠️ Invalid lock file. Removing.")
            os.remove(lock_file)

    # Create lock
    current_pid = os.getpid()
    with open(lock_file, "w") as f:
        f.write(str(current_pid))
    
    try:
        parser = argparse.ArgumentParser(description="X-Watcher Hybrid Agent")
        parser.add_argument("--scraper-only", "-s", action="store_true", help="Run only the scraper in the loop, skip brain and replier.")
        parser.add_argument("--quantifier", "-q", action="store_true", help="Automatically run the quantifier after each scraper cycle.")
        args = parser.parse_args()

        print(f"Project X-Watcher: Starting Hybrid Agent{' (Scraper Only Mode)' if args.scraper_only else ''} (PID {current_pid})...")
        init_db()

        # Start the automation loop in a daemon thread
        t = threading.Thread(
            target=run_automation_loop,
            args=(args.scraper_only, args.quantifier),
            daemon=True
        )
        t.start()

        print("Agent is running in the background. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            print("🔒 Lock file removed.")

if __name__ == "__main__":
    main()
