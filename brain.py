import json
import random
import os
import csv
import time
from datetime import datetime, timezone
from db import POSTS_CSV, REPLIES_CSV, get_existing_reply_post_ids, get_all_posts, update_post_score
from quantifier import get_personality, get_ai_config, estimate_cost

def add_pending_reply(post_id, reply_content, cost=0.0):
    # Get max ID for auto-increment simulation
    max_id = 0
    if os.path.exists(REPLIES_CSV):
        with open(REPLIES_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    max_id = max(max_id, int(row['id']))
                except: pass
            
    with open(REPLIES_CSV, 'a', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([max_id + 1, post_id, reply_content, 'pending', datetime.now(timezone.utc).isoformat(), cost])

def draft_reply_with_ai(content, persona, handle):
    cfg = get_ai_config()
    
    # Test mode: use template responses instead of AI
    if cfg.get("test_mode", False):
        content_lower = content.lower()
        
        if "crypto" in content_lower or "bitcoin" in content_lower:
            options = [
                "This is exactly why decentralized infrastructure is the only exit from legacy control.",
                "Bitcoin is the signal; everything else is just noise in the fiat system.",
                "Self-custody is the first step towards true sovereignty."
            ]
        elif "privacy" in content_lower or "surveillance" in content_lower:
            options = [
                "Privacy is not a crime, it's a prerequisite for a free society.",
                "Modern legibility is just a polite word for state extraction.",
                "Surveillance capitalism relies on your compliance. Opt out."
            ]
        elif "identity" in content_lower or "kyc" in content_lower:
            options = [
                "Administrative control lineages remain unbroken from parish registers to digital IDs.",
                "KYC is just the digital fence around the tax farm.",
                "Your identity should belong to you, not a database in a government server."
            ]
        else:
            options = [
                "Historical lineages suggest governance by infrastructure is inevitable.",
                "The future belongs to those who build parallel institutions.",
                "Decentralization is not just a technology, it's a moral imperative."
            ]
        
        return random.choice(options), 0.0  # No cost in test mode
    
    # Production mode: use Gemini API
    import google.generativeai as genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return None, 0.0

    genai.configure(api_key=api_key)
    
    model_name = cfg.get("drafter_model", "gemini-1.5-pro")
    model = genai.GenerativeModel(model_name)

    prompt = f"""
    You are an AI agent with the following persona:
    {persona}

    Your task is to draft a reply to the following X (Twitter) post by @{handle}.
    
    Guidelines:
    - Keep it under 200 characters.
    - Be insightful, slightly witty, but professional.
    - Challenge the status quo if relevant (crypto, privacy, freedom).
    - Do NOT be generic.
    - Do NOT use hashtags.

    Post Content:
    "{content}"

    Return ONLY the reply text.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace('"', '')
        
        input_tokens = model.count_tokens(prompt).total_tokens
        output_tokens = model.count_tokens(text).total_tokens
        cost = estimate_cost(model_name, input_tokens, output_tokens)
        
        return text, cost
    except Exception as e:
        print(f"AI Error: {e}")
        return None, 0.0
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
    reply_to_reposts = cfg.get("reply_to_reposts", False)

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
        
        is_retweet = row.get('is_retweet', 'False') == 'True'
        if is_retweet and not reply_to_reposts:
            continue

        # Get existing score (from quantifier)
        try:
            score = int(row.get('score', 0) if row.get('score', '') != '' else 0)
        except ValueError:
            score = 0
        
        if score < threshold:
            continue
            
        print(f"Drafting for {handle} (Score: {score})...")
        
        reply, cost = draft_reply_with_ai(content, personality, handle)
        
        if reply:
            if emojis_enabled and "🔒" not in reply:
                 reply += " 🔒"

            add_pending_reply(post_id, reply, cost)
            print(f"Drafted: {reply} (Cost: ${cost:.5f})")
            time.sleep(2) # Rate limiting

if __name__ == "__main__":
    draft_replies()

if __name__ == "__main__":
    draft_replies()
