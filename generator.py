import json
import random
import os
import csv
import time
from datetime import datetime, timezone
from db import POSTS_CSV, REPLIES_CSV, get_existing_reply_post_ids, get_all_posts, update_post_score, add_reply
from quantifier import get_brand, get_ai_config, estimate_cost

def get_persona():
    with open("persona.txt", "r") as f:
        return f.read()

def draft_reply_with_ai(content, brand_text, persona_text, handle):
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
        
        return random.choice(options), "Using a pre-set thematic response for test mode.", 0.0, "Test-Template"
    
    # Production mode: use Gemini API
    # Production mode: use Google GenAI SDK
    from google import genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        api_key = api_key.split('#')[0].strip()
        
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return None, None, 0.0, "Error"

    client = genai.Client(api_key=api_key)
    
    model_name = cfg.get("drafter_model", "gemini-2.5-pro")

    prompt = f"""
    You are an AI agent representing the following brand:
    {brand_text}

    You speak with the following persona:
    {persona_text}

    Your task is to draft a short, engaging reply to the following X (Twitter) post by @{handle}.
    
    Guidelines:
    - Keep it under 220 characters.
    - Be conversational, punchy, and additive. Don't just observe; add a fresh thought.
    - Use simple, direct language. Avoid academic, over-analytical, or "big" words.
    - Avoid being verbose or overly formal. Think "insightful friend", not "textbook."
    - Challenge the status quo (crypto, privacy, freedom) if it makes sense, but keep it readable.
    - Do NOT use hashtags.

    Post Content:
    "{content}"

    Return ONLY a JSON object:
    {{
      "reply": "the draft text",
      "insight": "a 1-sentence analytical strategy for this reply"
    }}
    """

    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        raw_text = response.text.strip()
        # Extract JSON if it's wrapped in backticks
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].strip()
            
        res = json.loads(raw_text)
        text = res.get("reply", "").replace('"', '')
        insight = res.get("insight", "No insight provided.")
        
        input_tokens = client.models.count_tokens(model=model_name, contents=prompt).total_tokens
        output_tokens = client.models.count_tokens(model=model_name, contents=raw_text).total_tokens
        cost = estimate_cost(model_name, input_tokens, output_tokens)
        
        return text, insight, cost, model_name
    except Exception as e:
        print(f"AI Error parsing JSON: {e}")
        # Fallback to simple text if JSON fails
        return raw_text[:280], "Fallback due to parse error.", 0.0, "Error"

def run_generator():
    with open("config.json") as f:
        cfg = json.load(f)
        
    mode = cfg.get("workflow_mode", "draft")
    if mode not in ["draft", "post"]:
        print(f"Generator: Workflow mode is '{mode}'. Skipping drafting.")
        return

    print(f"\n💡 Generator: Drafting replies (Mode: {mode})...")
    
    threshold = cfg.get("quantifier_threshold", 80)
    emojis_enabled = cfg.get("emojis_enabled", True)
    reply_to_replies = cfg.get("reply_to_replies", False)
    reply_to_reposts = cfg.get("reply_to_reposts", False)

    existing_reply_ids = get_existing_reply_post_ids()
    brand_text = get_brand()
    persona_text = get_persona()
    
    posts_data = []
    if os.path.exists(POSTS_CSV):
        with open(POSTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            posts_data = list(reader)

    count = 0
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
            
        # Optional but HIGHLY recommended: Age check here too to avoid drafting for expired posts
        age_limit_hours = cfg.get("qualify_age_limit_hours", 12)
        posted_at_str = row.get('posted_at')
        if posted_at_str:
            try:
                try:
                    posted_at = datetime.fromisoformat(posted_at_str)
                except ValueError:
                    clean_date = posted_at_str.replace(" UTC", "").replace("· ", "")
                    posted_at = datetime.strptime(clean_date, "%b %d, %Y %I:%M %p")
                
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                
                age_hours = (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600
                if age_hours > age_limit_hours:
                    # Skip drafting for posts that are already too old
                    continue
            except:
                pass # If date parse fails, we continue and let qualifier handle it
            
        print(f"  📝 Drafting reply for @{handle} (Score: {score})...")
        
        reply, insight, cost, model_name = draft_reply_with_ai(content, brand_text, persona_text, handle)
        
        if reply:
            if insight:
                print(f"  🧠 Strategy: {insight}")
            if emojis_enabled and "🔒" not in reply:
                 reply += " 🔒"

            add_reply(post_id, handle, reply, status="pending", generation_model=model_name, cost=cost, insight=insight)
            print(f"  ✅ Drafted: {reply[:50]}... (Cost: ${cost:.5f}) [{model_name}]")
            count += 1
            time.sleep(2) # Rate limiting
            
    print(f"Generator: Drafted {count} new replies.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_generator()
