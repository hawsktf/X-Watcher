import csv
import os
import shutil
import sqlite3
from datetime import datetime, timezone

# Ensure data directory exists
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

POSTS_CSV = os.path.join(DATA_DIR, "posts.csv")
HANDLES_CSV = os.path.join(DATA_DIR, "handles.csv")
REPLIES_CSV = os.path.join(DATA_DIR, "replies.csv")
# Legacy files for migration
PENDING_REPLIES_CSV = os.path.join(DATA_DIR, "pending_replies.csv")
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
            # Added score, is_reply, is_pinned + media flags + link_url + AI cost/reply tracking
            writer.writerow(["post_id", "handle", "content", "scraped_at", "posted_at", "score", "is_reply", "is_pinned", "has_image", "has_video", "has_link", "link_url", "media_url", "is_retweet", "retweet_source", "quantification_cost", "replied_to", "reply_post_id"])
    
    if not os.path.exists(POSTED_REPLIES_CSV):
        with open(POSTED_REPLIES_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['id', 'post_id', 'handle', 'reply_content', 'posted_at', 'generation_cost'])
            
    
    if not os.path.exists(REPLIES_CSV):
        # Create consolidated replies CSV
        with open(REPLIES_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['id', 'target_post_id', 'handle', 'content', 'status', 'created_at', 'posted_at', 'generation_model', 'generation_cost', 'insight', 'reply_tweet_id'])
            
    # Perform Migration if legacy files exist
    migrate_replies()

    # Migration for posts.csv
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.reader(f)
            p_header = next(reader, None)
        
        if p_header:
            new_cols = ['media_url', 'is_retweet', 'retweet_source', 'quantification_cost', 'replied_to', 'reply_post_id']
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
                        for c in cols_to_add:
                            if c == 'replied_to':
                                rows[i].append('False')
                            elif c == 'quantification_cost':
                                rows[i].append('0.0')
                            else:
                                rows[i].append('')
                    
                    with open(POSTS_CSV, 'w', newline='') as f:
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        writer.writerows(rows)
    
    # Migration: Set score='0' to score='' (unscored) for correct quantification logic
    # migrate_zero_scores() # Run once manually if needed, do not run on every startup

