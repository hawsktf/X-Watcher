import csv
import os
import shutil
from datetime import datetime

REPLIES_CSV = "data/replies.csv"
BACKUP_DIR = "data/archive"

def clean_replies():
    if not os.path.exists(REPLIES_CSV):
        print("replies.csv not found.")
        return

    # Backup
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = int(datetime.now().timestamp())
    backup_path = os.path.join(BACKUP_DIR, f"replies_backup_{timestamp}.csv")
    shutil.copy(REPLIES_CSV, backup_path)
    print(f"Backup created at {backup_path}")

    rows = []
    removed_count = 0
    
    with open(REPLIES_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['status'] == 'rejected_duplicate':
                removed_count += 1
                continue
            rows.append(row)
            
    with open(REPLIES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Cleaned {removed_count} duplicate rows from replies.csv.")

if __name__ == "__main__":
    clean_replies()
