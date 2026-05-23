import jobspy
import pandas as pd
import smtplib
import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

# ── CONFIG (set these as GitHub Secrets) ──────────────────────────────────────
GMAIL_USER   = os.environ["GMAIL_USER"]          # your@gmail.com
GMAIL_PASS   = os.environ["GMAIL_APP_PASS"]      # Gmail App Password (not real password)
TO_EMAIL     = os.environ["TO_GMAIL"]

# ── JOB SEARCH QUERIES ────────────────────────────────────────────────────────
# Customize: add/remove dicts. location="" means remote/anywhere.

# Combined keywords to cover the 14 requested Transformation & Change roles
TRANSFORMATION_KEYWORDS = (
    '"Business Transformation" OR "Transformation Lead" OR "Transformation Director" OR '
    '"Change Management" OR "Strategic Initiatives" OR "Digital Transformation" OR '
    '"Agile Transformation" OR "Chief Transformation Officer" OR "Enterprise Transformation"'
)

SEARCHES = [
    {"title": "Transformation Roles (India)",        "keywords": TRANSFORMATION_KEYWORDS, "location": "India",       "country": "india"},
    {"title": "Transformation Roles (Middle East)",  "keywords": TRANSFORMATION_KEYWORDS, "location": "Middle East", "country": "ae"},
    {"title": "Transformation Roles (Remote)",       "keywords": TRANSFORMATION_KEYWORDS, "location": "remote",      "country": "usa"},
]

HOURS_BACK = 24   # only show jobs posted in the last N hours

# ── FETCH & FILTER ────────────────────────────────────────────────────────────
def fetch_jobs(search):
    jobs_list = []
    
    try:
        loc = search.get("location")
        is_remote = False
        if loc and loc.lower() == "remote":
            is_remote = True
            loc = None
            
        # JobSpy automatically handles bypassing bot protection for Indeed, LinkedIn, etc.
        jobs_df = jobspy.scrape_jobs(
            site_name=["indeed", "linkedin", "glassdoor"],
            search_term=search["keywords"],
            location=loc,
            is_remote=is_remote,
            results_wanted=15,
            hours_old=HOURS_BACK,
            country_indeed=search.get('country', 'usa')
        )
    except Exception as e:
        print(f"[WARN] JobSpy failed for '{search['keywords']}': {e}")
        return []

    if jobs_df is None or jobs_df.empty:
        return []

    # Process dataframe into the list format expected by the email template
    for _, row in jobs_df.iterrows():
        # Clean up publication date
        published = row.get("date_posted", "")
        if pd.notnull(published):
            published = str(published).split()[0]
        else:
            published = "Recent"

        # Clean up summary/description
        desc = row.get("description", "")
        if pd.notnull(desc):
            summary = str(desc).replace('\n', ' ')[:300]
        else:
            summary = "No description provided."

        loc_str = str(row.get("location", ""))
        if loc_str == "nan" or not loc_str:
            loc_str = "Remote" if search.get("location", "").lower() == "remote" else "Location unknown"

        jobs_list.append({
            "title": str(row.get("title", "No title")),
            "company": str(row.get("company", "Unknown")),
            "location": loc_str,
            "link": str(row.get("job_url", "")),
            "source": str(row.get("site", "Unknown")).capitalize(),
            "published": published,
            "summary": summary
        })
        
    return jobs_list

# ── EMAIL BUILDER ─────────────────────────────────────────────────────────────
def build_html(all_results):
    today = datetime.now().strftime("%B %d, %Y")
    sections = ""

    for search, jobs in all_results.items():
        if not jobs:
            block = f"<p style='color:#888;font-style:italic;'>No new listings in the last {HOURS_BACK}h.</p>"
        else:
            cards = ""
            for j in jobs:
                cards += f"""
            <div style="border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin-bottom:10px;background:#fff;">
              <a href="{j['link']}" style="font-size:16px;font-weight:600;color:#1a56db;text-decoration:none;">{j['title']}</a>
              <div style="color:#555;font-size:13px;margin:4px 0;">{j['company']} &nbsp;·&nbsp; {j['location']} &nbsp;·&nbsp; <span style="color:#16a34a;">{j['source']}</span> &nbsp;·&nbsp; {j['published']}</div>
              <div style="color:#444;font-size:13px;margin-top:6px;">{j['summary']}…</div>
            </div>"""
        block = cards if jobs else block
        sections += f"""
      <h2 style="font-size:18px;margin:28px 0 10px;color:#1e293b;">🔍 {search} <span style="font-size:13px;color:#64748b;font-weight:normal;">({len(jobs)} new)</span></h2>
      {block}"""

    total = sum(len(j) for j in all_results.values())
    return f"""
<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:0;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">
  <div style="background:linear-gradient(135deg,#1a56db,#0ea5e9);border-radius:12px;padding:24px;color:#fff;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">📋 Daily Job Alert</h1>
    <p style="margin:6px 0 0;opacity:.85;">{today} &nbsp;·&nbsp; {total} new listings found</p>
  </div>
  {sections}
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:32px;">
    Powered by GitHub Actions + feedparser · Runs daily at 8 AM UTC
  </p>
</div>
</body></html>"""

# ── SEND EMAIL ────────────────────────────────────────────────────────────────
def send_email(html_body, total_jobs):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Daily Job Alert — {total_jobs} new listings ({datetime.now().strftime('%b %d')})"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print(f"✅ Email sent to {TO_EMAIL} with {total_jobs} jobs.")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    all_results = {}
    for search in SEARCHES:
        print(f"Fetching: {search['title']}...")
        jobs = fetch_jobs(search)
        all_results[search["title"]] = jobs
        print(f"  → {len(jobs)} jobs found")

    total = sum(len(j) for j in all_results.values())
    html  = build_html(all_results)
    send_email(html, total)

    # Save job data for downstream workflow jobs (resume optimizer)
    with open("jobs_data.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"📄 Saved jobs_data.json ({total} jobs) for resume optimizer.")

if __name__ == "__main__":
    main()
