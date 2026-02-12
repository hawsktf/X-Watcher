import json
import asyncio
import os
import random
import csv
from datetime import datetime, timezone
import tweepy
from playwright.async_api import async_playwright
from db import get_qualified_replies, mark_reply_status, update_handle_check, get_conn, REPLIES_CSV # Changed import

def get_twitter_client():
    """
    Returns an authenticated Tweepy Client using credentials from .env
    """
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    
    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("  ❌ API Error: Missing Twitter API credentials in .env")
        return None

    try:
        # V2 Client for posting tweets
        # For Free Tier and posting, we often need OAuth 1.0a User Context.
        # Passing bearer_token might force App-only auth in some contexts or be mixed up.
        # Let's try forcing OAuth 1.0a by OMITTING bearer_token if we have user tokens.
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True
        )
        return client
    except Exception as e:
        print(f"  ❌ API Error initializing client: {e}")
        return None

async def post_reply_via_api(content, reply_to_id):
    """
    Posts a reply using official Twitter API (v2) via Tweepy.
    """
    client = get_twitter_client()
    if not client:
        return False, None

    print(f"  API: Attempting to reply to ID {reply_to_id}...")
    try:
        response = client.create_tweet(text=content, in_reply_to_tweet_id=reply_to_id)
        if response and response.data:
            tweet_id = response.data['id']
            print(f"  ✅ API: Posted reply successfully! ID: {tweet_id}")
            return True, tweet_id
        else:
            print("  ❌ API: No data in response.")
            return False, None
    except tweepy.TweepyException as e:
        print(f"  ❌ API Error posting reply: {e}")
        return False, None

async def post_tweet_via_api(content):
    """
    Posts a new tweet using official Twitter API (v2) via Tweepy.
    """
    client = get_twitter_client()
    if not client:
        return False, None, None

    print(f"  API: Attempting to post new tweet...")
    try:
        response = client.create_tweet(text=content)
        if response and response.data:
            tweet_id = response.data['id']
            # We need to fetch the handle separately if we want it, or just return "API_USER"
            print(f"  ✅ API: Posted new tweet successfully! ID: {tweet_id}")
            return True, tweet_id, "API_USER"
        else:
            print("  ❌ API: No data in response.")
            return False, None, None
    except tweepy.TweepyException as e:
        print(f"  ❌ API Error posting tweet: {e}")
        return False, None, None

async def post_reply_via_browser(handle, content, reply_to_url):
    """
    Spins up a browser, logs in (if needed), finds the post, and replies.
    Returns True if success, False otherwise.
    """
    print(f"  Browser: Launching to reply to @{handle}...")
    
    with open("config.json") as f:
        cfg = json.load(f)

    # Use persistent context to keep login state
    user_data_dir = "data/browser_session"
    
    async with async_playwright() as p:
        # Launch persistent context
        browser = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=cfg.get("headless_browser", True),
            args=["--disable-blink-features=AutomationControlled"] # Anti-detect
        )
        
        page = await browser.new_page()
        
        try:
            # Randomize user agent slightly if possible, or just rely on persistent context
            
            print(f"  Browser: Navigating to {reply_to_url}...")
            await page.goto(reply_to_url, wait_until="domcontentloaded", timeout=60000)
            
            # Check if login is required (simple check for "Log in" text or input field)
            try:
                login_indicator = await page.wait_for_selector('[data-testid="login"]', timeout=3000)
                if login_indicator:
                    print("  Browser: Login required! (This should be handled by a manual login session first)")
                    # We could try auto-login here if credentials are in .env, but for now we assume session is valid
            except:
                pass # No login button found, assume logged in
                
            # Wait for reply input area
            # Twitter class names change, but data-ids are usually stable
            print("  Browser: Looking for reply input...")
            
            # Click the reply div/button
            # The structure is usually the post > reply icon OR the "Post your reply" placeholder
            try:
                # Click the "Reply" icon/text area. 
                # Strategy 1: Look for "Post your reply" placeholder
                reply_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
                await reply_input.click()
                await reply_input.fill(content)
                
                # Random pause
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                # Click "Reply" button
                submit_button = await page.wait_for_selector('[data-testid="tweetButtonInline"]', timeout=5000)
                
                # Check if button is disabled (empty text?)
                if await submit_button.is_disabled():
                    print("  Browser Error: Reply button disabled!")
                    return False, ""
                    
                await submit_button.click()
                
                # Wait for success indicator (e.g., toast or potential redirect)
                print("  Browser: Reply submitted. Waiting for confirmation...")
                await asyncio.sleep(5) 
                
                # Capture URL? Twitter doesn't always redirect to the new tweet immediately.
                # We can assume success if no error toast appears.
                
                return True, "browser_posted_id_placeholder" # We can't easily get the ID without scraping the new post
                
            except Exception as e:
                print(f"  Browser Error finding reply elements: {e}")
                # DIAGNOSTIC: Log page title and snippet to debug login/shadowban issues
                title = await page.title()
                content_snippet = await page.content()
                print(f"  [DIAGNOSTIC] Page Title: {title}")
                print(f"  [DIAGNOSTIC] Page Snippet: {content_snippet[:200]}...")
                # Save screenshot for debug
                await page.screenshot(path=f"data/debug_reply_fail_{handle}.png")
                return False, ""
                
        except Exception as e:
            print(f"  Browser Navigation Error: {e}")
            return False, ""
        finally:
            await browser.close()

