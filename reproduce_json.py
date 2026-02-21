
def extract_reply(raw_text):
    import json
    # Simulate the logic in generator.py
    text = ""
    insight = ""
    try:
        # Extract JSON if it's wrapped in backticks
        if "```json" in raw_text:
            cleaned = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            cleaned = raw_text.split("```")[1].strip()
        else:
            cleaned = raw_text
            
        res = json.loads(cleaned)
        text = res.get("reply", "").strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        text = text.replace("*", "")
        insight = res.get("insight", "No insight provided.")
        return text, insight, "Success"
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        # Robust fallback
        cleaned = raw_text
        if '"reply":' in cleaned:
            try:
                parts = cleaned.split('"reply":')
                if len(parts) > 1:
                    # The problematic splitting logic from generator.py
                    content_part = parts[1].split('","')[0].split('", "')[0].split('"}')[0].split('"}')[0].strip()
                    content_part = content_part.strip(':').strip().strip('"').strip()
                    if content_part:
                        return content_part[:280].replace("*", ""), "Extracted from malformed JSON.", "Fallback"
            except Exception as e2:
                print(f"Fallback Error: {e2}")
        
        return None, "Fallback due to AI/parse error.", "Error"

# Test cases from user logs
test_cases = [
    """{
  "reply": "Epstein files & technocracy intersect? Chilling

  Power concentrates, surveillance expands.

  Privacy isn't just a right; it's a shield🛡️",
  "insight": "Highlight the connection between surveillance (technocracy) and compromised power structures (Epstein files), emphasizing pr 🔒"
}""",
    """{
  "reply": "Interesting angle

  Stablecoins walking the line—decentralized facade, centralized control?

  History repeats, just with faster tech",
  "insight": "Highlight potential centralization risks within decentralized-seeming systems and draw historical parallels to reinforce the idea 🔒"
}"""
]

for i, tc in enumerate(test_cases):
    print(f"--- Test Case {i+1} ---")
    reply, insight, status = extract_reply(tc)
    print(f"Status: {status}")
    print(f"Reply: {reply}")
    print(f"Insight: {insight}")
    print("-" * 20)
