import json
import random
import os
import csv
import time
from db import POSTS_CSV, update_post_score

def get_brand():
    with open("config_user/brand.txt", "r") as f:
        return f.read()

def get_ai_config():
    with open("config_user/config.json") as f:
        return json.load(f)

def estimate_cost(model_name, input_tokens, output_tokens):
    cfg = get_ai_config()
    models = cfg.get("ai_models", {})
    if model_name in models:
        in_cost = models[model_name]["input_cost"]
        out_cost = models[model_name]["output_cost"]
        return (input_tokens / 1000 * in_cost) + (output_tokens / 1000 * out_cost)
    return 0.0

def qualify_post_with_ai(content, brand_text):
    cfg = get_ai_config()
    
    # Test mode: use keyword matching instead of AI
    if cfg.get("test_mode", False):
        keywords = ["crypto", "monero", "privacy", "surveillance", "identity", "kyc", "freedom", "money"]
        content_lower = content.lower()
        hits = sum(1 for k in keywords if k in content_lower)
        if hits > 0:
            score = min(100, 50 + (hits * 20))
        else:
            score = random.randint(20, 60)
        return score, 0.0  # No cost in test mode
    
    # Production mode: use Gemini API
    # Production mode: use Google GenAI SDK
    from google import genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        api_key = api_key.split('#')[0].strip()
    
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return 0, 0.0

    client = genai.Client(api_key=api_key)
    
    model_name = cfg.get("quantifier_model", "gemini-1.5-flash")

    prompt = f"""
    You are an AI agent representing the following brand:
    {brand_text}

    Your task is to score the following content based on how relevant and aligned it is to your brand's core thesis and focus areas.
    Score it from 0 to 100.
    
    0 = Irrelevant, spam, or boring.
    100 = Highly relevant, perfect for starting a conversation or debate.

    Post Content:
    "{content}"

    Return ONLY the numeric score (e.g., 85).
    """

    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = response.text.strip()
        score = int(''.join(filter(str.isdigit, text)))
        
        # Estimate usage
        input_tokens = client.models.count_tokens(model=model_name, contents=prompt).total_tokens
        output_tokens = client.models.count_tokens(model=model_name, contents=text).total_tokens
        cost = estimate_cost(model_name, input_tokens, output_tokens)
        
        return score, cost
    except Exception as e:
        print(f"AI Error: {e}")
        return 0, 0.0

def run_quantifier():
    cfg = get_ai_config()
    reply_to_replies = cfg.get("reply_to_replies", False)
    reply_to_reposts = cfg.get("reply_to_reposts", False)
    threshold = cfg.get("quantifier_threshold", 80)
    
    print("\n🧠 AI Quantifier: Scoring posts with Gemini...")
    
    if not os.path.isabs(POSTS_CSV):
        posts_path = os.path.join(os.getcwd(), POSTS_CSV)
    else:
        posts_path = POSTS_CSV

    if not os.path.exists(posts_path):
        print("  ℹ️ No posts to quantify.")
        return

    brand_text = get_brand()
    
    posts_data = []
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        posts_data = list(reader)
        fieldnames = reader.fieldnames

    # Count unscored posts
    # Count unscored posts (score is empty string or None)
    unscored_count = sum(1 for row in posts_data if row.get('score') in [None, ''])
    
    print(f"🧐 Quantification Start: {unscored_count} posts to be scored. Replies enabled: {reply_to_replies}, Reposts enabled: {reply_to_reposts}")

    # Check if we need to update rows
    updates = []
    qualified_count = 0
    processed_count = 0
    
    for row in posts_data:
        post_id = row['post_id']
        handle = row['handle']
        content = row['content']
        
        # Check if score is missing (empty string or None)
        # Note: '0' is a valid score now (meaning AI rated it 0)
        raw_score = row.get('score')
        needs_scoring = raw_score in [None, '']

        if needs_scoring:
            score, cost = qualify_post_with_ai(content, brand_text)
            print(f"  📊 Scored @{handle}: {score} (Cost: ${cost:.5f})")
            
            row['score'] = score
            row['quantification_cost'] = cost
            
            # Rate limit protection (simple sleep)
            time.sleep(1)
            
        try:
            final_score = int(row.get('score', 0) if row.get('score') not in [None, ''] else 0)
        except ValueError:
            final_score = 0
            
        if final_score >= threshold:
            qualified_count += 1
            
        processed_count += 1
        
        # Always append the row (whether updated or not)
        updates.append(row)

    # Rewrite CSV if changes happened (and if we are running this logic, we likely rely on memory for small datasets)
    # The previous logic used update_post_score which re-read the CSV. 
    # To support cost updating, we will write back the whole file here since we have it in memory.
    
    if updates:
        with open(POSTS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(updates)
            
    print(f"✅ Quantification Complete: {qualified_count} out of {processed_count} posts qualified (Score >= {threshold}).")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_quantifier()