async def post_tweet_via_browser(content):
    """
    Spins up a browser, logs in (if needed), posts a new tweet.
    Returns (True, tweet_id, handle) if success, otherwise (False, None, None).
    """
    print(f"  Browser: Launching to post new tweet...")
    
    with open("config.json") as f:
        cfg = json.load(f)

    # Use persistent context to keep login state
    user_data_dir = "data/browser_session"
    
    async with async_playwright() as p:
        # Launch persistent context
        browser = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=cfg.get("headless_browser", True),
            args=["--disable-blink-features=AutomationControlled"] # Anti-detect
        )
        
        page = await browser.new_page()
        
        try:
            # Navigate to Base URL
            print(f"  Browser: Navigating to X.com...")
            await page.goto("https://x.com", wait_until="domcontentloaded", timeout=60000)
            
            # Check for generic error page "Something went wrong"
            try:
                # Text "Retry" or button with "Retry"
                retry_button = await page.wait_for_selector('text="Retry"', timeout=5000)
                if retry_button:
                    print("  Browser: Found 'Retry' button. Clicking...")
                    await retry_button.click()
                    await page.wait_for_load_state("domcontentloaded")
            except:
                pass

            # Check for login requirement
            try:
                login_indicator = await page.wait_for_selector('[data-testid="login"]', timeout=5000)
                if login_indicator:
                    print("  Browser: Login required!")
                    return False, None, None
            except:
                pass 
            
            # Click the main "Post" button on the side nav
            print("  Browser: Looking for 'Post' button...")
            try:
                # This button ID is usually stable
                post_button = await page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', timeout=10000)
                await post_button.click()
            except Exception as e:
                print(f"  Browser: Could not find side nav Post button. Trying to find inline composer...")
                await page.keyboard.press("n")

            # Wait for text area in the modal
            print("  Browser: Waiting for text area...")
            try:
                # The text area in the modal
                text_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
                await text_input.click()
                await text_input.fill(content)
                
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                # Click Post button
                submit_button = await page.wait_for_selector('[data-testid="tweetButton"]', timeout=5000)
                
                if await submit_button.is_disabled():
                    print("  Browser Error: Post button disabled!")
                    return False, None, None
                    
                await submit_button.click()
                print("  Browser: Tweet submitted. Waiting for confirmation...")
                
                # Wait for "Your post was sent" toast and "View" link
                try:
                    view_link = await page.wait_for_selector('a[href*="/status/"]', timeout=10000)
                    if view_link:
                        href = await view_link.get_attribute("href")
                        print(f"  Browser: Found post URL: {href}")
                        parts = href.split('/')
                        if len(parts) >= 4:
                            handle = parts[1]
                            tweet_id = parts[3]
                            return True, tweet_id, handle
                except:
                    print("  Browser: Could not find 'View' link. Checking profile...")
                    # Fallback to profile
                    profile_link = await page.wait_for_selector('[data-testid="AppTabBar_Profile_Link"]', timeout=5000)
                    profile_href = await profile_link.get_attribute("href")
                    handle = profile_href.strip('/')
                    
                    print(f"  Browser: Checking profile @{handle}...")
                    await page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded")
                    
                    # Get the first tweet
                    first_article = await page.wait_for_selector('article', timeout=10000)
                    status_link = await first_article.query_selector('a[href*="/status/"]')
                    if status_link:
                        href = await status_link.get_attribute("href")
                        if "/status/" in href:
                             parts = href.split('/')
                             tweet_id = parts[3] if len(parts) >= 4 else href.split("/status/")[1]
                             print(f"  Browser: Found latest post ID: {tweet_id}")
                             return True, tweet_id, handle

            except Exception as e:
                print(f"  Browser Error posting/finding elements: {e}")
                # Save screenshot
                await page.screenshot(path="data/debug_post_fail_3.png")
                return False, None, None
                
        except Exception as e:
            print(f"  Browser Navigation Error: {e}")
            return False, None, None
        finally:
            await browser.close()
    return False, None, None

