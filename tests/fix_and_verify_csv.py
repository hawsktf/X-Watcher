
import csv
import os
import shutil

POSTS_CSV = "data/posts.csv"
BACKUP_CSV = "data/posts.csv.bak"

def fix_csv():
    if not os.path.exists(POSTS_CSV):
        print(f"File {POSTS_CSV} not found.")
        return

    # Use the existing backup if available, otherwise create one
    if not os.path.exists(BACKUP_CSV):
        print(f"Backing up {POSTS_CSV} to {BACKUP_CSV}...")
        shutil.copy2(POSTS_CSV, BACKUP_CSV)
    
    # Read from the source (which is currently the one with issues)
    rows = []
    try:
        with open(POSTS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames:
                print("CSV has no header.")
                return

            for row in reader:
                # Sanitize content: remove newlines to flatten the CSV
                if 'content' in row and row['content']:
                    row['content'] = row['content'].replace('\n', '  ').replace('\r', '')
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if not rows:
        print("No rows found. formatting header only.")
    else:
        print(f"Processed {len(rows)} rows.")

    # Write to a temporary file first
    TEMP_CSV = "data/posts.csv.tmp"
    try:
        with open(TEMP_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        
        # Verify it's not empty (at least header)
        if os.path.getsize(TEMP_CSV) > 10:
            print("New file created successfully. Replacing original.")
            os.replace(TEMP_CSV, POSTS_CSV)
            print("Success! CSV fixed.")
        else:
            print("Error: Resulting file is too small. Aborting.")
            if os.path.exists(TEMP_CSV): os.remove(TEMP_CSV)
            return

    except Exception as e:
        print(f"Error writing CSV: {e}")
        if os.path.exists(TEMP_CSV): os.remove(TEMP_CSV)
        return

    # Delete backup if requested (only if success)
    if os.path.exists(BACKUP_CSV):
        print("Deleting backup...")
        os.remove(BACKUP_CSV)

if __name__ == "__main__":
    fix_csv()
