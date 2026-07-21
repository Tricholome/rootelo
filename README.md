# Rootelo

Automated Elo-based leaderboard and stats for the Root Digital League.

👉 **[View the Live Website](https://tricholome.github.io/rootelo)**

## 🛠️ How it Works
Rootelo is a custom static site generator built with Python:
1. **Extraction**: Fetches match results from the **Root Digital League API**.
2. **Processing**: Calculates Elo ratings, assigns tiers, compiles match stats, and extracts player relationships using `pandas`.
3. **Rendering**: Injects processed data into HTML templates to generate a static website and exports a live JSON API.

## 📂 Project Structure

### ⚙️ Core Scripts
* `main.py`: The primary engine for daily updates, live Elo computation, and site rendering.
* `archive_season.py`: Utility script executed at the end of a season to process, freeze, and export historical data into season archives.

### 📊 Data
Separated into two clear scopes for maintainability:
* **`/data/config`**: Manual inputs edited directly by maintainers.
* **`/data/archives`**: Immutable datasets generated automatically at season end.

### 🎨 Frontend & Assets
* **`/templates`**: Modular Jinja2 HTML templates. All pages extend `base.html` for layout and navigation.
* **`/static`**: Houses the single global stylesheet (`style.css`) and single JavaScript file (`script.js`) driving all frontend interactivity.
* **`/assets`**: Media assets organized into two folders (`/icons` and `/images`).
* **`/api`**: Public JSON endpoint generated for external integrations.

### 🤖 Automation & Workflows
The deployment pipeline is fully automated via GitHub Actions:
* `update_rootelo.yml`: Daily production build and site update, triggered by an external cron job.
* `archive_season.yml`: Manual workflow to process and freeze new historical season archives.
* `deploy-dev.yml`: Manual deployment workflow used for testing features before production.
