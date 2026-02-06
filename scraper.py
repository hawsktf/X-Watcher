import asyncio
import random
import json
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from db import add_post, update_handle_check, get_existing_post_ids

# Load environment variables
load_dotenv()

NITTER_MIRRORS_DEFAULT = [
    "https://nitter.privacydev.net",
    "https://xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.cz",
]

def update_config_source(source):
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        cfg["last_successful_source"] = source
        with open("config.json", "w") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"Error updating config source: {e}")

async def scrape_x_dot_com(handle, headless=True, timeout=60000):
    user = os.getenv("TWITTER_USERNAME")
    pwd = os.getenv("TWITTER_PASSWORD")
    
    if user: user = user.strip('"').strip("'")
    if pwd: pwd = pwd.strip('"').strip("'")
    
    if not user or user == "YOUR_USERNAME":
        print("X.com: No credentials in .env. Skipping.")
        return False, False

    with open("config.json") as f:
        cfg = json.load(f)
    
    base_url = cfg.get("x_dot_com_base_url", "https://x.com").rstrip("/")
    with_replies = cfg.get("scrape_with_replies", False)
    suffix = "/with_replies" if with_replies else ""
    url = f"{base_url}/{handle}{suffix}"
    print(f"X.com: Scraping {handle} via {url}...")
    
    async with async_playwright() as p:
        user_data_dir = cfg.get("browser_user_data_dir", "data/browser_session")
        if not os.path.isabs(user_data_dir):
            user_data_dir = os.path.join(os.getcwd(), user_data_dir)
        
        context = await p.firefox.launch_persistent_context(
            user_data_dir,
            headless=headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            viewport={"width": 1280, "height": 720}
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            # ATTEMPT TO CLOSE MODALS
            try:
                close_btn = await page.query_selector('div[role="dialog"] div[aria-label="Close"]')
                if close_btn:
                    await close_btn.click()
                    print("X.com: Closed blocking modal.")
            except: pass

            # LOGIN DETECTION
            is_logged_in = await page.query_selector('[data-testid="SideNav_AccountSwitcher_Button"]')
            login_needed = "/login" in page.url or \
                           await page.query_selector('input[autocomplete="username"]') or \
                           await page.query_selector('[data-testid="loginButton"]') or \
                           not is_logged_in

            if login_needed:
                print(f"X.com: Login required for {handle}. (Current URL: {page.url})")
                if "/login" not in page.url:
                    await page.goto("https://x.com/i/flow/login", wait_until="networkidle")
                
                # Step 1: Username
                user_input = await page.wait_for_selector('input[autocomplete="username"]', timeout=20000)
                await user_input.click()
                await page.keyboard.type(user, delay=random.randint(100, 200))
                
                next_btn = await page.query_selector('button:has-text("Next")')
                if next_btn: await next_btn.click()
                else: await page.keyboard.press("Enter")
                
                await page.wait_for_timeout(random.randint(4000, 6000))
                
                # Check for "Try again later"
                page_text = await page.content()
                if any(k in page_text for k in ["Could not log you in now", "Please try again later", "suspicious activity"]):
                     print("X.com: Blocked by 'Try again later' or suspicious activity detection. Aborting X.")
                     return False, True

                # Step 2: Password
                try:
                    pwd_input = await page.wait_for_selector('input[autocomplete="current-password"]', timeout=15000)
                    await pwd_input.click()
                    await page.keyboard.type(pwd, delay=random.randint(100, 250))
                    
                    login_btn = await page.query_selector('button[data-testid="LoginForm_Login_Button"]')
                    if login_btn: await login_btn.click()
                    else: await page.keyboard.press("Enter")
                except:
                    print(f"X.com: Password field didn't appear for {handle}. (URL: {page.url})")
                    return False, False
                
                await page.wait_for_timeout(5000)
                await page.goto(url, wait_until="networkidle")

            # SCRAPE TWEETS
            existing_ids = get_existing_post_ids()
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
            except:
                print(f"X.com: No tweets found for {handle}.")
                return False, False
            
            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(3000)

            tweets = await page.query_selector_all('article[data-testid="tweet"]')
            found_any = False
            scraped_count = 0
            for tweet in tweets:
                # Basic Promoted Check
                if await tweet.query_selector('path[d*="M19.498 3h-15c-1.381 0-2.5 1.119-2.5 2.5v13"]'): continue

                pinned_label = await tweet.query_selector('div[data-testid="socialContext"]')
                is_pinned = False
                if pinned_label:
                    label_text = await pinned_label.inner_text()
                    if "Pinned" in label_text: is_pinned = True
                if is_pinned and cfg.get("ignore_pinned", False): continue

                # Post ID and Time
                time_link = await tweet.query_selector('time')
                post_id = None
                posted_at = None
                if time_link:
                    posted_at = await time_link.get_attribute("datetime")
                    parent_a = await time_link.evaluate_handle('el => el.closest("a")')
                    href = await parent_a.get_attribute("href")
                    if href and "/status/" in href:
                        post_id = href.split("/")[-1].split("?")[0]
                
                if not post_id: continue

                # STOP IF ALREADY SCRAPED (assuming chronological order after pinned)
                if not is_pinned and str(post_id) in existing_ids:
                    print(f"X.com: Reached already scraped post {post_id} for {handle}. Stopping scan.")
                    break

                # Content
                content_el = await tweet.query_selector('div[data-testid="tweetText"]')
                if not content_el: continue
                content = await content_el.inner_text()
                
                # Media and Links
                has_image = bool(await tweet.query_selector('div[data-testid="tweetPhoto"]'))
                has_video = bool(await tweet.query_selector('div[data-testid="videoPlayer"]'))
                
                link_url = ""
                has_link = False
                ext_links = await content_el.query_selector_all("a")
                for el in ext_links:
                    href = await el.get_attribute("href")
                    if href and not href.startswith("/") and ("t.co" in href or "http" in href):
                        link_url = href
                        has_link = True
                        inner_txt = await el.inner_text()
                        content = content.replace(inner_txt, "").strip()
                        break

                # Reply Detection
                reply_context = await tweet.query_selector('div[data-testid="replyContext"]')
                is_reply = bool(reply_context)
                if not is_reply:
                    social_c = await tweet.query_selector('div[data-testid="socialContext"]')
                    if social_c:
                        t = await social_c.inner_text()
                        if "Replying to" in t: is_reply = True

                if post_id and content:
                    status = ""
                    if is_pinned: status += "[PINNED] "
                    if is_reply: status += "[REPLY] "
                    print(f"Found post {post_id}: {status}{content[:50]}...")
                    add_post(post_id, handle, content, score=0, is_reply=is_reply, is_pinned=is_pinned,
                             has_image=has_image, has_video=has_video, has_link=has_link, link_url=link_url, posted_at=posted_at)
                    update_config_source("https://x.com")
                    found_any = True
                    scraped_count += 1
                
                if scraped_count >= 10:
                    print(f"X.com: Reached max scan limit (10) for {handle}.")
                    break
            
            return found_any, False
            
        except Exception as e:
            print(f"X.com error for {handle}: {e}")
            return False, False
        finally:
            try: await context.close()
            except: pass
    return False, False

async def scrape_handle(handle, mirror=None, skip_x=False):
    with open("config.json") as f:
        cfg = json.load(f)
    
    last_source = cfg.get("last_successful_source", "https://x.com")
    use_x = cfg.get("use_x_dot_com", True)
    mirrors = cfg.get("nitter_mirrors", NITTER_MIRRORS_DEFAULT)
    
    with_replies = cfg.get("scrape_with_replies", False)
    nitter_suffix = "?replies=on" if with_replies else "?replies=off"
    
    # 1. Try the prioritized source first
    prioritized_successful = False
    blocked = False
    
    source_to_try = mirror if mirror else last_source
    
    if source_to_try == "https://x.com" and not skip_x and use_x:
        success, blocked = await scrape_x_dot_com(handle, 
                                        headless=cfg.get("headless_browser", True), 
                                        timeout=cfg.get("x_dot_com_timeout_seconds", 60) * 1000)
        if success:
            update_handle_check(handle)
            return True, blocked
        print(f"X.com (prioritized) failed for {handle}, trying Nitter fallback...")
    elif source_to_try.startswith("http") and source_to_try != "https://x.com":
        success, _ = await scrape_nitter(handle, source_to_try, cfg, nitter_suffix)
        if success:
            update_handle_check(handle)
            return True, False
        print(f"Nitter mirror {source_to_try} (prioritized) failed for {handle}, checking alternatives...")

    # 2. Sequential fallback if prioritized source failed
    if not skip_x and use_x and source_to_try != "https://x.com":
        success, blocked = await scrape_x_dot_com(handle, 
                                        headless=cfg.get("headless_browser", True), 
                                        timeout=cfg.get("x_dot_com_timeout_seconds", 60) * 1000)
        if success:
            update_handle_check(handle)
            return True, blocked
        print(f"X.com fallback failed for {handle}, trying alternate mirrors...")

    # Try remaining Nitter mirrors
    # Filter out the source_to_try if it was a Nitter mirror and already failed
    other_mirrors = [m for m in mirrors if m != source_to_try]
    random.shuffle(other_mirrors)

    # If the prioritized source was a Nitter mirror and failed, try other mirrors
    for m in other_mirrors:
        success, _ = await scrape_nitter(handle, m, cfg, nitter_suffix)
        if success:
            update_handle_check(handle)
            return True, blocked
            
    return False, blocked

async def scrape_nitter(handle, mirror, cfg, suffix=""):
    url = f"{mirror}/{handle}{suffix}"
    print(f"Scraping {handle} via {mirror}...")
    
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=cfg.get("headless_browser", True))
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("browser_timeout_seconds", 30)*1000)
            
            # Anti-bot
            title = await page.title()
            if "Verifying" in title or "Cloudflare" in title:
                print(f"Negotiating anti-bot on {mirror}...")
                await page.wait_for_timeout(5000)
                try: await page.wait_for_selector(".timeline-item", timeout=15000)
                except:
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    if not await page.query_selector(".timeline-item"): return False, False

            try: await page.wait_for_selector(".timeline-item", timeout=10000)
            except:
                print(f"No timeline on {mirror}.")
                return False, False

            existing_ids = get_existing_post_ids()
            tweets = await page.query_selector_all(".timeline-item")
            found_any = False
            scraped_count = 0
            for tweet in tweets:
                if await tweet.query_selector(".unavailable"): continue
                
                # ID and Content
                link_el = await tweet.query_selector(".tweet-link")
                if not link_el: continue
                href = await link_el.get_attribute("href")
                post_id = href.split("/")[-1].split("#")[0]
                
                # Meta
                is_pinned = bool(await tweet.query_selector(".pinned"))
                if not is_pinned and str(post_id) in existing_ids:
                    print(f"Nitter: Reached already scraped post {post_id} for {handle}. Stopping scan.")
                    break

                content_el = await tweet.query_selector(".tweet-content")
                if not content_el: continue
                content = await content_el.inner_text()
                
                # Timestamp extraction
                posted_at = None
                date_el = await tweet.query_selector(".tweet-date a")
                if date_el:
                    # title often contains "Feb 6, 2026 · 10:10:10 AM UTC"
                    posted_at = await date_el.get_attribute("title")
                
                if not posted_at:
                    time_el = await tweet.query_selector("time")
                    if time_el:
                        posted_at = await time_el.get_attribute("datetime") or await time_el.get_attribute("title")

                if is_pinned and cfg.get("ignore_pinned", False): continue

                is_reply = bool(await tweet.query_selector(".replying-to"))
                has_image = bool(await tweet.query_selector(".attachment.image"))
                has_video = bool(await tweet.query_selector(".attachment.video"))
                
                # Links
                link_url = ""
                has_link = False
                ext_links = await content_el.query_selector_all("a")
                for el in ext_links:
                    l_href = await el.get_attribute("href")
                    if l_href and not l_href.startswith("/"):
                        link_url = l_href
                        has_link = True
                        break

                if post_id and content:
                    status = ""
                    if is_pinned: status += "[PINNED] "
                    if is_reply: status += "[REPLY] "
                    print(f"Found post {post_id}: {status}{content[:50]}...")
                    add_post(post_id, handle, content, score=0, is_reply=is_reply, is_pinned=is_pinned,
                             has_image=has_image, has_video=has_video, has_link=has_link, link_url=link_url, posted_at=posted_at)
                    update_config_source(mirror)
                    found_any = True
                    scraped_count += 1
                
                if scraped_count >= 10:
                    print(f"Nitter: Reached max scan limit (10) for {handle}.")
                    break
            
            return found_any, False
        except Exception as e:
            print(f"Nitter error for {handle}: {e}")
            return False, False
        finally:
            try:
                await browser.close()
            except:
                pass
    return False, False

async def main():
    with open("config.json") as f: cfg = json.load(f)
    handles = cfg.get("handles", [])
    skip_x_remaining = False
    
    for handle in handles:
        success, blocked = await scrape_handle(handle, skip_x=skip_x_remaining)
        if blocked: skip_x_remaining = True
        if not success:
            print(f"Retrying {handle}...")
            await scrape_handle(handle, skip_x=True)
            
    print("\nScraper completed.")

if __name__ == "__main__":
    asyncio.run(main())
