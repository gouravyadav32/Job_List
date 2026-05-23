"""
Resume Keyword Optimizer — powered by Google Gemini API (free tier).

Reads jobs_data.json produced by job_alert.py, sends job descriptions to
Gemini 2.0 Flash via Google's free API, and emails you:
  • Top ATS keywords to add to your resume
  • A tailored professional summary
  • Suggested bullet points for each role category

Requires one extra GitHub Secret:
  GEMINI_API_KEY  — free at https://aistudio.google.com/apikey
"""

import json
import os
import smtplib
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_APP_PASS"]
TO_EMAIL   = os.environ.get["GMAIL_USER"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = "gemini-2.0-flash"   # free tier, no rate-limit issues from CI/CD

JOBS_FILE = "jobs_data.json"

# ── LOAD JOB DATA ─────────────────────────────────────────────────────────────
def load_jobs():
    if not os.path.exists(JOBS_FILE):
        print(f"[WARN] {JOBS_FILE} not found — nothing to optimize.")
        return {}
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_job_context(all_results):
    """Flatten all job titles + descriptions into a single context block."""
    lines = []
    for category, jobs in all_results.items():
        for j in jobs:
            title = j.get("title", "")
            company = j.get("company", "")
            summary = j.get("summary", "")
            lines.append(f"Role: {title} at {company}\nDescription: {summary}")
    return "\n---\n".join(lines)


# ── GEMINI API (no SDK needed — plain HTTP) ────────────────────────────────────
def call_gemini(prompt, max_tokens=2048, max_retries=3):
    """Call Google Gemini's OpenAI-compatible API with retry logic for rate limits."""
    import time
    import re

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert ATS resume consultant and career coach. "
                    "You help candidates optimize their resumes for Applicant Tracking Systems."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            GEMINI_API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {GEMINI_API_KEY}",
                "Content-Type": "application/json",
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
                # Extract retry delay from response, default to 30s
                match = re.search(r'"retryDelay":\s*"(\d+)s?"', body)
                wait = int(match.group(1)) + 5 if match else 30 * attempt
                print(f"[WARN] Rate limited (attempt {attempt}/{max_retries}). Retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"[ERROR] Gemini API {e.code}: {body}")
            return None
        except Exception as e:
            print(f"[ERROR] Gemini API call failed: {e}")
            return None


# ── PROMPTS ───────────────────────────────────────────────────────────────────
def get_keywords_prompt(job_context):
    return f"""Analyze the following job listings and provide resume optimization advice.

JOB LISTINGS:
{job_context}

Please provide the following in a well-structured format:

1. **TOP 25 ATS KEYWORDS** — The most frequently mentioned and important technical skills, tools, and qualifications across these jobs. Rank them by importance.

2. **PROFESSIONAL SUMMARY** — Write a tailored 3-4 sentence professional summary that a Data Engineer could use, naturally incorporating the top keywords.

3. **SUGGESTED BULLET POINTS** — Write 8-10 strong resume bullet points (using the X-Y-Z formula: Accomplished [X] as measured by [Y], by doing [Z]) that align with these job requirements.

4. **SKILLS SECTION** — Organize the extracted skills into categories (e.g., Cloud Platforms, Databases, Programming Languages, ETL/Pipeline Tools, etc.)

5. **MISSING SKILLS ALERT** — Identify any trending skills or certifications mentioned frequently that a candidate should consider learning.

Format everything in clean HTML with inline styles for email rendering. Use a professional color scheme."""


# ── EMAIL BUILDER ─────────────────────────────────────────────────────────────
def build_email_html(ai_response, total_jobs):
    today = datetime.now().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:0;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">
  <div style="background:linear-gradient(135deg,#7c3aed,#ec4899);border-radius:12px;padding:24px;color:#fff;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">🎯 Resume Keyword Optimizer</h1>
    <p style="margin:6px 0 0;opacity:.85;">{today} &nbsp;·&nbsp; Analyzed {total_jobs} job listings &nbsp;·&nbsp; Powered by Gemini AI</p>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:16px;">
    {ai_response}
  </div>
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:32px;">
    Powered by GitHub Actions + Google Gemini · Free AI-powered analysis
  </p>
</div>
</body></html>"""


def send_email(html_body, total_jobs):
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

    # Build context from job descriptions
    job_context = build_job_context(all_results)

    # Truncate if too large (Groq free tier has token limits)
    if len(job_context) > 12000:
        job_context = job_context[:12000] + "\n... [truncated for token limit]"

    print(f"🤖 Calling Gemini API ({MODEL})...")
    ai_response = call_gemini(get_keywords_prompt(job_context))

    if not ai_response:
        print("❌ Failed to get AI response. Skipping email.")
        return

    print(f"✅ Got AI response ({len(ai_response)} chars)")

    html = build_email_html(ai_response, total_jobs)
    send_email(html, total_jobs)


if __name__ == "__main__":
    main()
