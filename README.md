# X-Watcher: Hybrid Social Automation Agent

X-Watcher is a powerful social media monitoring and automation agent designed for high reliability and visual excellence. It captures content from X/Twitter through a hybrid approach and providing a premium feed experience for real-time monitoring.

## 🚀 Key Features

- **Hybrid High-Reliability Scraping**: 
  - **Authenticated X.com Scraping**: Logs into X.com to retrieve the most accurate data.
  - **Nitter Mirror Fallback**: Automatically rotates through a list of Nitter mirrors if `x.com` is blocked or failing, ensuring zero downtime.
  - **Source Prioritization**: Tracks the last successful source and prioritizes it for the next run.
- **Session Persistence**: Uses Playwright persistent contexts to keep you logged in to X, avoiding repeated login attempts and potential flags.
- **AI-Powered Quantification**: Uses Google Gemini to intelligently score posts (0-100) based on your brand alignment, with full cost tracking and blacklist filtering.
- **Intelligent Reply Drafting**: Generates contextual, witty replies using Gemini Pro, respecting your brand voice and persona guidelines.
- **Auto-Qualification**: Filters drafts based on age, duplicate checks, and relevance thresholds before posting.
- **Engagement Monitoring**: Monitors and replies to interactions on your own posts to boost visibility and community engagement.
- **Nostr Integration**: Optionally broadcasts qualified replies to multiple Nostr relays, with automatic screenshot attachments.
- **Premium Feed GUI**: 
  - Modern, X-style visualization of your `posts.csv`.
  - Dark mode with glassmorphism design and Outfit typography.
  - **Newest-to-Oldest** chronological sorting across all sources.
  - Threaded layout with dedicated **↩️ Reply** indicators.
  - Configurable auto-refresh (default 5 minutes).
- **Interactive Dashboard**: A terminal-based hub to manage settings and run manual scrapers/repliers.

## 🔄 Core Automation Flow

![Core Automation Flow](core_flow_scraper_quantifier_generator_qualifier_poster.png)

The agent operates in a continuous loop through five specialized stages:
1. **Scraper**: Collects new posts from target handles via X.com or Nitter mirrors.
2. **Quantifier**: Evaluates post relevance using AI and filters out noise based on your `brand.txt`.
3. **Generator**: Drafts contextual replies using your `persona.txt` for communication style.
4. **Qualifier**: Gatekeeper that ensures replies are timely, unique, and meeting quality standards.
5. **Poster**: Publishes the qualified replies to X (via API or Browser) and Nostr.


## 🛠️ Project Structure

- `app.py`: The central automation controller.
- `scraper.py`: Advanced scraping logic for X and Nitter.
- `quantifier.py`: AI relevance scoring and filtering.
- `generator.py`: AI reply generation engine.
- `qualifier.py`: Quality control and age-limit enforcement.
- `poster.py`: Multi-platform publishing (X & Nostr).
- `engagement.py`: Self-interaction monitoring.
- `dashboard.py`: Terminal-based control panel.
- `feed_app.py`: Flask backend for the web feed.
- `db.py`: Local CSV-based data storage engine.
- `config_user/`: User-specific configuration.
  - `config.json`: Master configuration file.
  - `persona.txt`: AI communication style (Tone, Vibe).
  - `brand.txt`: AI content direction (Mission, Mission).
- `data/`: CSV databases (`posts.csv`, `replies.csv`, `handles.csv`).
- `debug/`: Screenshots and diagnostic files.
- `tests/`: Utility scripts and verification tests.
- `data/browser_session`: Persistent browser cookies and session data.


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
   GOOGLE_API_KEY=your_gemini_api_key
   ```

2. **JSON Settings**: Edit `config_user/config.json`:

| Key | Description | Default |
|-----|-------------|---------|
| `handles` | List of X handles to track for content. | `[]` |
| `refresh_seconds` | Interval between auto-scraper cycles. | `1800` |
| `quantifier_threshold` | Minimum score (0-100) to draft a reply. | `80` |
| `qualify_age_limit_hours` | Max age of a post to be considered for a reply. | `4` |
| `workflow_mode` | `draft` (review only) or `post` (automated posting). | `post` |
| `engagement_enabled` | Monitor and reply to interactions on your own posts. | `true` |
| `nostr_enabled` | Enable cross-posting to Nostr relays. | `true` |
| `use_x_dot_com` | Set to `true` to use authenticated X scraping instead of Nitter. | `false` |
| `headless_browser` | Run browser in background without a window. | `true` |
| `blacklist_words` | Stop processing posts containing these keywords. | `[]` |
| `quantifier_model` | AI model used for scoring (fast/cheap). | `gemini-2.0-flash` |
| `drafter_model` | AI model used for complex reply drafting. | `gemini-2.0-flash` |
| `gui_refresh_seconds` | GUI auto-refresh interval in seconds. | `300` |


## 🏃 Usage

### Recommended: Use the Helper Script
The easiest way to run the agent is using the provided helper script, which ensures the correct virtual environment is used:
```bash
./run_app.sh
```
To run **only** the scraper: `./run_app.sh --scraper-only`

To automatically score posts after scraping: `./run_app.sh --quantifier`

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
