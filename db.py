import csv
import os
import shutil
import sqlite3
from datetime import datetime

# Ensure data directory exists
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

POSTS_CSV = os.path.join(DATA_DIR, "posts.csv")
HANDLES_CSV = os.path.join(DATA_DIR, "handles.csv")
REPLIES_CSV = os.path.join(DATA_DIR, "pending_replies.csv")
POSTED_REPLIES_CSV = os.path.join(DATA_DIR, "posted_replies.csv")
SCORECARD_CSV = os.path.join(DATA_DIR, "scorecard.csv")


def get_conn():
    # Deprecated SQLite connection
    return None

def init_db():
    # Initialize CSV files with headers if they don't exist
    if not os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            # Added score, is_reply, is_pinned + media flags + link_url
            writer.writerow(["post_id", "handle", "content", "scraped_at", "posted_at", "score", "is_reply", "is_pinned", "has_image", "has_video", "has_link", "link_url", "media_url", "is_retweet", "retweet_source"])
    
    if not os.path.exists(POSTED_REPLIES_CSV):
        with open(POSTED_REPLIES_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['id', 'post_id', 'handle', 'reply_content', 'posted_at'])
            
    if not os.path.exists(HANDLES_CSV):
        with open(HANDLES_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['handle', 'last_checked', 'last_posted'])

    if not os.path.exists(SCORECARD_CSV):
        with open(SCORECARD_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['timestamp', 'source', 'handle', 'success', 'latency_seconds', 'posts_scraped', 'new_posts_found', 'error_message'])
    else:
        # Migration: Add new_posts_found column if missing
        with open(SCORECARD_CSV, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
        
        if header and 'new_posts_found' not in header:
            print("Migrating scorecard.csv to include new_posts_found column...")
            rows = []
            with open(SCORECARD_CSV, 'r', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if rows:
                new_header = rows[0]
                try:
                    # Find insertion point before 'error_message' or at the end
                    idx = new_header.index('error_message') if 'error_message' in new_header else len(new_header)
                    new_header.insert(idx, 'new_posts_found')
                    for i in range(1, len(rows)):
                        rows[i].insert(idx, '0')
                    
                    with open(SCORECARD_CSV, 'w', newline='') as f:
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        writer.writerows(rows)
                except Exception as e:
                    print(f"Migration error: {e}")

        # Migration for posts.csv
        if os.path.exists(POSTS_CSV):
            with open(POSTS_CSV, 'r', newline='') as f:
                reader = csv.reader(f)
                p_header = next(reader, None)
            
            if p_header:
                new_cols = ['media_url', 'is_retweet', 'retweet_source']
                cols_to_add = [c for c in new_cols if c not in p_header]
                
                if cols_to_add:
                    print(f"Migrating posts.csv to include {', '.join(cols_to_add)} column(s)...")
                    rows = []
                    with open(POSTS_CSV, 'r', newline='') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                    
                    if rows:
                        actual_header = rows[0]
                        for c in cols_to_add:
                            actual_header.append(c)
                        
                        for i in range(1, len(rows)):
                            for _ in cols_to_add:
                                rows[i].append('')
                        
                        with open(POSTS_CSV, 'w', newline='') as f:
                            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                            writer.writerows(rows)

def add_post(post_id, handle, content, score=0, is_reply=False, is_pinned=False, has_image=False, has_video=False, has_link=False, link_url="", media_url="", is_retweet=False, retweet_source="", posted_at=None):
    now = datetime.utcnow()
    if not posted_at:
        posted_at = now.isoformat()
    
    # Try to normalize posted_at early if it is a simple date
    # This helps with alphabetical sort if we still use it (though feed_app fixes it)
    
    posts = []
    exists = False
    fieldnames = ["post_id", "handle", "content", "scraped_at", "posted_at", "score", "is_reply", "is_pinned", "has_image", "has_video", "has_link", "link_url", "media_url", "is_retweet", "retweet_source"]
    
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or fieldnames
            for row in reader:
                if row['post_id'] == str(post_id):
                    exists = True
                posts.append(row)

    if not exists:
        new_row = {
            "post_id": post_id,
            "handle": handle,
            "content": content,
            "scraped_at": now.isoformat(), # Use full ISO for better debugging
            "posted_at": posted_at,
            "score": score,
            "is_reply": is_reply,
            "is_pinned": is_pinned,
            "has_image": has_image,
            "has_video": has_video,
            "has_link": has_link,
            "link_url": link_url,
            "media_url": media_url,
            "is_retweet": is_retweet,
            "retweet_source": retweet_source
        }
        posts.append(new_row)
        
        # PURE CHRONOLOGICAL SORT BY ID (Snowflake) as a fallback, but we should parse dates
        # Let's use a smarter sort value for the CSV itself
        from dateutil import parser as dt_parser
        def csv_sort_key(x):
            try:
                # Clean and parse for sorting
                clean = x.get('posted_at', '').replace(' · ', ' ').strip()
                dt = dt_parser.parse(clean or '1970-01-01')
                ts = dt.timestamp()
            except:
                ts = 0
            
            try:
                pid = int(x.get('post_id', 0))
            except:
                pid = 0
            return (ts, pid)

        posts.sort(key=csv_sort_key, reverse=True)

        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(posts)
        return True
    return False

def update_post_score(post_id, score):
    rows = []
    updated = False
    fieldnames = []
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row['post_id'] == str(post_id): # Ensure comparison is type-safe
                    row['score'] = score
                    updated = True
                rows.append(row)
    
    if updated:
        # SORT BY POSTED_AT DESCENDING EVEN ON UPDATE
        rows.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

def update_handle_check(handle):
    rows = []
    found = False
    now = datetime.utcnow().isoformat()
    
    # Read existing
    if os.path.exists(HANDLES_CSV):
        with open(HANDLES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames: # Handle empty file case
                 fieldnames = ['handle', 'last_checked']
            for row in reader:
                if row['handle'] == handle:
                    row['last_checked'] = now
                    found = True
                rows.append(row)
    else:
        fieldnames = ['handle', 'last_checked']

    if not found:
        rows.append({'handle': handle, 'last_checked': now})
        
    with open(HANDLES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

def get_latest_post_id(handle):
    latest_id = None
    latest_time = ""
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['handle'] == handle:
                if row['scraped_at'] > latest_time:
                    latest_time = row['scraped_at']
                    latest_id = row['post_id']
    return latest_id

def add_pending_reply(post_id, reply_content):
    # Get max ID for auto-increment simulation
    max_id = 0
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                max_id = max(max_id, int(row['id']))
            except: pass
            
    with open(REPLIES_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([max_id + 1, post_id, reply_content, 'pending', datetime.utcnow().isoformat()])

def get_pending_replies():
    replies = []
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['status'] == 'pending':
                replies.append((row['id'], row['post_id'], row['reply_content']))
    return replies

def mark_reply_posted(reply_id):
    rows = []
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for row in rows:
        if row['id'] == str(reply_id):
            row['status'] = 'posted'
            
    with open(REPLIES_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'post_id', 'reply_content', 'status', 'created_at'])
        for row in rows:
            writer.writerow([row['id'], row['post_id'], row['reply_content'], row['status'], row['created_at']])

def get_all_handles():
    handles = []
    with open(HANDLES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            handles.append((row['handle'], row['last_checked']))
    return handles

# Added for cleaner retrieval in brain.py
def get_all_posts():
    posts = []
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append((row['post_id'], row['handle'], row['content']))
    return posts

def get_existing_reply_post_ids():
    ids = set()
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ids.add(row['post_id'])
    return ids

def get_existing_post_ids():
    ids = set()
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ids.add(row['post_id'])
    return ids

def log_scraper_performance(source, handle, success, latency, posts_scraped=0, new_posts_found=0, error_msg=""):
    with open(SCORECARD_CSV, 'a', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            datetime.utcnow().isoformat(),
            source,
            handle,
            success,
            f"{latency:.2f}",
            posts_scraped,
            new_posts_found,
            error_msg
        ])
