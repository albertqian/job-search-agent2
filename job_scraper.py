"""
job_scraper.py
Fetches PMM jobs via JobSpy, scores each against Albert's resume,
generates cover letters for 85+ matches, deduplicates across runs.
Only listings scoring 80+ are passed to the email.
"""

import json
import math
import os
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from jobspy import scrape_jobs

OUTPUT_PATH  = Path("data/job_results.json")
SEEN_PATH    = Path("data/seen_urls.json")
DAYS_BACK    = 14
MIN_SCORE    = 70   # only email listings at or above this score
COVER_LETTER_THRESHOLD = 75  # generate cover letter for these

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

RESUME = """
Albert Qian — SaaS Product Marketer & Content Strategist

SUMMARY
Product Marketing Alliance certified PMM with background bringing software solutions
to market through product launches, top/middle/bottom of funnel content marketing,
and demand generation. Experience across Fortune 500 companies, channel partners,
and post series A startups.

SKILLS
Product Marketing: Messaging & Positioning, Product Launches, Data Sheets, Battle Cards,
Competitive Intelligence, Product Pages
Content Marketing: SEO, Content Strategy, Copywriting, Blogging, Newsletters, Web Copy
Platforms: Salesforce, Pardot, HubSpot, Oracle Content Marketing, Google Analytics
AI Tools: ChatGPT, Claude, Vizard, OpusClip, GitHub

EXPERIENCE
Product Marketing Manager — SAS (2022–Present, Remote)
- Led product marketing for Microsoft Strategic Partnership, Snowflake Partnership,
  and Intelligent Decisioning solution
- Supported Gartner Magic Quadrant Leader placement in Decision Intelligence
- Launched SAS Viya Copilot; drove $500K in MQLs for Azure Confidential Computing
- Led win/loss analysis, webinars with Deloitte (150–200 attendees), 20+ blog posts

Content Marketing Manager, HCM — Oracle (2019–2022)
- Led Oracle Cloud HCM blog: 500K+ page views, 300K+ unique visitors over 36 months
- Co-led HR Matters newsletter to 5,000+ HR executives; drove $275K in MQLs
- Increased blog clickthrough 6% to 10%

Product Marketing Manager — Cloud Academy (2018–2019)
- Led B2B Enterprise transition; generated $300K initial revenue
- Improved email clickthrough 50%+ MoM

Partner/Product Marketing Manager — Perficient (2011–2018)
- Led GTM for IBM Cloud, AWS, Dell Boomi, CloudBees, Liferay partnerships
- Enabled $10M+ opportunity pipeline; 300+ blogs, 15+ authors

Global Content/Product Marketing Manager — Ingram Micro
- Improved reseller adoption 62%

Various Marketing Roles — Cisco, HP Enterprise

OTHER
Founder — Albert's List LLC (2013–Present): 50,700+ member job seeker community,
$20M+ economic activity, 150+ webinars, 15,000+ email subscribers

EDUCATION
BS Commerce, Santa Clara University — Operations Management / MIS

CERTIFICATIONS
Product Marketing Alliance — Product Marketing Certified Core (2022)
Google — Fundamentals of Digital Marketing (2019)

LANGUAGES: Mandarin Chinese (Native), Spanish (Intermediate)
"""


# ── Seen URLs (deduplication) ─────────────────────────────────────────────────

def load_seen_urls() -> set:
    if SEEN_PATH.exists():
        with open(SEEN_PATH) as f:
            return set(json.load(f))
    return set()


def save_seen_urls(seen: set):
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PATH, "w") as f:
        json.dump(list(seen), f, indent=2)


# ── Claude API calls ──────────────────────────────────────────────────────────

def call_claude(prompt: str, max_tokens: int = 150) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"[Claude] API error: {e}")
        return ""


def score_job_match(job_title: str, company: str, description: str = "") -> dict:
    prompt = f"""You are evaluating job fit for a product marketing professional.

CANDIDATE RESUME:
{RESUME}

JOB TO EVALUATE:
Title: {job_title}
Company: {company or 'Unknown'}
{f'Description: {description[:500]}' if description else ''}

Score this job's fit on a scale of 0-100:
- 90-100: Excellent fit — matches seniority, industry, and skills closely
- 70-89: Good fit — strong overlap with minor gaps
- 50-69: Moderate fit — relevant but notable mismatches
- Below 50: Poor fit — significant gaps

Respond ONLY with valid JSON, nothing else:
{{"score": 85, "reason": "Strong SaaS PMM background matches; enterprise B2B focus aligns well"}}"""

    text = call_claude(prompt, max_tokens=120)
    try:
        result = json.loads(text)
        return {
            "score":  int(result.get("score", 0)),
            "reason": str(result.get("reason", "")),
        }
    except Exception:
        return {"score": None, "reason": "Scoring unavailable"}


def generate_cover_letter(job_title: str, company: str, description: str = "") -> str:
    prompt = f"""Write a concise, professional cover letter for this job application.

CANDIDATE RESUME:
{RESUME}

JOB:
Title: {job_title}
Company: {company or 'the company'}
{f'Description: {description[:600]}' if description else ''}

Instructions:
- 3 short paragraphs maximum
- Opening: why this role and company specifically
- Middle: 2-3 most relevant achievements from the resume, with metrics
- Closing: confident call to action
- Tone: professional but not stiff — warm and direct
- Do NOT include subject line, date, or address headers
- Start directly with "Dear Hiring Team," or personalized if company name known

Write the cover letter now:"""

    return call_claude(prompt, max_tokens=500)


