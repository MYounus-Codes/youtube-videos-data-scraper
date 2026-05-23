"""
YouTube Search Scraper  —  with Infinite-Scroll Pagination
===========================================================
Scrapes video titles, view counts, and URLs from YouTube search results.
Automatically follows YouTube's continuation tokens to load more results
(equivalent to scrolling down) until the requested count is reached.

Usage:
    python youtube_scraper.py --query "python tutorials" --max_results 100
    python youtube_scraper.py -q "lo-fi music" -n 200 -o lofi.csv
    python youtube_scraper.py -q "machine learning" -n 50 --delay 1.2
"""

import argparse
import re
import json
import time
import logging
import sys
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd


# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────
BASE_URL        = "https://www.youtube.com"
SEARCH_URL      = f"{BASE_URL}/results"
# YouTube's internal endpoint that returns continuation pages as JSON
CONTINUATION_URL = f"{BASE_URL}/youtubei/v1/search"

# Matches the YouTube client version embedded in every page
_CLIENT_VER_RE  = re.compile(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"')
_API_KEY_RE     = re.compile(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "X-YouTube-Client-Name": "1",
}

REQUEST_TIMEOUT = 20
RETRY_ATTEMPTS  = 3
RETRY_DELAY     = 2


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None, session: requests.Session | None = None) -> str | None:
    """GET with retry logic. Returns response text or None."""
    requester = session or requests
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requester.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP %s on attempt %d/%d", exc.response.status_code, attempt, RETRY_ATTEMPTS)
            if exc.response.status_code < 500:
                return None          # client error — no point retrying
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.warning("Network issue on attempt %d/%d. Retrying in %ds…", attempt, RETRY_ATTEMPTS, RETRY_DELAY)
        except requests.exceptions.RequestException as exc:
            logger.error("Request error: %s", exc)
            return None
        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY)
    logger.error("All retries exhausted for GET %s", url)
    return None


def _post(url: str, payload: dict, params: dict | None = None,
          session: requests.Session | None = None) -> dict | None:
    """POST JSON with retry logic. Returns parsed JSON dict or None."""
    requester = session or requests
    post_headers = {**HEADERS, "Content-Type": "application/json"}
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requester.post(url, json=payload, params=params,
                                  headers=post_headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP %s on attempt %d/%d", exc.response.status_code, attempt, RETRY_ATTEMPTS)
            if exc.response.status_code < 500:
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.warning("Network issue on attempt %d/%d. Retrying in %ds…", attempt, RETRY_ATTEMPTS, RETRY_DELAY)
        except requests.exceptions.RequestException as exc:
            logger.error("Request error: %s", exc)
            return None
        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY)
    logger.error("All retries exhausted for POST %s", url)
    return None


# ── View-count parsing ─────────────────────────────────────────────────────────

def parse_view_count(raw: str) -> int | None:
    """'1.2M views' → 1_200_000.  Returns None on parse failure."""
    if not raw:
        return None
    raw = raw.lower().replace(",", "").replace(" views", "").strip()
    for suffix, mult in (("b", 1_000_000_000), ("m", 1_000_000), ("k", 1_000)):
        if raw.endswith(suffix):
            try:
                return int(float(raw[:-1]) * mult)
            except ValueError:
                return None
    try:
        return int(raw)
    except ValueError:
        return None


# ── Video extraction helpers ───────────────────────────────────────────────────

