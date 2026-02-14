import json
import asyncio
import os
import random
import csv
import sys
from datetime import datetime, timezone, timedelta
from tqdm import tqdm
import tweepy
from playwright.async_api import async_playwright
from db import get_qualified_replies, mark_reply_status, update_handle_check, get_post_details, update_nostr_status, add_post, REPLIES_CSV # Added add_post
from nostr_publisher import publish_to_nostr
from media_uploader import upload_media

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
            wait_on_rate_limit=False  # We handle this manually with a progress bar
        )
        return client
    except Exception as e:
        print(f"  ❌ API Error initializing client: {e}")
        return None

def check_manual_rate_limits():
    """
    Checks if we have exceeded the manual rate limits:
    - 17 requests / 24 hours
    - 500 requests / 30 days
    Returns (True, wait_seconds) if limited, (False, 0) if allowed.
    """
    if not os.path.exists(REPLIES_CSV):
        return False, 0
        
    api_posts = []
    
    # Read REPLIES_CSV to find successful API posts
    # We assume 'posted' status means successful API post if reply_tweet_id is present, 
    # but strictly speaking browser posts also set 'posted'. 
    # However, 'browser_posted_id_placeholder' indicates a browser post.
    # We should look for numeric IDs or differentiate. 
    # For safety, let's count ALL 'posted' entries towards the limit if we can't distinguish,
    # OR we assume browser posts don't count towards API limits (which they don't).
    # Browser post ID placeholder is 'browser_posted_id_placeholder'.
    
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['status'] == 'posted' and row.get('posted_at'):
                # Check if it was an API post
                # If reply_tweet_id is not the placeholder, it's likely API or scraped ID.
                # Ideally we should log the method. For now, let's assume all non-placeholder are API
                # or just count everything to be safe/conservative? 
                # The user requirement is specific to API limits.
                # Looking at logs: API posts have real IDs. Browser fallback has placeholder.
                
                tid = row.get('reply_tweet_id', '')
                if tid == 'browser_posted_id_placeholder':
                    continue
                    
                try:
                    posted_at = datetime.fromisoformat(row['posted_at'])
                    if posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
                    api_posts.append(posted_at)
                except:
                    pass

    now = datetime.now(timezone.utc)
    
    # 24h limit
    cutoff_24h = now - timedelta(hours=24)
    posts_24h = [t for t in api_posts if t > cutoff_24h]
    
    if len(posts_24h) >= 17:
        # Find when the oldest post in the window expires
        oldest_in_window = min(posts_24h)
        # reset time is oldest + 24h
        reset_time = oldest_in_window + timedelta(hours=24)
        wait_seconds = (reset_time - now).total_seconds()
        if wait_seconds < 0: wait_seconds = 0
        return True, wait_seconds + 5 # Buffer
        
    # Monthly limit (approx 30 days)
    cutoff_30d = now - timedelta(days=30)
    posts_30d = [t for t in api_posts if t > cutoff_30d]
    
    if len(posts_30d) >= 500:
        oldest_in_window = min(posts_30d)
        reset_time = oldest_in_window + timedelta(days=30)
        wait_seconds = (reset_time - now).total_seconds()
        if wait_seconds < 0: wait_seconds = 0
        return True, wait_seconds + 30 # Buffer
        
    return False, 0

def wait_with_progress(seconds, reason="Rate limit reached"):
    """Displays a progress bar for the wait duration."""
    print(f"\n🛑 {reason}. Waiting {int(seconds)}s for reset...")
    for _ in tqdm(range(int(seconds)), desc="⏳ Backing off", unit="s", ncols=75):
        import time
        time.sleep(1)

