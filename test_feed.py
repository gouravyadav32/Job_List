import jobspy
import pandas as pd

jobs = jobspy.scrape_jobs(
    site_name=["indeed", "linkedin"],
    search_term="data engineer",
    location="remote",
    results_wanted=5,
    hours_old=24,
    country_epa='USA'
)

print(f"JobSpy Found {len(jobs)} jobs")
if not jobs.empty:
    print(jobs[["site", "title", "company", "job_url"]].head())
