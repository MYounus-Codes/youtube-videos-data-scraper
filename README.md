# 🎬 YouTube Search Scraper

A robust, browser-based YouTube search scraper that collects **as many results as you ask for** by simulating real infinite scroll — no API keys, no hard limits.

Built with **Selenium + undetected-chromedriver**, **BeautifulSoup**, and **Pandas**.

---

## 📋 Table of Contents

- [Why This Exists](#-why-this-exists)
- [How It Works](#-how-it-works)
- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [CLI Reference](#-cli-reference)
- [Output Format](#-output-format)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [Troubleshooting](#-troubleshooting)
- [Limitations](#-limitations)
- [License](#-license)

---

## 🤔 Why This Exists

YouTube's internal search continuation API (`/youtubei/v1/search`) silently stops issuing pagination tokens after ~4 pages when it detects a scripted/headless client. This means pure-requests scrapers hard-cap at ~36 results regardless of what you ask for.

This scraper solves that by driving a **real Chrome browser** that YouTube cannot distinguish from a human. Chrome scrolls the page, YouTube lazily loads more cards, the scraper harvests them — indefinitely until your target is reached.

---

## ⚙️ How It Works

```
1.  Launch Chrome (visible or headless) via undetected-chromedriver
2.  Navigate to youtube.com/results?search_query=<your query>
3.  Dismiss cookie/consent dialogs automatically if present
4.  Loop:
      a. Extract videos from window.ytInitialData  (JS context — rich metadata)
      b. Extract videos from ytd-video-renderer DOM cards  (catches dynamic loads)
      c. Merge both sources, deduplicate by URL
      d. Scroll down 3000px
      e. Wait 1.5s for new cards to render
      f. Repeat until target count reached OR 6 consecutive scrolls yield nothing
5.  Trim to exact requested count
6.  Save to CSV via Pandas
```

The dual-harvest strategy (JS snapshot + DOM cards) ensures no video is missed even when YouTube's internal data object lags behind the rendered page.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Unlimited results** | Scrolls until your target is hit — tested to 300+ |
| **Bot-detection bypass** | `undetected-chromedriver` patches Chrome automation fingerprints |
| **Dual data extraction** | JS context + DOM fallback — catches every card |
| **Deduplication** | URL-based seen-set prevents double-counting across scrolls |
| **Smart stall detection** | Stops after 6 empty scrolls — won't hang on short result sets |
| **Auto consent handling** | Clicks away cookie banners automatically |
| **Headless mode** | `--headless` flag for server / CI use |
| **Auto-named output** | CSV filename includes query slug + UTC timestamp |
| **Dual logging** | Console + `scraper.log` file |
| **View count normalisation** | `"1.2M views"` → `1200000` integer column |
| **Rich metadata** | Title, channel, view count, duration, publish date, URL, scraped_at |

---

## 📦 Requirements

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| Google Chrome | 112 or higher (must be installed) |
| selenium | latest |
| undetected-chromedriver | latest |
| pandas | latest |

> **ChromeDriver is managed automatically** by `undetected-chromedriver` — you do not need to download or configure it manually.

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/youtube-scraper.git
cd youtube-scraper
```

### 2. Create a virtual environment (recommended)

```bash
# Standard venv
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install selenium undetected-chromedriver pandas
```

Or if you use `uv`:

```bash
uv pip install selenium undetected-chromedriver pandas
```

### 4. Verify Chrome is installed

```bash
# Windows — check version in Chrome's about page
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version

# Linux
google-chrome --version
# or
chromium-browser --version
```

---

## 💻 Usage

### Basic — collect 50 videos (default)

```bash
python youtube_scraper.py -q "python tutorials"
```

### Collect a specific number of results

```bash
python youtube_scraper.py -q "machine learning" -n 150
```

### Save to a custom file

```bash
python youtube_scraper.py -q "lo-fi beats" -n 200 -o lofi_music.csv
```

### Run headless (no browser window — good for servers)

```bash
python youtube_scraper.py -q "data science" -n 100 --headless
```

### Combine all options

```bash
python youtube_scraper.py -q "deep learning course" -n 300 --headless -o deep_learning.csv
```

### Use long-form flags

```bash
python youtube_scraper.py --query "web development" --max_results 75 --output webdev.csv
```

---

## 📌 CLI Reference

```
usage: youtube_scraper.py [-h] --query QUERY [--max_results MAX_RESULTS]
                          [--output OUTPUT] [--headless]

options:
  -h, --help                        Show this help message and exit

required:
  -q, --query       QUERY           YouTube search query string

optional:
  -n, --max_results MAX_RESULTS     Number of videos to collect (default: 50)
  -o, --output      OUTPUT          Output CSV file path
                                    Auto-named as youtube_<query>_<timestamp>.csv
                                    if omitted
      --headless                    Run Chrome without a visible window
```

### Examples at a glance

| Goal | Command |
|---|---|
| Quick 50-video scrape | `python youtube_scraper.py -q "react tutorial"` |
| Large dataset, 300 videos | `python youtube_scraper.py -q "javascript" -n 300` |
| Server / no display | `python youtube_scraper.py -q "ai tools" -n 100 --headless` |
| Named output file | `python youtube_scraper.py -q "cooking" -n 80 -o cooking.csv` |
| All options combined | `python youtube_scraper.py -q "guitar lessons" -n 200 --headless -o guitar.csv` |

---

## 📊 Output Format

Results are saved as a **UTF-8 BOM CSV** (opens correctly in Excel without encoding issues).

### Columns

| Column | Type | Example | Description |
|---|---|---|---|
| `title` | string | `Python Full Course for Beginners` | Full video title |
| `channel` | string | `freeCodeCamp.org` | Channel / uploader name |
| `view_count` | integer | `47772495` | Parsed numeric view count (`null` if unavailable) |
| `view_text` | string | `47,772,495 views` | Raw view count string as shown on YouTube |
| `duration` | string | `6:14:07` | Video duration (H:MM:SS or MM:SS) |
| `published` | string | `3 years ago` | Relative publish date as shown on YouTube |
| `url` | string | `https://youtube.com/watch?v=...` | Full canonical video URL |
| `scraped_at` | string | `2026-05-24T12:30:00+00:00` | UTC timestamp of when the row was scraped |

### Auto-named file format

When `--output` is omitted, the file is named:

```
youtube_<query_slug>_<YYYYMMDD_HHMMSS>.csv

# Examples:
youtube_python_tutorials_20260524_123045.csv
youtube_machine_learning_20260524_130512.csv
```

### Terminal preview

After saving, a summary table is printed to the console:

```
========================================================================
  150 videos saved → youtube_python_course_20260524_123045.csv
========================================================================
                                    title        view_text         channel
         Python Full Course for Beginners  47,772,495 views  Programming ...
                   Learn Python in 1 Hour  24,297,526 views  Programming ...
  ...
========================================================================
```

---

## 🗂 Project Structure

```
youtube-scraper/
│
├── youtube_scraper.py      # Main script — all scraping logic
├── README.md               # This file
├── scraper.log             # Auto-generated log file (created on first run)
│
└── outputs/                # Suggested folder for CSV files (optional)
    └── youtube_*.csv
```

The project is intentionally single-file for simplicity — no package structure needed.

---

## 🏗 Architecture

### Key components

```
youtube_scraper.py
│
├── build_driver()               Browser setup with bot-bypass options
│
├── scrape_youtube_search()      Main orchestration loop
│   ├── _extract_from_dom_json() Harvest from window.ytInitialData (JS)
│   ├── _scrape_rendered_cards() Harvest from ytd-video-renderer DOM nodes
│   └── _merge()                 Deduplicate and accumulate results
│
├── _parse_renderer()            Parse a single videoRenderer dict → flat record
├── parse_view_count()           "1.2M views" → 1200000
│
└── save_to_csv()                Pandas DataFrame → UTF-8 BOM CSV
```

### Why `undetected-chromedriver`?

Standard `selenium.webdriver.Chrome` injects JavaScript properties (`navigator.webdriver`, `__selenium_*`, etc.) that YouTube detects and uses to throttle or stop serving continuation tokens. `undetected-chromedriver` patches these at the binary level before Chrome starts, making the session indistinguishable from a normal user.

### Stall detection logic

```
stale_scrolls = 0

on each scroll:
  if newly_added == 0:
    stale_scrolls += 1
    extra wait (2.25s instead of 1.5s)
  else:
    stale_scrolls = 0

if stale_scrolls >= 6:
  stop — YouTube has no more results
```

This means the scraper **never hangs** — it exits cleanly whether you ask for 50 videos on a query with 40 results, or 500 on a saturated topic.

---

## 🔧 Troubleshooting

### `ModuleNotFoundError: No module named 'undetected_chromedriver'`
```bash
pip install undetected-chromedriver
```

### Chrome version mismatch error
`undetected-chromedriver` auto-downloads the matching ChromeDriver. If it fails, update Chrome to the latest version and retry.

### Only getting ~20–36 results
You are likely running an older version of this script that used the requests-based approach. Switch to this Selenium version — that hard cap does not exist here.

### Browser window flashes and closes immediately
Chrome crashed during launch. Try:
```bash
# Add to build_driver() options if on Linux with no display:
options.add_argument("--headless=new")
options.add_argument("--disable-software-rasterizer")
```

### `TimeoutException: waiting for search results`
YouTube loaded slowly or returned a captcha. Try:
- Running without `--headless` so you can see what the browser shows
- Adding a longer `PAGE_TIMEOUT` value in the constants section

### Consent dialog not dismissed
YouTube occasionally changes its consent dialog markup. The scraper looks for buttons containing "Accept", "Reject all", or "I agree". If your region shows different text, you can extend the XPath in `scrape_youtube_search()`.

### CSV opens with garbled characters in Excel
The file is saved with UTF-8 BOM encoding (`utf-8-sig`) specifically to fix this. If it still happens, use **Data → From Text/CSV** in Excel and select UTF-8 manually.

---

## ⚠️ Limitations

- **YouTube search cap** — YouTube itself typically returns 200–400 unique results per query regardless of scroll count. Highly specific queries may return fewer. The scraper will stop cleanly when results are exhausted.
- **Speed** — each scroll waits 1.5s for renders, so 150 results takes roughly 30–60 seconds depending on your internet speed.
- **Chrome required** — Firefox is not supported. Chrome must be installed on the machine.
- **No proxy support** — built-in. Add `options.add_argument("--proxy-server=...")` to `build_driver()` manually if needed.
- **YouTube ToS** — scraping YouTube may conflict with their Terms of Service. Use responsibly, for personal/research purposes only.

---

## 📄 License

MIT License — free to use, modify, and distribute with attribution.

---

<p align="center">
  Built with Python 🐍 · Selenium 🤖 · Pandas 🐼
</p>
