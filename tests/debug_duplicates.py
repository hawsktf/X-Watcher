import csv
import os
from db import get_existing_reply_post_ids, POSTS_CSV, REPLIES_CSV

def check_posts_duplicates():
    print("--- Checking posts.csv for duplicates ---")
    if not os.path.exists(POSTS_CSV):
        print("posts.csv not found")
        return

    ids = []
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.append(row['post_id'])
    
    seen = set()
    dupes = [x for x in ids if x in seen or seen.add(x)]
    if dupes:
        print(f"Found {len(dupes)} duplicate post IDs in posts.csv:")
        print(dupes[:10])
    else:
        print("No duplicates found in posts.csv")

def check_existing_replies_logic():
    print("\n--- Checking get_existing_reply_post_ids logic ---")
    
    # 1. Inspect raw CSV for the problematic ID
    target_id = "2020361952867066353"
    print(f"Inspecting replies.csv for target_post_id: {target_id}")
    
    found_rows = []
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['target_post_id'] == target_id:
                found_rows.append(row)
                print(f"Row found: ID={row['id']}, Status={row['status']}")

    # 2. Run the function
    existing = get_existing_reply_post_ids()
    print(f"\nget_existing_reply_post_ids() returned {len(existing)} IDs.")
    
    if target_id in existing:
        print(f"SUCCESS: {target_id} is in existing_reply_ids.")
    else:
        print(f"FAILURE: {target_id} is NOT in existing_reply_ids!")
        
    # 3. Debug string/type issues?
    print("\nSample of existing IDs:")
    print(list(existing)[:5])

if __name__ == "__main__":
    check_posts_duplicates()
    check_existing_replies_logic()
