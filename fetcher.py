import feedparser
from db import upsert_handle

NITTER_BASE = "https://nitter.net"

def fetch_latest(handle):
    url = f"{NITTER_BASE}/{handle}/rss"
    feed = feedparser.parse(url)

    if not feed.entries:
        return

    entry = feed.entries[0]

    post_id = entry.id
    content = entry.title
    post_time = entry.published

    upsert_handle(handle, post_id, content, post_time)

