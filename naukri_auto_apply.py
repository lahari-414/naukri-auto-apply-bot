"""
Naukri Auto Apply Bot - FIXED VERSION
Fixes:
  1. ElementClickInterceptedException  -> JS click after scrolling past navbar
  2. Invalid PDF download              -> verify PDF magic bytes before saving
  3. company-site-button skip          -> skip external apply jobs automatically
"""

import os
import time
import json
import datetime
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)

import requests
import pdfplumber

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DOWNLOAD_DIR   = str(Path.home() / "Downloads" / "Auto bot" / "downloads")
RESUME_PATH    = os.path.join(DOWNLOAD_DIR, "resume.pdf")
LOG_FILE       = os.path.join(DOWNLOAD_DIR, "applied_jobs.json")
REPORT_FILE    = os.path.join(DOWNLOAD_DIR, "apply_report.html")
NAUKRI_PROFILE = "https://www.naukri.com/mnjuser/profile"
MAX_PAGES      = 3
APPLY_DELAY    = 3
MAX_APPLY      = 50

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def load_applied_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_applied_log(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────────
def launch_browser():
    options = Options()
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=options)

# ─────────────────────────────────────────────
# STEP 1: MANUAL LOGIN
# ─────────────────────────────────────────────
def manual_login(driver):
    log("Opening Naukri login page...")
    driver.get("https://www.naukri.com/nlogin/login")
    print("\n" + "="*55)
    print("  Browser lo Naukri login cheyyi (email + password)")
    print("  Login complete ayaka ENTER press cheyyi...")
    print("="*55)
    input()
    log("Login confirmed. Continuing...")

# ─────────────────────────────────────────────
# STEP 2: DOWNLOAD RESUME (FIXED)
# ─────────────────────────────────────────────
def is_valid_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"%PDF"
    except:
        return False

def download_resume(driver):
    log("Navigating to Naukri profile to download resume...")
    driver.get(NAUKRI_PROFILE)
    time.sleep(5)

    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    ua = driver.execute_script("return navigator.userAgent;")
    headers = {"User-Agent": ua, "Referer": "https://www.naukri.com/"}

    downloaded = False
    links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    pdf_links = [
        el.get_attribute("href") for el in links
        if el.get_attribute("href") and
        (".pdf" in el.get_attribute("href").lower() or
         "resume" in el.get_attribute("href").lower())
    ]
    log(f"  Found {len(pdf_links)} resume/pdf candidate links")

    for url in pdf_links:
        try:
            r = requests.get(url, cookies=cookies, headers=headers, timeout=30)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                with open(RESUME_PATH, "wb") as f:
                    f.write(r.content)
                log(f"  Resume downloaded OK: {RESUME_PATH}")
                downloaded = True
                break
            else:
                log(f"  Skipped (not a real PDF): {url[:60]}")
        except Exception as e:
            log(f"  Error: {e}")

    if not downloaded:
        print("\n" + "="*55)
        print("  Auto download failed.")
        print(f"  Please manually copy your resume PDF to:")
        print(f"  {RESUME_PATH}")
        print("="*55)
        input("  Press ENTER after placing the file... ")

    return is_valid_pdf(RESUME_PATH)

# ─────────────────────────────────────────────
# STEP 3: EXTRACT SKILLS FROM RESUME
# ─────────────────────────────────────────────
KNOWN_SKILLS = [
    "Python","Java","JavaScript","TypeScript","C++","C#","Go","Rust","PHP","Ruby",
    "React","Angular","Vue","Node.js","Django","Flask","FastAPI","Spring","Spring Boot",
    "HTML","CSS","SQL","MySQL","PostgreSQL","MongoDB","Redis","SQLite","Oracle",
    "AWS","Azure","GCP","Docker","Kubernetes","Terraform","Jenkins","GitHub Actions",
    "REST API","GraphQL","Microservices","Kafka","RabbitMQ","Elasticsearch",
    "Machine Learning","Deep Learning","NLP","TensorFlow","PyTorch","Scikit-learn",
    "Selenium","Playwright","Pytest","JUnit","Pandas","NumPy","Spark","Hadoop",
    "Linux","Git","Agile","Scrum","DevOps","Data Analysis","Power BI","Tableau",
    "Android","iOS","Flutter","React Native","Kotlin","Swift",
    "Manual Testing","Automation Testing","JIRA","TestNG","Appium","Postman",
    "API Testing","Performance Testing","Load Testing","Regression Testing",
    "SDLC","STLC","Bug Tracking","Test Cases","UFT","QTP","Cucumber","BDD",
]

