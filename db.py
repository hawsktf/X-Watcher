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
ENGAGEMENT_CSV = os.path.join(DATA_DIR, "engagement.csv")
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
            writer.writerow(['id', 'target_post_id', 'handle', 'content', 'status', 'created_at', 'posted_at', 'generation_model', 'generation_cost', 'insight', 'reply_tweet_id', 'nostr_event_id', 'posted_to_nostr'])
            
    if not os.path.exists(ENGAGEMENT_CSV):
        with open(ENGAGEMENT_CSV, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['reply_id', 'target_post_id', 'handle', 'content', 'scraped_at', 'likes', 'retweets', 'replied_to', 'engagement_mode'])
            
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
    
    # Migration for replies.csv
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.reader(f)
            r_header = next(reader, None)
        
        if r_header:
            new_cols = ['nostr_event_id', 'posted_to_nostr']
            cols_to_add = [c for c in new_cols if c not in r_header]
            
            if cols_to_add:
                print(f"Migrating replies.csv to include {', '.join(cols_to_add)} column(s)...")
                rows = []
                with open(REPLIES_CSV, 'r', newline='') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                
                if rows:
                    actual_header = rows[0]
                    for c in cols_to_add:
                        actual_header.append(c)
                    
                    for i in range(1, len(rows)):
                        for c in cols_to_add:
                            if c == 'posted_to_nostr':
                                rows[i].append('N')
                            else:
                                rows[i].append('')
                    
                    with open(REPLIES_CSV, 'w', newline='') as f:
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
    
    existing_keys = get_existing_post_keys()
    if (str(post_id), handle.lower()) in existing_keys:
        print(f"  ℹ️ Skipping duplicate post {post_id} for @{handle}.")
        return False

    # Sanitize content to avoid CSV issues (remove carriage returns only if needed, CSV handles newlines)
    if content:
        content = content.replace("\r", "")

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
    fieldnames = ['id', 'target_post_id', 'handle', 'content', 'status', 'created_at', 'posted_at', 'generation_model', 'generation_cost', 'insight', 'reply_tweet_id', 'nostr_event_id', 'posted_to_nostr']
    
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
                # Add default values for new columns if missing in migrated row
                if 'nostr_event_id' not in r: r['nostr_event_id'] = ''
                if 'posted_to_nostr' not in r: r['posted_to_nostr'] = 'N'
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

    # Sanitize content to avoid CSV issues
    if content:
        content = content.replace("\r", "")

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
            "",
            "",
            "N"
        ])

def get_pending_replies(status='pending'):
    replies = []
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'] == status:
                    replies.append(row)
    return replies

def get_qualified_replies():
    return get_pending_replies(status='qualified')

def get_post_details(post_id):
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['post_id'] == str(post_id):
                    return row
    return None

def is_already_replied(target_post_id):
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['target_post_id'] == str(target_post_id) and row['status'] in ['posted', 'qualified']:
                    return True
    return False

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
                    elif status == 'posted_nostr':
                         # Specialized status update for Nostr if we want to log it separately, 
                         # but we usually just update the flag.
                         pass
                    updated = True
                rows.append(row)
    
    if updated:
        with open(REPLIES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

def mark_replies_batch(updates):
    """
    Updates multiple replies in a single file write.
    'updates' should be a dict of {reply_id: status} or {reply_id: {'status': status, 'reply_tweet_id': ...}}
    """
    if not updates or not os.path.exists(REPLIES_CSV):
        return
        
    rows = []
    fieldnames = []
    updated_count = 0
    
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames: return
        for row in reader:
            rid = row['id']
            if rid in updates:
                upd = updates[rid]
                if isinstance(upd, dict):
                    new_status = upd.get('status')
                    if new_status: row['status'] = new_status
                    if new_status == 'posted':
                         row['posted_at'] = datetime.now(timezone.utc).isoformat()
                         row['reply_tweet_id'] = upd.get('reply_tweet_id', '')
                else:
                    row['status'] = upd
                    if upd == 'posted':
                        row['posted_at'] = datetime.now(timezone.utc).isoformat()
                updated_count += 1
            rows.append(row)
            
    if updated_count > 0:
        with open(REPLIES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        # print(f"  💾 DB: Batch updated {updated_count} replies.")

def update_nostr_status(reply_id, event_id, posted="Y"):
    """Updates the Nostr status for a reply."""
    rows = []
    fieldnames = []
    updated = False
    
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row['id'] == str(reply_id):
                    row['nostr_event_id'] = event_id
                    row['posted_to_nostr'] = posted
                    updated = True
                rows.append(row)
    
    if updated:
        with open(REPLIES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

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
                # Return ALL target_post_ids regardless of status to prevent re-generation
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

def get_existing_post_keys():
    """Returns a set of (post_id, handle) for accurate duplicate checking."""
    keys = set()
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                keys.add((row['post_id'], row['handle'].lower()))
    return keys

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

def add_engagement_reply(reply_id, target_post_id, handle, content, likes=0, retweets=0, engagement_mode="assess only"):
    now = datetime.now(timezone.utc).isoformat()
    fieldnames = ['reply_id', 'target_post_id', 'handle', 'content', 'scraped_at', 'likes', 'retweets', 'replied_to', 'engagement_mode']
    
    # Check for existence
    existing_ids = set()
    if os.path.exists(ENGAGEMENT_CSV):
        with open(ENGAGEMENT_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row['reply_id'])
    
    if str(reply_id) in existing_ids:
        # Update metrics instead of skipping? For now, let's just skip duplicates
        return False

    if content:
        content = content.replace("\r", "")

    new_row = {
        'reply_id': reply_id,
        'target_post_id': target_post_id,
        'handle': handle,
        'content': content,
        'scraped_at': now,
        'likes': likes,
        'retweets': retweets,
        'replied_to': 'False',
        'engagement_mode': engagement_mode
    }
    
    with open(ENGAGEMENT_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writerow(new_row)
    return True

def get_pending_engagement_replies():
    replies = []
    if os.path.exists(ENGAGEMENT_CSV):
        with open(ENGAGEMENT_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('replied_to') == 'False':
                    replies.append(row)
    return replies

def mark_engagement_replied(reply_id):
    if not os.path.exists(ENGAGEMENT_CSV): return
    rows = []
    updated = False
    with open(ENGAGEMENT_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['reply_id'] == str(reply_id):
                row['replied_to'] = 'True'
                updated = True
            rows.append(row)
    
    if updated:
        with open(ENGAGEMENT_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

def update_post_metrics(post_id, likes, retweets):
    # This might apply to posts.csv or engagement.csv
    # For now, let's assume we want to track these in posts.csv maybe?
    # Actually, the requirement said "monitor and record for replies (and possibly post performance re engagement)"
    # Let's add columns to posts.csv if they don't exist
    pass
