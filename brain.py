import json
import random
import os
import csv
from db import POSTS_CSV, get_existing_reply_post_ids, add_pending_reply, update_post_score
from quantifier import qualify_post_content, get_personality

def draft_replies():
    with open("config.json") as f:
        cfg = json.load(f)
        
    mode = cfg.get("workflow_mode", "draft")
    if mode not in ["draft", "post"]:
        print(f"Brain: Workflow mode is '{mode}'. Skipping drafting.")
        return

    print(f"AI Brain: Drafting replies (Mode: {mode})...")
    
    threshold = cfg.get("quantifier_threshold", 80)
    emojis_enabled = cfg.get("emojis_enabled", True)
    reply_to_replies = cfg.get("reply_to_replies", False)

    existing_reply_ids = get_existing_reply_post_ids()
    personality = get_personality()
    
    posts_data = []
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            posts_data = list(reader)

    for row in posts_data:
        post_id = row['post_id']
        handle = row['handle']
        content = row['content']
        
        if post_id in existing_reply_ids:
            continue
            
        is_reply = row.get('is_reply', 'False') == 'True'
        if is_reply and not reply_to_replies:
            continue

        # Score it (Always update score if drafted)
        score = qualify_post_content(content, personality)
        update_post_score(post_id, score)
        
        if score < threshold:
            continue
            
        print(f"Drafting for {handle} (Score: {score})...")
        
        # MOCK AI LOGIC 
        content_lower = content.lower()
        if "crypto" in content_lower or "bitcoin" in content_lower:
            reply = "This is why decentralized infrastructure is the exit from legacy control."
        elif "privacy" in content_lower or "surveillance" in content_lower:
            reply = "Privacy is survival. Modern legibility is extraction."
        elif "identity" in content_lower or "kyc" in content_lower:
            reply = "Administrative control lineages remain unbroken from parish registers to digital IDs."
        else:
            reply = f"Historical lineages suggest governance by infrastructure is inevitable."

        if emojis_enabled:
             reply += " 🔒"

        add_pending_reply(post_id, reply)
        print(f"Drafted: {reply}")

if __name__ == "__main__":
    draft_replies()

if __name__ == "__main__":
    draft_replies()
