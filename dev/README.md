# Rootelo

Automated Elo-based leaderboard and stats for the Root Digital League.

👉 **[View the Live Website](https://tricholome.github.io/rootelo)**

## 🛠️ How it Works
Rootelo is a custom static site generator built with Python:
1. **Extraction**: Fetches match results from the **Root Digital League API**.
2. **Processing**: Calculates Elo ratings, assigns tiers, compiles match stats and builds player trends using `pandas`.
3. **Rendering**: Injects the processed data into HTML templates to generate a static website.

## 📂 Project Structure

### ⚙️ Core Scripts
* `main.py`: The primary engine for daily updates and data rendering.
* `archive_season.py`: Utility script executed at the end of a season to process, freeze, and export historical data.

### 📊 Data
Stores the frozen state of completed seasons. Each season consists of:
* `*_final_ratings.csv`: Final Elo standings and tier distributions.
* `*_matches_fixed.csv`: Processed match history.
* `*_history_full.json`: Player rating progression over time.
* `*_metadata.json`: Static stats for archives.
* `*_corrections.csv`: Manual overrides to fix API dates anomalies without altering the source code.

### 🎨 Frontend & Templates
* **`/templates`**: Modular Jinja2 HTML templates. All pages (leaderboard, trends, etc.) extend `base.html`, which serves as the master layout for navigation and structure.
* **`/static`**: Custom frontend logic and styling (`script.js`, `style.css`).
* **`/assets`**: Icons, images, and other static media files.

### 🤖 Automation & Workflows
The deployment pipeline is fully automated via GitHub Actions:
* `update_rootelo.yml`: Daily production build, triggered by an external cron job.
* `archive_season.yml`: Processes and freezes historical data for new archives.
* `deploy-dev.yml`: Manual deployment workflow used for testing features before production.
