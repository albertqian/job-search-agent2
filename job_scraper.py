"""
job_scraper.py
Fetches product marketing jobs from RemoteOK's public API.
Tightly filtered to PMM-specific roles only.
"""

import json
import requests
from datetime import datetime
from pathlib import Path

HEADERS = {
    "User-Agent": "job-leads-agent/1.0 (personal job search tool)",
}

OUTPUT_PATH = Path("data/job_results.json")

# Hit the most specific tags RemoteOK supports
TAGS = [
    "product-marketing",
    "marketing-manager",
    "marketing",
]

# ALL of these: title must contain at least one to pass
TITLE_MUST_INCLUDE = [
    "product marketing",
    "pmm",
    "product marketer",
]

# If title contains any of these, reject it outright
TITLE_EXCLUDE = [
    "engineer",
    "developer",
    "software",
    "data",
    "designer",
    "devops",
    "backend",
    "frontend",
    "fullstack",
    "full stack",
    "qa ",
    "analyst",
    "recruiter",
    "sales",
    "accountant",
    "finance",
    "legal",
    "customer success",
    "customer support",
]


def fetch_remoteok(tag: str) -> list[dict]:
    url = f"https://remoteok.com/api?tag={tag}"
    print(f"[RemoteOK] Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        jobs = [j for j in data if isinstance(j, dict) and j.get("id")]
        print(f"[RemoteOK] {len(jobs)} raw jobs for tag '{tag}'")
        return jobs
    except Exception as e:
        print(f"[RemoteOK] Failed for tag '{tag}': {e}")
        return []


def is_relevant(job: dict) -> bool:
    title = job.get("position", "").lower()

    # Must contain at least one PMM keyword in the title
    if not any(kw in title for kw in TITLE_MUST_INCLUDE):
        return False

    # Must not contain any exclusion keywords
    if any(kw in title for kw in TITLE_EXCLUDE):
        return False

    return True


def format_job(job: dict) -> dict:
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    if salary_min and salary_max:
        salary = f"${salary_min:,} – ${salary_max:,} / yr"
    elif salary_min:
        salary = f"${salary_min:,}+ / yr"
    else:
        salary = None

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

    print(f"\n[RemoteOK] {len(deduped)} unique jobs before filtering")

    # Tight filter
    relevant = [j for j in deduped if is_relevant(j)]
    print(f"[RemoteOK] {len(relevant)} PMM-specific jobs after filtering")

    # Format and sort newest first
    formatted = [format_job(j) for j in relevant]
    formatted.sort(key=lambda x: x.get("posted", ""), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "source":   "RemoteOK",
            "tags":     TAGS,
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
