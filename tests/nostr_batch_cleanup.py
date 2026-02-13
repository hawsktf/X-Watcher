import os
import csv
import json
import time
from db import REPLIES_CSV, update_nostr_status, get_post_details
from nostr_publisher import publish_to_nostr
from media_uploader import upload_media
from poster import capture_tweet_screenshot
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def backpost_to_nostr():
    print("🚀 Starting NOSTR Backposter (Catching up on missed posts)...")
    
    with open("config_user/config.json") as f:
        cfg = json.load(f)
    
    if not cfg.get("nostr_enabled", False):
        print("❌ NOSTR is not enabled in config. Exiting.")
        return

    # Read replies and find those with nostr_status 'N' that were actually posted to X (or are qualified)
    replies_to_fix = []
    if not os.path.exists(REPLIES_CSV):
        print("❌ replies.csv not found.")
        return

    with open(REPLIES_CSV, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # We want to post things that are 'posted' on X or 'qualified' but missing NOSTR
            if row.get('posted_to_nostr') == 'N' and row.get('status') in ['posted', 'qualified']:
                replies_to_fix.append(row)

    if not replies_to_fix:
        print("✅ No missing NOSTR posts found.")
        return

    print(f"📂 Found {len(replies_to_fix)} replies to backpost.")

    for r in replies_to_fix:
        reply_id = r['id']
        handle = r['handle']
        content = r['content']
        post_id = r['target_post_id']
        
        print(f"  🔗 NOSTR: Processing backpost for reply {reply_id} (Handle: @{handle})...")
        
        screenshot_url = None
        if cfg.get("nostr_screenshot_enabled", False):
            screenshot_path = f"debug/screenshots/{post_id}.png"
            # Attempt to capture if not exists, or just try to upload if it does
            if not os.path.exists(screenshot_path):
                print(f"     📸 Capturing missing screenshot for {post_id}...")
                await capture_tweet_screenshot(handle, post_id, screenshot_path)
            
            if os.path.exists(screenshot_path):
                screenshot_url = upload_media(screenshot_path)
        
        # Build nitter link
        mirrors = cfg.get("nitter_mirrors", ["https://nitter.poast.org"])
        nitter_mirror = mirrors[0] if mirrors else "https://nitter.poast.org"
        nitter_link = f"{nitter_mirror.rstrip('/')}/{handle}/status/{post_id}"
        
        # Publish
        nostr_event_id = publish_to_nostr(content, nitter_link, screenshot_url)
        if nostr_event_id:
            print(f"     ✅ Successfully backposted! Event ID: {nostr_event_id}")
            update_nostr_status(reply_id, nostr_event_id, "Y")
        else:
            print(f"     ❌ Failed to backpost {reply_id}")
            
        # Rate limit to avoid relay spam
        print("     ⏳ Waiting 5s...")
        await asyncio.sleep(5)

    print("\n✅ NOSTR Backposter complete!")

if __name__ == "__main__":
    asyncio.run(backpost_to_nostr())
