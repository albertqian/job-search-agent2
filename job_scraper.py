"""
job_scraper.py
Scrapes Craigslist SF Bay Area for product marketing roles.
Writes results to data/job_results.json for send_email.py to consume.
"""

import json
import re
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

OUTPUT_PATH = Path("data/job_results.json")

QUERIES = [
    "product marketing manager",
    "product marketing",
    "PMM",
    "go to market manager",
    "senior product marketing",
]


def scrape_craigslist_jobs(query: str, max_results: int = 25) -> list[dict]:
    results = []
    url = (
        f"https://sfbay.craigslist.org/search/jjj"
        f"?query={requests.utils.quote(query)}&sort=date"
    )

    print(f"[CL] Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[CL] Request failed: {e}")
        return results

    soup = BeautifulSoup(resp.text, "html.parser")
    listings = soup.select("li.cl-search-result")
    print(f"[CL] Found {len(listings)} raw listings for '{query}'")

    for listing in listings[:max_results]:
        try:
            title_el = listing.select_one("a.cl-app-anchor span.label")
            date_el  = listing.select_one("div.meta span.date, time")
            link_el  = listing.select_one("a.cl-app-anchor")
            meta_el  = listing.select_one(".meta")

            title    = title_el.get_text(strip=True) if title_el else "Unknown"
            date_raw = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
            url      = link_el["href"] if link_el else ""
            meta     = meta_el.get_text(" ", strip=True) if meta_el else ""
            salary   = extract_salary(title + " " + meta)

            results.append({
                "title":      title,
                "company":    None,
                "salary":     salary,
                "location":   "San Francisco, CA",
                "url":        url,
                "posted":     format_date(date_raw),
                "query":      query,
                "scraped_at": datetime.now().isoformat(),
            })

        except Exception as e:
            print(f"[CL] Parse error: {e}")
            continue

    return results


def enrich_listings(listings: list[dict], max_enrich: int = 15) -> list[dict]:
    """Visit individual listing pages to extract company and salary."""
    for listing in listings[:max_enrich]:
        if not listing.get("url"):
            continue
        try:
            resp = requests.get(listing["url"], headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")

            body  = soup.select_one("#postingbody")
            attrs = soup.select_one(".attrgroup")
            body_text = (body.get_text(" ", strip=True) if body else "") + \
                        (attrs.get_text(" ", strip=True) if attrs else "")

            if not listing["salary"]:
                listing["salary"] = extract_salary(body_text)
            if not listing["company"]:
                listing["company"] = extract_company(body_text)

            time.sleep(random.uniform(0.8, 1.5))
        except Exception:
            continue
    return listings


def extract_salary(text: str) -> str | None:
    patterns = [
        r"\$[\d,]+\s*(?:[-–]\s*\$[\d,]+)?\s*(?:\/\s*(?:hr|hour|year|yr|annually|mo|month))?",
        r"[\d,]+k?\s*(?:[-–]\s*[\d,]+k?)?\s*(?:per|\/)\s*(?:hr|hour|year|yr|mo|month)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group().strip()
    return None


def extract_company(text: str) -> str | None:
    patterns = [
        r"(?:company|employer|organization|firm)[:\s]+([A-Z][A-Za-z0-9\s&,\.]{2,40})",
        r"(?:at|@|with|for)\s+([A-Z][A-Za-z0-9\s&]{2,30})(?:\s+is|\s+are|\s+we|\.|,)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            noise = {"we", "our", "the", "a", "an", "this", "that"}
            if candidate.lower() not in noise and len(candidate) > 2:
                return candidate
    return None


def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return date_str.strip()


def run_scraper():
    all_results = []

    for query in QUERIES:
        results = scrape_craigslist_jobs(query, max_results=25)
        all_results.extend(results)
        time.sleep(random.uniform(2.0, 3.5))

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in all_results:
        key = r.get("url") or r["title"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Enrich with company/salary from individual pages
    deduped = enrich_listings(deduped)

    # Sort newest first
    deduped.sort(key=lambda x: x.get("posted", ""), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "city":    "San Francisco, CA",
            "queries": QUERIES,
        },
        "count":    len(deduped),
        "listings": deduped,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n✓ Done. {len(deduped)} listings written to {OUTPUT_PATH}")
    return payload


if __name__ == "__main__":
    run_scraper()
