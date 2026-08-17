"""
job_scraper.py
Fetches product marketing jobs using JobSpy.
Sources: Indeed + LinkedIn only (Glassdoor blocks GitHub Actions IPs).
"""

import json
import math
import pandas as pd
from datetime import datetime
from pathlib import Path

from jobspy import scrape_jobs

OUTPUT_PATH = Path("data/job_results.json")
DAYS_BACK   = 14

SEARCHES = [
    "product marketing manager",
    "senior product marketing manager",
    "PMM",
]

TITLE_MUST_INCLUDE = [
    "product marketing",
    "pmm",
    "product marketer",
]

TITLE_EXCLUDE = [
    "engineer", "developer", "software", "data",
    "designer", "devops", "backend", "frontend",
    "analyst", "recruiter", "sales", "finance",
    "customer success", "customer support",
]


def fetch_jobs(search_term: str) -> pd.DataFrame:
    print(f"[JobSpy] Searching: '{search_term}'")
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin"],
            search_term=search_term,
            location="Remote",
            results_wanted=25,
            hours_old=24 * DAYS_BACK,
            country_indeed="USA",
        )
        print(f"[JobSpy] Found {len(jobs)} results for '{search_term}'")
        return jobs
    except Exception as e:
        print(f"[JobSpy] Failed for '{search_term}': {e}")
        return pd.DataFrame()


def is_relevant(title: str) -> bool:
    title = title.lower()
    if not any(kw in title for kw in TITLE_MUST_INCLUDE):
        return False
    if any(kw in title for kw in TITLE_EXCLUDE):
        return False
    return True


def safe_int(val) -> int | None:
    """Convert to int safely — handles NaN, None, and empty strings."""
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return int(val)
    except (ValueError, TypeError):
        return None


def format_job(row) -> dict:
    min_sal  = safe_int(row.get("min_amount"))
    max_sal  = safe_int(row.get("max_amount"))
    interval = row.get("interval") or ""
    interval = "" if (isinstance(interval, float) and math.isnan(interval)) else interval

    if min_sal and max_sal:
        salary = f"${min_sal:,} – ${max_sal:,} / {interval}".strip(" /")
    elif min_sal:
        salary = f"${min_sal:,}+ / {interval}".strip(" /")
    else:
        salary = None

    date_posted = row.get("date_posted")
    if hasattr(date_posted, "strftime"):
        posted = date_posted.strftime("%b %d, %Y")
    else:
        posted = str(date_posted) if date_posted and not (isinstance(date_posted, float) and math.isnan(date_posted)) else ""

    location = row.get("location") or "Remote"
    if isinstance(location, float) and math.isnan(location):
        location = "Remote"

    company = row.get("company") or None
    if isinstance(company, float):
        company = None

    return {
        "title":      str(row.get("title", "Unknown")),
        "company":    company,
        "salary":     salary,
        "location":   str(location),
        "source":     str(row.get("site", "")).title(),
        "url":        str(row.get("job_url", "")),
        "posted":     posted,
        "scraped_at": datetime.now().isoformat(),
    }


def run_scraper():
    all_frames = []

    for term in SEARCHES:
        df = fetch_jobs(term)
        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        print("No results returned from any source.")
        payload = {
            "last_updated": datetime.now().isoformat(),
            "params": {"searches": SEARCHES, "days_back": DAYS_BACK},
            "count": 0,
            "listings": [],
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    print(f"\n[JobSpy] {len(combined)} unique jobs before title filter")

    mask     = combined["title"].apply(lambda t: is_relevant(str(t)))
    relevant = combined[mask]
    print(f"[JobSpy] {len(relevant)} PMM-specific jobs after filter")

    formatted = [format_job(row) for _, row in relevant.iterrows()]
    formatted.sort(key=lambda x: x.get("posted", ""), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "searches": SEARCHES,
            "days_back": DAYS_BACK,
            "sources": ["Indeed", "LinkedIn"],
        },
        "count":    len(formatted),
        "listings": formatted,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"✓ Done. {len(formatted)} listings written to {OUTPUT_PATH}")
    return payload


if __name__ == "__main__":
    run_scraper()
