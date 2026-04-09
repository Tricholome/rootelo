# Rootelo

Automated Elo-based leaderboard and stats for the Root Digital League.

## 🚀 Live Website
👉 **[View the Website](https://tricholome.github.io/rootelo)**

## ⚙️ How it works
Rootelo is a custom static site generator (SSG) built with **Python**, designed to provide a lightweight and high-performance competitive dashboard.

### 📊 Data Processing & Life Cycle
* **Live Season**: Fetches and processes real-time match data directly from the Root Digital League API.
* **Historical Archives**: Seasons are "frozen" once completed. A dedicated processing script (`archive_season.py`) converts raw historical data into optimized CSV/JSON assets, which are then integrated into the main rendering pipeline.
* **Data Integrity**: Includes a manual correction layer (CSV-based) to fix API anomalies (e.g., incorrect match dates or player aliases) without altering the source.

### 🏗️ Technology Stack
* **Core Engine**: Powered by `pandas` for Elo calculations and data manipulation.
* **Templating**: **Jinja2** is used to generate dynamic HTML pages from a modular base, ensuring consistent UI across live and archived seasons.
* **Frontend**: A custom **Glassmorphism CSS** theme with **DataTables.js** for interactive, searchable, and responsive leaderboards.
* **Automation**: The entire site is rebuilt daily via **GitHub Actions**, triggered by an external cron job for maximum reliability.

### 🛠️ Architecture
The generator follows a "Single Source of Truth" pattern:
1.  **Ingest**: Collects API data and Local Assets.
2.  **Calculate**: Computes Elo ratings, tiers, and player trends.
3.  **Render**: Injects statistics and metadata into Jinja2 templates.
4.  **Deploy**: Pushes the static build to GitHub Pages.

---
*Last updated: Automated via GitHub Actions*
