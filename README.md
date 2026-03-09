# Google Maps Lead Parser Pro

A powerful, robust, and smart asynchronous web scraper for Google Maps built with Python, Playwright, and FastAPI. It extracts business leads (company names, phone numbers, Google Maps links) directly from search results based on granular local grids and smartly filters them by reviews, ratings, and freshness.

## Features

- **Asynchronous Parsing:** Built on `playwright.async_api` and `asyncio` for high performance with batch processing.
- **Smart Grid Scanning:** Scans locations by automatically breaking down target cities into smaller geographic grids (using math coordinates) ensuring no business is missed.
- **Deduplication:** Keeps track of inner Google Maps IDs to strictly prevent duplicates across sessions and projects.
- **Smart Filter Engine:** Capable of filtering out businesses that already have a website. Filters businesses by the amount of reviews or "Freshness" of reviews (e.g., skips if no reviews in the last 6 months).
- **Web UI Dashboard:** Built-in FastAPI dashboard to configure parsing tasks, set filters, view progress with a visual progress bar, and manage task quotas.
- **Memory Optimal:** Creates and destroys isolated browser contexts per zone to prevent RAM leakage during massive parsing over several days.
- **Adaptive Speed Modes:** "Fast", "Medium", and "Deep" modes automatically skip unpromising geographic zones to save scraping time.
- **Persistent Progress:** Automatically saves state and can resume flawlessly after internet drops or system reboots.

## Requirements

- Python 3.9+
- Google Chrome installed

## Installation

Run the provided `setup_and_run.bat` (on Windows). 
It will automatically:
1. Create a `venv` (virtual environment).
2. Install all requirements (`fastapi`, `playwright`, `uvicorn`, etc.).
3. Download the necessary Playwright Chromium binary.
4. Launch the local FastAPI server and open the Web UI in your browser.

## Usage
1. Open the UI map at `http://127.0.0.1:8000`.
2. Configure **Default Settings** (Radius, Quota, Speed Mode, Review Filters).
3. Add a **New Task** by selecting Cities and Niches (Keywords).
4. Click **Start Parsing** and watch the real-time logs and progress bar.
5. All parsed data is saved in real-time to CSV files in the project directory, named automatically (e.g., `Miami_Plumbing_Leads.csv`). Any rejected entries due to filters are documented in `Rejects_*.txt`.

## Disclaimer

This project is intended for educational purposes only. Make sure to comply with Google's Terms of Service and your local data protection laws before scraping data.