def extract_skills_from_resume(path):
    log(f"Reading resume PDF: {path}")
    text = ""
    applicant_name = "Unknown"
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "")
        log(f"  Resume text: {len(text)} chars")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            applicant_name = lines[0]
    except Exception as e:
        log(f"  Could not read PDF: {e}")
        return [], applicant_name

    found = []
    tl = text.lower()
    for skill in KNOWN_SKILLS:
        if skill.lower() in tl and skill not in found:
            found.append(skill)

    log(f"  Skills extracted ({len(found)}): {found}")
    return found, applicant_name

# ─────────────────────────────────────────────
# STEP 4: ASK PREFERRED SKILLS IN CMD
# ─────────────────────────────────────────────
def ask_preferred_skills(resume_skills):
    print("\n" + "="*55)
    print("  Resume lo detected skills:")
    print(f"  {', '.join(resume_skills) if resume_skills else 'None found'}")
    print("="*55)
    print("\n  Preferred skills enter cheyyi (comma separated)")
    print("  Example: Manual Testing, Selenium, JIRA")
    print("  (Empty leave cheste resume skills use avutayi)")
    user_input = input(">>> Preferred Skills: ").strip()

    preferred = [s.strip() for s in user_input.split(",") if s.strip()] if user_input else []
    combined  = list(dict.fromkeys(preferred + resume_skills))

    print(f"\n  Skills to search: {combined}")
    print("="*55 + "\n")
    return preferred, combined

# ─────────────────────────────────────────────
# STEP 5: SCRAPE JOB LISTINGS
# ─────────────────────────────────────────────
def scrape_jobs(driver, skills, max_pages=MAX_PAGES):
    all_jobs = {}
    keyword  = quote_plus(" ".join(skills[:3]))

    for page_num in range(1, max_pages + 1):
        url = f"https://www.naukri.com/jobs-in-india?k={keyword}&experience=0&pageNo={page_num}"
        log(f"Scraping page {page_num}: {url}")
        driver.get(url)
        time.sleep(4)

        cards = driver.find_elements(By.CSS_SELECTOR,
            ".srp-jobtuple-wrapper, article.jobTuple")
        log(f"  Cards: {len(cards)}")
        if not cards:
            break

        for card in cards:
            try:
                title_el = card.find_element(By.CSS_SELECTOR, "a.title, a.jobTitle")
                title    = title_el.text.strip()
                link     = title_el.get_attribute("href")

                try:
                    company = card.find_element(
                        By.CSS_SELECTOR, ".comp-name, .companyInfo a").text.strip()
                except:
                    company = "Unknown"

                try:
                    location = card.find_element(
                        By.CSS_SELECTOR, ".locWdth, .location").text.strip()
                except:
                    location = "N/A"

                # Detect external apply jobs
                try:
                    card.find_element(By.CSS_SELECTOR,
                        "#company-site-button, .company-site-button, [id*='company-site']")
                    apply_type = "external"
                except:
                    apply_type = "naukri"

                job_id = link.split("-")[-1].split("?")[0] if link else title
                if job_id not in all_jobs:
                    all_jobs[job_id] = {
                        "id": job_id, "title": title, "company": company,
                        "location": location, "link": link, "apply_type": apply_type,
                    }
            except:
                continue

        log(f"  Page {page_num} done | Total: {len(all_jobs)}")

    log(f"Total unique jobs: {len(all_jobs)}")
    return all_jobs

# ─────────────────────────────────────────────
# STEP 6: APPLY (FIXED - JS click, close popups)
# ─────────────────────────────────────────────
def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def scroll_to_center(driver, element):
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center',inline:'center'});", element)
    time.sleep(0.8)

