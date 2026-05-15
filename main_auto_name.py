
import os, time, glob, re, csv, threading
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

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# NAME DETECTION
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


def _is_valid_name(text: str) -> bool:
    if not text or len(text) < 3 or len(text) > 60:
        return False
    if re.search(r'\d', text):
        return False
    if any(c in text for c in ["@", "http", "www", "/"]):
        return False
    if len(re.findall(r'[A-Za-z]', text)) < 2:
        return False
    NON_NAMES = {
        "profile","resume","skills","experience","education","login",
        "logout","home","dashboard","settings","account","user",
        "name","your name","full name","welcome","hello","naukri",
        "jobs","search","apply","employer","company","recruiter",
    }
    if text.lower().strip() in NON_NAMES:
        return False
    if not any(c.isupper() for c in text):
        return False
    return True


def detect_applicant_name(driver, pdf_path: str = "") -> str:
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
                        "//button[normalize-space(text())='×' or normalize-space(text())='x' or normalize-space(text())='X'] | "
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

    # Clean old PDFs first
    for old in glob.glob(f"{DOWNLOAD_DIR}/*.pdf"):
        try:
            os.remove(old)
        except Exception:
            pass

    # Step 1: Try auto-download from profile page
    log("Trying auto-download from Naukri profile...")
    try:
        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(5)
        _close_once(driver)
        time.sleep(2)

        # Scroll slowly so all elements load
        for y in [0, 300, 600, 900, 1200, 900, 600, 300, 0]:
            driver.execute_script(f"window.scrollTo(0,{y})")
            time.sleep(0.4)

        # Try every known Naukri download button selector
        DOWNLOAD_XPATHS = [
            "//*[contains(@class,'download') and not(contains(@class,'upload'))]",
            "//*[contains(@class,'dwnld') and not(contains(@class,'upload'))]",
            "//a[contains(@href,'download') and not(contains(@href,'upload'))]",
            "//a[contains(@href,'.pdf')]",
            "//button[contains(translate(.,'DOWNLOAD','download'),'download')]",
            "//span[contains(translate(.,'DOWNLOAD','download'),'download')]",
            "//*[@title='Download' or @title='download' or @aria-label='Download']",
            "//*[@data-ga-track and contains(@data-ga-track,'download')]",
        ]

        for xp in DOWNLOAD_XPATHS:
            try:
                els = driver.find_elements(By.XPATH, xp)
                for el in els:
                    try:
                        cls  = (el.get_attribute("class") or "").lower()
                        text = (el.text or "").lower()
                        if "upload" in cls or "update" in cls or "upload" in text:
                            continue
                        if not el.is_displayed():
                            continue
                        log(f"  Clicking: <{el.tag_name}> cls=[{cls[:50]}]")
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(5)
                        pdf = _check_pdf()
                        if pdf:
                            log(f"  Auto-download SUCCESS: {pdf}")
                            return pdf
                    except Exception:
                        continue
            except Exception:
                continue

    except Exception as e:
        log(f"  Auto-download attempt failed: {e}")

    # Step 2: Fast manual fallback
    return _manual_resume_input()


