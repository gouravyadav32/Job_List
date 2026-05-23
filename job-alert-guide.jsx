import { useState } from "react";

const steps = [
  {
    id: 1,
    icon: "⬡",
    title: "Create a GitHub Repo",
    time: "1 min",
    color: "#6366f1",
    substeps: [
      <>Go to <a href="https://github.com/new" target="_blank" rel="noreferrer" style={{color:"#818cf8"}}>github.com/new</a></>,
      <>Name it <code>job-alerts</code> → click <strong>Create repository</strong></>,
      <>It can be <strong>private</strong> — Actions still run free (2000 min/month)</>,
    ],
  },
  {
    id: 2,
    icon: "⬡",
    title: "Add the Two Files",
    time: "2 min",
    color: "#0ea5e9",
    substeps: [
      <>In your repo, click <strong>Add file → Create new file</strong></>,
      <>Name it <code>job_alert.py</code> → paste the Python script (copy below)</>,
      <>Create another file at <code>.github/workflows/job_alert.yml</code> → paste the YAML</>,
      <>Edit <code>SEARCHES</code> in <code>job_alert.py</code> to match your target roles</>,
    ],
  },
  {
    id: 3,
    icon: "⬡",
    title: "Get a Gmail App Password",
    time: "2 min",
    color: "#10b981",
    substeps: [
      <>Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{color:"#34d399"}}>myaccount.google.com/apppasswords</a></>,
      <>2-Step Verification must be ON (enable it first if not)</>,
      <>App name: <code>job-alerts</code> → click <strong>Create</strong></>,
      <>Copy the 16-char password shown — you won't see it again</>,
    ],
  },
  {
    id: 4,
    icon: "⬡",
    title: "Add GitHub Secrets",
    time: "1 min",
    color: "#f59e0b",
    substeps: [
      <>In your repo: <strong>Settings → Secrets → Actions → New repository secret</strong></>,
      <>Add <code>GMAIL_USER</code> = your Gmail address</>,
      <>Add <code>GMAIL_APP_PASS</code> = the 16-char App Password</>,
      <>(Optional) Add <code>TO_EMAIL</code> = delivery address if different</>,
    ],
  },
  {
    id: 5,
    icon: "⬡",
    title: "Test It Now",
    time: "30 sec",
    color: "#ec4899",
    substeps: [
      <>Go to <strong>Actions</strong> tab in your repo</>,
      <>Click <strong>Daily Job Alert → Run workflow</strong></>,
      <>Wait ~20 seconds → check your inbox 🎉</>,
      <>After that, it runs automatically every day at 8 AM UTC</>,
    ],
  },
];

const pyCode = `import feedparser, smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_APP_PASS"]
TO_EMAIL   = os.environ.get("TO_EMAIL", GMAIL_USER)

# ✏️  EDIT THESE — your target roles & locations
SEARCHES = [
    {"title": "Data Engineer",       "keywords": "data engineer",            "location": "remote"},
    {"title": "Databricks Engineer", "keywords": "databricks spark",         "location": "remote"},
    {"title": "Azure Data Engineer", "keywords": "azure data factory spark", "location": "remote"},
]
HOURS_BACK = 24

def indeed_rss(kw, loc):
    return f"https://www.indeed.com/rss?q={quote_plus(kw)}&l={quote_plus(loc)}&sort=date&fromage=1"

def fetch_jobs(search):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    jobs = []
    try:
        feed = feedparser.parse(indeed_rss(search["keywords"], search["location"]))
        for e in feed.entries[:20]:
            p = e.get("published_parsed")
            if p and datetime(*p[:6], tzinfo=timezone.utc) < cutoff:
                continue
            jobs.append({"title": e.get("title",""), "company": e.get("author",""),
                         "link": e.get("link",""),   "published": e.get("published",""),
                         "summary": e.get("summary","")[:300]})
    except Exception as ex:
        print(f"Feed error: {ex}")
    return jobs

def build_html(results):
    today = datetime.now().strftime("%B %d, %Y")
    total = sum(len(j) for j in results.values())
    sections = ""
    for title, jobs in results.items():
        cards = "".join(f'''<div style="border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin-bottom:10px;">
          <a href="{j['link']}" style="font-size:16px;font-weight:600;color:#1a56db;">{j['title']}</a>
          <div style="color:#555;font-size:13px;">{j['company']} · {j['published']}</div>
          <div style="color:#444;font-size:13px;margin-top:6px;">{j['summary']}…</div>
        </div>''' for j in jobs) if jobs else "<p style='color:#888'>No new listings.</p>"
        sections += f"<h2>🔍 {title} ({len(jobs)} new)</h2>{cards}"
    return f"""<html><body style="font-family:sans-serif;max-width:680px;margin:auto;padding:24px">
      <h1 style="background:linear-gradient(135deg,#1a56db,#0ea5e9);color:#fff;padding:20px;border-radius:12px">
        📋 Daily Job Alert · {today} · {total} listings</h1>
      {sections}</body></html>"""

def main():
    results = {s["title"]: fetch_jobs(s) for s in SEARCHES}
    total   = sum(len(j) for j in results.values())
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Daily Jobs — {total} new ({datetime.now().strftime('%b %d')})"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(build_html(results), "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print(f"✅ Sent {total} jobs to {TO_EMAIL}")

if __name__ == "__main__":
    main()`;

