import os
import json
import time
import threading
from pynostr.key import PrivateKey
from pynostr.event import Event
from pynostr.relay_manager import RelayManager
from dotenv import load_dotenv

load_dotenv()

def _publish_worker(event, relays):
    try:
        print(f"  📡 NOSTR (Worker): Connecting to {len(relays)} relays...")
        relay_manager = RelayManager()
        for r in relays:
            relay_manager.add_relay(r)
        
        relay_manager.open_connections()
        time.sleep(2)
        relay_manager.publish_event(event)
        time.sleep(3)
        relay_manager.close_connections()
        print(f"  ✅ NOSTR (Worker): Broadcasted event {event.id}")
    except Exception as e:
        print(f"  ❌ NOSTR (Worker) Error: {e}")

def publish_to_nostr(content, nitter_link, screenshot_url=None):
    sk_hex = os.getenv("NOSTR_PRIVATE_KEY")
    if not sk_hex: return None

    try:
        if sk_hex.startswith("nsec"):
            private_key = PrivateKey.from_nsec(sk_hex)
        else:
            sk_hex = sk_hex.strip('"').strip("'")
            private_key = PrivateKey.from_hex(sk_hex)
        
        message = content
        if nitter_link: message += f"\n\n🔗 Original Post: {nitter_link}"
        if screenshot_url: message += f"\n\n🖼️ {screenshot_url}"
            
        event = Event(content=message, kind=1)
        event.sign(private_key.hex())

        relays = ["wss://relay.damus.io", "wss://nos.lol"]
        
        # Run in a separate thread to avoid asyncio loop conflicts
        t = threading.Thread(target=_publish_worker, args=(event, relays))
        t.start()
        # We can either join or let it run in background. 
        # Joining ensures we can return the event ID reliably if we wait.
        t.join(timeout=10) # Wait up to 10s
        
        return event.id
    except Exception as e:
        print(f"  ❌ NOSTR Error: {e}")
        return None

if __name__ == "__main__":
    import asyncio
    async def main():
        print("Testing NOSTR publish from within an async loop...")
        eid = publish_to_nostr("Async loop conflict test.", None)
        print(f"Result ID: {eid}")
    
    asyncio.run(main())
