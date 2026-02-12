import os
import json
import time
from pynostr.key import PrivateKey
from pynostr.event import Event
from pynostr.relay_manager import RelayManager
from dotenv import load_dotenv

# Load .env for private key
load_dotenv()

import threading

def _publish_worker(event, relays):
    """Worker thread to handle the asynchronous pynostr RelayManager."""
    try:
        print(f"  📡 NOSTR: Connecting to {len(relays)} relays...")
        relay_manager = RelayManager()
        for r in relays:
            relay_manager.add_relay(r)
        
        # Open connections (starts a background loop)
        relay_manager.open_connections()
        
        # Give it enough time to handshake with all relays
        time.sleep(5)
        
        # Broadcast
        relay_manager.publish_event(event)
        
        # Give it more time to ensure broadcast reached relays and settled
        time.sleep(10)
        relay_manager.close_connections()
        print(f"  ✅ NOSTR: Broadcasted event {event.id}")
    except Exception as e:
        print(f"  ❌ NOSTR Worker Error: {e}")

def publish_to_nostr(content, nitter_link, screenshot_url=None):
    """
    Publishes a Kind 1 note to Nostr using pynostr.
    """
    sk_hex = os.getenv("NOSTR_PRIVATE_KEY")
    if not sk_hex:
        print("  ❌ NOSTR: Private key not found in .env")
        return None

    try:
        # Handle nsec (bech32) or hex
        if sk_hex.startswith("nsec"):
            private_key = PrivateKey.from_nsec(sk_hex)
        else:
            # Strip quotes if they were included in .env accidentally
            sk_hex = sk_hex.strip('"').strip("'")
            private_key = PrivateKey.from_hex(sk_hex)
        
        # Build message
        message = content
        if nitter_link:
            message += f"\n\n🔗 Original Post: {nitter_link}"
        if screenshot_url:
            message += f"\n\n🖼️ {screenshot_url}"
            
        # Kind 1 is default for Note
        event = Event(content=message, kind=1)
        event.sign(private_key.hex())

        # Load relays from config
        try:
            with open("config_user/config.json") as f:
                cfg = json.load(f)
            default_relays = [
                "wss://relay.damus.io", 
                "wss://nos.lol", 
                "wss://relay.snort.social",
                "wss://purplepag.es",
                "wss://relay.primal.net",
                "wss://relay.nostr.band"
            ]
            relays = cfg.get("nostr_relays", default_relays)
        except:
            relays = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.primal.net"]
        
        # Run in a separate thread to avoid asyncio loop conflicts with Playwright
        t = threading.Thread(target=_publish_worker, args=(event, relays), daemon=True)
        t.start()
        
        # We join with a timeout but we don't strictly NEED to block the main thread for long
        # if the daemon is doing its job. However, to return the ID, we wait.
        print(f"  📡 NOSTR: Broadcast thread started. Handing off event {event.id[:8]}...")
        t.join(timeout=15) # Increased timeout for slow relay connections
        
        return event.id
    except Exception as e:
        print(f"  ❌ NOSTR Error: {e}")
        return None

if __name__ == "__main__":
    # Test logic if run directly
    test_key = os.getenv("NOSTR_PRIVATE_KEY")
    if test_key:
        print("Testing NOSTR publish...")
        publish_to_nostr("Test post from X-Watcher enhancement.", "https://nitter.poast.org/elonmusk/status/123456")
    else:
        print("NOSTR_PRIVATE_KEY not set, skipping test.")
