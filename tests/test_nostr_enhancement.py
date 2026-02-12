import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from poster import capture_tweet_screenshot
from nostr_publisher import publish_to_nostr
from media_uploader import upload_media
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def test_screenshot():
    print("\n--- 📸 Testing Screenshot ---")
    handle = "elonmusk"
    # Use a recent post ID if possible, or a stable one
    post_id = "1889419131641016805" 
    output = "debug/test_screenshot.png"
    
    # Ensure debug dir exists
    os.makedirs("debug", exist_ok=True)
    
    success = await capture_tweet_screenshot(handle, post_id, output)
    if success:
        print(f"✅ Screenshot success: {output}")
        return output
    else:
        print("❌ Screenshot failed.")
        return None

def test_nostr_publish(screenshot_path=None):
    print("\n--- 📡 Testing Nostr Publish ---")
    content = "This is a test reply from X-Watcher's NOSTR enhancement verification."
    nitter_link = "https://nitter.poast.org/elonmusk/status/1889419131641016805"
    screenshot_url = None
    if screenshot_path:
        screenshot_url = upload_media(screenshot_path)
    
    event_id = publish_to_nostr(content, nitter_link, screenshot_url)
    if event_id:
        print(f"✅ Nostr publish success: {event_id}")
    else:
        print("❌ Nostr publish failed.")

async def test_general_screenshot():
    print("\n--- 📸 Testing General Screenshot (Example.com) ---")
    output = "debug/test_general.png"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.com")
        await page.screenshot(path=output)
        await browser.close()
    if os.path.exists(output):
        print(f"✅ General screenshot success: {output}")
        return True
    return False

async def main():
    print("🚀 Starting NOSTR Enhancement Verification...")
    
    # Try general first to prove toolchain
    await test_general_screenshot()
    
    path = await test_screenshot()
    
    if not os.getenv("NOSTR_PRIVATE_KEY"):
        print("⚠️ Skipping Nostr publish: NOSTR_PRIVATE_KEY not found in .env")
    else:
        test_nostr_publish(path)
        
    print("\n🏁 Verification Batch Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
