import json
import time
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
                
                print("\n📢 Starting Poster (Execution) ---")
                asyncio.run(run_poster_process())
                print("✅ Poster Complete ---")
            else:
                print("\n--- Scraper Only Mode: Skipping Generator & Poster ---")
            
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
        for _ in tqdm(range(refresh), desc="Waiting for next cycle", unit="s"):
            time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="X-Watcher Hybrid Agent")
    parser.add_argument("--scraper-only", "-s", action="store_true", help="Run only the scraper in the loop, skip brain and replier.")
    parser.add_argument("--quantifier", "-q", action="store_true", help="Automatically run the quantifier after each scraper cycle.")
    args = parser.parse_args()

    print(f"Project X-Watcher: Starting Hybrid Agent{' (Scraper Only Mode)' if args.scraper_only else ''}...")
    init_db()

    # Start the automation loop in a daemon thread
    t = threading.Thread(
        target=run_automation_loop,
        args=(args.scraper_only, args.quantifier),
        daemon=True
    )
    t.start()

    print("Agent is running in the background. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