def _extract_video(renderer: dict) -> dict | None:
    """Parse a single videoRenderer dict into a flat record. Returns None if invalid."""
    title_runs = renderer.get("title", {}).get("runs", [])
    title = "".join(r.get("text", "") for r in title_runs).strip()

    video_id = renderer.get("videoId", "")
    url = f"{BASE_URL}/watch?v={video_id}" if video_id else ""

    if not title or not url:
        return None

    view_text = (
        renderer.get("viewCountText", {}).get("simpleText", "")
        or "".join(
            r.get("text", "")
            for r in renderer.get("viewCountText", {}).get("runs", [])
        )
    )

    channel_runs = renderer.get("ownerText", {}).get("runs", [])
    channel = "".join(r.get("text", "") for r in channel_runs).strip()

    return {
        "title":      title,
        "url":        url,
        "channel":    channel or "N/A",
        "view_count": parse_view_count(view_text),
        "view_text":  view_text or "N/A",
        "duration":   renderer.get("lengthText", {}).get("simpleText", "N/A"),
        "published":  renderer.get("publishedTimeText", {}).get("simpleText", "N/A"),
        "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def _extract_videos_and_token(contents: list) -> tuple[list[dict], str | None]:
    """
    Walk a list of content items (from sectionListRenderer or
    appendContinuationItemsAction) and return:
      - list of video records found
      - next continuationToken (or None if no more pages)
    """
    videos: list[dict] = []
    token: str | None = None

    for item in contents:
        # ── Video results ──────────────────────────────────────────────────
        for renderer in item.get("itemSectionRenderer", {}).get("contents", []):
            vid = renderer.get("videoRenderer")
            if vid:
                record = _extract_video(vid)
                if record:
                    videos.append(record)

        # ── Continuation token (= "load more" / next scroll page) ─────────
        cont = item.get("continuationItemRenderer", {})
        ep   = cont.get("continuationEndpoint", {})
        tok  = ep.get("continuationCommand", {}).get("token", "")
        if tok:
            token = tok

    return videos, token


# ── Page-1: initial HTML fetch ─────────────────────────────────────────────────

def _parse_initial_page(html: str) -> tuple[list[dict], str | None, str, str]:
    """
    Extract videos, continuation token, API key, and client version
    from the first HTML page.
    Returns (videos, token, api_key, client_version).
    """
    # ── ytInitialData JSON blob ────────────────────────────────────────────
    m = re.search(r"var\s+ytInitialData\s*=\s*(\{.*?\});\s*(?:var\s|</script)", html, re.DOTALL)
    if not m:
        logger.warning("ytInitialData blob not found.")
        return [], None, "", ""

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s", exc)
        return [], None, "", ""

    try:
        contents = (
            data["contents"]
            ["twoColumnSearchResultsRenderer"]
            ["primaryContents"]
            ["sectionListRenderer"]
            ["contents"]
        )
    except KeyError:
        logger.error("Unexpected ytInitialData structure.")
        return [], None, "", ""

    videos, token = _extract_videos_and_token(contents)

    # ── API key & client version (needed for continuation POSTs) ──────────
    api_key = (_API_KEY_RE.search(html) or type("", (), {"group": lambda s, n: ""})()).group(1)
    client_ver = (_CLIENT_VER_RE.search(html) or type("", (), {"group": lambda s, n: "2.20240101.00.00"})()).group(1)

    logger.info("Page 1: %d videos | token=%s | ver=%s", len(videos), bool(token), client_ver)
    return videos, token, api_key, client_ver


# ── Subsequent pages: continuation POST ───────────────────────────────────────

def _fetch_continuation(token: str, api_key: str, client_ver: str,
                         query: str, session: requests.Session) -> tuple[list[dict], str | None]:
    """
    POST to YouTube's internal /youtubei/v1/search endpoint using the
    continuation token.  Returns (new_videos, next_token).
    """
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": client_ver or "2.20240101.00.00",
                "hl": "en",
                "gl": "US",
            }
        },
        "continuation": token,
    }
    params = {"key": api_key} if api_key else {}

    data = _post(CONTINUATION_URL, payload, params=params, session=session)
    if not data:
        return [], None

    videos: list[dict] = []
    token: str | None  = None

    # Results arrive inside onResponseReceivedCommands
    for cmd in data.get("onResponseReceivedCommands", []):
        action = cmd.get("appendContinuationItemsAction", {})
        items  = action.get("continuationItems", [])
        if items:
            new_vids, new_tok = _extract_videos_and_token(items)
            videos.extend(new_vids)
            if new_tok:
                token = new_tok

    return videos, token


# ── BeautifulSoup fallback (page 1 only) ──────────────────────────────────────

