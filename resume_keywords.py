"""
Resume Keyword Optimizer — powered by GitHub Models (free tier).

Reads jobs_data.json produced by job_alert.py, compares each job description
against YOUR RESUME (passed via RESUME_TEMPLATE env var / GitHub Secret), and
emails you per-job ATS keyword gaps + tailored bullet points.

Uses the built-in GITHUB_TOKEN — no external API keys required!
"""

import json
import os
import smtplib
import time
import re
import urllib.request
import urllib.error
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASS     = os.environ["GMAIL_APP_PASS"]
TO_EMAIL       = os.environ["TO_GMAIL"]
GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]

# Your resume text — stored as a GitHub Secret "RESUME_TEMPLATE"
# If not set, a placeholder message is used so the script doesn't crash.
RESUME_TEMPLATE = os.environ.get("RESUME_TEMPLATE", "").strip()

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
MODEL = "gpt-4o-mini"   # free tier on GitHub Models

JOBS_FILE = "jobs_data.json"

# Global cap on per-job deep-analysis to stay within API rate limits.
# All jobs across ALL categories are analyzed up to this number.
# GitHub Models free tier: ~10 req/min — 25 jobs + 1 overview ≈ 3.5 min with 8 s delays.
MAX_TOTAL_JOBS = 25

# ── FREE POINT OF CONTACT LOOKUP (no API key needed) ─────────────────────────
#
# Strategy 1 — jobspy email extraction:
#   jobspy already parses emails from job descriptions automatically.
#   When a company includes contact details in the posting, they appear here.
#
# Strategy 2 — emailformat.com scraping:
#   emailformat.com catalogs the email naming convention used by thousands of
#   companies (e.g. {first}.{last}@accenture.com). Completely free, no sign-up.
#   Returns a pattern string (not a real address) when Strategy 1 finds nothing.

_JUNK_PREFIXES = ("noreply", "no-reply", "donotreply", "mailer", "bounce", "support", "info@")
_domain_fmt_cache: dict = {}   # domain → pattern string or None


def _extract_domain(url: str) -> str:
    """Pull the bare domain (no www) from any URL string."""
    try:
        parsed = urllib.parse.urlparse(url if "://" in url else "https://" + url)
        host = parsed.netloc or parsed.path.split("/")[0]
        return re.sub(r"^www\.", "", host).strip().lower()
    except Exception:
        return ""


def _scrape_email_format(domain: str) -> str | None:
    """
    Scrape emailformat.com/d/<domain> for the most-used email pattern.
    Returns a pattern like '{first}.{last}@company.com' or None.
    Results are cached per domain to avoid repeat requests.
    """
    if domain in _domain_fmt_cache:
        return _domain_fmt_cache[domain]

    try:
        url = f"https://www.emailformat.com/d/{domain}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # emailformat.com renders patterns like {first}.{last}@domain.com in the page
        match = re.search(
            r'(\{[a-z_.]+\}(?:\.[a-z]+)?@' + re.escape(domain) + r')',
            html,
        )
        result = match.group(1) if match else None
        _domain_fmt_cache[domain] = result
        return result
    except Exception:
        _domain_fmt_cache[domain] = None
        return None


def find_poc_free(job: dict) -> dict | None:
    """
    Find a point-of-contact email using two free, no-signup strategies.
    Returns a dict with keys: email, source, is_pattern.
    """
    # ── Strategy 1: real emails extracted from job description by jobspy ──
    raw_emails: list = job.get("emails") or []
    real_emails = [
        e for e in raw_emails
        if e and not any(e.lower().startswith(p) for p in _JUNK_PREFIXES)
    ]
    if real_emails:
        print(f"    📧 POC (from job desc): {real_emails[0]}")
        return {"email": real_emails[0], "source": "job description", "is_pattern": False}

    # ── Strategy 2: email format pattern from emailformat.com ─────────────
    company_url = job.get("company_url", "")
    if company_url:
        domain = _extract_domain(company_url)
        if domain:
            pattern = _scrape_email_format(domain)
            if pattern:
                print(f"    📋 POC pattern (emailformat.com): {pattern}")
                return {"email": pattern, "source": "emailformat.com", "is_pattern": True}

    return None


