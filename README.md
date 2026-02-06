# X-Watcher: Hybrid Social Automation Agent

X-Watcher is a powerful social media monitoring and automation agent designed for high reliability and visual excellence. It captures content from X/Twitter through a hybrid approach and providing a premium feed experience for real-time monitoring.

## 🚀 Key Features

- **Hybrid High-Reliability Scraping**: 
  - **Authenticated X.com Scraping**: Logs into X.com to retrieve the most accurate data.
  - **Nitter Mirror Fallback**: Automatically rotates through a list of Nitter mirrors if `x.com` is blocked or failing, ensuring zero downtime.
  - **Source Prioritization**: Tracks the last successful source and prioritizes it for the next run.
- **Session Persistence**: Uses Playwright persistent contexts to keep you logged in to X, avoiding repeated login attempts and potential flags.
- **Intelligent Quantification**: Scores posts based on custom logic to identify the most relevant content.
- **Automated AI Replier**: Drafts context-aware responses and posts them directly via a browser, bypassing API limitations.
- **Premium Feed GUI**: 
  - Modern, X-style visualization of your `posts.csv`.
  - Dark mode with glassmorphism design and Outfit typography.
  - **Newest-to-Oldest** chronological sorting across all sources.
  - Threaded layout with dedicated **↩️ Reply** indicators.
  - Configurable auto-refresh (default 5 minutes).
- **Interactive Dashboard**: A terminal-based hub to manage settings and run manual scrapers/repliers.

## 🛠️ Project Structure

- `app.py`: The central automation controller.
- `scraper.py`: Advanced scraping logic for X and Nitter.
- `dashboard.py`: Terminal-based control panel.
- `feed_app.py`: Flask backend for the web feed.
- `templates/feed.html`: Frontend for the premium web feed.
- `db.py`: Local CSV-based data storage (`posts.csv`).
- `config.json`: Master configuration file.
- `data/browser_session`: Persistent browser data storage.

## 📦 Installation

1. **Clone and Setup Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Install Browser Dependencies**:
   ```bash
   playwright install firefox
   ```

## ⚙️ Configuration

1. **Environment Variables**: Create a `.env` file in the root directory:
   ```env
   TWITTER_USERNAME=your_x_username
   TWITTER_PASSWORD=your_x_password
   OPENAI_API_KEY=your_openai_key
   ```

2. **JSON Settings**: Edit `config.json`:
   - `handles`: List of X handles to track.
   - `refresh_seconds`: Interval between auto-scraper cycles.
   - `gui_refresh_seconds`: GUI auto-refresh interval (default `300`).
   - `headless_browser`: Set `true` to run browsers in the background.

## 🏃 Usage

### Recommended: Use the Helper Script
The easiest way to run the agent is using the provided helper script, which ensures the correct virtual environment is used:
```bash
./run_app.sh
```
To run **only** the scraper: `./run_app.sh --scraper-only`

### Alternative: Direct Execution
If you prefer direct execution, ensure you are using the virtual environment interpreter:

**Option 1: Activate the venv first**
```bash
source venv/bin/activate
python app.py
```

**Option 2: Use the venv path**
```bash
./venv/bin/python app.py
```

### 📊 Other Components
All other scripts should also be run using the virtual environment:
- **Dashboard**: `./venv/bin/python dashboard.py`
- **Feed GUI**: `./venv/bin/python feed_app.py`

## ⚖️ License
This project is intended for personal monitoring and automation. Use responsibly and in accordance with X.com's Terms of Service.