async def post_reply_via_api(content, reply_to_id):
    """
    Posts a reply using official Twitter API (v2) via Tweepy.
    """
    client = get_twitter_client()
    if not client:
        return False, None

    print(f"  API: Attempting to reply to ID {reply_to_id}...")
    
    # Check manual limits before attempting
    is_limited, wait_time = check_manual_rate_limits()
    if is_limited:
        wait_with_progress(wait_time, "Manual 24h/Monthly Limit Reached")
        return False, None
        
    try:
        response = client.create_tweet(text=content, in_reply_to_tweet_id=reply_to_id)
        if response and response.data:
            tweet_id = response.data['id']
            print(f"  ✅ API: Posted reply successfully! ID: {tweet_id}")
            return True, tweet_id
        else:
            print("  ❌ API: No data in response.")
            return False, None
    except tweepy.TooManyRequests as e:
        # Extract reset time from headers if possible, otherwise default
        reset_time = int(e.response.headers.get("x-rate-limit-reset", 0)) if e.response else 0
        wait_seconds = 900 # Default 15m
        if reset_time > 0:
            wait_seconds = reset_time - datetime.now(timezone.utc).timestamp()
            if wait_seconds < 0: wait_seconds = 900
            
        print(f"\n⚠️ API Window Limit: Received 429 (Too Many Requests).")
        print(f"   Note: This is a short-term 15-minute window throttle from X, separate from your daily/monthly ceiling.")
        wait_with_progress(wait_seconds, "API 429 Window Throttled")
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
    
    is_limited, wait_time = check_manual_rate_limits()
    if is_limited:
        wait_with_progress(wait_time, "Manual 24h/Monthly Limit Reached")
        return False, None, None

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
    except tweepy.TooManyRequests as e:
        # Extract reset time from headers if possible, otherwise default
        reset_time = int(e.response.headers.get("x-rate-limit-reset", 0)) if e.response else 0
        wait_seconds = 900 # Default 15m
        if reset_time > 0:
            wait_seconds = reset_time - datetime.now(timezone.utc).timestamp()
            if wait_seconds < 0: wait_seconds = 900
            
        print(f"\n⚠️ API Window Limit: Received 429 (Too Many Requests).")
        print(f"   Note: This is a short-term 15-minute window throttle from X, separate from your daily/monthly ceiling.")
        wait_with_progress(wait_seconds, "API 429 Window Throttled")
        return False, None, None
    except tweepy.Forbidden as e:
        print(f"  ❌ API Error posting tweet: 403 Forbidden")
        print(f"     Details: {e}")
        print(f"     TIP: Check 'App permissions' in X Developer Portal (must be 'Read and Write').")
        return False, None, None
    except tweepy.TweepyException as e:
        print(f"  ❌ API Error posting tweet: {e}")
        return False, None, None

async def capture_tweet_screenshot(handle, post_id, output_path):
    """
    Captures a screenshot of a specific tweet element.
    """
    print(f"  📸 Screenshot: Capturing @{handle}/status/{post_id}...")
    
    with open("config_user/config.json") as f:
        cfg = json.load(f)

    user_data_dir = "data/browser_session"
    handle = handle.strip().strip("@")
    url = f"https://x.com/{handle}/status/{post_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=cfg.get("headless_browser", True),
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Try to find the specific tweet article
            # article[data-testid="tweet"] is the usual selector
            # We want the main one, not replies. Usually first or filtered by ID link
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            
            # Find the article that contains the status link with our post_id
            articles = await page.query_selector_all('article[data-testid="tweet"]')
            target_article = None
            for art in articles:
                link = await art.query_selector(f'a[href*="/status/{post_id}"]')
                if link:
                    target_article = art
                    break
            
            if not target_article and articles:
                target_article = articles[0]
                
            if target_article:
                # --- AESTHETIC REFINEMENT ---
                # Hide the login banner, sticky headers, and other overlays
                await page.evaluate("""
                    () => {
                        const selectors = [
                            '[data-testid="BottomBar-root"]', 
                            '#layers', 
                            '[data-testid="cookieBar"]',
                            'header', 
                            '[data-testid="TopTabBar"]',
                            'div[role="progressbar"]'
                        ];
                        selectors.forEach(s => {
                            const elements = document.querySelectorAll(s);
                            elements.forEach(el => el.style.display = 'none');
                        });
                        
                        // Also try to remove any generic "fixed" or "sticky" elements that might overlap
                        const allFixed = document.querySelectorAll('*');
                        allFixed.forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.position === 'fixed' || style.position === 'sticky') {
                                if (!el.contains(document.querySelector('article'))) {
                                     // el.style.display = 'none'; // Dangerous but effective
                                }
                            }
                        });
                    }
                """)
                
                # Ensure the article is in view and wait a bit for any dynamic content/images
                await target_article.scroll_into_view_if_needed()
                await asyncio.sleep(2) 
                
                # Ensure screenshots directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                await target_article.screenshot(path=output_path)
                print(f"  ✅ Screenshot: Saved to {output_path}")
                return True
            else:
                print("  ❌ Screenshot: Article element not found.")
                return False
        except Exception as e:
            print(f"  ❌ Screenshot Error: {e}")
            return False
        finally:
            await browser.close()

async def post_reply_via_browser(handle, content, reply_to_url):
    """
    Spins up a browser, logs in (if needed), finds the post, and replies.
    Returns True if success, False otherwise.
    """
    print(f"  Browser: Launching to reply to @{handle}...")
    
    with open("config_user/config.json") as f:
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
                await page.screenshot(path=f"debug/debug_reply_fail_{handle}.png")
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
    
    with open("config_user/config.json") as f:
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
                await page.screenshot(path="debug/debug_post_fail_3.png")
                return False, None, None
                
        except Exception as e:
            print(f"  Browser Navigation Error: {e}")
            return False, None, None
        finally:
            await browser.close()
    return False, None, None

