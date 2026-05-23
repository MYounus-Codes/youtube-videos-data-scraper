# 🎬 YouTube Search Scraper

A robust, lightweight YouTube search scraper that collects video titles, view counts, channels, and URLs — **no browser, no API key, no Selenium** — using Python's `requests`, `BeautifulSoup`, and `Pandas`.

Automatically paginates through YouTube's internal continuation API to collect as many results as you need, with full error handling, retry logic, and clean CSV export.

---

## 📋 Table of Contents

- [How It Works](#-how-it-works)
- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [CLI Reference](#-cli-reference)
- [Output Format](#-output-format)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [Known Limitation](#-known-limitation)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## ⚙️ How It Works

```
1.  GET youtube.com/results?search_query=<query>
      └─ Parse ytInitialData JSON blob embedded in the HTML
      └─ Extract first ~12–20 videos + continuation token + API key + client version
      └─ BeautifulSoup fallback if JSON blob is missing

2.  POST youtube.com/youtubei/v1/search   (repeat until target reached)
      └─ Body: { context: { client: {...} }, continuation: <token> }
      └─ Response: next batch of videos + next continuation token

3.  Deduplicate all videos by URL across every page

4.  Trim to exact requested count → save to CSV via Pandas
```

Every network call has **retry logic** (3 attempts, 2s delay). Client errors (4xx) are not retried; server errors (5xx) are.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **No browser required** | Pure `requests` — fast, lightweight, no Chrome/Selenium dependency |
| **No API key needed** | Uses YouTube's internal `ytInitialData` JSON and continuation endpoint |
| **Automatic pagination** | Follows continuation tokens page-by-page until target count is hit |
| **Retry logic** | 3 attempts per request with configurable delay; smart 4xx/5xx handling |
| **BeautifulSoup fallback** | Falls back to HTML parsing if the JSON blob is unavailable |
| **Deduplication** | URL-based seen-set prevents duplicates across pages |
| **Configurable delay** | `--delay` flag controls pause between continuation requests |
| **View count normalisation** | `"1.2M views"` → `1200000` integer + raw text both saved |
| **Rich metadata** | Title, channel, view count (int + text), duration, publish date, URL, timestamp |
| **Auto-named output** | CSV filename includes query slug + UTC timestamp if no name given |
| **Dual logging** | Console output + `scraper.log` file written simultaneously |
| **UTF-8 BOM CSV** | Opens correctly in Excel without encoding issues |

---

## 📦 Requirements

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| requests | latest |
| beautifulsoup4 | latest |
| pandas | latest |
| lxml *(optional)* | faster HTML parser for BeautifulSoup fallback |

No browser. No ChromeDriver. No API credentials.

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/youtube-scraper.git
cd youtube-scraper
```

### 2. Create a virtual environment (recommended)

```bash
# Create
python -m venv .venv

# Activate — Windows
.venv\Scripts\activate

# Activate — macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install requests beautifulsoup4 pandas lxml
```

Using `uv`:

```bash
uv pip install requests beautifulsoup4 pandas lxml
```

No other setup needed.

---

## 💻 Usage

### Collect 50 videos (default)

```bash
python youtube_scraper.py -q "python tutorials"
```

### Collect a specific number of results

```bash
python youtube_scraper.py -q "machine learning" -n 150
```

### Save to a custom file name

```bash
python youtube_scraper.py -q "lo-fi music" -n 100 -o lofi.csv
```

### Slow down requests (be more polite)

```bash
python youtube_scraper.py -q "web development" -n 80 --delay 1.5
```

### Combine all options

```bash
python youtube_scraper.py -q "deep learning course" -n 200 -o deep_learning.csv --delay 1.2
```

### Use long-form flags

```bash
python youtube_scraper.py --query "data science" --max_results 75 --output ds.csv --delay 1.0
```

---

## 📌 CLI Reference

```
usage: youtube_scraper.py [-h] --query QUERY [--max_results MAX_RESULTS]
                          [--output OUTPUT] [--delay DELAY]

options:
  -h, --help                        Show help and exit

required:
  -q, --query       QUERY           YouTube search query string

optional:
  -n, --max_results MAX_RESULTS     Number of videos to collect
                                    (default: 50)
  -o, --output      OUTPUT          Output CSV file path
                                    Auto-named as youtube_<query>_<timestamp>.csv
                                    if omitted
  -d, --delay       DELAY           Seconds to wait between continuation
                                    requests (default: 0.8)
```

### Quick-reference table

| Goal | Command |
|---|---|
| Quick 50-video scrape | `python youtube_scraper.py -q "react tutorial"` |
| Large dataset | `python youtube_scraper.py -q "javascript" -n 200` |
| Custom output file | `python youtube_scraper.py -q "cooking" -n 80 -o cooking.csv` |
| Slower, polite scraping | `python youtube_scraper.py -q "AI tools" -n 100 -d 2.0` |
| All options | `python youtube_scraper.py -q "guitar lessons" -n 150 -o guitar.csv -d 1.2` |

---

## 📊 Output Format

Results are saved as a **UTF-8 BOM CSV** — opens correctly in Excel without any encoding configuration.

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
| `scraped_at` | string | `2026-05-24T12:30:00` | UTC timestamp of when the row was scraped |

### Auto-named file format

When `--output` is omitted, the filename is generated as:

```
youtube_<query_slug>_<YYYYMMDD_HHMMSS>.csv

# Examples:
youtube_python_tutorials_20260524_123045.csv
youtube_machine_learning_20260524_130512.csv
youtube_lo_fi_music_20260524_141200.csv
```

### Terminal preview

After every run a summary table prints to the console:

```
======================================================================
  150 videos saved → youtube_python_course_20260524_123045.csv
======================================================================
                                    title        view_text            channel
         Python Full Course for Beginners  47,772,495 views  Programming with Mosh
                   Learn Python in 1 Hour  24,297,526 views  Programming with Mosh
  ...
======================================================================
```

---

## 🗂 Project Structure

```
youtube-scraper/
│
├── youtube_scraper.py      # Main script — all scraping logic
├── README.md               # This file
└── scraper.log             # Auto-created on first run; appended on each run
```

Single-file project — no package structure, no config files needed.

---

## 🏗 Architecture

### Module layout

```
youtube_scraper.py
│
├── _get()                      HTTP GET with 3-attempt retry logic
├── _post()                     HTTP POST with 3-attempt retry logic
│
├── _parse_initial_page()       Parse page-1 HTML → videos + token + api_key + client_ver
│   ├── ytInitialData regex     Extracts embedded JSON blob from raw HTML
│   └── _extract_videos_and_token()  Walks sectionListRenderer contents
│
├── _fetch_continuation()       POST to /youtubei/v1/search with token
│   └── _extract_videos_and_token()  Walks appendContinuationItemsAction items
│
├── _bs4_fallback()             BeautifulSoup HTML parse — used if JSON blob missing
│
├── _extract_video()            Parse one videoRenderer dict → flat record dict
├── parse_view_count()          "1.2M views" → 1200000 integer
│
├── scrape_youtube_search()     Orchestration loop: page 1 → continuations → dedup
└── save_to_csv()               Pandas DataFrame → UTF-8 BOM CSV + terminal table
```

### Pagination flow in detail

```
GET /results?search_query=python
  └─ ytInitialData JSON  →  ~12–20 videos  +  token₁  +  API key  +  client version
        │
        ▼
POST /youtubei/v1/search  { continuation: token₁, context: { client: WEB } }
  └─ onResponseReceivedCommands  →  ~8–20 videos  +  token₂
        │
        ▼
POST /youtubei/v1/search  { continuation: token₂ }
  └─  ~8–20 videos  +  token₃
        │
        ▼  (repeat until max_results reached OR no token returned)
```

### Retry logic

```
for attempt in 1..3:
    try request
    on HTTPError:
        if status < 500:  return None  # don't retry client errors
        else:             continue     # retry server errors
    on ConnectionError / Timeout:
        wait 2s, retry
    on other RequestException:
        return None immediately
return None after all attempts exhausted
```

### Deduplication

A `seen_urls: set[str]` is built from page-1 results and extended on every continuation page. Only videos whose URL is not already in the set are appended. This prevents counting the same video twice if YouTube returns overlapping results across pages.

---

## ⚠️ Known Limitation

YouTube's internal continuation API stops issuing tokens after approximately **4–5 pages** (~36–50 results) when it detects a non-browser client — regardless of how the requests are structured.

This means:

- Queries with massive result pools (e.g. "python") may cap around **36–50 results** with this script
- The scraper will stop cleanly with a log message: `No new unique videos — stopping pagination`
- This is a server-side decision by YouTube based on the absence of real browser signals

**If you need more than ~50 results**, use a browser-based approach (Selenium + undetected-chromedriver) which bypasses this limit by running a real Chrome session. This script is best suited for collecting up to ~50 high-quality results quickly and without any browser dependency.

---

## 🔧 Troubleshooting

### `ModuleNotFoundError`
```bash
pip install requests beautifulsoup4 pandas lxml
```

### Script exits with "No videos found"
YouTube may have changed its page structure. Check `scraper.log` for the specific error. The most common cause is a change to the `ytInitialData` JSON path. The BeautifulSoup fallback will activate automatically if the JSON blob regex fails.

### Only getting 12–36 results when requesting more
This is the [known limitation](#-known-limitation) above — YouTube caps continuation tokens for non-browser clients. The scraper collects everything available and stops cleanly.

### `JSONDecodeError` in scraper.log
YouTube returned a malformed or truncated page. This usually resolves on retry. Run the command again.

### CSV opens with garbled characters in Excel
The file is saved with UTF-8 BOM encoding (`utf-8-sig`) specifically for Excel compatibility. If it still garbles, use **Data → From Text/CSV** in Excel and manually select UTF-8.

### `view_count` column shows `null` / `NaN`
Some videos (live streams, premieres, very new uploads) don't expose a view count in search results. The `view_text` column will show `N/A` in those cases.

### Rate limiting / 429 errors
Increase the delay between requests:
```bash
python youtube_scraper.py -q "your query" -n 100 --delay 3.0
```

---

## 📄 License

MIT License — free to use, modify, and distribute with attribution.

> **Note:** Scraping YouTube may conflict with their Terms of Service. Use responsibly and for personal or research purposes only.

---

<p align="center">Built with Python 🐍 · requests · BeautifulSoup · Pandas</p>
