import json
import time
import asyncio
import threading
import argparse
from dotenv import load_dotenv

# Load .env globally
load_dotenv()

from db import init_db
from scraper import main as run_scraper
from brain import draft_replies
from replier import process_replies

def run_automation_loop(scraper_only=False):
    """Main automation loop."""
    while True:
        try:
            print("\n--- Starting Scraper Cycle ---")
            asyncio.run(run_scraper())
            print("--- Scraper Cycle Complete ---")
            
            if not scraper_only:
                print("\n--- Starting Brain Drafting ---")
                draft_replies()
                print("--- Brain Drafting Complete ---")
                
                print("\n--- Starting Replier Process ---")
                process_replies()
                print("--- Replier Process Complete ---")
            else:
                print("\n--- Scraper Only Mode: Skipping Brain & Replier ---")
            
        except Exception as e:
            print(f"Error in main loop: {e}")
        
        # Sleep for the refresh interval
        try:
            with open("config.json") as f:
                cfg = json.load(f)
            refresh = cfg.get("refresh_seconds", 3600)
        except:
            refresh = 3600
            
        print(f"Waiting {refresh} seconds for next cycle...")
        time.sleep(refresh)

def main():
    parser = argparse.ArgumentParser(description="X-Watcher Hybrid Agent")
    parser.add_argument("--scraper-only", "-s", action="store_true", help="Run only the scraper in the loop, skip brain and replier.")
    args = parser.parse_args()

    print(f"Project X-Watcher: Starting Hybrid Agent{' (Scraper Only Mode)' if args.scraper_only else ''}...")
    init_db()

    # Start the automation loop in a daemon thread
    t = threading.Thread(
        target=run_automation_loop,
        args=(args.scraper_only,),
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
