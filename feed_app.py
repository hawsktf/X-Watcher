from flask import Flask, render_template, jsonify
import csv
import os
import json
from dateutil import parser
from datetime import datetime

app = Flask(__name__)

POSTS_CSV = "data/posts.csv"
REPLIES_CSV = "data/replies.csv"

def get_pending_reply_map():
    replies = {}
    if os.path.exists(REPLIES_CSV):
        try:
            with open(REPLIES_CSV, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['status'] == 'pending':
                        replies[row['post_id']] = {
                            "content": row['reply_content'],
                            "cost": row.get('generation_cost', 0.0)
                        }
        except: pass
    return replies

def get_posts():
    posts = []
    pending_map = get_pending_reply_map()
    
    if os.path.exists(POSTS_CSV):
        try:
            with open(POSTS_CSV, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Priority: posted_at (datetime) > scraped_at (date)
                    p_at = row.get('posted_at', '').strip()
                    s_at = row.get('scraped_at', '').strip()
                    
                    date_str = p_at or s_at or '1970-01-01'
                    
                    # Clean Nitter dots
                    clean_date = date_str.replace(' · ', ' ').replace(' ·', ' ').strip()
                    
                    try:
                        dt = parser.parse(clean_date)
                        row['dt_obj'] = dt
                        # Nicer display format: Feb 6, 2026 · 10:10 PM
                        row['formatted_date'] = dt.strftime("%b %-d, %Y · %-I:%M %p")
                    except:
                        row['dt_obj'] = None
                        row['formatted_date'] = date_str
                    
                    # Attach pending reply if exists
                    if row['post_id'] in pending_map:
                        reply_data = pending_map[row['post_id']]
                        row['pending_reply'] = reply_data['content']
                        row['reply_cost'] = reply_data['cost']
                    
                    posts.append(row)
        except Exception as e:
            print(f"Error reading CSV: {e}")
    
    # PURE CHRONOLOGICAL SORT
    def sort_key(x):
        dt = x.get('dt_obj')
        db_id = x.get('post_id', '0')
        ts = dt.timestamp() if dt else 0
        try:
            numeric_id = int(db_id)
        except:
            numeric_id = 0
        return (ts, numeric_id)

    posts.sort(key=sort_key, reverse=True)
    return posts

@app.route('/')
def index():
    return render_template('feed.html')

@app.route('/api/posts')
def api_posts():
    results = []
    for p in get_posts():
        p_copy = p.copy()
        if 'dt_obj' in p_copy: del p_copy['dt_obj']
        results.append(p_copy)
    return jsonify(results)

@app.route('/api/config')
def api_config():
    try:
        with open("config_user/config.json") as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"gui_refresh_seconds": 300})

if __name__ == '__main__':
    port = 5000
    try:
        with open("config_user/config.json") as f:
            cfg = json.load(f)
            port = cfg.get("gui_port", 5000)
    except: pass
    
    print(f"Feed GUI starting at http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
