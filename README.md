# Rootelo

Automated Elo-based leaderboard and stats for Root Digital League.

## 🚀 Live Website
👉 **[View the Website](https://tricholome.github.io/rootelo)**

## ⚙️ How it works
This project is a static site generator powered by **Python**:

### 📊 Data Management
* **Live Standings**: Fetches real-time match data from the Root Digital League API.
* **Archives**: Uses a secondary script (`generate_lh01_db.py`) to process and freeze historical data into CSV/JSON format. The main site then reads these files to display past seasons (e.g., LH01).
* **Manual Corrections**: Dedicated CSV file are used to manually fix specific data points (like dates) that might be incorrect in the source API.

### 🏗️ Technology Stack
* **Engine**: Data processing via `pandas`.
* **Templating**: Pages generated with **Jinja2 HTML templates**.
* **Frontend**: Custom **CSS/JS** and assets for a tailored user experience.
* **Automation**: Pipeline triggered daily by an **external Cron job** via GitHub Actions for maximum reliability.

*Last updated: Automated via GitHub Actions*