# ── LOAD JOB DATA ─────────────────────────────────────────────────────────────
def load_jobs():
    if not os.path.exists(JOBS_FILE):
        print(f"[WARN] {JOBS_FILE} not found — nothing to optimize.")
        return {}
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ── GITHUB MODELS API ─────────────────────────────────────────────────────────
def call_github_models(prompt: str, max_tokens: int = 1200, max_retries: int = 3) -> str | None:
    """Call GitHub's OpenAI-compatible endpoint with retry on rate-limit (429)."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert ATS resume consultant. "
                    "You compare job descriptions against a candidate's existing resume "
                    "and return ONLY concise, actionable HTML — no preamble, no markdown fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            GITHUB_MODELS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Accept": "application/vnd.github+json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429 and attempt < max_retries:
                match = re.search(r'"retryDelay":\s*"(\d+)s?"', body)
                wait = int(match.group(1)) + 5 if match else 30 * attempt
                print(f"[WARN] Rate limited (attempt {attempt}/{max_retries}). Retrying in {wait}s…")
                time.sleep(wait)
                continue
            print(f"[ERROR] GitHub Models API {e.code}: {body}")
            return None
        except Exception as exc:
            print(f"[ERROR] GitHub Models API call failed: {exc}")
            return None
    return None


# ── PROMPTS ───────────────────────────────────────────────────────────────────
def per_job_prompt(job: dict, resume: str) -> str:
    title   = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")
    desc    = job.get("summary", "No description available.")

    resume_section = (
        f"CANDIDATE'S CURRENT RESUME:\n{resume}"
        if resume
        else "CANDIDATE'S CURRENT RESUME: [Not provided — give general advice for this role]"
    )

    return f"""You are helping a candidate tailor their resume for the following job opening.

JOB TITLE: {title}
COMPANY: {company}
JOB DESCRIPTION:
{desc}

---
{resume_section}
---

Provide the following in clean HTML (inline styles only, suitable for email):

<h3>🔑 ATS Keywords to Add</h3>
List the 10–15 most critical keywords/phrases from this job description that are
MISSING or UNDER-REPRESENTED in the candidate's resume. Output as a styled
pill/badge list (span tags with background #ede9fe, color #5b21b6, padding 3px 10px,
border-radius 9999px, font-size 13px, margin 3px, display inline-block).

<h3>✍️ Tailored Bullet Points</h3>
Write 4–6 strong, quantified resume bullet points (X-Y-Z formula) that:
- Directly mirror the language and priorities of THIS specific job description
- Would slot into the candidate's existing experience sections
- Start each bullet with a strong action verb
Output as a styled <ul> list (list-style: none; padding: 0).
Each <li> should have a left border: 3px solid #7c3aed; padding-left: 12px; margin-bottom: 8px.

<h3>⚠️ Gap Alert</h3>
In 2–3 short sentences, highlight the single most important skill or qualification
gap between the candidate's resume and this job, and suggest how to address it.

Keep HTML compact — no outer wrapper div needed."""


def overview_prompt(all_jobs_flat: list[dict], resume: str) -> str:
    """Build a global prompt for top-level summary across ALL jobs."""
    lines = []
    for j in all_jobs_flat:
        lines.append(f"• {j.get('title','')} at {j.get('company','')} — {j.get('summary','')[:200]}")
    context = "\n".join(lines)

    resume_section = (
        f"CANDIDATE'S CURRENT RESUME:\n{resume}"
        if resume
        else "CANDIDATE'S CURRENT RESUME: [Not provided]"
    )

    return f"""Analyze ALL of the following job listings together.

JOB LISTINGS:
{context}

---
{resume_section}
---

Return clean HTML (inline styles only) with:

<h3>🏆 Top 20 ATS Keywords (across all roles)</h3>
Ranked list of the most repeated / highest-importance keywords across all listings.
Style as a numbered <ol> (font-size 13px; columns split into two using a flex layout).

