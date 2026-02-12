import os
import sys
import time
import json
from pynostr.key import PrivateKey
from pynostr.event import Event
from pynostr.relay_manager import RelayManager
from dotenv import load_dotenv

load_dotenv()

from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado import gen

@gen.coroutine
def send_to_relay(url, message):
    try:
        print(f"     Attempting to connect to {url}...")
        ws = yield websocket_connect(url, connect_timeout=10)
        print(f"     ✅ Connected. Writing message...")
        ws.write_message(message)
        # Give it a moment to actually send
        yield gen.sleep(3)
        ws.close()
        print(f"     ✅ Closed {url}")
        return True
    except Exception as e:
        print(f"     ❌ Error with {url}: {e}")
        return False

def test_direct():
    print("🚀 Starting Direct NOSTR Test (Tornado One-Shot) ---")
    
    sk_hex = os.getenv("NOSTR_PRIVATE_KEY")
    if sk_hex.startswith("nsec"):
        private_key = PrivateKey.from_nsec(sk_hex)
    else:
        private_key = PrivateKey.from_hex(sk_hex.strip('"').strip("'"))
        
    content = "Direct One-Shot Test: Hello from X-Watcher via Tornado."
    event = Event(content=content, kind=1)
    event.sign(private_key.hex())
    
    # Primal, Damus, and Nos.lol are good targets
    relays = ["wss://nos.lol", "wss://relay.damus.io", "wss://relay.primal.net"]
    message = event.to_message()
    
    loop = IOLoop()
    for url in relays:
        print(f"📡 Processing {url}...")
        loop.run_sync(lambda: send_to_relay(url, message))
    
    print(f"\n✅ Finished. Event ID: {event.id}")
    print(f"Check: https://primal.net/e/{event.id}")

if __name__ == "__main__":
    test_direct()
