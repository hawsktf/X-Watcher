import json
from datetime import datetime, timezone
from db import get_pending_replies, get_post_details, is_already_replied, mark_replies_batch

def run_qualifier():
    print("\n🛡️ Starting Qualifier (Safety Checks) ---")
    
    with open("config_user/config.json") as f:
        cfg = json.load(f)
        
    age_limit_hours = cfg.get("qualify_age_limit_hours", 12)
    
    pending = get_pending_replies(status='pending')
    qualified = get_pending_replies(status='qualified')
    
    if not pending and not qualified:
        print("  ✅ No pending or qualified replies to check.")
        return

    print(f"  🔍 Qualifier: {len(pending)} pending, {len(qualified)} qualified to check.")
    
    updates = {}
    qualified_posts = set() # Track posts we've qualified in this batch
    
    count_qualified = 0
    count_rejected = 0
    
    now = datetime.now(timezone.utc)
    
    # 0. Check Existing Qualified Replies for Expiry
    qualified = get_pending_replies(status='qualified')
    count_expired_existing = 0
    if qualified:
        print(f"  🔍 Re-assessing {len(qualified)} already qualified replies for expiry...")
        for reply in qualified:
            reply_id = reply['id']
            post_id = reply['target_post_id']
            handle = reply['handle']
            
            post = get_post_details(post_id)
            if not post:
                # Should not happen often, but if post is gone, maybe expire the reply?
                continue

            posted_at_str = post.get('posted_at') or post.get('scraped_at')
            try:
                try:
                    posted_at = datetime.fromisoformat(posted_at_str)
                except ValueError:
                    clean_date = posted_at_str.replace(" UTC", "").replace("· ", "")
                    posted_at = datetime.strptime(clean_date, "%b %d, %Y %I:%M %p")
                
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                    
                age_hours = (now - posted_at).total_seconds() / 3600
                
                if age_hours > age_limit_hours:
                    print(f"  ❌ Qualified reply {reply_id} to @{handle} is now too old ({age_hours:.1f}h > {age_limit_hours}h). Expiring.")
                    updates[reply_id] = 'expired'
                    count_rejected += 1
                    count_expired_existing += 1
            except Exception as e:
                print(f"  ⚠️ Error re-assessing date for reply {reply_id}: {e}")

        if count_expired_existing > 0:
            print(f"  🗑️ {count_expired_existing} qualified posts have expired.")

    # 1. Check Pending Replies
    for reply in pending:
        reply_id = reply['id']
        post_id = reply['target_post_id']
        handle = reply['handle']
        
        # 1. Get Post Details (for Age Check)
        post = get_post_details(post_id)
        if not post:
             print(f"  ⚠️ Post {post_id} not found in DB. Rejecting reply {reply_id}.")
             updates[reply_id] = 'rejected_missing_post'
             count_rejected += 1
             continue
             
        posted_at_str = post.get('posted_at')
        if not posted_at_str:
            posted_at_str = post.get('scraped_at')
            
        try:
            try:
                posted_at = datetime.fromisoformat(posted_at_str)
            except ValueError:
                # Twitter format fallback
                clean_date = posted_at_str.replace(" UTC", "").replace("· ", "")
                posted_at = datetime.strptime(clean_date, "%b %d, %Y %I:%M %p")
                
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
                
            age_hours = (now - posted_at).total_seconds() / 3600
            
            if age_hours > age_limit_hours:
                print(f"  ❌ Reply {reply_id} to @{handle} is too old ({age_hours:.1f}h > {age_limit_hours}h). Expiring.")
                updates[reply_id] = 'expired'
                count_rejected += 1
                continue
                
        except Exception as e:
            print(f"  ⚠️ Error parsing date '{posted_at_str}' for reply {reply_id}: {e}. Skipping.")
            continue

        # 2. Duplicate Check
        # Check if already replied in DB OR already qualified in this current loop
        if is_already_replied(post_id) or post_id in qualified_posts:
             print(f"  ❌ Reply {reply_id} to @{handle} is a duplicate target. Rejecting.")
             updates[reply_id] = 'rejected_duplicate'
             count_rejected += 1
             continue
             
        # If passed all checks
        print(f"  ✅ Qualified reply {reply_id} to @{handle} (Age: {age_hours:.1f}h).")
        updates[reply_id] = 'qualified'
        qualified_posts.add(post_id)
        count_qualified += 1
        
    # Apply all updates at once
    if updates:
        mark_replies_batch(updates)
        
    print(f"🛡️ Qualifier Complete: {count_qualified} qualified, {count_rejected} rejected/expired.")

if __name__ == "__main__":
    run_qualifier()
