import os
import json
import csv
import time
import subprocess
import sys
from datetime import datetime

# Path to the virtual environment python
VENV_PYTHON = os.path.join(os.getcwd(), "venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    # Fallback to sys.executable if venv is missing
    VENV_PYTHON = sys.executable

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_config():
    with open("config_user/config.json") as f:
        return json.load(f)

def view_posts():
    if not os.path.exists("data/posts.csv"):
        print("No posts found.")
        input("Press Enter...")
        return

    with open("data/posts.csv", "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n--- {len(rows)} Scraped Posts ---")
    print(f"{'ID':<15} | {'Handle':<15} | {'Score':<5} | {'Pin?':<5} | {'Content'}")
    print("-" * 100)
    
    # Simple scroll/pagination
    page_size = 10
    for i in range(0, len(rows), page_size):
        chunk = rows[i:i + page_size]
        for row in chunk:
            content = row.get('content', '')[:40].replace('\n', ' ')
            score = row.get('score', '0')
            pinned = row.get('is_pinned', 'False')
            print(f"{row['post_id']:<15} | {row['handle']:<15} | {score:<5} | {pinned:<5} | {content}...")
        
        if i + page_size < len(rows):
            choice = input("\n[n]ext page, [q]uit view: ").lower()
            if choice == 'q':
                break
        else:
            input("\nEnd of list. Press Enter...")

def view_config():
    cfg = load_config()
    print("\n--- Current Configuration ---")
    for k, v in cfg.items():
        print(f"{k:<25}: {v}")
    input("\nPress Enter...")

def run_scraper_now():
    print("\nRunning Scraper...")
    subprocess.run([VENV_PYTHON, "scraper.py"])
    input("\nCompleted. Press Enter...")

def run_quantifier_now():
    print("\nRunning Quantifier...")
    subprocess.run([VENV_PYTHON, "quantifier.py"])
    input("\nCompleted. Press Enter...")

def run_brain_now():
    print("\nRunning Brain (Drafting)...")
    subprocess.run([VENV_PYTHON, "generator.py"])
    input("\nCompleted. Press Enter...")

def run_replier_now():
    print("\nRunning Replier (Posting)...")
    subprocess.run([VENV_PYTHON, "poster.py"])
    input("\nCompleted. Press Enter...")

def run_feed_now():
    print("\nLaunching Feed GUI...")
    print(f"Using environment: {VENV_PYTHON}")
    print("Dashboard will remain active. Visit: http://localhost:5000")
    # Run in background
    subprocess.Popen([VENV_PYTHON, "feed_app.py"])
    input("\nServer started. Press Enter to return to menu...")

def dashboard_menu():
    while True:
        clear()
        print("=== X-Watcher Hybrid Agent Dashboard ===")
        print("1. View Scraped Posts")
        print("2. View Configuration")
        print("3. Run Scraper (Manual)")
        print("4. Run Quantifier (Manual)")
        print("5. Run Brain/Drafting (Manual)")
        print("6. Run Replier/Posting (Manual)")
        print("7. Launch Feed GUI (Browser View)")
        print("8. Exit")
        
        choice = input("\nSelect an option: ")
        
        if choice == '1':
            view_posts()
        elif choice == '2':
            view_config()
        elif choice == '3':
            run_scraper_now()
        elif choice == '4':
            run_quantifier_now()
        elif choice == '5':
            run_brain_now()
        elif choice == '6':
            run_replier_now()
        elif choice == '7':
            run_feed_now()
        elif choice == '8':
            break

if __name__ == "__main__":
    try:
        dashboard_menu()
    except KeyboardInterrupt:
        pass