async def run_poster():
    # Load config
    with open("config_user/config.json") as f:
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
    
    # Check overall limits before starting loop
    is_limited, wait_time = check_manual_rate_limits()
    if is_limited:
        wait_with_progress(wait_time, "Daily/Monthly API limit reached")
        # Proceed to next only if we want to run browser posts? 
        # But loop mixes them. We should probably let it continue and individual API calls will fail/block?
        # Or better: if globally limited, we can only do browser posts.
        # But check_manual_rate_limits blocks.
        # Actually, if we are manual limited, check_manual_rate_limits returning true means we SHOULD wait.
        # But wait_with_progress sleeps. So we just sleep and then return or continue?
        # If we return, we skip this cycle.
        return
    
    for r in replies:
        reply_id = r['id']
        handle = r['handle']
        content = r['content']
        created_at_str = r.get('created_at')
        post_id = r['target_post_id']
        
        # Check latency
        # Check latency against POST creation time
        post = get_post_details(post_id)
        if post:
            posted_at_str = post.get('posted_at') or post.get('scraped_at')
            if posted_at_str:
                try:
                    # Support both ISO and Twitter format
                    try:
                        posted_at = datetime.fromisoformat(posted_at_str)
                    except ValueError:
                        clean_date = posted_at_str.replace(" UTC", "").replace("· ", "")
                        posted_at = datetime.strptime(clean_date, "%b %d, %Y %I:%M %p")

                    if posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
                        
                    post_age_minutes = (current_time - posted_at).total_seconds() / 60
                    
                    if post_age_minutes < latency:
                        print(f"  ⏳ Skipping reply to @{handle} (Post Age {post_age_minutes:.1f}m < Latency {latency}m)...")
                        continue
                except Exception as e:
                    print(f"  ⚠️ Date parse error for post {post_id}: {e}")
        else:
             print(f"  ⚠️ Warning: Target post {post_id} not found for latency check.")
        
        print(f"  📣 Posting reply to @{handle} (ID: {reply_id})...")
        
        # Construct Reply URL (just the post URL)
        # Assuming we can find the post by ID. Nitter ID is usually the tweet ID.
        reply_to_url = f"https://x.com/{handle}/status/{post_id}"
        
        success = False
        reply_tweet_id = ""
        
        use_browser = cfg.get("use_browser_replier", False)
        
        # Try Browser if enabled
        if use_browser:
            try:
                 success, reply_tweet_id = await post_reply_via_browser(handle, content, reply_to_url)
            except Exception as e:
                print(f"  Browser posting failed: {e}")
            
        # Fallback to API if Browser fails OR if browser is disabled
        if not success:
            if use_browser:
                print("  ⚠️ Browser posting failed. Attempting API fallback...")
            else:
                print("  🔌 Browser replier disabled. Using API...")
                
            # We need the tweet ID for the API, which is post_id
            success, api_tweet_id = await post_reply_via_api(content, post_id)
            if success:
                reply_tweet_id = api_tweet_id

        if not success:
            print("  ❌ Failed to post reply to X.")
        else:
            print(f"  ✅ Successfully posted reply to @{handle}!")
            mark_reply_status(reply_id, 'posted', reply_tweet_id)
            update_handle_check(handle)
            
            # Immediately record in posts.csv so engagement monitor can find it
            my_handle = cfg.get("twitter_handle", "kangofire").strip("@")
            add_post(
                post_id=reply_tweet_id,
                handle=my_handle,
                content=content,
                score="100", # Our own replies are always relevant
                is_reply=True,
                posted_at=datetime.now(timezone.utc).isoformat()
            )
            print(f"  💾 Recorded bot reply {reply_tweet_id} in posts.csv for engagement tracking.")

        # --- NOSTR INTEGRATION (DECOUPLED) ---
        if cfg.get("nostr_enabled", False):
            print(f"  🔗 NOSTR: Starting broadcast for reply {reply_id}...")
            
            screenshot_url = None
            if cfg.get("nostr_screenshot_enabled", False):
                screenshot_path = f"debug/screenshots/{post_id}.png"
                if await capture_tweet_screenshot(handle, post_id, screenshot_path):
                    screenshot_url = upload_media(screenshot_path)
            
            # Use nitter link as requested
            mirrors = cfg.get("nitter_mirrors", ["https://nitter.poast.org"])
            nitter_mirror = mirrors[0] if mirrors else "https://nitter.poast.org"
            nitter_link = f"{nitter_mirror.rstrip('/')}/{handle}/status/{post_id}"
            
            nostr_event_id = publish_to_nostr(content, nitter_link, screenshot_url)
            if nostr_event_id:
                update_nostr_status(reply_id, nostr_event_id, "Y")
            else:
                update_nostr_status(reply_id, "", "N")

        # Rate limiting between posts
        await asyncio.sleep(random.uniform(10, 30))
    
    print("✅ Poster Complete ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_poster())