# ── Job fetching and processing ───────────────────────────────────────────────

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
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return int(val)
    except (ValueError, TypeError):
        return None


def clean_str(val) -> str | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    return s if s else None


def format_job(row) -> dict:
    min_sal  = safe_int(row.get("min_amount"))
    max_sal  = safe_int(row.get("max_amount"))
    interval = clean_str(row.get("interval")) or ""

    if min_sal and max_sal:
        salary = f"${min_sal:,} – ${max_sal:,} / {interval}".strip(" /")
    elif min_sal:
        salary = f"${min_sal:,}+ / {interval}".strip(" /")
    else:
        salary = None

    date_posted = row.get("date_posted")
    if hasattr(date_posted, "strftime"):
        posted = date_posted.strftime("%b %d, %Y")
    elif date_posted and not (isinstance(date_posted, float) and math.isnan(date_posted)):
        posted = str(date_posted)
    else:
        posted = ""

    return {
        "title":        clean_str(row.get("title")) or "Unknown",
        "company":      clean_str(row.get("company")),
        "salary":       salary,
        "location":     clean_str(row.get("location")) or "Remote",
        "source":       clean_str(row.get("site", "")).title(),
        "url":          clean_str(row.get("job_url")) or "",
        "posted":       posted,
        "description":  (clean_str(row.get("description")) or "")[:400],
        "match_score":  None,
        "match_reason": None,
        "cover_letter": None,
        "scraped_at":   datetime.now().isoformat(),
    }


# ── Daily summary ─────────────────────────────────────────────────────────────

def generate_summary(listings: list[dict]) -> str:
    if not listings:
        return ""

    top = listings[:3]
    top_text = "\n".join([
        f"- {l['title']} at {l.get('company') or 'Unknown'} "
        f"(score: {l.get('match_score')}%, {l.get('match_reason', '')})"
        for l in top
    ])

    prompt = f"""Write a 2-3 sentence briefing for a job seeker reviewing today's PMM job matches.

Today's top matches:
{top_text}

Total listings found: {len(listings)}

Be direct and specific. Mention the strongest match by name and why it stands out.
Reference the candidate's SaaS enterprise PMM background where relevant.
Do not use bullet points. Write in second person ("Your strongest match today is...").
Keep it under 60 words."""

    return call_claude(prompt, max_tokens=150)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_scraper():
    seen_urls = load_seen_urls()
    print(f"[Dedup] {len(seen_urls)} URLs already seen from previous runs")

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
            "summary": "",
            "count": 0,
            "listings": [],
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # Deduplicate by URL within this run
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    print(f"[JobSpy] {len(combined)} unique jobs before filters")

    # Filter by title relevance
    mask     = combined["title"].apply(lambda t: is_relevant(str(t)))
    relevant = combined[mask]
    print(f"[JobSpy] {len(relevant)} PMM-specific jobs after title filter")

    # Filter out already-seen URLs
    new_only = relevant[~relevant["job_url"].isin(seen_urls)]
    print(f"[Dedup] {len(new_only)} new listings (not seen in previous runs)")

    # Format
    formatted = [format_job(row) for _, row in new_only.iterrows()]

    # Score each listing
    print(f"\n[Score] Scoring {len(formatted)} listings...")
    for i, job in enumerate(formatted):
        print(f"[Score] {i+1}/{len(formatted)}: {job['title']} @ {job.get('company') or 'Unknown'}")
        result = score_job_match(
            job_title=job["title"],
            company=job.get("company") or "",
            description=job.get("description") or "",
        )
        job["match_score"]  = result["score"]
        job["match_reason"] = result["reason"]
        time.sleep(0.3)

    # Filter to 80+ only
    qualified = [j for j in formatted if (j.get("match_score") or 0) >= MIN_SCORE]
    print(f"[Score] {len(qualified)} listings scored {MIN_SCORE}+")

    # Generate cover letters for 85+
    for job in qualified:
        if (job.get("match_score") or 0) >= COVER_LETTER_THRESHOLD:
            print(f"[CoverLetter] Generating for: {job['title']} @ {job.get('company') or 'Unknown'}")
            job["cover_letter"] = generate_cover_letter(
                job_title=job["title"],
                company=job.get("company") or "",
                description=job.get("description") or "",
            )
            time.sleep(0.3)

    # Sort by score descending
    qualified.sort(key=lambda x: (x.get("match_score") or 0), reverse=True)

    # Generate top summary
    print("\n[Summary] Generating daily briefing...")
    summary = generate_summary(qualified)

    # Update seen URLs with ALL scored listings (not just qualified)
    # so we don't re-score low matches on future runs either
    new_seen = {j["url"] for j in formatted if j.get("url")}
    seen_urls.update(new_seen)
    save_seen_urls(seen_urls)
    print(f"[Dedup] Saved {len(seen_urls)} total seen URLs")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "params": {
            "searches":  SEARCHES,
            "days_back": DAYS_BACK,
            "min_score": MIN_SCORE,
            "sources":   ["Indeed", "LinkedIn"],
        },
        "summary":  summary,
        "count":    len(qualified),
        "listings": qualified,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"✓ Done. {len(qualified)} qualified listings written to {OUTPUT_PATH}")
    return payload


if __name__ == "__main__":
    run_scraper()