def add_post(post_id, handle, content, score="", is_reply=False, is_pinned=False, has_image=False, has_video=False, has_link=False, link_url="", media_url="", is_retweet=False, retweet_source="", posted_at=None):
    now = datetime.now(timezone.utc)
    if not posted_at:
        posted_at = now.isoformat()
    
    # Try to normalize posted_at early if it is a simple date
    # This helps with alphabetical sort if we still use it (though feed_app fixes it)
    
    # Optimized: Check existence first, then append.
    # No sorting on write.
    fieldnames = ["post_id", "handle", "content", "scraped_at", "posted_at", "score", "is_reply", "is_pinned", "has_image", "has_video", "has_link", "link_url", "media_url", "is_retweet", "retweet_source", "quantification_cost", "replied_to", "reply_post_id"]
    
    existing_ids = get_existing_post_ids()
    if str(post_id) in existing_ids:
        return False

    # Sanitize content to avoid CSV issues (remove newlines and commas)
    if content:
        content = content.replace("\n", "  ").replace("\r", "").replace(",", " ")

    new_row = {
        "post_id": post_id,
        "handle": handle,
        "content": content,
        "scraped_at": now.isoformat(),
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
        "retweet_source": retweet_source,
        "quantification_cost": 0.0,
        "replied_to": False,
        "reply_post_id": ""
    }
    
    # Append to file
    with open(POSTS_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        # Ensure we don't write header here assuming it exists (init_db handles creation)
        writer.writerow(new_row)
        
    return True

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
        # Optimized: No sort on update, just rewrite (CSV limitation)
        # rows.sort(key=lambda x: x.get('posted_at', ''), reverse=True) 
        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

def update_handle_check(handle):
    rows = []
    found = False
    now = datetime.now(timezone.utc).isoformat()
    
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
    return latest_id


def migrate_zero_scores():
    """Converts posts with score='0' to score='' to ensure they are treated as unscored."""
    if not os.path.exists(POSTS_CSV): return

    rows = []
    updated = False
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row.get('score') == '0':
                row['score'] = ''
                updated = True
            rows.append(row)
    
    if updated:
        print("Migrating zero scores to empty strings...")
        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

def migrate_replies():
    if not os.path.exists(PENDING_REPLIES_CSV) and not os.path.exists(POSTED_REPLIES_CSV):
        return

    print("Migrating legacy reply databases to unified replies.csv...")
    
    # Read handles map
    post_handles = {}
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                post_handles[row['post_id']] = row['handle']

    replies = []
    max_id = 0
    
    # Process Pending
    if os.path.exists(PENDING_REPLIES_CSV):
        with open(PENDING_REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                created_at = row.get('created_at', datetime.now(timezone.utc).isoformat())
                replies.append({
                    'id': row['id'],
                    'target_post_id': row['post_id'],
                    'handle': post_handles.get(row['post_id'], 'unknown'),
                    'content': row['reply_content'],
                    'status': 'pending',
                    'created_at': created_at,
                    'posted_at': '',
                    'generation_model': 'legacy',
                    'generation_cost': row.get('generation_cost', 0.0),
                    'insight': '',
                    'reply_tweet_id': ''
                })
                try: max_id = max(max_id, int(row['id']))
                except: pass
        
        # Archive
        archive_dir = os.path.join(DATA_DIR, "archive")
        if not os.path.exists(archive_dir): os.makedirs(archive_dir)
        shutil.move(PENDING_REPLIES_CSV, os.path.join(archive_dir, f"pending_replies_migrated_{int(datetime.now().timestamp())}.csv"))

    # Process Posted
    if os.path.exists(POSTED_REPLIES_CSV):
        with open(POSTED_REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use handle from file or map
                handle = row.get('handle', post_handles.get(row['post_id'], 'unknown'))
                posted_at = row.get('posted_at', datetime.now(timezone.utc).isoformat())
                
                # Assign new ID to avoid collisions if necessary, or preserve if unique
                max_id += 1
                new_id = max_id
                
                replies.append({
                    'id': new_id,
                    'target_post_id': row['post_id'],
                    'handle': handle,
                    'content': row['reply_content'],
                    'status': 'posted',
                    'created_at': posted_at, # Assume created roughly when posted for legacy
                    'posted_at': posted_at,
                    'generation_model': 'legacy',
                    'generation_cost': row.get('generation_cost', 0.0),
                    'insight': '',
                    'reply_tweet_id': ''
                })
        
        # Archive
        archive_dir = os.path.join(DATA_DIR, "archive")
        if not os.path.exists(archive_dir): os.makedirs(archive_dir)
        shutil.move(POSTED_REPLIES_CSV, os.path.join(archive_dir, f"posted_replies_migrated_{int(datetime.now().timestamp())}.csv"))

    # Append to replies.csv
    fieldnames = ['id', 'target_post_id', 'handle', 'content', 'status', 'created_at', 'posted_at', 'generation_model', 'generation_cost', 'insight', 'reply_tweet_id']
    
    existing_ids = set()
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row['id'])

    with open(REPLIES_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        for r in replies:
            if str(r['id']) not in existing_ids:
                writer.writerow(r)
    
    print(f"Migrated {len(replies)} replies to replies.csv.")

def add_reply(post_id, handle, content, status="pending", generation_model="unknown", cost=0.0, insight=""):
    max_id = 0
    if os.path.exists(REPLIES_CSV):
         with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try: max_id = max(max_id, int(row['id']))
                except: pass

    with open(REPLIES_CSV, 'a', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            max_id + 1, 
            post_id, 
            handle, 
            content, 
            status, 
            datetime.now(timezone.utc).isoformat(), 
            "" if status == "pending" else datetime.now(timezone.utc).isoformat(),
            generation_model,
            cost,
            insight,
            ""
        ])

def get_pending_replies():
    replies = []
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'] == 'pending':
                    replies.append(row)
    return replies

def mark_reply_status(reply_id, status, reply_tweet_id=""):
    rows = []
    fieldnames = []
    updated = False
    
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames: return
            for row in reader:
                if row['id'] == str(reply_id):
                    row['status'] = status
                    if status == 'posted':
                        row['posted_at'] = datetime.now(timezone.utc).isoformat()
                        row['reply_tweet_id'] = reply_tweet_id
                    updated = True
                rows.append(row)
    
    if updated:
        with open(REPLIES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

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
                # Include pending and posted to prevent duplication
                if row['status'] in ['pending', 'posted']:
                    ids.add(row['target_post_id'])
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
            datetime.now(timezone.utc).isoformat(),
            source,
            handle,
            success,
            f"{latency:.2f}",
            posts_scraped,
            new_posts_found,
            error_msg
        ])
