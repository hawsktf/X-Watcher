import json
import time
import threading

from db import init_db
from fetcher import fetch_latest
from cli import show_cli
from dashboard import run_dashboard

def updater(handles, refresh):
    while True:
        for h in handles:
            try:
                fetch_latest(h)
            except Exception as e:
                print("Fetch error:", h, e)

        time.sleep(refresh)

def main():
    init_db()

    with open("config.json") as f:
        cfg = json.load(f)

    handles = cfg["handles"]
    refresh = cfg.get("refresh_seconds", 300)

    t = threading.Thread(
        target=updater,
        args=(handles, refresh),
        daemon=True
    )
    t.start()

    show_cli()
    run_dashboard()

if __name__ == "__main__":
    main()