def _bs4_fallback(html: str) -> list[dict]:
    logger.info("BeautifulSoup fallback parsing…")
    soup   = BeautifulSoup(html, "html.parser")
    videos = []
    for tag in soup.find_all("a", id="video-title"):
        title = tag.get("title") or tag.get_text(strip=True)
        href  = tag.get("href", "")
        url   = urljoin(BASE_URL, href) if href else ""
        if title and url:
            videos.append({
                "title": title, "url": url, "channel": "N/A",
                "view_count": None, "view_text": "N/A",
                "duration": "N/A", "published": "N/A",
                "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
            })
    return videos


# ── Public API ─────────────────────────────────────────────────────────────────

def scrape_youtube_search(
    query: str,
    max_results: int = 50,
    delay: float = 0.8,
) -> list[dict]:
    """
    Scrape YouTube search results for *query*, returning up to *max_results*
    videos.  Automatically follows continuation tokens (= infinite scroll)
    to load additional pages when needed.

    Args:
        query:       Search string.
        max_results: How many videos to collect (stops early if YouTube
                     has no more results).
        delay:       Polite pause (seconds) between continuation requests.

    Returns:
        List of dicts with keys: title, url, channel, view_count, view_text,
        duration, published, scraped_at.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # ── Page 1 ─────────────────────────────────────────────────────────────
    html = _get(SEARCH_URL, params={"search_query": query}, session=session)
    if not html:
        logger.error("Failed to fetch search page.")
        return []

    videos, token, api_key, client_ver = _parse_initial_page(html)

    if not videos:
        videos = _bs4_fallback(html)
        token  = None          # BS4 fallback can't give us a continuation token

    seen_urls: set[str] = {v["url"] for v in videos}
    page = 1

    # ── Continuation pages ─────────────────────────────────────────────────
    while len(videos) < max_results and token:
        page += 1
        logger.info("Fetching page %d … (%d/%d collected)", page, len(videos), max_results)
        time.sleep(delay)

        new_vids, token = _fetch_continuation(token, api_key, client_ver, query, session)

        if not new_vids:
            logger.info("No more results returned by YouTube.")
            break

        added = 0
        for v in new_vids:
            if v["url"] not in seen_urls:
                seen_urls.add(v["url"])
                videos.append(v)
                added += 1

        logger.info("Page %d: +%d unique videos (total %d)", page, added, len(videos))

        if added == 0:
            logger.info("No new unique videos — stopping pagination.")
            break

    result = videos[:max_results]
    logger.info("Done. Collected %d videos.", len(result))
    return result


# ── CSV export ─────────────────────────────────────────────────────────────────

def save_to_csv(videos: list[dict], output_path: str) -> None:
    if not videos:
        logger.warning("No data to save.")
        return

    col_order = ["title", "channel", "view_count", "view_text",
                 "duration", "published", "url", "scraped_at"]
    df = pd.DataFrame(videos)
    df = df[[c for c in col_order if c in df.columns]]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info("Saved %d rows → %s", len(df), output_path)
    print(f"\n{'='*70}")
    print(f"  {len(df)} videos saved → {output_path}")
    print(f"{'='*70}")
    pd.set_option("display.max_colwidth", 55)
    print(df[["title", "view_text", "channel"]].to_string(index=False))
    print(f"{'='*70}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape YouTube search results (with pagination) and save to CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--query", "-q", required=True, help="YouTube search query")
    parser.add_argument("--max_results", "-n", type=int, default=50,
                        help="Number of videos to collect")
    parser.add_argument("--output", "-o", default="",
                        help="Output CSV path (auto-named if omitted)")
    parser.add_argument("--delay", "-d", type=float, default=0.8,
                        help="Seconds to wait between continuation requests")
    args = parser.parse_args()

    query       = args.query.strip()
    max_results = max(1, args.max_results)
    output_path = args.output or (
        f"youtube_{re.sub(r'[^a-z0-9]+', '_', query.lower()[:30])}"
        f"_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    logger.info("Query      : %s", query)
    logger.info("Max results: %d", max_results)
    logger.info("Delay      : %.1fs between pages", args.delay)
    logger.info("Output     : %s", output_path)

    videos = scrape_youtube_search(query, max_results=max_results, delay=args.delay)

    if not videos:
        logger.error("No videos found. Exiting.")
        sys.exit(1)

    save_to_csv(videos, output_path)


if __name__ == "__main__":
    main()