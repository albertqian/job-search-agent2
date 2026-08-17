# PMM Job Leads Agent

A GitHub Actions agent that automatically scrapes remote **Product Marketing Manager** job listings from Indeed and LinkedIn every weekday morning and delivers them to your inbox as a formatted HTML email.

No API keys. No servers. No dashboards to check. Just leads in your inbox at 9 AM.

---

## What it does

- Searches for `product marketing manager`, `senior product marketing manager`, and `PMM` roles
- Pulls from **Indeed** and **LinkedIn** simultaneously using JobSpy
- Filters to listings posted in the **last 14 days** only
- Applies a tight title filter to remove irrelevant results (engineers, analysts, recruiters, etc.)
- Sends a clean HTML email with title, company, salary, location, source, and a direct link to each listing

---

## Email preview

Each morning email includes:

- **Header** — total listings, how many include salary, how many include company name
- **Listings table** — one row per job with Title, Company, Salary, Location, Posted date, Source, and a View link
- **Footer** — timestamp and source attribution

---

## File structure

```
job-search-agent/
├── job_scraper.py          # Fetches and filters job listings via JobSpy
├── send_email.py           # Builds and sends the HTML email via Gmail SMTP
├── requirements.txt        # Python dependencies
├── data/
│   └── job_results.json    # Temporary results file (written at runtime)
└── .github/
    └── workflows/
        └── job_leads.yml   # GitHub Actions workflow
```

---

## Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/job-search-agent.git
cd job-search-agent
```

### 2. Create a Gmail App Password

The agent sends email via Gmail SMTP. You need an App Password — not your regular Gmail password.

1. Go to [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Enable **2-Step Verification** if not already on
3. Search for **App passwords**
4. Select app: **Mail**, device: **Other** → name it `job-leads-bot`
5. Copy the 16-character password

### 3. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret name | Value |
|---|---|
| `GMAIL_ADDRESS` | `your.email@gmail.com` |
| `GMAIL_APP_PASS` | 16-character App Password (no spaces) |
| `TO_ADDRESS` | Email address to send leads to |

No PAT or API key required.

### 4. Trigger your first run

Go to **Actions → Job Leads — Daily Email → Run workflow**

Check your inbox 2–3 minutes later.

---

## Schedule

Runs automatically at **9 AM Pacific Time, Monday–Friday** (`0 16 * * 1-5` UTC).

To change the time, edit the `cron` line in `.github/workflows/job_leads.yml`.

---

## Customization

All key settings are at the top of `job_scraper.py`:

### Change search terms
```python
SEARCHES = [
    "product marketing manager",
    "senior product marketing manager",
    "PMM",
]
```

### Change date window
```python
DAYS_BACK = 14  # only return jobs posted within this many days
```

### Add or remove title filters
```python
TITLE_MUST_INCLUDE = [
    "product marketing",
    "pmm",
    "product marketer",
]

TITLE_EXCLUDE = [
    "engineer", "developer", "analyst", "recruiter", ...
]
```

### Change job sources
```python
site_name=["indeed", "linkedin"]  # options: indeed, linkedin, zip_recruiter
```

> **Note:** Glassdoor is excluded — it returns 403 errors from GitHub Actions IP ranges.

---

## Dependencies

| Package | Purpose |
|---|---|
| `python-jobspy` | Scrapes Indeed and LinkedIn for job listings |
| `pandas` | Data processing and deduplication |

No browser, no Playwright, no API keys.

---

## Known limitations

| Issue | Detail |
|---|---|
| **Salary missing on many listings** | Indeed and LinkedIn don't require salary disclosure. Expect ~30–40% of listings to include it. |
| **LinkedIn rate limits** | LinkedIn may throttle requests if the agent runs too frequently. Daily runs are fine. |
| **Glassdoor blocked** | GitHub Actions IPs are blocked by Glassdoor. Not included. |
| **PMM listings vary daily** | Some days will return more leads than others depending on posting activity. |

---

## Workshop discussion points

1. **GitHub Actions as a scheduler** — why this works and where it breaks down vs. a dedicated cron service
2. **JobSpy as an aggregator** — how it works under the hood (scraping + structured extraction)
3. **Email as an output** — when email beats a dashboard (passive delivery vs. active checking)
4. **Filter design** — title inclusion/exclusion lists vs. LLM-based relevance scoring
5. **Upgrade path** — add resume parsing + LLM scoring to rank listings by fit before sending
