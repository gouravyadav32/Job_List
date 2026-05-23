# 📋 Job Alert + 🎯 AI Resume Optimizer

**Automated daily job scraping + AI-powered resume keyword analysis — completely free.**

Scrapes Transformation Manager, Change Management & Agile roles from **Indeed, LinkedIn & Glassdoor** across India, Middle East & Remote, then uses **GitHub Models** to analyze the listings and generate tailored resume keywords, bullet points, and skills — all delivered to your inbox every morning.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Multi-platform scraping** | Indeed, LinkedIn, Glassdoor via [JobSpy](https://github.com/Bunsly/JobSpy) |
| **Location filters** | India, Middle East (UAE), Remote — fully customizable |
| **AI Resume Optimizer** | Extracts ATS keywords, writes bullet points, identifies skill gaps |
| **Daily email alerts** | Beautiful HTML emails with job cards + AI analysis |
| **100% free** | GitHub Actions (2000 min/mo) + GitHub Models (built-in free tier) |
| **Zero external API keys** | Uses the built-in `GITHUB_TOKEN` |

## 📧 What You Receive Daily

**Email 1 — Job Alert**
> Fresh job listings with title, company, location, source, and description preview.

**Email 2 — Resume Optimizer**
> AI-generated ATS keywords, professional summary, achievement bullet points (X-Y-Z formula), categorized skills section, and missing skills alert.

---

## 🚀 Quick Setup (6 minutes)

### 1. Fork / Clone this repo

```bash
git clone https://github.com/gouravyadav32/Job_List.git
```

### 2. Get a Gmail App Password

- Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- 2-Step Verification must be ON
- Create an app password named `job-alerts`
- Copy the 16-character password

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Value |
|---|---|
| `GMAIL_USER` | Your Gmail address |
| `GMAIL_APP_PASS` | 16-char App Password from step 2 |
| `TO_GMAIL` | *(Optional)* Delivery address if different from `GMAIL_USER` |

### 5. Test it

Go to **Actions → Daily Job Alert → Run workflow** → check your inbox in ~30 seconds.

After that, it runs automatically every day at **8:00 AM IST** (2:30 AM UTC).

---

## 🔧 Customization

### Change target roles & locations

Edit the `SEARCHES` list in [`job_alert.py`](job_alert.py):

```python
SEARCHES = [
    {"title": "Data Engineer (India)",       "keywords": "data engineer",  "location": "India",       "country": "india"},
    {"title": "Data Engineer (Middle East)", "keywords": "data engineer",  "location": "Middle East", "country": "ae"},
    {"title": "Data Engineer (Remote)",      "keywords": "data engineer",  "location": "remote",      "country": "usa"},
]
```

### Change schedule

Edit the cron in [`.github/workflows/job_alert.yml`](.github/workflows/job_alert.yml):

```yaml
schedule:
  - cron: "30 2 * * *"      # 2:30 AM UTC = 8:00 AM IST daily
  # - cron: "30 1 * * 1-5"  # Weekdays only at 1:30 AM UTC (7:00 AM IST)
```

### Change lookback window

```python
HOURS_BACK = 48  # show jobs from last 2 days instead of 24h
```

---

## 📁 Project Structure

```
Job_List/
├── .github/workflows/
│   └── job_alert.yml          # GitHub Actions workflow (2 jobs)
├── job_alert.py               # Job scraper + email sender
├── resume_keywords.py         # AI resume optimizer (Gemini)
├── preview.html               # Interactive setup guide (React)
├── .gitignore
└── README.md
```

## ⚙️ How It Works

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions (daily)                 │
│                                                         │
│  Job 1: send-job-alert                                  │
│  ├── Scrape Indeed, LinkedIn, Glassdoor via JobSpy       │
│  ├── Send HTML email with job listings                  │
│  └── Save jobs_data.json → upload as artifact           │
│                         │                               │
│                         ▼                               │
│  Job 2: resume-optimizer                                │
│  ├── Download jobs_data.json artifact                   │
│  ├── Build context from job descriptions                │
│  ├── Call GitHub Models API (gpt-4o-mini)                 │
│  │   └── Extract keywords, write summary & bullets      │
│  └── Send HTML email with AI analysis                   │
└─────────────────────────────────────────────────────────┘
```

---

## 📄 License

MIT — use it, fork it, customize it.
