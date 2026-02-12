
import csv
import os

POSTS_CSV = "data/posts.csv"

def clean_csv():
    if not os.path.exists(POSTS_CSV):
        print(f"File {POSTS_CSV} not found.")
        return

    # Use the existing backup logic if needed, but we trust the previous step deleted it.
    # Let's just process in place via a temp file.
    
    rows = []
    print(f"Reading {POSTS_CSV}...")
    try:
        with open(POSTS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                # Sanitize content: remove commas
                if 'content' in row and row['content']:
                    # We might as well ensure newlines are gone too, just in case
                    row['content'] = row['content'].replace('\n', '  ').replace('\r', '').replace(',', ' ')
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Processed {len(rows)} rows. Rewrite with sanitized content...")

    TEMP_CSV = "data/posts.csv.clean"
    try:
        with open(TEMP_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        
        if os.path.getsize(TEMP_CSV) > 10:
            print("New file created successfully. Replacing original.")
            os.replace(TEMP_CSV, POSTS_CSV)
            print("Success! CSV cleaned of commas.")
        else:
            print("Error: Resulting file is too small. Aborting.")
            if os.path.exists(TEMP_CSV): os.remove(TEMP_CSV)
    except Exception as e:
        print(f"Error writing CSV: {e}")
        if os.path.exists(TEMP_CSV): os.remove(TEMP_CSV)

if __name__ == "__main__":
    clean_csv()