async def run_poster():
    # Load config
    with open("config.json") as f:
        cfg = json.load(f)
    
    mode = cfg.get("workflow_mode", "draft")
    if mode == "draft":
        replies = get_qualified_replies() # Changed to qualified
        if replies:
            print(f"\nℹ️ Poster: workflow_mode is 'draft'. Skipping actual posting.")
            print(f"   {len(replies)} QUALIFIED replies are waiting in 'replies.csv' for review (set mode='post' to execute).")
        return

    latency = cfg.get("reply_latency_minutes", 10)
    
    print(f"\n🚀 Poster: Checking for QUALIFIED replies (Latency: {latency}m)...")
    
    replies = get_qualified_replies() # Changed to qualified
    
    if not replies:
        print("  No qualified replies.")
        return

    current_time = datetime.now(timezone.utc)
    
    for r in replies:
        reply_id = r['id']
        handle = r['handle']
        content = r['content']
        created_at_str = r.get('created_at')
        post_id = r['target_post_id']
        
        # Check latency
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                # Ensure created_at is aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                    
                diff = (current_time - created_at).total_seconds() / 60
                if diff < latency:
                    print(f"  ⏳ Skipping reply to @{handle} (Created {diff:.1f}m ago, Waiting {latency}m)...")
                    continue
            except Exception as e:
                print(f"  Date parse error for {reply_id}: {e}")
        
        print(f"  📣 Posting reply to @{handle} (ID: {reply_id})...")
        
        # Construct Reply URL (just the post URL)
        # Assuming we can find the post by ID. Nitter ID is usually the tweet ID.
        reply_to_url = f"https://x.com/{handle}/status/{post_id}"
        
        success = False
        reply_tweet_id = ""
        
        # Try Browser first (Preferred)
        try:
             success, reply_tweet_id = await post_reply_via_browser(handle, content, reply_to_url)
        except Exception as e:
            print(f"  Browser posting failed: {e}")
            
        # Fallback to API if Browser fails
        if not success:
            print("  ⚠️ Browser posting failed. Attempting API fallback...")
            # We need the tweet ID for the API, which is post_id
            success, api_tweet_id = await post_reply_via_api(content, post_id)
            if success:
                reply_tweet_id = api_tweet_id

        if not success:
            print("  ❌ Failed to post reply.")
            # Optional: Mark as 'failed' or keep 'pending' to retry?
            # For now, let's keep pending but maybe log an error count (not impl)
        else:
            print(f"  ✅ Successfully posted reply to @{handle}!")
            mark_reply_status(reply_id, 'posted', reply_tweet_id)
            update_handle_check(handle) # Update last_posted indirectly? Or add log
            
        # Rate limiting between posts
        await asyncio.sleep(random.uniform(10, 30))

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_poster())
