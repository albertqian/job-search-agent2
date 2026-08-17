"""
job_scraper.py
Fetches product marketing jobs from RemoteOK's public API.
No scraping, no API key, no blocking.
Writes results to data/job_results.json for send_email.py to consume.
"""

import json
import requests
from datetime import datetime
from pathlib import Path

HEADERS = {
    "User-Agent": "job-leads-agent/1.0 (personal job search tool)",
}

OUTPUT_PATH = Path("data/job_results.json")

# RemoteOK API tags to search — fetches each and merges
TAGS = [
    "marketing",
    "product",
    "manager",
]

KEYWORDS = [
    "product marketing",
    "pmm",
    "product manager",
    "go to market",
    "gtm",
    "growth marketing",
    "content marketing manager",
]


def fetch_remoteok(tag: str) -> list[dict]:
    """Fetch jobs from RemoteOK API for a given tag."""
    url = f"https://remoteok.com/api?tag={tag}"
    print(f"[RemoteOK] Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        # First item is always a legal notice dict, skip it
        jobs = [j for j in data if isinstance(j, dict) and j.get("id")]
        print(f"[RemoteOK] Found {len(jobs)} jobs for tag '{tag}'")
        return jobs
    except Exception as e:
        print(f"[RemoteOK] Failed for tag '{tag}': {e}")
        return []


def is_relevant(job: dict) -> bool:
    """Filter jobs to product marketing relevant roles."""
    title = job.get("position", "").lower()
    tags  = " ".join(job.get("tags", [])).lower()
    text  = title + " " + tags

    return any(kw in text for kw in KEYWORDS)


def format_job(job: dict) -> dict:
    """Normalize a RemoteOK job into our standard schema."""
    # Salary: RemoteOK provides min/max as integers
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    if salary_min and salary_max:
        salary = f"${salary_min:,} – ${salary_max:,} / yr"
    elif salary_min:
        salary = f"${salary_min:,}+ / yr"
    else:
        salary = None

    # Date
    epoch = job.get("epoch")
    posted = (
        datetime.utcfromtimestamp(epoch).strftime("%b %d, %Y")
        if epoch else ""
    )

    return {
        "title":      job.get("position", "Unknown"),
        "company":    job.get("company", None),
        "salary":     salary,
        "location":   "Remote",
        "url":        job.get("url", f"https://remoteok.com/l/{job.get('id', '')}"),
        "posted":     posted,
        "tags":       ", ".join(job.get("tags", [])[:5]),
        "scraped_at": datetime.now().isoformat(),
    }


def run_scraper():
    all_jobs = []

    for tag in TAGS:
        jobs = fetch_remoteok(tag)
        all_jobs.extend(jobs)

    # Deduplicate by job ID
    seen = set()
    deduped = []
    for job in all_jobs:
        job_id = job.get("id")
        if job_id and job_id not in seen:
            seen.add(job_id)
            deduped.append(job)

    # Filter to relevant roles only
    relevant = [j for j in deduped if is_relevant(j)]
    print(f"\n[RemoteOK] {len(relevant)} relevant jobs after filtering")

    # Format and sort newest first
    formatted = [format_job(j) for j in relevant]
    formatted.sort(key=lambda x: x.get("posted", ""), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "source":   "RemoteOK",
            "tags":     TAGS,
            "keywords": KEYWORDS,
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
