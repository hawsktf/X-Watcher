import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from db import add_engagement_reply, get_existing_post_ids, init_db, POSTS_CSV
import csv

# Import the proven scraper logic
from scraper import scrape_handle, NITTER_MIRRORS_DEFAULT

load_dotenv()

async def scrape_post_replies(post_url, context):
    """
    Visits a post URL and scrapes replies using selectors consistent with scraper.py.
    """
    page = await context.new_page()
    replies = []
    try:
        print(f"  🔍 Checking replies for {post_url}...")
        # Check if URL is Nitter or X
        is_nitter = "nitter" in post_url or "xcancel" in post_url
        
        await page.goto(post_url, wait_until="networkidle" if not is_nitter else "domcontentloaded", timeout=30000)
        
        if is_nitter:
            # Nitter selectors
            try: await page.wait_for_selector(".timeline-item", timeout=10000)
            except: return []
            
            items = await page.query_selector_all(".timeline-item")
            if len(items) <= 1: return []
            
            # Skip first one (main post)
            for item in items[1:]:
                content_el = await item.query_selector(".tweet-content")
                if not content_el: continue
                content = await content_el.inner_text()
                
                handle_el = await item.query_selector(".username")
                handle = (await handle_el.inner_text()).strip("@") if handle_el else ""
                
                link_el = await item.query_selector(".tweet-link")
                reply_id = None
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href: reply_id = href.split("/")[-1].split("#")[0]
                
                if reply_id and content and handle:
                    replies.append({'reply_id': reply_id, 'handle': handle, 'content': content})
        else:
            # X.com selectors
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            except:
                return []

            tweets = await page.query_selector_all('article[data-testid="tweet"]')
            if len(tweets) <= 1:
                return []

            # Skip the first one (the main post)
            for tweet in tweets[1:]:
                content_el = await tweet.query_selector('div[data-testid="tweetText"]')
                if not content_el: continue
                content = await content_el.inner_text()
                
                handle_el = await tweet.query_selector('div[data-testid="User-Name"] a')
                handle = ""
                if handle_el:
                    href = await handle_el.get_attribute("href")
                    if href: handle = href.strip("/")
                
                time_link = await tweet.query_selector('time')
                reply_id = None
                if time_link:
                    parent_a = await time_link.evaluate_handle('el => el.closest("a")')
                    href = await parent_a.get_attribute("href")
                    if href and "/status/" in href:
                        reply_id = href.split("/")[-1].split("?")[0]
                
                if reply_id and content and handle:
                    replies.append({'reply_id': reply_id, 'handle': handle, 'content': content})
                
    except Exception as e:
        print(f"  ❌ Error scraping replies: {e}")
    finally:
        await page.close()
    return replies

async def run_engagement():
    load_dotenv()
    
    with open("config_user/config.json") as f:
        cfg = json.load(f)
    
    if not cfg.get("engagement_enabled", False):
        print("Engagement: Disabled in config. Skipping.")
        return

    my_handle = cfg.get("twitter_handle")
    if not my_handle:
        print("Engagement: twitter_handle not found in config.json. Skipping.")
        return

    my_handle = my_handle.strip("@")
    mode = cfg.get("engagement_mode", "assess only")
    
    print(f"\n📈 Starting Engagement Monitor for @{my_handle} (Mode: {mode})...")

    async with async_playwright() as p:
        user_data_dir = cfg.get("browser_user_data_dir", "data/browser_session")
        if not os.path.isabs(user_data_dir):
            user_data_dir = os.path.join(os.getcwd(), user_data_dir)
            
        headless = cfg.get("headless_browser", True)
        
        # Consistent browser launch with scraper.py
        context = await p.firefox.launch_persistent_context(
            user_data_dir,
            headless=headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True
        )
        
        try:
            # 1. Use the proven scrape_handle logic to get the user's latest posts
            print(f"  🐦 Scraping @{my_handle} profile using fallback logic...")
            success, blocked, count, new_c, new_rep, new_rt = await scrape_handle(my_handle, context)
            
            if not success:
                print(f"  ❌ Failed to scrape @{my_handle} profile.")
                return

            # 2. Get the latest posts for this handle from the DB
            post_links = []
            if os.path.exists(POSTS_CSV):
                with open(POSTS_CSV, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    all_posts = list(reader)
                    
                    # Filter for my handle, exclude retweets, and ensure it's within 48 hours
                    my_posts = []
                    now = datetime.now(timezone.utc)
                    limit_hours = 48
                    
                    for p in all_posts:
                        if p['handle'].lower() != my_handle.lower(): continue
                        if p.get('is_retweet') == "True": continue
                        
                        posted_at_str = p.get('posted_at')
                        if not posted_at_str:
                            posted_at_str = p.get('scraped_at')
                            
                        try:
                            try:
                                posted_at = datetime.fromisoformat(posted_at_str)
                            except ValueError:
                                # Twitter format fallback
                                clean_date = posted_at_str.replace(" UTC", "").replace("· ", "")
                                posted_at = datetime.strptime(clean_date, "%b %d, %Y %I:%M %p")
                                
                            if posted_at.tzinfo is None:
                                posted_at = posted_at.replace(tzinfo=timezone.utc)
                                
                            age_hours = (now - posted_at).total_seconds() / 3600
                            if age_hours <= limit_hours:
                                my_posts.append(p)
                        except:
                            # If date parse fails, we'll keep it as a fallback if it's very recent scraped_at
                            pass

                    my_posts.sort(key=lambda x: x.get('scraped_at', ''), reverse=True)
                    
                    for p in my_posts[:5]: # Check last 5 recent posts
                        post_id = p['post_id']
                        # Determine current source for the URL
                        source = cfg.get("last_successful_source", "https://x.com")
                        if not source.startswith("http"): source = "https://x.com"
                        
                        full_url = f"{source.rstrip('/')}/{my_handle}/status/{post_id}"
                        post_links.append((post_id, full_url))
            
            if not post_links:
                print("  ℹ️ No posts found in database for this handle.")
                return

            print(f"  📊 Found {len(post_links)} posts to check for replies.")
            
            new_replies_count = 0
            for post_id, post_url in post_links:
                replies = await scrape_post_replies(post_url, context)
                for r in replies:
                    # Filter out own handle
                    if r['handle'].lower() == my_handle.lower():
                        continue
                        
                    is_new = add_engagement_reply(
                        reply_id=r['reply_id'],
                        target_post_id=post_id,
                        handle=r['handle'],
                        content=r['content'],
                        engagement_mode=mode
                    )
                    if is_new:
                        new_replies_count += 1
                        print(f"    📩 New reply from @{r['handle']}: {r['content'][:50]}...")
            
            print(f"✅ Engagement Check Complete: {new_replies_count} new replies recorded.")
            
        finally:
            await context.close()

if __name__ == "__main__":
    init_db()
    asyncio.run(run_engagement())
