import json
import asyncio
import os
import random
import csv
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from db import get_pending_replies, mark_reply_status, update_handle_check, get_conn, REPLIES_CSV

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

async def run_poster():
    # Load config
    with open("config.json") as f:
        cfg = json.load(f)
    
    mode = cfg.get("workflow_mode", "draft")
    if mode == "draft":
        replies = get_pending_replies()
        if replies:
            print(f"\nℹ️ Poster: workflow_mode is 'draft'. Skipping actual posting.")
            print(f"   {len(replies)} replies are waiting in 'replies.csv' for review.")
        return

    latency = cfg.get("reply_latency_minutes", 10)
    
    print(f"\n🚀 Poster: Checking for pending replies (Latency: {latency}m)...")
    
    replies = get_pending_replies()
    
    if not replies:
        print("  No pending replies.")
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