<h3>📝 Universal Professional Summary</h3>
One polished 3-sentence professional summary paragraph that covers the breadth of
these transformation / change management roles and naturally uses the top keywords.
Style with background:#f5f3ff; border-left:4px solid #7c3aed; padding:12px 16px.

<h3>🛠️ Skills Matrix</h3>
Organize extracted skills into a compact HTML table (3 columns: Category | Key Skills | Priority)
with alternating row colors (#f9f9f9 / #fff).

Keep HTML compact."""


# ── EMAIL BUILDER ─────────────────────────────────────────────────────────────
CARD_STYLE = (
    "background:#fff;border:1px solid #e2e8f0;border-radius:12px;"
    "padding:20px 24px;margin-bottom:20px;"
)
HEADER_STYLE = (
    "margin:0 0 4px;font-size:17px;font-weight:700;color:#1e293b;"
)
META_STYLE = (
    "font-size:12px;color:#64748b;margin:0 0 14px;"
)
DIVIDER_STYLE = (
    "border:none;border-top:1px solid #e2e8f0;margin:16px 0;"
)
JOB_TAG_STYLE = (
    "display:inline-block;background:#ede9fe;color:#5b21b6;"
    "font-size:11px;padding:2px 8px;border-radius:9999px;margin-right:6px;"
)


def build_email_html(overview_html: str, per_job_sections: list[dict], total_jobs: int) -> str:
    today = datetime.now().strftime("%B %d, %Y")

    # Build per-job cards
    job_cards_html = ""
    for item in per_job_sections:
        title   = item["title"]
        company = item["company"]
        location = item.get("location", "")
        source  = item.get("source", "")
        link    = item.get("link", "#")
        analysis = item["analysis"]

        # Build POC block if available
        poc = item.get("poc")
        if poc:
            if poc["is_pattern"]:
                # Strategy 2: show email format pattern
                label  = "📋 EMAIL FORMAT PATTERN (via emailformat.com)"
                badge  = "<span style='font-size:11px;color:#d97706;margin-left:8px;'>Pattern — not a real address</span>"
                bg     = "#fffbeb"
                border = "#fde68a"
                lcolor = "#92400e"
            else:
                # Strategy 1: real email from job description
                label  = "📬 POINT OF CONTACT (from job posting)"
                badge  = "<span style='font-size:11px;color:#16a34a;margin-left:8px;'>✓ Found in job description</span>"
                bg     = "#f0fdf4"
                border = "#bbf7d0"
                lcolor = "#15803d"

            poc_html = f"""
    <div style="background:{bg};border:1px solid {border};border-radius:8px;padding:10px 14px;margin-bottom:14px;">
      <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{lcolor};letter-spacing:.05em;">{label}</p>
      <p style="margin:0;font-size:13px;">
        <a href="mailto:{poc['email']}" style="color:#1a56db;text-decoration:none;font-weight:600;">{poc['email']}</a>
        {badge}
      </p>
    </div>"""
        else:
            poc_html = ""

        job_cards_html += f"""
  <div style="{CARD_STYLE}">
    <p style="{HEADER_STYLE}">
      <a href="{link}" style="color:#1a56db;text-decoration:none;">{title}</a>
    </p>
    <p style="{META_STYLE}">
      <span style="{JOB_TAG_STYLE}">{company}</span>
      <span style="{JOB_TAG_STYLE}">{location}</span>
      <span style="{JOB_TAG_STYLE}">{source}</span>
    </p>
    <hr style="{DIVIDER_STYLE}">
    {poc_html}
    {analysis}
  </div>"""

    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:0;">
<div style="max-width:700px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#7c3aed,#ec4899);border-radius:12px;padding:24px;color:#fff;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">🎯 Resume Keyword Optimizer</h1>
    <p style="margin:6px 0 0;opacity:.85;">{today} &nbsp;·&nbsp; {total_jobs} jobs analyzed &nbsp;·&nbsp; Powered by GitHub Models</p>
  </div>

  <!-- Overview Section -->
  <div style="{CARD_STYLE}">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1e293b;">📊 Overall Analysis</h2>
    {overview_html}
  </div>

  <!-- Per-Job Analysis -->
  <h2 style="font-size:18px;color:#1e293b;margin:24px 0 12px;">🔍 Job-by-Job Breakdown</h2>
  {job_cards_html}

  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:32px;">
    Powered by GitHub Actions + GitHub Models · Free AI-powered resume analysis
  </p>
</div>
</body></html>"""


def send_email(html_body: str, total_jobs: int) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 Resume Keywords — {total_jobs} jobs analyzed ({datetime.now().strftime('%b %d')})"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print(f"✅ Resume keywords email sent to {TO_EMAIL}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    all_results = load_jobs()
    if not all_results:
        print("No job data found. Skipping resume optimization.")
        return

    total_jobs = sum(len(jobs) for jobs in all_results.values())
    if total_jobs == 0:
        print("Zero jobs in data file. Skipping.")
        return

    print(f"📊 Loaded {total_jobs} jobs from {JOBS_FILE}")

    if not RESUME_TEMPLATE:
        print("[WARN] RESUME_TEMPLATE env var not set. Analysis will be generic (no gap comparison).")
    else:
        print(f"📄 Resume template loaded ({len(RESUME_TEMPLATE)} chars).")

    # ── 1. Overview analysis across all jobs ───────────────────────────────
    all_jobs_flat = [j for jobs in all_results.values() for j in jobs]

    # Cap context to avoid token overflow
    flat_for_overview = all_jobs_flat[:20]

    print("⏳ Waiting 5 s before first API call…")
    time.sleep(5)

    print(f"🤖 Calling GitHub Models for overall analysis ({MODEL})…")
    overview_html = call_github_models(
        overview_prompt(flat_for_overview, RESUME_TEMPLATE),
        max_tokens=1800,
    )
    if not overview_html:
        overview_html = "<p style='color:#ef4444;'>⚠️ Overview analysis unavailable (API error).</p>"

    # ── 2. Per-job analysis — ALL jobs across every category ──────────────
    per_job_sections = []

    # Flatten all jobs preserving category label, then cap globally.
    all_jobs_for_analysis = [
        (category, job)
        for category, jobs in all_results.items()
        for job in jobs
    ]

    if len(all_jobs_for_analysis) > MAX_TOTAL_JOBS:
        print(f"[INFO] {len(all_jobs_for_analysis)} jobs found — capping at {MAX_TOTAL_JOBS} to respect API limits.")
        all_jobs_for_analysis = all_jobs_for_analysis[:MAX_TOTAL_JOBS]
    else:
        print(f"[INFO] Analyzing all {len(all_jobs_for_analysis)} jobs.")

    for idx, (category, job) in enumerate(all_jobs_for_analysis, start=1):
        title   = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        print(f"  [{idx}/{len(all_jobs_for_analysis)}] 🔎 {title} @ {company} ({category})")

        # Polite delay between calls to stay within rate limits
        time.sleep(8)

        analysis_html = call_github_models(
            per_job_prompt(job, RESUME_TEMPLATE),
            max_tokens=1200,
        )

        if not analysis_html:
            analysis_html = "<p style='color:#ef4444;'>⚠️ Analysis unavailable for this job.</p>"

        # Free POC lookup — no API key or sign-up needed
        poc = find_poc_free(job)

        per_job_sections.append({
            "title":    title,
            "company":  company,
            "location": job.get("location", ""),
            "source":   job.get("source", ""),
            "link":     job.get("link", "#"),
            "analysis": analysis_html,
            "poc":      poc,
        })

    print(f"\n✅ Analyzed {len(per_job_sections)} jobs individually.")

    # ── 3. Build & send email ──────────────────────────────────────────────
    html = build_email_html(overview_html, per_job_sections, total_jobs)
    send_email(html, total_jobs)


if __name__ == "__main__":
    main()
