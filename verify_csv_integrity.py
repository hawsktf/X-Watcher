
import csv
import os

POSTS_CSV = "data/posts.csv"

def verify_csv():
    if not os.path.exists(POSTS_CSV):
        print("File not found.")
        return

    expected_fields = [
        "post_id", "handle", "content", "scraped_at", "posted_at", "score", "is_reply", 
        "is_pinned", "has_image", "has_video", "has_link", "link_url", "media_url", 
        "is_retweet", "retweet_source", "quantification_cost", "replied_to", "reply_post_id"
    ]
    expected_count = len(expected_fields)

    print(f"Checking {POSTS_CSV} for integrity...")
    print(f"Expected {expected_count} columns.")

    issues = 0
    rows = []
    
    try:
        with open(POSTS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            if not header:
                print("Empty file.")
                return

            if len(header) != expected_count:
                print(f"HEADER ERROR: Found {len(header)} columns, expected {expected_count}")
                issues += 1
            
            for i, row in enumerate(reader, start=1):
                if len(row) != expected_count:
                    print(f"ROW {i} ERROR: Found {len(row)} columns, expected {expected_count}")
                    issues += 1
                    # Attempt simple fix: invalid row often happens due to unescaped quotes
                    # For now, just report
                
                # Check for commas in content (sanity check)
                content_idx = 2
                if len(row) > content_idx:
                    content = row[content_idx]
                    if "," in content:
                        # This verifies that the parser handled the comma correctly (kept it IN the field)
                        # If the parser split on the comma, len(row) would be > expected_count
                        pass 

                rows.append(row)

    except Exception as e:
        print(f"CRITICAL ERROR reading CSV: {e}")
        return

    if issues == 0:
        print(f"SUCCESS: All {len(rows)} rows have correct column count.")
        print("Commas within fields are correctly handled by CSV quoting.")
    else:
        print(f"FOUND {issues} ISSUES. Please review output.")

if __name__ == "__main__":
    verify_csv()
