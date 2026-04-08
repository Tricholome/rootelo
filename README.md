# Rootelo

Automated Elo-based leaderboard and stats for Root Digital League.

## 🚀 Live Website
👉 **[View the Website](https://tricholome.github.io/rootelo)**

## ⚙️ How it works
This project is a static site generator powered by **Python**:
* **Data**: Fetches match data from the Root Digital League API and processes it using `pandas`.
* **Templating**: Generates the final website pages using **Jinja2 HTML templates**.
* **Frontend**: Uses custom **CSS** and **JS** located in the `static` folder for the UI and interactive charts.
* **Automation**: The pipeline runs once a day, triggered by an **external Cron job** calling GitHub Actions to ensure precise timing.

*Last updated: Automated via GitHub Actions*