def close_popups(driver):
    # Close search overlay / any popup that intercepts clicks
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.4)
    except:
        pass
    for sel in ["button[class*='close']", "span[class*='close']",
                 ".nI-gNb-sb__placeholder"]:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    js_click(driver, el)
                    time.sleep(0.2)
        except:
            pass

def apply_to_job(driver, job):
    if job.get("apply_type") == "external":
        return False, "External company site — skipped"

    try:
        driver.get(job["link"])
        time.sleep(3)

        close_popups(driver)
        time.sleep(0.5)

        # Find Naukri apply button (NOT company-site-button)
        apply_btn = None
        try:
            apply_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "apply-button"))
            )
        except:
            pass

        if not apply_btn:
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                txt = btn.text.strip().lower()
                bid = (btn.get_attribute("id") or "").lower()
                cls = (btn.get_attribute("class") or "").lower()
                if "apply" in txt and "company-site" not in bid and "company-site" not in cls:
                    apply_btn = btn
                    break

        if not apply_btn:
            return False, "Apply button not found"

        # KEY FIX: scroll to center + JS click (bypasses navbar intercept)
        scroll_to_center(driver, apply_btn)
        js_click(driver, apply_btn)
        time.sleep(2)

        # Handle confirmation popup
        try:
            confirm = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[contains(text(),'Apply') or contains(text(),'Submit')]"))
            )
            js_click(driver, confirm)
            time.sleep(1)
        except:
            pass

        return True, "Applied"

    except Exception as e:
        return False, str(e).split("\n")[0][:120]

