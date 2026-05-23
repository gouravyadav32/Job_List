import feedparser
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
TO_EMAIL     = os.environ["GMAIL_USER"]

# ── JOB SEARCH QUERIES ────────────────────────────────────────────────────────
# Customize: add/remove dicts. location="" means remote/anywhere.
SEARCHES = [
    {"title": "Data Engineer",        "keywords": "data engineer",           "location": "remote"},
    {"title": "Databricks Engineer",  "keywords": "databricks spark",        "location": "remote"},
    {"title": "Azure Data Engineer",  "keywords": "azure data factory spark","location": "remote"},
]

HOURS_BACK = 24   # only show jobs posted in the last N hours

# ── RSS FEED BUILDERS ─────────────────────────────────────────────────────────
def indeed_rss(keywords, location):
    q = quote_plus(keywords)
    l = quote_plus(location)
    return f"https://www.indeed.com/rss?q={q}&l={l}&sort=date&fromage=1"

def linkedin_rss(keywords):
    q = quote_plus(keywords)
    # LinkedIn's public job RSS (no auth needed)
    return f"https://www.linkedin.com/jobs/search/?keywords={q}&f_TPR=r86400&format=rss"

# ── FETCH & FILTER ────────────────────────────────────────────────────────────
def fetch_jobs(search):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    jobs   = []

    feeds = [
        ("Indeed",   indeed_rss(search["keywords"], search["location"])),
    ]

    for source, url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:           # cap per feed
                published = entry.get("published_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                jobs.append({
                    "title":     entry.get("title", "No title"),
                    "company":   entry.get("author", ""),
                    "link":      entry.get("link",  ""),
                    "source":    source,
                    "published": entry.get("published", ""),
                    "summary":   entry.get("summary", "")[:300],
                })
        except Exception as e:
            print(f"[WARN] {source} feed failed for '{search['keywords']}': {e}")

    return jobs

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
              <div style="color:#555;font-size:13px;margin:4px 0;">{j['company']} &nbsp;·&nbsp; <span style="color:#16a34a;">{j['source']}</span> &nbsp;·&nbsp; {j['published']}</div>
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

if __name__ == "__main__":
    main()
