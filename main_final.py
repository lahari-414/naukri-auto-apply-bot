
import os, time, glob, re, csv, threading, json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pdfplumber


DOWNLOAD_DIR = os.path.abspath("downloads")
REPORTS_DIR  = os.path.abspath("reports")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR,  exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

SKILLS_DICT = {
    "Python","Java","JavaScript","TypeScript","C++","C#","Go","Rust",
    "Kotlin","Swift","Ruby","PHP","Scala","MATLAB","Perl","Shell","Bash",
    "HTML","CSS","React","Angular","Vue","Next.js","jQuery","Bootstrap",
    "Tailwind","Redux","GraphQL","REST","Node.js","Express","Django","Flask",
    "FastAPI","Spring Boot","Spring","Laravel","Rails","ASP.NET",".NET",
    "MySQL","PostgreSQL","SQLite","MongoDB","Redis","Cassandra","DynamoDB",
    "Oracle","SQL Server","Firebase","Elasticsearch","MariaDB",
    "AWS","Azure","GCP","Docker","Kubernetes","Terraform","Ansible","Jenkins",
    "GitHub Actions","CI/CD","Linux","Nginx","Heroku","Vercel",
    "Machine Learning","Deep Learning","NLP","Computer Vision","TensorFlow",
    "PyTorch","Keras","Scikit-learn","Pandas","NumPy","Matplotlib","Spark",
    "Hadoop","Kafka","Power BI","Tableau","Data Analysis","Data Science",
    "LLM","Generative AI","LangChain","OpenCV",
    "Git","GitHub","GitLab","Jira","Postman","Agile","Scrum","Microservices",
    "OOP","Android","iOS","Flutter","React Native",
    "Selenium","Playwright","Excel","SAP","Salesforce","Blockchain","Solidity",
}

_SKIP_WORDS = [
    "yrs","year","lakh","apply","login","register","salary","experience",
    "hyderabad","bengaluru","bangalore","mumbai","delhi","pune","chennai",
    "kolkata","noida","gurugram","remote","hybrid","india","worldwide",
    "full time","part time","contract","fresher","intern","job","jobs",
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def _is_bad_company(txt):
    tl = txt.lower()
    return any(w in tl for w in _SKIP_WORDS) or len(txt) < 2


# ─────────────────────────────────────────────────────────────────────────────
# NAME DETECTION (reads from resume PDF)
# ─────────────────────────────────────────────────────────────────────────────

def get_name_from_resume_pdf(pdf_path: str) -> str:
    log(f"Extracting name from resume PDF: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return ""
            first_page_text = pdf.pages[0].extract_text() or ""

        lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]

        for line in lines[:8]:
            if any(c in line for c in ["@", "http", "www", "+91", "linkedin"]):
                continue
            if re.search(r'\d', line):
                continue
            if re.search(r'[^A-Za-z\s.\-]', line):
                continue

            words = line.split()
            if not (2 <= len(words) <= 5):
                continue
            if any(len(w) < 2 for w in words):
                continue

            is_title = all(w[0].isupper() for w in words if w.isalpha())
            is_caps  = line.isupper()
            if not (is_title or is_caps):
                continue

            SKIP = {
                "resume","curriculum","vitae","cv","profile","summary",
                "objective","contact","information","details","education",
                "experience","skills","projects","certifications","hobbies",
                "references","address","email","phone","mobile","linkedin",
                "github","portfolio","developer","engineer","analyst",
                "manager","intern","student","graduate","fresher",
            }
            if any(w.lower() in SKIP for w in words):
                continue

            name = " ".join(w.capitalize() for w in words)
            log(f"  Name from resume: {name}")
            return name

    except Exception as e:
        log(f"  Resume name extraction failed: {e}")

    return ""


def detect_applicant_name(pdf_path: str = "") -> str:
    if pdf_path and os.path.exists(pdf_path):
        name = get_name_from_resume_pdf(pdf_path)
        if name:
            log(f"Applicant name (from resume PDF): {name}")
            return name
    log("Name not found in resume. Using fallback.")
    return "Naukri_User"


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────────────────────────────────────────

def launch_browser():
    log("Launching Chrome...")
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    })
    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    log("Browser launched OK")
    return driver