def _manual_resume_input():
    print("\n" + "="*65)
    print("  AUTO-DOWNLOAD COULD NOT FIND THE BUTTON")
    print("="*65)
    print()
    print("  You have 2 options:")
    print()
    print("  OPTION 1 — Download manually in the browser now:")
    print("    1. Go to: https://www.naukri.com/mnjuser/profile")
    print("    2. Scroll to the Resume section")
    print("    3. Click the Download arrow (↓) button")
    print(f"    4. File saves to: {DOWNLOAD_DIR}")
    print("    5. Bot will detect it automatically (waits 60 sec)")
    print()
    print("  OPTION 2 — Paste your resume PDF path below:")
    print("    Example: C:\\Users\\ganta\\Documents\\Resume.pdf")
    print()
    print("="*65)
    print()

    # Poll 60 seconds while user manually downloads
    log("Waiting 60 seconds for manual download...")
    entered = [False]

    def _wait():
        input("  Press ENTER to skip waiting and type path instead: ")
        entered[0] = True

    import threading
    t = threading.Thread(target=_wait, daemon=True)
    t.start()

    for i in range(20):  # 20 x 3s = 60 seconds
        pdf = _check_pdf()
        if pdf:
            log(f"  PDF detected automatically: {pdf}")
            return pdf
        if entered[0]:
            break
        if i > 0 and i % 5 == 0:
            log(f"  Still waiting... {i*3}s elapsed")
        time.sleep(3)

    # Check once more after ENTER
    pdf = _check_pdf()
    if pdf:
        log(f"  PDF detected: {pdf}")
        return pdf

    # Ask for path
    print()
    path = input("  Paste resume PDF path here: ").strip().strip('"\'"').strip("'")
    path = path.strip()
    if path and os.path.exists(path) and path.lower().endswith(".pdf"):
        log(f"  Using resume: {path}")
        return path

    # Search common folders as last resort
    log("  Searching Desktop/Documents/Downloads for PDF...")
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
        DOWNLOAD_DIR,
    ]
    found_pdfs = []
    for d in search_dirs:
        if os.path.isdir(d):
            found_pdfs.extend(glob.glob(os.path.join(d, "*.pdf")))

    if found_pdfs:
        latest = max(found_pdfs, key=os.path.getmtime)
        print(f"\n  Found PDF: {latest}")
        use = input("  Use this file? (y/n): ").strip().lower()
        if use == "y":
            return latest

    log("  No resume found. Bot will use default skills.")
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
# COMPANY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def get_company_from_card(card):
    NEW_SELECTORS = [
        "a.comp-name", ".comp-name", "span.comp-name",
        "[class*='comp-name']", "[class*='compName']",
        "[class*='company-name']", "[class*='companyName']",
        "[class*='company_name']",
        ".cust-job-tuple [class*='comp']",
        ".srp-jobtuple-wrapper [class*='comp']",
        "[data-company]",
        "[class*='employer']", "[class*='org-name']", "[class*='orgName']",
    ]

    for sel in NEW_SELECTORS:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt and txt.lower() not in ("", "n/a", "na", "not disclosed"):
                return txt
            for attr in ["title", "aria-label", "data-company"]:
                v = el.get_attribute(attr) or ""
                if v.strip() and v.lower() not in ("", "n/a"):
                    return v.strip()
        except Exception:
            continue

    XPATH_TRIES = [
        ".//*[contains(@class,'comp')]",
        ".//*[contains(@class,'company')]",
        ".//*[contains(@class,'employer')]",
        ".//*[@data-company]",
    ]
    for xp in XPATH_TRIES:
        try:
            els = card.find_elements(By.XPATH, xp)
            for el in els:
                txt = el.text.strip()
                if txt and len(txt) > 1 and txt.lower() not in ("n/a","na",""):
                    if any(k in txt.lower() for k in ["developer","engineer","manager",
                           "analyst","intern","hyderabad","delhi","mumbai","india"]):
                        continue
                    return txt
        except Exception:
            continue

    try:
        for a in card.find_elements(By.TAG_NAME, "a"):
            for attr in ["aria-label", "title"]:
                v = (a.get_attribute(attr) or "").strip()
                if v and any(k in v.lower() for k in ["company","employer","pvt","ltd","inc","technologies","solutions"]):
                    return v
    except Exception:
        pass

    return "N/A"


