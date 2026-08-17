"""
send_email.py
Reads data/job_results.json and sends a formatted HTML email via Gmail SMTP.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

GMAIL_ADDRESS  = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
TO_ADDRESS     = os.environ.get("TO_ADDRESS", os.environ["GMAIL_ADDRESS"])
DATA_PATH      = Path("data/job_results.json")


def build_email(data: dict) -> tuple[str, str]:
    listings     = data.get("listings", [])
    count        = data.get("count", 0)
    timestamp    = datetime.now().strftime("%A, %B %-d · %-I:%M %p")
    with_salary  = sum(1 for l in listings if l.get("salary"))
    with_company = sum(1 for l in listings if l.get("company"))

    subject = f"💼 {count} PMM Job Leads · San Francisco · {datetime.now().strftime('%b %-d')}"

    if not listings:
        rows_html = """
        <tr>
          <td colspan="5" style="padding:32px;text-align:center;color:#6b7280;font-size:14px;">
            No listings found for this run.
          </td>
        </tr>
        """
    else:
        rows = []
        for l in listings:
            title   = l.get("title", "Unknown")
            company = l.get("company") or "<span style='color:#9ca3af'>—</span>"
            salary  = l.get("salary")  or "<span style='color:#9ca3af'>—</span>"
            posted  = l.get("posted")  or "—"
            url     = l.get("url", "")
            link    = f'<a href="{url}" style="color:#1a1a2e;font-weight:600;text-decoration:none;">View →</a>' if url else "—"

            rows.append(f"""
            <tr style="border-bottom:1px solid #f3f4f6;">
              <td style="padding:12px 8px;font-size:14px;font-weight:600;color:#1a1a2e;">{title}</td>
              <td style="padding:12px 8px;font-size:13px;color:#4b5563;">{company}</td>
              <td style="padding:12px 8px;font-size:13px;color:#065f46;font-weight:500;">{salary}</td>
              <td style="padding:12px 8px;font-size:13px;color:#6b7280;">{posted}</td>
              <td style="padding:12px 8px;font-size:13px;">{link}</td>
            </tr>
            """)
        rows_html = "\n".join(rows)

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0;">
    <tr><td align="center">
      <table width="680" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">

        <tr>
          <td style="background:#1a1a2e;padding:28px 32px;">
            <p style="margin:0;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.02em;">💼 PMM Job Leads</p>
            <p style="margin:6px 0 0;font-size:13px;color:#9ca3af;">San Francisco Bay Area · {timestamp}</p>
          </td>
        </tr>

        <tr>
          <td style="padding:24px 32px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:40px;">
                  <p style="margin:0;font-size:32px;font-weight:700;color:#1a1a2e;">{count}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Total Listings</p>
                </td>
                <td style="padding-right:40px;">
                  <p style="margin:0;font-size:32px;font-weight:700;color:#065f46;">{with_salary}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">With Salary</p>
                </td>
                <td>
                  <p style="margin:0;font-size:32px;font-weight:700;color:#1a1a2e;">{with_company}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">With Company</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:0 32px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <thead>
                <tr style="background:#f9fafb;">
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Title</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Company</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Salary</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Posted</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Link</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:20px 32px;border-top:1px solid #f3f4f6;background:#f9fafb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              Sent by your Job Leads agent · Craigslist SF Bay Area · Weekdays at 9 AM Pacific
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
    """
    return subject, html


def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = TO_ADDRESS
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
        server.sendmail(GMAIL_ADDRESS, TO_ADDRESS, msg.as_string())

    print(f"✓ Email sent to {TO_ADDRESS}")


if __name__ == "__main__":
    if not DATA_PATH.exists():
        print(f"No data file at {DATA_PATH}. Run job_scraper.py first.")
        exit(1)

    with open(DATA_PATH) as f:
        data = json.load(f)

    subject, html = build_email(data)
    send_email(subject, html)