# ─────────────────────────────────────────────────────────────────────────────
# POPUP WATCHER
# ─────────────────────────────────────────────────────────────────────────────

_stop_watcher = False

def start_popup_watcher(driver):
    global _stop_watcher
    _stop_watcher = False

    CLOSE_CSS = [
        "[class*='crossIcon']","[class*='cross-icon']",
        "[class*='closeIcon']","[class*='close-icon']",
        "[class*='popupClose']","[class*='modalClose']",
        "[class*='closeButton']","[class*='naukModalClose']",
        "button.close","span.close",
        "[aria-label='Close']","[aria-label='close']","[title='Close']",
    ]

    def _watch():
        while not _stop_watcher:
            try:
                for sel in CLOSE_CSS:
                    try:
                        for el in driver.find_elements(By.CSS_SELECTOR, sel):
                            if el.is_displayed():
                                driver.execute_script("arguments[0].click();", el)
                                time.sleep(0.2)
                    except Exception:
                        pass
                try:
                    for el in driver.find_elements(By.XPATH,
                        "//button[normalize-space(text())='×' or normalize-space(text())='x' "
                        "or normalize-space(text())='X'] | "
                        "//span[normalize-space(text())='×' or normalize-space(text())='x']"):
                        if el.is_displayed():
                            driver.execute_script("arguments[0].click();", el)
                except Exception:
                    pass
                try:
                    driver.execute_script("""
                        document.querySelectorAll('[class*="modal"],[class*="popup"],[class*="naukModal"]')
                        .forEach(function(m){
                            if(!m.offsetParent) return;
                            m.querySelectorAll('[class*="close"],[class*="cross"],[aria-label="Close"]')
                            .forEach(function(b){ if(b.offsetParent) b.click(); });
                        });
                    """)
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.8)

    threading.Thread(target=_watch, daemon=True).start()
    log("Popup watcher started")

def stop_popup_watcher():
    global _stop_watcher
    _stop_watcher = True


# ─────────────────────────────────────────────────────────────────────────────
# RESUME DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

def download_resume(driver):
    log("Starting resume download...")

    for old in glob.glob(f"{DOWNLOAD_DIR}/*.pdf"):
        try:
            os.remove(old)
        except Exception:
            pass

    profile_urls = [
        "https://www.naukri.com/mnjuser/profile",
        "https://www.naukri.com/mnjuser/homepage",
        "https://www.naukri.com/mnjuser/myprofile",
    ]

    for purl in profile_urls:
        log(f"Trying profile URL: {purl}")
        try:
            driver.get(purl)
            time.sleep(4)
            _close_once(driver)
            time.sleep(2)
            log(f"  Loaded: {driver.current_url} | {driver.title}")

            for y in [0, 400, 800, 1200, 800, 400, 0]:
                driver.execute_script(f"window.scrollTo(0,{y})")
                time.sleep(0.3)

            log("  Scanning page for download elements...")
            found_candidates = _scan_download_elements(driver)
            log(f"  Found {len(found_candidates)} candidate elements")

            for info in found_candidates:
                result = _try_click_element(driver, info)
                if result:
                    log(f"Resume downloaded: {result}")
                    return result
        except Exception as e:
            log(f"  Profile URL failed: {e}")
            continue

    return _live_manual_fallback(driver)


def _scan_download_elements(driver):
    candidates = []
    try:
        all_els = driver.find_elements(By.XPATH, "//*")
        for el in all_els:
            try:
                if not el.is_displayed():
                    continue
                tag  = el.tag_name.lower()
                text = (el.text or "").strip().lower()
                cls  = (el.get_attribute("class") or "").lower()
                href = (el.get_attribute("href") or "").lower()

                if "upload" in cls or "update" in text:
                    continue

                if "download" in cls:
                    candidates.insert(0, {"el": el, "tag": tag, "cls": cls,
                                          "text": text[:50], "href": href[:60]})
                    log(f"    HIGH: <{tag}> cls=[{cls[:50]}] text=[{text[:30]}]")
                elif any(k in href for k in [".pdf","download","resume"]):
                    candidates.append({"el": el, "tag": tag, "cls": cls,
                                       "text": text[:50], "href": href[:60]})
                    log(f"    MED:  <{tag}> href=[{href[:50]}]")
                elif "download" in text and tag in ["a","button","span","div"]:
                    candidates.append({"el": el, "tag": tag, "cls": cls,
                                       "text": text[:50], "href": href[:60]})
                    log(f"    LOW:  <{tag}> text=[{text[:50]}]")
            except Exception:
                continue
    except Exception:
        pass
    return candidates