# ─────────────────────────────────────────────
# STEP 7: HTML REPORT
# ─────────────────────────────────────────────
def generate_report(session_data):
    ts      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = session_data["results"]
    total   = len(results)
    applied = sum(1 for r in results if r["status"] == "Applied")
    skipped = sum(1 for r in results if r["status"] == "Skipped")
    ext_sk  = sum(1 for r in results if r["status"] == "External-Skip")
    failed  = total - applied - skipped - ext_sk

    rows = ""
    for i, r in enumerate(results, 1):
        color = {"Applied":"#22c55e","Skipped":"#f59e0b",
                 "External-Skip":"#64748b"}.get(r["status"],"#ef4444")
        rows += f"""
        <tr>
          <td>{i}</td>
          <td><a href="{r.get('link','#')}" target="_blank">{r['title']}</a></td>
          <td>{r['company']}</td><td>{r['location']}</td>
          <td><span style="background:{color};color:#fff;padding:3px 12px;
              border-radius:20px;font-size:12px">{r['status']}</span></td>
          <td style="color:#94a3b8;font-size:12px">{r.get('reason','')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>Naukri Auto Apply Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:32px}}
h1{{font-size:26px;color:#38bdf8;margin-bottom:4px}}
.sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
.cards{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
.card{{background:#1e293b;border-radius:12px;padding:18px 24px;min-width:130px}}
.card .num{{font-size:34px;font-weight:700}}
.card .lbl{{font-size:12px;color:#94a3b8;margin-top:4px}}
.green{{color:#22c55e}}.amber{{color:#f59e0b}}.red{{color:#ef4444}}
.blue{{color:#38bdf8}}.gray{{color:#64748b}}
.skills{{background:#1e293b;border-radius:10px;padding:12px 18px;margin-bottom:24px}}
.skills span{{display:inline-block;background:#0f3460;color:#38bdf8;
    border-radius:20px;padding:3px 12px;margin:3px;font-size:12px}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}}
th{{background:#0f2744;color:#94a3b8;padding:11px 14px;text-align:left;font-size:12px}}
td{{padding:10px 14px;font-size:13px;border-bottom:1px solid #0f172a}}
tr:hover td{{background:#1a3050}}
a{{color:#38bdf8;text-decoration:none}}
a:hover{{text-decoration:underline}}
.footer{{margin-top:24px;color:#475569;font-size:11px;text-align:center}}
</style></head><body>
<h1>🚀 Naukri Auto Apply Report</h1>
<div class="sub">Generated: {ts} &nbsp;|&nbsp; Applicant: {session_data['applicant_name']}</div>
<div class="cards">
  <div class="card"><div class="num blue">{total}</div><div class="lbl">Total</div></div>
  <div class="card"><div class="num green">{applied}</div><div class="lbl">✅ Applied</div></div>
  <div class="card"><div class="num amber">{skipped}</div><div class="lbl">⏭ Already Applied</div></div>
  <div class="card"><div class="num gray">{ext_sk}</div><div class="lbl">🌐 External Site</div></div>
  <div class="card"><div class="num red">{failed}</div><div class="lbl">❌ Failed</div></div>
</div>
<div class="skills"><strong style="color:#94a3b8;font-size:12px">SKILLS SEARCHED</strong><br/>
{''.join(f'<span>{s}</span>' for s in session_data['skills_used'])}
</div>
<table><thead>
  <tr><th>#</th><th>Job Title</th><th>Company</th><th>Location</th><th>Status</th><th>Note</th></tr>
</thead><tbody>{rows}</tbody></table>
<div class="footer">Naukri Auto Apply Bot &mdash; {ts}</div>
</body></html>"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Report saved: {REPORT_FILE}")
    print(f"\n  📊 Report ready — open in browser:\n  {REPORT_FILE}\n")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("     NAUKRI AUTO APPLY BOT  v2 (Fixed)")
    print("="*55)

    session_results = []
    applied_log     = load_applied_log()
    applicant_name  = "Unknown"
    resume_skills   = []

    driver = launch_browser()

    try:
        manual_login(driver)

        resume_ok = download_resume(driver)

        if resume_ok:
            resume_skills, applicant_name = extract_skills_from_resume(RESUME_PATH)
            print(f"\n>>> Applicant Detected: {applicant_name}")
        else:
            log("Resume unavailable — using preferred skills only")

        preferred_skills, combined_skills = ask_preferred_skills(resume_skills)

        if not combined_skills:
            log("No skills provided. Exiting.")
            return

        jobs = scrape_jobs(driver, combined_skills)
        if not jobs:
            log("No jobs found. Exiting.")
            return

        naukri_jobs   = {k:v for k,v in jobs.items() if v["apply_type"]=="naukri"}
        external_jobs = {k:v for k,v in jobs.items() if v["apply_type"]=="external"}

        log(f"Breakdown: {len(naukri_jobs)} Naukri | {len(external_jobs)} External (skip)")
        print(f"\n>>> {len(jobs)} jobs found. Applying to {len(naukri_jobs)} Naukri jobs...\n")

        for job in external_jobs.values():
            session_results.append({**job, "status":"External-Skip",
                                    "reason":"Apply on company site"})

        applied_count = 0
        for idx, (job_id, job) in enumerate(list(naukri_jobs.items())[:MAX_APPLY], 1):
            prefix = f"[{idx}/{len(naukri_jobs)}]"

            if job_id in applied_log:
                log(f"{prefix} SKIP: {job['title']} @ {job['company']}")
                session_results.append({**job,"status":"Skipped","reason":"Already applied"})
                continue

            log(f"{prefix} Applying: {job['title']} @ {job['company']}")
            success, reason = apply_to_job(driver, job)
            status = "Applied" if success else "Failed"
            session_results.append({**job,"status":status,"reason":reason})

            if success:
                applied_log[job_id] = {
                    "title": job["title"], "company": job["company"],
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                save_applied_log(applied_log)
                applied_count += 1
                log(f"  ✅ Applied!")
            else:
                log(f"  ❌ Failed: {reason}")

            time.sleep(APPLY_DELAY)

        log(f"\nDone! Applied: {applied_count} / {len(naukri_jobs)}")

    except KeyboardInterrupt:
        log("Stopped by user (Ctrl+C).")
    finally:
        generate_report({
            "applicant_name": applicant_name,
            "skills_used": combined_skills if 'combined_skills' in dir() else [],
            "results": session_results,
        })
        driver.quit()
        log("Browser closed. ✅")

if __name__ == "__main__":
    main()
