import os
import sys

# Add root to sys.path
sys.path.append(os.getcwd())

from media_uploader import upload_media
from nostr_publisher import publish_to_nostr
from dotenv import load_dotenv

load_dotenv()

def test_isolation():
    print("🚀 Starting Isolated Test: Hello World NOSTR ---\n")
    
    # 1. Prepare Dummy Image
    dummy_path = "debug/hello_world.png"
    if not os.path.exists(dummy_path):
        with open(dummy_path, "w") as f:
            f.write("Dummy Image Data for Hello World Test")

    # 2. Test Media Upload
    print("Step 1: Testing Media Uploader...")
    image_url = upload_media(dummy_path)
    
    if image_url:
        print(f"✅ Media Upload Success: {image_url}")
    else:
        print("❌ Media Upload Failed (Falling back to text-only NOSTR test)")

    # 3. Test NOSTR Publish
    print("\nStep 2: Testing NOSTR Publisher...")
    content = "Hello World! 🌍 This is an isolated test of the X-Watcher NOSTR + Media toolchain."
    nitter_link = "https://nitter.poast.org/XWatcher/status/123456789"
    
    event_id = publish_to_nostr(content, nitter_link, image_url)
    
    if event_id:
        print(f"\n✅ NOSTR Publish Success! Event ID: {event_id}")
        print("Check your NOSTR feed to verify visibility.")
    else:
        print("\n❌ NOSTR Publish Failed.")

if __name__ == "__main__":
    test_isolation()
