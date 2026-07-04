# ⚡ Energy Consumption Optimizer

A web-based smart energy monitoring system for Pakistani households.

## Features
- **Smart Energy Monitoring** — Appliance-level consumption tracking in kWh & Rupees
- **Weather-Aware Solar Integration** — Real-time weather API + solar output estimation
- **Energy Margin Banking** — Save energy credits on low-usage days, use on hot days
- **Budget Warning System** — Red alert when monthly bill exceeds budget
- **Interactive Load Balancer** — Drag sliders to balance appliance usage
- **Visual Charts** — Monthly usage & cost breakdown per appliance

## Tech Stack
- Python Flask (Backend)
- MySQL (Database)
- HTML/CSS with Glassmorphism (Frontend)
- Chart.js (Graphs)
- OpenWeatherMap API (Weather)

## Setup
1. Clone: `git clone https://github.com/jinn-vs/Energy-Consumption-Optimizer.git`
2. Create venv: `python -m venv venv`
3. Activate: `venv\bin\Activate.ps1`
4. Install: `pip install flask mysql-connector-python requests`
5. Create `config.py` with your MySQL password & API key
6. Create database: `CREATE DATABASE energy_optimizer;`
7. Run: `python app.py`
8. Open: `http://127.0.0.1:5000`

## Author
M.Ali.Qamer | BSE-4B-F24 | CUI WAH