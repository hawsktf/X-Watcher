import asyncio
import time
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from datetime import datetime, timedelta
import csv
import os
import json

# Load .env
load_dotenv()

from db import get_pending_replies, mark_reply_posted, POSTS_CSV

def get_twitter_client():
    # Attempt to load credentials from environment
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    
    # Check if we have real credentials
    if not api_key or api_key == "YOUR_API_KEY":
        print("Replier: No active Twitter API credentials found in .env. Using MOCK mode.")
        return None

    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        return client
    except ImportError:
        print("Replier: Tweepy not installed. Using MOCK mode.")
        return None
    except Exception as e:
        print(f"Replier: Error initializing Tweepy client: {e}")
        return None

async def post_reply_via_browser(post_id, handle, content, headless=True):
    with open("config.json") as f:
        cfg = json.load(f)
    
    user = os.getenv("TWITTER_USERNAME")
    pwd = os.getenv("TWITTER_PASSWORD")
    user_data_dir = cfg.get("browser_user_data_dir", "data/browser_session")
    if not os.path.isabs(user_data_dir):
        user_data_dir = os.path.join(os.getcwd(), user_data_dir)

    print(f"Replier: Posting browser reply to {handle} for post {post_id}...")
    
    async with async_playwright() as p:
        context = await p.firefox.launch_persistent_context(
            user_data_dir,
            headless=headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            viewport={"width": 1280, "height": 720}
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            url = f"https://x.com/{handle}/status/{post_id}"
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Check if logged in
            if "/login" in page.url or await page.query_selector('input[autocomplete="username"]'):
                print("Replier: Not logged in. Authenticating...")
                if "/login" not in page.url:
                    await page.goto("https://x.com/i/flow/login")
                
                await page.wait_for_selector('input[autocomplete="username"]', timeout=20000)
                await page.fill('input[autocomplete="username"]', user)
                await page.keyboard.press("Enter")
                
                await page.wait_for_timeout(2000)
                if await page.query_selector('input[data-testid="ocfEnterTextTextInput"]'):
                     print("Replier: Additional verification needed. Cannot post.")
                     await context.close()
                     return False

                await page.wait_for_selector('input[autocomplete="current-password"]', timeout=10000)
                await page.fill('input[autocomplete="current-password"]', pwd)
                await page.keyboard.press("Enter")
                await page.wait_for_url("https://x.com/home", timeout=30000)
                await page.goto(url, wait_until="networkidle")

            # Click reply box
            reply_box = await page.wait_for_selector('div[data-testid="tweetTextarea_0"]', timeout=20000)
            if reply_box:
                await reply_box.click()
                await reply_box.fill(content)
                
                # Click Post button
                post_btn = await page.query_selector('div[data-testid="tweetButtonInline"]')
                if post_btn:
                    await post_btn.click()
                    await page.wait_for_timeout(3000) # Wait for animation/sending
                    print(f"Replier: Reply posted successfully via browser to {post_id}.")
                    return True
            
            print(f"Replier: Could not find reply elements for {post_id}.")
            return False
            
        except Exception as e:
            print(f"Replier Browser Error: {e}")
            return False
        finally:
            await context.close()

def check_previous_reply_posted(target_post_id):
    from db import REPLIES_CSV, POSTED_REPLIES_CSV
    # Check pending
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['post_id'] == str(target_post_id) and row['status'] == 'posted':
                    return True
    # Check history
    if os.path.exists(POSTED_REPLIES_CSV):
        with open(POSTED_REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['post_id'] == str(target_post_id):
                    return True
    return False

async def process_replies():
    # Load config
    with open("config.json") as f:
        cfg = json.load(f)
    
    latency = cfg.get("reply_latency_minutes", 10)
    use_browser = cfg.get("use_browser_replier", True)
    headless = cfg.get("headless_browser", False)
    
    replies = get_pending_replies()
    if not replies:
        print("Replier: No pending replies to post.")
        return

    now = datetime.utcnow()
    for reply in replies:
        if check_previous_reply_posted(reply['post_id']):
            print(f"Replier: Skipping {reply['post_id']}, already replied previously.")
            mark_reply_posted(reply['id'])
            continue

        created_at = datetime.fromisoformat(reply['created_at'])
        if now - created_at < timedelta(minutes=latency):
            print(f"Replier: Waiting for latency on {reply['post_id']}. ({(now - created_at).seconds//60}m / {latency}m)")
            continue
            
        post_id = reply['post_id']
        handle = reply['handle']
        content = reply['reply_content']
        
        success = False
        if use_browser:
            success = await post_reply_via_browser(post_id, handle, content, headless=headless)
        
        if not success:
            api = get_twitter_client()
            if api:
                try:
                    print(f"Replier: Posting reply via API to {post_id}...")
                    api.create_tweet(text=content, in_reply_to_tweet_id=post_id)
                    success = True
                except Exception as e:
                    print(f"Replier: API Error: {e}")
            else:
                print("Replier: No API client or browser success.")
        
        if success:
            mark_reply_posted(reply['id'])
            print(f"Replier: Successfully processed reply for {post_id}")
        
        await asyncio.sleep(5) 

if __name__ == "__main__":
    asyncio.run(process_replies())