const yamlCode = `name: Daily Job Alert
on:
  schedule:
    - cron: "0 8 * * *"   # 8 AM UTC daily — change to your timezone
  workflow_dispatch:        # manual trigger from GitHub UI

jobs:
  send-job-alert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install feedparser
      - name: Run job alert
        env:
          GMAIL_USER:     \${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASS: \${{ secrets.GMAIL_APP_PASS }}
          TO_EMAIL:       \${{ secrets.TO_EMAIL }}
        run: python job_alert.py`;

export default function JobAlertGuide() {
  const [activeStep, setActiveStep] = useState(1);
  const [copied, setCopied] = useState(null);
  const [activeTab, setActiveTab] = useState("python");

  const copy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const codeMap = { python: pyCode, yaml: yamlCode };
  const fileMap  = { python: "job_alert.py", yaml: ".github/workflows/job_alert.yml" };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#09090b",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      color: "#e2e8f0",
      padding: "32px 16px",
    }}>
      {/* Header */}
      <div style={{ maxWidth: 860, margin: "0 auto" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          marginBottom: 6,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: "linear-gradient(135deg,#6366f1,#0ea5e9)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 20,
          }}>📋</div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: "-0.5px" }}>
              Free Daily Job Alerts
            </h1>
            <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>
              GitHub Actions + Gmail · 0$/month · Setup in ~6 minutes
            </p>
          </div>
        </div>

        {/* Badge row */}
        <div style={{ display: "flex", gap: 8, margin: "20px 0 32px", flexWrap: "wrap" }}>
          {["✅ Completely Free","⚡ 6-min Setup","📧 Email Delivery","🔄 Runs Daily","🔒 Private"].map(b => (
            <span key={b} style={{
              background: "#18181b", border: "1px solid #27272a",
              borderRadius: 20, padding: "4px 12px", fontSize: 12, color: "#a1a1aa",
            }}>{b}</span>
          ))}
        </div>

        {/* How it works */}
        <div style={{
          background: "#18181b", border: "1px solid #27272a",
          borderRadius: 12, padding: "16px 20px", marginBottom: 32,
          fontSize: 13, color: "#94a3b8", lineHeight: 1.7,
        }}>
          <strong style={{ color: "#e2e8f0" }}>How it works: </strong>
          A Python script fetches Indeed's job RSS feeds filtered to your searches → formats them into a
          rich HTML email → sends it to your Gmail. GitHub Actions runs this free every day on a schedule.
          No server. No paid API. No browser extensions. Just code + your GitHub account.
        </div>

        {/* Steps */}
        <div style={{ display: "flex", gap: 12, marginBottom: 32, flexWrap: "wrap" }}>
          {steps.map(s => (
            <button key={s.id} onClick={() => setActiveStep(s.id)} style={{
              flex: "1 1 140px",
              background: activeStep === s.id ? "#18181b" : "transparent",
              border: `1px solid ${activeStep === s.id ? s.color : "#27272a"}`,
              borderRadius: 10, padding: "12px 14px", cursor: "pointer",
              textAlign: "left", transition: "all .15s",
              boxShadow: activeStep === s.id ? `0 0 0 1px ${s.color}22, 0 4px 20px ${s.color}22` : "none",
            }}>
              <div style={{ fontSize: 18, marginBottom: 4 }}>
                <span style={{ color: s.color, fontWeight: 700 }}>Step {s.id}</span>
              </div>
              <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600, marginBottom: 2 }}>{s.title}</div>
              <div style={{ fontSize: 11, color: "#64748b" }}>⏱ {s.time}</div>
            </button>
          ))}
        </div>

        {/* Active step detail */}
        {steps.filter(s => s.id === activeStep).map(s => (
          <div key={s.id} style={{
            background: "#18181b", border: `1px solid ${s.color}44`,
            borderRadius: 12, padding: "20px 24px", marginBottom: 32,
            boxShadow: `0 0 40px ${s.color}11`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <span style={{
                background: `${s.color}22`, color: s.color,
                borderRadius: 8, padding: "4px 12px", fontSize: 12, fontWeight: 700,
              }}>STEP {s.id}</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9" }}>{s.title}</span>
            </div>
            <ol style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 10 }}>
              {s.substeps.map((sub, i) => (
                <li key={i} style={{ fontSize: 14, color: "#cbd5e1", lineHeight: 1.6 }}>{sub}</li>
              ))}
            </ol>
            <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
              {s.id > 1 && (
                <button onClick={() => setActiveStep(s.id - 1)} style={{
                  background: "transparent", border: "1px solid #3f3f46",
                  color: "#94a3b8", borderRadius: 8, padding: "8px 18px", cursor: "pointer", fontSize: 13,
                }}>← Back</button>
              )}
              {s.id < 5 && (
                <button onClick={() => setActiveStep(s.id + 1)} style={{
                  background: s.color, border: "none",
                  color: "#fff", borderRadius: 8, padding: "8px 18px", cursor: "pointer",
                  fontSize: 13, fontWeight: 600,
                }}>Next →</button>
              )}
              {s.id === 5 && (
                <span style={{ color: "#10b981", fontSize: 14, paddingTop: 6 }}>
                  🎉 You're all set! Emails start arriving daily.
                </span>
              )}
            </div>
          </div>
        ))}

        {/* Code section */}
        <div style={{
          background: "#18181b", border: "1px solid #27272a",
          borderRadius: 12, overflow: "hidden", marginBottom: 32,
        }}>
          <div style={{
            display: "flex", borderBottom: "1px solid #27272a",
            background: "#141414",
          }}>
            {["python","yaml"].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                background: activeTab === tab ? "#18181b" : "transparent",
                border: "none", borderBottom: activeTab === tab ? "2px solid #6366f1" : "2px solid transparent",
                color: activeTab === tab ? "#e2e8f0" : "#64748b",
                padding: "12px 20px", cursor: "pointer", fontSize: 13, fontWeight: 600,
              }}>
                {tab === "python" ? "📄 job_alert.py" : "⚙️ job_alert.yml"}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            <button onClick={() => copy(codeMap[activeTab], activeTab)} style={{
              background: copied === activeTab ? "#10b98122" : "transparent",
              border: "none", color: copied === activeTab ? "#10b981" : "#64748b",
              padding: "10px 18px", cursor: "pointer", fontSize: 12, fontWeight: 600,
            }}>
              {copied === activeTab ? "✓ Copied!" : "Copy"}
            </button>
          </div>
          <div style={{ padding: "4px 0" }}>
            <div style={{
              padding: "6px 16px 4px",
              fontSize: 11, color: "#4b5563",
              borderBottom: "1px solid #1f2937",
            }}>
              Save as: <code style={{ color: "#818cf8" }}>{fileMap[activeTab]}</code>
            </div>
            <pre style={{
              margin: 0, padding: "16px 20px",
              fontSize: 12, lineHeight: 1.65,
              color: "#a5b4fc",
              overflowX: "auto",
              maxHeight: 420,
            }}>
              {codeMap[activeTab]}
            </pre>
          </div>
        </div>

        {/* Customization tips */}
        <div style={{
          background: "#18181b", border: "1px solid #27272a",
          borderRadius: 12, padding: "20px 24px", marginBottom: 16,
        }}>
          <h3 style={{ margin: "0 0 14px", fontSize: 14, color: "#f1f5f9" }}>
            ✏️ Customize Your Searches
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { label: "More roles", code: `{"title":"MLOps Engineer","keywords":"mlops databricks","location":"remote"}` },
              { label: "Specific city", code: `{"keywords":"data engineer","location":"bangalore india"}` },
              { label: "Change time", code: `HOURS_BACK = 48  # show 2 days` },
              { label: "Change schedule", code: `cron: "0 7 * * 1-5"  # weekdays 7AM` },
            ].map(tip => (
              <div key={tip.label} style={{
                background: "#09090b", borderRadius: 8, padding: "12px 14px",
                border: "1px solid #27272a",
              }}>
                <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6 }}>{tip.label}</div>
                <code style={{ fontSize: 11, color: "#86efac", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                  {tip.code}
                </code>
              </div>
            ))}
          </div>
        </div>

        <div style={{ textAlign: "center", color: "#3f3f46", fontSize: 12, paddingTop: 8 }}>
          GitHub Free tier · 2000 Actions minutes/month · More than enough for daily job alerts
        </div>
      </div>
    </div>
  );
}
