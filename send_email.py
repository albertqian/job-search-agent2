"""
send_email.py
Reads data/job_results.json and sends a formatted HTML email via Gmail SMTP.
Includes daily summary, color-coded match scores, and cover letter drafts.
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


def score_badge(score) -> str:
    if score is None:
        return "<span style='color:#9ca3af;font-size:12px;'>—</span>"
    if score >= 80:
        bg, color = "#dcfce7", "#166534"
    elif score >= 60:
        bg, color = "#fef9c3", "#854d0e"
    else:
        bg, color = "#fee2e2", "#991b1b"
    return (
        f'<span style="background:{bg};color:{color};padding:3px 8px;'
        f'border-radius:12px;font-size:12px;font-weight:700;">{score}%</span>'
    )


def cover_letter_block(cover_letter: str, job_title: str, company: str) -> str:
    if not cover_letter:
        return ""
    # Escape any HTML in the cover letter text
    safe = cover_letter.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe.replace("\n", "<br>")
    return f"""
    <tr>
      <td colspan="7" style="padding:0 16px 16px;">
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px 20px;">
          <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#64748b;
             text-transform:uppercase;letter-spacing:0.06em;">
             ✉️ Draft Cover Letter — {job_title} at {company or 'the company'}
          </p>
          <p style="margin:0;font-size:13px;color:#374151;line-height:1.6;">{safe}</p>
          <p style="margin:10px 0 0;font-size:11px;color:#9ca3af;font-style:italic;">
            Review and personalize before sending.
          </p>
        </div>
      </td>
    </tr>
    """


def build_email(data: dict) -> tuple[str, str]:
    listings     = data.get("listings", [])
    count        = data.get("count", 0)
    summary      = data.get("summary", "")
    timestamp    = datetime.now().strftime("%A, %B %-d · %-I:%M %p")
    with_salary  = sum(1 for l in listings if l.get("salary"))
    with_cl      = sum(1 for l in listings if l.get("cover_letter"))
    scored       = [l for l in listings if l.get("match_score") is not None]
    avg_score    = int(sum(l["match_score"] for l in scored) / len(scored)) if scored else 0

    subject = f"💼 {count} PMM Matches (80%+) · Avg {avg_score}% · {datetime.now().strftime('%b %-d')}"

    if not listings:
        rows_html = """
        <tr>
          <td colspan="7" style="padding:32px;text-align:center;color:#6b7280;font-size:14px;">
            No listings scored 80% or higher today. Check back tomorrow.
          </td>
        </tr>
        """
    else:
        rows = []
        for l in listings:
            title        = l.get("title", "Unknown")
            company      = l.get("company") or "—"
            salary       = l.get("salary")  or "<span style='color:#9ca3af'>—</span>"
            posted       = l.get("posted")  or "—"
            source       = l.get("source")  or "—"
            reason       = l.get("match_reason") or ""
            url          = l.get("url", "")
            cover_letter = l.get("cover_letter")
            badge        = score_badge(l.get("match_score"))
            link         = f'<a href="{url}" style="color:#1a1a2e;font-weight:600;text-decoration:none;">View →</a>' if url else "—"
            cl_block     = cover_letter_block(cover_letter, title, company)

            rows.append(f"""
            <tr style="border-bottom:{'none' if cl_block else '1px solid #f3f4f6'};">
              <td style="padding:12px 8px;font-size:14px;font-weight:600;color:#1a1a2e;min-width:160px;">{title}</td>
              <td style="padding:12px 8px;font-size:13px;color:#4b5563;">{company}</td>
              <td style="padding:12px 8px;font-size:13px;color:#065f46;font-weight:500;white-space:nowrap;">{salary}</td>
              <td style="padding:12px 8px;text-align:center;">
                {badge}
                <br><span style="font-size:11px;color:#9ca3af;display:block;margin-top:4px;max-width:140px;">{reason}</span>
              </td>
              <td style="padding:12px 8px;font-size:13px;color:#6b7280;white-space:nowrap;">{posted}</td>
              <td style="padding:12px 8px;font-size:12px;color:#9ca3af;">{source}</td>
              <td style="padding:12px 8px;font-size:13px;">{link}</td>
            </tr>
            {cl_block}
            {'<tr><td colspan="7" style="border-bottom:1px solid #f3f4f6;padding:0;"></td></tr>' if cl_block else ''}
            """)
        rows_html = "\n".join(rows)

    # Summary block
    summary_block = ""
    if summary:
        summary_block = f"""
        <tr>
          <td style="padding:0 32px 20px;">
            <div style="background:#f0f9ff;border-left:3px solid #0ea5e9;
                        border-radius:0 8px 8px 0;padding:14px 18px;">
              <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#0369a1;
                 text-transform:uppercase;letter-spacing:0.06em;">Today's Briefing</p>
              <p style="margin:0;font-size:14px;color:#1e3a5f;line-height:1.6;">{summary}</p>
            </div>
          </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0;">
    <tr><td align="center">
      <table width="860" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">

        <!-- Header -->
        <tr>
          <td style="background:#1a1a2e;padding:28px 32px;">
            <p style="margin:0;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.02em;">💼 PMM Job Leads</p>
            <p style="margin:6px 0 0;font-size:13px;color:#9ca3af;">Remote · Indeed + LinkedIn · {timestamp}</p>
          </td>
        </tr>

        <!-- Stats -->
        <tr>
          <td style="padding:24px 32px 16px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:40px;">
                  <p style="margin:0;font-size:32px;font-weight:700;color:#1a1a2e;">{count}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">80%+ Matches</p>
                </td>
                <td style="padding-right:40px;">
                  <p style="margin:0;font-size:32px;font-weight:700;color:#166534;">{avg_score}%</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Avg Score</p>
                </td>
                <td style="padding-right:40px;">
                  <p style="margin:0;font-size:32px;font-weight:700;color:#065f46;">{with_salary}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">With Salary</p>
                </td>
                <td>
                  <p style="margin:0;font-size:32px;font-weight:700;color:#1a1a2e;">{with_cl}</p>
                  <p style="margin:2px 0 0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Cover Letters</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Legend -->
        <tr>
          <td style="padding:0 32px 16px;">
            <span style="font-size:11px;color:#9ca3af;">Match: </span>
            <span style="background:#dcfce7;color:#166534;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:700;">80–100% Excellent</span>&nbsp;
            <span style="background:#fef9c3;color:#854d0e;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:700;">60–79% Good</span>
            <span style="margin-left:12px;font-size:11px;color:#9ca3af;">✉️ = cover letter draft included below listing</span>
          </td>
        </tr>

        <!-- Summary briefing -->
        {summary_block}

        <!-- Listings table -->
        <tr>
          <td style="padding:0 32px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <thead>
                <tr style="background:#f9fafb;">
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Title</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Company</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Salary</th>
                  <th style="padding:10px 8px;text-align:center;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Match</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Posted</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Source</th>
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Link</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;border-top:1px solid #f3f4f6;background:#f9fafb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              Sent by your Job Leads agent · Only 80%+ matches shown · Cover letters generated for 85%+ matches · Weekdays at 9 AM Pacific
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
