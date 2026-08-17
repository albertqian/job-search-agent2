"""
job_scraper.py
Fetches product marketing jobs using JobSpy.
Searches Indeed, LinkedIn, and Glassdoor simultaneously.
No API key required.
"""

import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jobspy import scrape_jobs

OUTPUT_PATH = Path("data/job_results.json")
DAYS_BACK   = 14

SEARCHES = [
    "product marketing manager",
    "senior product marketing manager",
    "PMM",
]


def fetch_jobs(search_term: str) -> pd.DataFrame:
    print(f"[JobSpy] Searching: '{search_term}'")
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin", "glassdoor"],
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
    must_include = [
        "product marketing",
        "pmm",
        "product marketer",
    ]
    exclude = [
        "engineer", "developer", "software", "data",
        "designer", "devops", "backend", "frontend",
        "analyst", "recruiter", "sales", "finance",
        "customer success", "customer support",
    ]
    if not any(kw in title for kw in must_include):
        return False
    if any(kw in title for kw in exclude):
        return False
    return True


def format_job(row) -> dict:
    # Salary
    salary = None
    min_sal = row.get("min_amount")
    max_sal = row.get("max_amount")
    interval = row.get("interval", "")
    if min_sal and max_sal:
        salary = f"${int(min_sal):,} – ${int(max_sal):,} / {interval}"
    elif min_sal:
        salary = f"${int(min_sal):,}+ / {interval}"

    # Date
    date_posted = row.get("date_posted")
    if hasattr(date_posted, "strftime"):
        posted = date_posted.strftime("%b %d, %Y")
    else:
        posted = str(date_posted) if date_posted else ""

    return {
        "title":      str(row.get("title", "Unknown")),
        "company":    str(row.get("company", "")) or None,
        "salary":     salary,
        "location":   str(row.get("location", "Remote")),
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

    # Combine and deduplicate by job URL
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    print(f"\n[JobSpy] {len(combined)} unique jobs before title filter")

    # Filter by title relevance
    mask     = combined["title"].apply(lambda t: is_relevant(str(t)))
    relevant = combined[mask]
    print(f"[JobSpy] {len(relevant)} PMM-specific jobs after filter")

    # Format
    formatted = [format_job(row) for _, row in relevant.iterrows()]
    formatted.sort(key=lambda x: x.get("posted", ""), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "searches": SEARCHES,
            "days_back": DAYS_BACK,
            "sources": ["indeed", "linkedin", "glassdoor"],
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