def _try_click_element(driver, info):
    try:
        el = info["el"]
        if not el.is_displayed():
            return None
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.5)
        log(f"  Clicking <{info['tag']}> cls=[{info['cls'][:40]}] text=[{info['text'][:30]}]")
        driver.execute_script("arguments[0].click();", el)
        time.sleep(4)
        pdf = _check_pdf()
        if pdf:
            return pdf
    except Exception as e:
        log(f"  Click failed: {e}")
    return None


def _check_pdf():
    pdfs = [p for p in glob.glob(f"{DOWNLOAD_DIR}/*.pdf")
            if not p.endswith(".crdownload")]
    return max(pdfs, key=os.path.getctime) if pdfs else None


def _close_once(driver):
    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.5)
    except Exception:
        pass
    try:
        driver.execute_script("""
            document.querySelectorAll('[class*="modal"],[class*="popup"],[class*="overlay"]')
            .forEach(m=>{ m.style.display='none'; });
            document.body.style.overflow='auto';
        """)
    except Exception:
        pass
    time.sleep(0.5)


def _live_manual_fallback(driver):
    print("\n" + "="*65)
    print("  RESUME AUTO-DOWNLOAD FAILED")
    print()
    print("  Browser is still open. Please follow these steps:")
    print()
    print("   Open Naukri profile page in Chrome")
    print("     URL: https://www.naukri.com/mnjuser/profile")
    print()
    print("   Scroll to the 'Resume' section on the page")
    print()
    print("   Click the Download icon (↓ arrow)")
    print("     (Do NOT click Upload — click Download)")
    print()
    print(f"   Bot will detect the file automatically")
    print()
    print(f"  Downloads folder: {DOWNLOAD_DIR}")
    print("="*65 + "\n")

    log("Polling for PDF every 3s (up to 5 minutes)...")
    for i in range(100):
        pdf = _check_pdf()
        if pdf:
            log(f"PDF detected automatically: {pdf}")
            return pdf
        if i % 5 == 0:
            log(f"  Still waiting... {i*3}s.")
        time.sleep(3)

    print("\n  5 minutes passed, PDF still not found.")
    path = input(f"  Enter full path of resume PDF: ").strip().strip('"')
    if path and os.path.exists(path) and path.lower().endswith(".pdf"):
        return path
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SKILLS EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_skills(pdf_path):
    log(f"Reading resume: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        log(f"Resume text: {len(text)} chars")
    except Exception as e:
        log(f"PDF read error: {e}")
        return []

    found = set()
    tl = text.lower()
    for skill in SKILLS_DICT:
        if len(skill) <= 1:
            continue
        pat = r"(?<![a-zA-Z0-9+#])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9+#])"
        if re.search(pat, tl):
            found.add(skill)

    skills = sorted(found)
    log(f"Skills extracted ({len(skills)}): {skills}")
    return skills


# ─────────────────────────────────────────────────────────────────────────────
# JOB SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search_jobs(driver, skills, max_jobs=20):
    BAD = {"C#","C++","ASP.NET",".NET","CI/CD","Next.js","MATLAB","R"}
    url_skills = [s for s in skills if s not in BAD][:2]
    if not url_skills:
        url_skills = ["software","developer"]

    kw = "+".join(
        s.lower().replace(" ","+").replace(".","").replace("/","")
         .replace("#","sharp").replace("+","plus")
        for s in url_skills
    )

    search_url = f"https://www.naukri.com/jobs-in-india?k={kw}&experience=0&sort=1"
    log(f"Searching latest jobs: {search_url}")

    try:
        driver.get(search_url)
    except Exception as e:
        log(f"Navigation error: {e}")
        return []

    time.sleep(5)
    _close_once(driver)
    time.sleep(2)

    all_jobs = []
    for page in range(1, 4):
        log(f"Scraping page {page}...")
        jobs = _scrape_page(driver)
        all_jobs.extend(jobs)
        log(f"  Page {page}: {len(jobs)} | Total: {len(all_jobs)}")
        if len(all_jobs) >= max_jobs or not jobs:
            break
        if not _next_page(driver):
            break
        time.sleep(3)

    seen, unique = set(), []
    for j in all_jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            unique.append(j)

    log(f"Unique jobs: {len(unique)}")
    return unique[:max_jobs]


def _scrape_page(driver):
    jobs = []
    time.sleep(2)
    driver.execute_script("window.scrollTo(0,document.body.scrollHeight/2)")
    time.sleep(1)

    cards = []
    for sel in [
        "article.jobTuple",".srp-jobtuple-wrapper","div.jobTuple",
        ".cust-job-tuple","article[class*='job']","div[class*='jobTuple']",
        "[class*='jobCard']","[class*='job-card']",
    ]:
        cards = driver.find_elements(By.CSS_SELECTOR, sel)
        if cards:
            log(f"  Cards [{sel}]: {len(cards)}")
            break

    if not cards:
        log("  No cards — trying direct link scrape...")
        try:
            links = driver.find_elements(By.XPATH,
                "//a[contains(@href,'/job-listings-') or contains(@href,'-jobs-in-')]")
            for lnk in links:
                href = lnk.get_attribute("href") or ""
                title = lnk.text.strip()
                if href and title and "naukri.com" in href and len(title) > 5:
                    jobs.append({"title": title[:100], "company": "",
                                 "location": "N/A", "experience": "N/A", "url": href})
        except Exception:
            pass
        return jobs

    for card in cards:
        try:
            title, url = "", ""
            for sel in ["a.title","a.jobTitle","a[class*='title']","h3 a","h2 a"]:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    t = el.text.strip()
                    u = el.get_attribute("href") or ""
                    if t and u and "naukri.com" in u:
                        title, url = t, u
                        break
                except Exception:
                    continue
            if not title or not url:
                continue

            def get(sels):
                for s in sels:
                    try:
                        v = card.find_element(By.CSS_SELECTOR, s).text.strip()
                        if v: return v
                    except Exception:
                        pass
                return "N/A"

            company_card = get([
                "a.comp-name", ".comp-name",
                "[class*='compName']", "[class*='companyName']",
                "[class*='company-name']", "a.subTitle",
                "a.companyName", "[class*='company']",
            ])

            jobs.append({
                "title":      title,
                "company":    company_card,
                "location":   get([".locWdth","[class*='location']","[class*='loc']"]),
                "experience": get([".expwdth","[class*='experience']","[class*='exp']"]),
                "url":        url,
            })
        except Exception:
            continue
    return jobs


def _next_page(driver):
    for sel in ["a[class*='next']","a[title='Next']","[class*='pagination'] a:last-child"]:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            if btn.is_enabled() and btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(3)
                return True
        except Exception:
            pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _get_company_from_page(driver):
    css_selectors = [
        "a.comp-name", ".comp-name", "[class*='companyName']",
        "[class*='comp-name']", "[class*='CompanyName']",
        "[class*='company-name']", ".jd-header-comp-name",
        "a[class*='company']", "[class*='compName']", "[class*='orgName']",
        "[class*='styles_comp']", "[class*='comp_info']",
        "a[data-ga-track*='company']",
    ]
    for sel in css_selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                txt = el.text.strip()
                if txt and not _is_bad_company(txt):
                    log(f"    Company [CSS:{sel}] => {txt}")
                    return txt
        except Exception:
            continue

    xpaths = [
        "//a[contains(@class,'comp-name')]",
        "//a[contains(@class,'company')]",
        "//*[contains(@class,'companyName')]",
        "//*[contains(@class,'comp-name')]",
        "//div[contains(@class,'jd-header')]//a",
        "//div[contains(@class,'job-header')]//a",
    ]
    for xp in xpaths:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                txt = el.text.strip()
                if txt and not _is_bad_company(txt):
                    log(f"    Company [XPath] => {txt}")
                    return txt
        except Exception:
            continue

    try:
        scripts = driver.find_elements(By.XPATH,
            "//script[@type='application/ld+json']")
        for script in scripts:
            content = script.get_attribute("innerHTML") or ""
            if "hiringOrganization" in content:
                data = json.loads(content)
                if isinstance(data, dict):
                    org = data.get("hiringOrganization", {})
                    if isinstance(org, dict) and org.get("name"):
                        name = org["name"].strip()
                        if name and not _is_bad_company(name):
                            log(f"    Company [JSON-LD] => {name}")
                            return name
    except Exception:
        pass

    return "N/A"


# ─────────────────────────────────────────────────────────────────────────────
# APPLY
# ─────────────────────────────────────────────────────────────────────────────

def apply_to_jobs(driver, job_listings):
    results = []
    total = len(job_listings)
    for idx, job in enumerate(job_listings, 1):
        log(f"\n[{idx}/{total}] {job['title']} @ {job.get('company') or '?'}")
        status, note, company = _apply_one(driver, job["url"], job.get("company",""))
        log(f"  => {status} | Company: {company}")
        results.append({
            **job,
            "company":    company,
            "status":     status,
            "note":       note,
            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        time.sleep(2)
    return results


def _apply_one(driver, url, company_card=""):
    """Returns (status, note, company_name)."""
    company = company_card
    try:
        driver.get(url)
        time.sleep(4)
        _close_once(driver)
        time.sleep(1)

        fetched = _get_company_from_page(driver)
        if fetched and fetched != "N/A":
            company = fetched
        elif not company or company == "N/A":
            company = "N/A"

        for xp in [
            "//button[contains(normalize-space(.),'Applied')]",
            "//*[contains(normalize-space(.),'already applied')]",
            "//*[contains(normalize-space(.),'Application submitted')]",
        ]:
            try:
                if driver.find_element(By.XPATH, xp).is_displayed():
                    return "already_applied", "Previously applied", company
            except Exception:
                pass

        apply_btn = None
        for xp in [
            "//button[normalize-space(.)='Apply' or normalize-space(.)='Apply Now']",
            "//button[contains(normalize-space(.),'Apply') and not(contains(normalize-space(.),'Applied'))]",
            "//a[contains(normalize-space(.),'Apply') and not(contains(normalize-space(.),'Applied'))]",
            "//button[@id='apply-button']",
            "//*[contains(@class,'applyBtn') and not(contains(@class,'applied'))]",
            "//*[contains(@class,'apply-button')]",
        ]:
            try:
                apply_btn = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                break
            except Exception:
                pass

        if not apply_btn:
            return "failed", "Apply button not found", company

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", apply_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", apply_btn)
        time.sleep(3)

        if "naukri.com" not in driver.current_url:
            driver.back()
            return "external", f"External: {driver.current_url[:80]}", company

        status, note = _handle_flow(driver)
        return status, note, company

    except Exception as e:
        return "failed", str(e)[:100], company


def _handle_flow(driver):
    for attempt in range(10):
        time.sleep(1.5)
        for xp in [
            "//div[contains(normalize-space(.),'successfully applied')]",
            "//div[contains(normalize-space(.),'Application submitted')]",
        ]:
            try:
                if driver.find_element(By.XPATH, xp).is_displayed():
                    try:
                        driver.find_element(By.XPATH,
                            "//*[contains(@class,'close') or normalize-space(.)='Close']"
                        ).click()
                    except Exception:
                        pass
                    return "applied", "Submitted successfully"
            except Exception:
                pass
        clicked = False
        for label in ["Submit","Confirm","Apply Now","Apply","Continue","Next","Done"]:
            try:
                btn = driver.find_element(By.XPATH,
                    f"//button[contains(normalize-space(.),'{label}')]")
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                    clicked = True
                    break
            except Exception:
                pass
        if attempt >= 5 and not clicked:
            return "applied", "Apply flow completed"
    return "applied", "Apply flow completed"


# ─────────────────────────────────────────────────────────────────────────────
# REPORT  ← KEY CHANGE: filename now uses applicant name instead of timestamp
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(applied_jobs, skills, applicant_name="Naukri_User"):
    # Build a filename-safe version of the applicant's name (e.g. "Lahari Reddy" → "Lahari_Reddy")
    safe_name = re.sub(r'[^A-Za-z0-9_]', '_', applicant_name.strip().replace(" ", "_"))

    # Files named as: Lahari_Reddy.csv / Lahari_Reddy.html
    # If a file with this name already exists, append timestamp to avoid overwrite
    base_csv  = os.path.join(REPORTS_DIR, f"{safe_name}.csv")
    base_html = os.path.join(REPORTS_DIR, f"{safe_name}.html")
    if os.path.exists(base_csv) or os.path.exists(base_html):
        csv_path  = os.path.join(REPORTS_DIR, f"{safe_name}_{TIMESTAMP}.csv")
        html_path = os.path.join(REPORTS_DIR, f"{safe_name}_{TIMESTAMP}.html")
    else:
        csv_path  = base_csv
        html_path = base_html

    fields = ["title","company","location","experience",
              "status","note","applied_at","url"]
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(applied_jobs)

    total    = len(applied_jobs)
    applied  = sum(1 for j in applied_jobs if j["status"]=="applied")
    already  = sum(1 for j in applied_jobs if j["status"]=="already_applied")
    external = sum(1 for j in applied_jobs if j["status"]=="external")
    failed   = sum(1 for j in applied_jobs if j["status"]=="failed")

    rows = ""
    for j in applied_jobs:
        if j["status"] == "failed":
            continue
        badge = {
            "applied":         "badge-applied",
            "already_applied": "badge-already",
            "external":        "badge-external",
        }.get(j["status"], "badge-applied")

        t = j["title"].replace("<","&lt;").replace(">","&gt;")
        c = (j.get("company") or "N/A").replace("<","&lt;").replace(">","&gt;")

        rows += f"""<tr>
            <td><a href="{j['url']}" target="_blank">{t}</a></td>
            <td><strong>{c}</strong></td>
            <td>{j['location']}</td>
            <td>{j['experience']}</td>
            <td><span class="badge {badge}">{j['status'].replace('_',' ').title()}</span></td>
            <td>{j['note']}</td>
            <td>{j['applied_at']}</td>
        </tr>"""

    stags = "".join(f'<span class="stag">{s}</span>' for s in skills)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Naukri Auto-Apply Report — {applicant_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#ffffff;color:#1e293b;padding:32px 24px}}
  .wrap{{max-width:1260px;margin:0 auto}}
  h1{{font-size:1.8rem;color:#16a34a;margin-bottom:6px}}
  .applicant-line{{font-size:.92rem;color:#64748b;margin-bottom:4px}}
  .applicant-line strong{{color:#2563eb;font-weight:600}}
  .sub{{color:#64748b;font-size:.85rem;margin-bottom:30px}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:26px}}
  .stat{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:18px;text-align:center}}
  .num{{font-size:2.2rem;font-weight:700}}
  .lbl{{color:#94a3b8;font-size:.72rem;text-transform:uppercase;margin-top:4px;letter-spacing:.05em}}
  .c1{{color:#2563eb}}.c2{{color:#16a34a}}.c3{{color:#d97706}}.c4{{color:#7c3aed}}.c5{{color:#dc2626}}
  .sk{{margin-bottom:22px}}
  .sk-t{{font-size:.72rem;text-transform:uppercase;color:#64748b;margin-bottom:8px;letter-spacing:.05em}}
  .stag{{display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;color:#2563eb;
         font-size:.78rem;padding:3px 11px;border-radius:20px;margin:3px}}
  .tw{{overflow-x:auto;border-radius:12px;border:1px solid #e2e8f0;
       box-shadow:0 1px 6px rgba(0,0,0,.06)}}
  table{{width:100%;border-collapse:collapse;font-size:.84rem}}
  thead tr{{background:#f1f5f9}}
  th{{padding:12px 14px;text-align:left;color:#475569;font-weight:600;
      text-transform:uppercase;font-size:.7rem;white-space:nowrap;letter-spacing:.04em}}
  tbody tr{{border-top:1px solid #f1f5f9}}
  tbody tr:hover{{background:#f8fafc}}
  td{{padding:11px 14px;vertical-align:middle}}
  td a{{color:#2563eb;text-decoration:none;font-weight:500}}
  td a:hover{{text-decoration:underline}}
  td strong{{color:#0f172a}}
  .badge{{display:inline-block;padding:4px 10px;border-radius:20px;
          font-size:.72rem;font-weight:600;white-space:nowrap}}
  .badge-applied{{background:#dcfce7;color:#15803d}}
  .badge-already{{background:#fef9c3;color:#a16207}}
  .badge-external{{background:#ede9fe;color:#6d28d9}}
  .ft{{margin-top:26px;text-align:center;color:#cbd5e1;font-size:.78rem}}
</style></head><body><div class="wrap">
  <h1>&#x1F4CB; Naukri Auto-Apply Report</h1>
  <div class="applicant-line">Applied by: <strong>{applicant_name}</strong></div>
  <div class="sub">
    Generated: {datetime.now().strftime("%d %b %Y, %I:%M %p")}
    &nbsp;&bull;&nbsp; Jobs sorted by: <strong>Latest First</strong>
  </div>
  <div class="stats">
    <div class="stat"><div class="num c1">{total}</div><div class="lbl">Total</div></div>
    <div class="stat"><div class="num c2">{applied}</div><div class="lbl">Applied</div></div>
    <div class="stat"><div class="num c3">{already}</div><div class="lbl">Already Applied</div></div>
    <div class="stat"><div class="num c4">{external}</div><div class="lbl">External</div></div>
    <div class="stat"><div class="num c5">{failed}</div><div class="lbl">Failed</div></div>
  </div>
  <div class="sk"><div class="sk-t">Skills from Resume</div>{stags}</div>
  <div class="tw"><table>
    <thead><tr>
      <th>Job Title</th>
      <th>Company</th>
      <th>Location</th>
      <th>Exp</th>
      <th>Status</th>
      <th>Note</th>
      <th>Applied At</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <div class="ft">Naukri Auto-Apply Bot &middot; {applicant_name} &middot; {datetime.now().year}</div>
</div></body></html>"""

    with open(html_path,"w",encoding="utf-8") as f:
        f.write(html)

    log(f"CSV  : {csv_path}")
    log(f"HTML : {html_path}")
    print(f"\n>>> Report ready!\n    {html_path}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*65)
    print("  NAUKRI AUTO-APPLY BOT — Final Version")
    print("="*65 + "\n")

    driver = launch_browser()
    start_popup_watcher(driver)

    log("Opening Naukri login...")
    driver.get("https://www.naukri.com/nlogin/login")
    print("\n>>> Login to Naukri in the browser (email + password)")
    input(">>> Press ENTER after login is complete...\n")
    time.sleep(3)

    # Step 1: Download resume
    resume_path = download_resume(driver)

    # Step 2: Extract skills
    skills = []
    if resume_path and os.path.exists(resume_path):
        skills = extract_skills(resume_path)

    if not skills:
        log("Skills not found — using defaults")
        skills = ["Java","Python","Selenium","SQL","Data Analysis"]

    log(f"Skills to search: {skills}")

    # Step 3: Detect applicant name from resume
    applicant_name = detect_applicant_name(resume_path or "")
    print(f"\n>>> Applicant Name Detected: {applicant_name}\n")

    # Step 4: Search jobs
    job_listings = search_jobs(driver, skills, max_jobs=20)
    if not job_listings:
        log("No jobs found. Check internet connection and try again.")

    # Step 5: Apply
    applied_jobs = []
    if job_listings:
        print(f"\n>>> {len(job_listings)} jobs found. Applying now...\n")
        applied_jobs = apply_to_jobs(driver, job_listings)

    # Step 6: Generate report (filename = applicant name + timestamp)
    if applied_jobs:
        generate_report(applied_jobs, skills, applicant_name)
    else:
        log("No applications made.")

    print("\n" + "="*65)
    log(f"Bot done! Reports saved in: {REPORTS_DIR}")
    print("="*65)

    stop_popup_watcher()
    input("\nPress ENTER to close browser")
    driver.quit()


if __name__ == "__main__":
    main()
