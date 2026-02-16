import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    user_data_dir = os.path.abspath("data/browser_session")
    print(f"🚀 Launching browser with persistent profile at: {user_data_dir}")
    print("ℹ️  Instructions:")
    print("1. The browser window will open.")
    print("2. Navigate to https://x.com/login if not already there.")
    print("3. Log in with your credentials.")
    print("4. Ensure you successfully reach the home feed.")
    print("5. Close the browser window to save the session.")
    
    # Ensure directory exists
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    async with async_playwright() as p:
        # Launch persistent context
        # headless=False is CRITICAL for manual interaction
        browser = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = await browser.new_page()
        await page.goto("https://x.com")
        
        print("\n⏳ Browser is open. Waiting for you to close it...")
        
        # Keep the script running until the browser concept is closed
        # We monitor the browser context
        try:
            # Simple wait loop
            while browser.pages:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Browser closed or error: {e}")
        finally:
            print("✅ Session saved (hopefully).")

if __name__ == "__main__":
    print("Starting Manual Login Tool...")
    asyncio.run(main())
