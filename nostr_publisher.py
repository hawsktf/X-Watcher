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

from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado import gen

@gen.coroutine
def _send_to_relay(url, message):
    """Coroutine to connect, send, and close."""
    try:
        ws = yield websocket_connect(url, connect_timeout=10)
        ws.write_message(message)
        # Primal and some others need a bit longer to process
        yield gen.sleep(5)
        ws.close()
        return True
    except Exception as e:
        print(f"     ❌ NOSTR: {url} failed: {e}")
        return False

def _publish_worker(event, relays):
    """Worker thread using Tornado to broadcast event to multiple relays."""
    try:
        message = event.to_message()
        loop = IOLoop()
        
        success_list = []
        fail_list = []
        
        print(f"  📡 NOSTR: Starting broadcast to {len(relays)} relays...")
        for url in relays:
            res = loop.run_sync(lambda: _send_to_relay(url, message))
            if res:
                success_list.append(url)
                print(f"     ✅ {url} (Success)")
            else:
                fail_list.append(url)
        
        print(f"  ✅ NOSTR: Broadcast finished. Success: {len(success_list)}, Failures: {len(fail_list)}")
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
            message += f"\n\n{screenshot_url}"
            
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
        
        # We join with a timeout that exceeds the worker's total wait time (approx 20s)
        print(f"  📡 NOSTR: Broadcast thread started. Handing off event {event.id[:8]}...")
        t.join(timeout=30) 
        
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