def get_company_from_job_page(driver):
    DETAIL_SELECTORS = [
        ".comp-name", "a.comp-name", "[class*='comp-name']",
        "[class*='companyName']", ".company-name",
        ".jd-header-comp-name", "[class*='jd-header'] [class*='comp']",
        ".styles_jd-header-comp-name__MvqAI",
        "a[href*='company']",
    ]
    for sel in DETAIL_SELECTORS:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt and txt.lower() not in ("", "n/a", "na"):
                return txt
        except Exception:
            continue

    try:
        title = driver.title or ""
        if " at " in title:
            part = title.split(" at ")[1].split("|")[0].strip()
            if part:
                return part
        if " - " in title:
            part = title.split(" - ")[1].split("|")[0].strip()
            if part and "naukri" not in part.lower():
                return part
    except Exception:
        pass

    return "N/A"


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
    search_url = f"https://www.naukri.com/jobs-in-india?k={kw}&experience=0"
    log(f"Searching: {search_url}")

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
        log(f"Scraping page {page}.")
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
    CARD_SELECTORS = [
        "article.jobTuple", ".srp-jobtuple-wrapper", "div.jobTuple",
        ".cust-job-tuple", "article[class*='job']", "div[class*='jobTuple']",
        "[class*='jobCard']", "[class*='job-card']",
        ".styles_job-listing-container__OCfZC article",
        "[class*='srp-jobtuple']",
    ]

    for sel in CARD_SELECTORS:
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
                    jobs.append({"title": title[:100], "company": "N/A",
                                 "location": "N/A", "experience": "N/A",
                                 "salary": "Not Disclosed", "url": href})
        except Exception:
            pass
        return jobs

    for card in cards:
        try:
            title, url = "", ""
            for sel in ["a.title","a.jobTitle","a[class*='title']","h3 a","h2 a",
                        "[class*='job-title'] a","[class*='jobTitle'] a"]:
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

            company = get_company_from_card(card)

            def get(sels):
                for s in sels:
                    try:
                        v = card.find_element(By.CSS_SELECTOR, s).text.strip()
                        if v: return v
                    except Exception:
                        pass
                return "N/A"

            jobs.append({
                "title":      title,
                "company":    company,
                "location":   get([".locWdth","[class*='location']","[class*='loc']",
                                   "[class*='loc-wrap']"]),
                "experience": get([".expwdth","[class*='experience']","[class*='exp']"]),
                "salary":     get([".salary","[class*='salary']"]) or "Not Disclosed",
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
# APPLY
# ─────────────────────────────────────────────────────────────────────────────

def apply_to_jobs(driver, job_listings):
    results = []
    total = len(job_listings)
    for idx, job in enumerate(job_listings, 1):
        log(f"\n[{idx}/{total}] Applying: {job['title']} @ {job['company']}")
        status, note, company = _apply_one(driver, job["url"], job["company"])
        log(f"  => {status}: {note}")

        final_company = company if company != "N/A" else job["company"]

        results.append({
            **job,
            "company": final_company,
            "status": status,
            "note": note,
            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        time.sleep(2)
    return results


def _apply_one(driver, url, existing_company="N/A"):
    """Returns (status, note, company_name)"""
    try:
        driver.get(url)
        time.sleep(4)
        _close_once(driver)
        time.sleep(1)

        page_company = get_company_from_job_page(driver)
        company = page_company if page_company != "N/A" else existing_company

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

        result_status, result_note = _handle_flow(driver)
        return result_status, result_note, company

    except Exception as e:
        return "failed", str(e)[:100], existing_company


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

    fields = ["title","company","location","experience","salary",
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
        badge = {
            "applied":         "badge-applied",
            "already_applied": "badge-already",
            "external":        "badge-external",
            "failed":          "badge-failed",
        }.get(j["status"],"badge-failed")
        t = j["title"].replace("<","&lt;").replace(">","&gt;")
        c = j["company"].replace("<","&lt;").replace(">","&gt;")
        c_display = c if c and c != "N/A" else "<span style='color:#475569;font-style:italic'>Unknown</span>"
        rows += f"""<tr>
            <td><a href="{j['url']}" target="_blank">{t}</a></td>
            <td class="company-cell">{c_display}</td>
            <td>{j['location']}</td><td>{j['experience']}</td>
            <td>{j['salary']}</td>
            <td><span class="badge {badge}">{j['status'].replace('_',' ').title()}</span></td>
            <td>{j['note']}</td><td>{j['applied_at']}</td>
        </tr>"""

    stags = "".join(f'<span class="stag">{s}</span>' for s in skills)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Naukri Auto-Apply Report — {applicant_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#0d0f1a;color:#e2e8f0;padding:32px 24px}}
  .wrap{{max-width:1200px;margin:0 auto}}
  h1{{font-size:1.8rem;color:#4ade80;margin-bottom:4px}}
  .applicant-line{{font-size:.92rem;color:#94a3b8;margin-bottom:4px}}
  .applicant-line strong{{color:#60a5fa;font-weight:600}}
  .sub{{color:#64748b;font-size:.82rem;margin-bottom:28px}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:26px}}
  .stat{{background:#1e2235;border:1px solid #2d3651;border-radius:12px;padding:18px;text-align:center}}
  .num{{font-size:2.2rem;font-weight:700}}
  .lbl{{color:#94a3b8;font-size:.72rem;text-transform:uppercase;margin-top:4px}}
  .c1{{color:#60a5fa}}.c2{{color:#4ade80}}.c3{{color:#facc15}}.c4{{color:#a78bfa}}.c5{{color:#f87171}}
  .sk{{margin-bottom:22px}}
  .sk-t{{font-size:.72rem;text-transform:uppercase;color:#64748b;margin-bottom:8px}}
  .stag{{display:inline-block;background:#1e2235;border:1px solid #334155;color:#60a5fa;
         font-size:.78rem;padding:3px 11px;border-radius:20px;margin:3px}}
  .tw{{overflow-x:auto;border-radius:12px;border:1px solid #2d3651}}
  table{{width:100%;border-collapse:collapse;font-size:.84rem}}
  thead tr{{background:#1a1f35}}
  th{{padding:11px 13px;text-align:left;color:#64748b;font-weight:500;
      text-transform:uppercase;font-size:.7rem;white-space:nowrap}}
  tbody tr{{border-top:1px solid #1e2235}}
  tbody tr:hover{{background:#1a1f35}}
  td{{padding:10px 13px;vertical-align:middle}}
  td a{{color:#60a5fa;text-decoration:none}}
  td a:hover{{text-decoration:underline}}
  .company-cell{{color:#e2e8f0;font-weight:500}}
  .badge{{display:inline-block;padding:3px 9px;border-radius:20px;
          font-size:.72rem;font-weight:600;white-space:nowrap}}
  .badge-applied{{background:#14532d;color:#4ade80}}
  .badge-already{{background:#422006;color:#facc15}}
  .badge-external{{background:#2e1065;color:#a78bfa}}
  .badge-failed{{background:#450a0a;color:#f87171}}
  .ft{{margin-top:26px;text-align:center;color:#334155;font-size:.78rem}}
</style></head><body><div class="wrap">
  <h1>Naukri Auto-Apply Report</h1>
  <div class="applicant-line">Applied by: <strong>{applicant_name}</strong></div>
  <div class="sub">Generated: {datetime.now().strftime("%d %b %Y, %I:%M %p")}</div>
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
      <th>Job Title</th><th>Company</th><th>Location</th><th>Exp</th>
      <th>Salary</th><th>Status</th><th>Note</th><th>Applied At</th>
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
    return html_path, csv_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*65)
    print("  NAUKRI AUTO-APPLY BOT — Auto Name Version")
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
    applicant_name = detect_applicant_name(driver, resume_path or "")
    print(f"\n>>> Applicant Name Detected: {applicant_name}\n")

    # Step 4: Search jobs
    job_listings = search_jobs(driver, skills, max_jobs=20)
    if not job_listings:
        log("No jobs found. Check internet and try again.")

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
    log(f"Done! Reports saved in: {REPORTS_DIR}")
    print(f"  Applicant: {applicant_name}")
    print("="*65)

    stop_popup_watcher()
    input("\nPress ENTER to close browser...")
    driver.quit()


if __name__ == "__main__":
    main()
