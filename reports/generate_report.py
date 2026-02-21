import csv
from datetime import datetime
from collections import defaultdict
import os

def generate_performance_report(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    daily_stats = defaultdict(lambda: {'x_posts': 0, 'nostr_posts': 0})

    try:
        with open(input_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                posted_at = row.get('posted_at')
                status = row.get('status')
                posted_to_nostr = row.get('posted_to_nostr')

                if not posted_at:
                    continue

                try:
                    # Parse timestamp (e.g., 2026-02-11T01:39:09.917073+00:00)
                    dt = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                    date_str = dt.date().isoformat()
                except ValueError:
                    # In case of any weird formats, skip or handle
                    continue

                if status == 'posted':
                    daily_stats[date_str]['x_posts'] += 1
                
                if posted_to_nostr == 'Y':
                    daily_stats[date_str]['nostr_posts'] += 1

        # Write the report
        with open(output_file, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'X Posts', 'Nostr Posts'])
            
            # Sort by date
            sorted_dates = sorted(daily_stats.keys())
            for date in sorted_dates:
                writer.writerow([
                    date,
                    daily_stats[date]['x_posts'],
                    daily_stats[date]['nostr_posts']
                ])

        print(f"Successfully generated {output_file}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    input_csv = "/home/spoonbill/Projects/git/X-Watcher-1/data/replies.csv"
    output_csv = "/home/spoonbill/Projects/git/X-Watcher-1/reports/performance_report.csv"
    generate_performance_report(input_csv, output_csv)
