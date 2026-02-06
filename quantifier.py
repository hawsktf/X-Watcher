import json
import random
import os
import csv
from db import POSTS_CSV, update_post_score

def get_personality():
    with open("persona.txt", "r") as f:
        return f.read()

def qualify_post_content(content, persona):
    # This logic matches what was previously in brain.py
    keywords = ["crypto", "bitcoin", "privacy", "surveillance", "identity", "kyc", "freedom", "money"]
    score = 0
    content_lower = content.lower()
    
    hits = sum(1 for k in keywords if k in content_lower)
    if hits > 0:
        score = min(100, 50 + (hits * 20)) 
    else:
        score = random.randint(20, 60)
        
    return score

def run_quantifier():
    print("AI Quantifier: Scoring posts based on brand alignment...")
    
    if not os.path.exists(POSTS_CSV):
        print("No posts to quantify.")
        return

    personality = get_personality()
    
    posts_data = []
    with open(POSTS_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        posts_data = list(reader)

    for row in posts_data:
        post_id = row['post_id']
        handle = row['handle']
        content = row['content']
        current_score = int(row.get('score', 0))

        if current_score == 0:
            score = qualify_post_content(content, personality)
            print(f"Quantifying {handle} [{post_id}]: New Score {score}")
            update_post_score(post_id, score)
        else:
            # Skip already quantified posts
            pass

if __name__ == "__main__":
    run_quantifier()
