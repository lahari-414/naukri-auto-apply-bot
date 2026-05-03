"""
Naukri Job Scraper — Fixed Version
====================================
FIX: Company name "N/A" రాకుండా Naukri 2024 HTML selectors పెట్టాం
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import csv
import json
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
SEARCH_KEYWORD  = "Python Developer"
SEARCH_LOCATION = "Hyderabad"
MAX_PAGES       = 5
OUTPUT_CSV      = "jobs_output.csv"
OUTPUT_JSON     = "jobs_output.json"
# ──────────────────────────────────────────────────────────


def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    return driver


# ══════════════════════════════════════════════════════════
# FIXED: Company Name — Naukri 2024 selectors
# ══════════════════════════════════════════════════════════
def get_company_name(card) -> str:
    """
    Naukri 2024 లో company name ఎక్కడ ఉంటుందో అన్ని selectors try చేస్తాం.
    పాత code లో .comp-name మాత్రమే try చేసేది — కానీ Naukri HTML మారింది.
    """

    # ── Layer 1: Direct CSS selectors (priority order) ───────────
    CSS_SELECTORS = [
        "a.comp-name",                      # Naukri classic
        ".comp-name",                       # Naukri classic span
        "span.comp-name",
        "[class*='comp-name']",             # partial match
        "[class*='compName']",              # camelCase
        "[class*='company-name']",          # kebab
        "[class*='companyName']",           # camelCase variant
        "[class*='company_name']",          # underscore
        # Naukri 2024 SRP styled-components
        "[class*='styles_comp']",
        "[class*='styles_company']",
        "[class*='styles_employer']",
        # Broader fallbacks
        "[class*='employer']",
        "[class*='org-name']",
        "[class*='orgName']",
        # data attributes
        "[data-company]",
        "[data-employer]",
    ]

    for sel in CSS_SELECTORS:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt and txt.lower() not in ("", "n/a", "na", "not disclosed"):
                return txt
            # text empty అయితే attributes చూడు
            for attr in ["title", "aria-label", "data-company", "data-employer"]:
                v = (el.get_attribute(attr) or "").strip()
                if v and v.lower() not in ("", "n/a"):
                    return v
        except NoSuchElementException:
            continue
        except Exception:
            continue

    # ── Layer 2: XPath with class contains ───────────────────────
    XPATH_SELECTORS = [
        ".//*[contains(@class,'comp-name')]",
        ".//*[contains(@class,'compName')]",
        ".//*[contains(@class,'company-name')]",
        ".//*[contains(@class,'companyName')]",
        ".//*[contains(@class,'employer')]",
        ".//*[@data-company]",
        ".//*[@data-employer]",
    ]

    for xp in XPATH_SELECTORS:
        try:
            els = card.find_elements(By.XPATH, xp)
            for el in els:
                txt = el.text.strip()
                # Job title / location keywords తో match అవ్వకుండా filter చేయి
                if not txt or txt.lower() in ("n/a", "na", ""):
                    continue
                SKIP_WORDS = [
                    "developer","engineer","manager","analyst","intern","designer",
                    "hyderabad","delhi","mumbai","bangalore","bengaluru","pune",
                    "chennai","kolkata","india","remote","years","lpa","lakhs",
                    "apply","view","save","job","full","stack","backend","frontend"
                ]
                tl = txt.lower()
                if any(w in tl for w in SKIP_WORDS):
                    continue
                if len(txt) > 2:
                    return txt
        except Exception:
            continue

    # ── Layer 3: Anchor aria-label / title ───────────────────────
    try:
        anchors = card.find_elements(By.TAG_NAME, "a")
        for a in anchors:
            for attr in ["aria-label", "title"]:
                v = (a.get_attribute(attr) or "").strip()
                if not v:
                    continue
                vl = v.lower()
                # Company-related keywords ఉంటే తీసుకో
                if any(k in vl for k in [
                    "pvt","ltd","inc","llc","technologies","solutions","systems",
                    "services","consulting","software","infotech","tech","corp",
                    "company","employer","group","enterprises","labs","studio"
                ]):
                    return v
    except Exception:
        pass

    # ── Layer 4: Structured data / JSON-LD ───────────────────────
    try:
        scripts = card.find_elements(By.XPATH, ".//script[@type='application/ld+json']")
        for s in scripts:
            import json
            try:
                data = json.loads(s.get_attribute("innerHTML") or "{}")
                # JobPosting schema
                hiring = data.get("hiringOrganization", {})
                name = hiring.get("name","") if isinstance(hiring, dict) else ""
                if name:
                    return name
            except Exception:
                pass
    except Exception:
        pass

    return "N/A"


# ══════════════════════════════════════════════════════════
# Other field extractors (unchanged but with extra selectors)
# ══════════════════════════════════════════════════════════
def get_job_title(card) -> str:
    selectors = [
        (By.CSS_SELECTOR, "a.title"),
        (By.CSS_SELECTOR, ".title"),
        (By.CSS_SELECTOR, "a.jobTitle"),
        (By.CSS_SELECTOR, "[class*='job-title'] a"),
        (By.CSS_SELECTOR, "[class*='jobTitle'] a"),
        (By.CSS_SELECTOR, "[class*='title'] a"),
        (By.CSS_SELECTOR, "h2 a"),
        (By.CSS_SELECTOR, "h3 a"),
    ]
    for by, sel in selectors:
        try:
            el = card.find_element(by, sel)
            txt = el.text.strip()
            if txt:
                return txt
        except NoSuchElementException:
            continue
    return "N/A"


def get_location(card) -> str:
    selectors = [
        (By.CSS_SELECTOR, ".loc-wrap"),
        (By.CSS_SELECTOR, ".location"),
        (By.CSS_SELECTOR, "[class*='location']"),
        (By.CSS_SELECTOR, "[class*='loc-wrap']"),
        (By.CSS_SELECTOR, "[class*='loc']"),
        (By.CSS_SELECTOR, "li.location"),
        (By.CSS_SELECTOR, "span.locWdth"),
        (By.CSS_SELECTOR, ".locWdth"),
    ]
    for by, sel in selectors:
        try:
            el = card.find_element(by, sel)
            txt = el.text.strip()
            if txt:
                return txt
        except NoSuchElementException:
            continue
    return "N/A"


def get_experience(card) -> str:
    selectors = [
        (By.CSS_SELECTOR, ".exp"),
        (By.CSS_SELECTOR, ".expwdth"),
        (By.CSS_SELECTOR, "[class*='experience']"),
        (By.CSS_SELECTOR, "[class*='exp']"),
        (By.CSS_SELECTOR, "li.experience"),
    ]
    for by, sel in selectors:
        try:
            el = card.find_element(by, sel)
            txt = el.text.strip()
            if txt:
                return txt
        except NoSuchElementException:
            continue
    return "N/A"


def get_salary(card) -> str:
    selectors = [
        (By.CSS_SELECTOR, ".salary"),
        (By.CSS_SELECTOR, "[class*='salary']"),
        (By.CSS_SELECTOR, "li.salary"),
    ]
    for by, sel in selectors:
        try:
            el = card.find_element(by, sel)
            txt = el.text.strip()
            if txt:
                return txt
        except NoSuchElementException:
            continue
    return "Not Disclosed"


def get_job_link(card) -> str:
    try:
        a = card.find_element(
            By.CSS_SELECTOR,
            "a.title, a.jobTitle, a[class*='title'], h2 a, h3 a"
        )
        return a.get_attribute("href") or "N/A"
    except NoSuchElementException:
        return "N/A"


# ══════════════════════════════════════════════════════════
# Page scraper
# ══════════════════════════════════════════════════════════
def scrape_page(driver) -> list[dict]:
    jobs = []

    # Wait for cards
    WAIT_SELECTORS = [
        ".jobTuple",
        "article.jobTuple",
        ".job-container",
        "[class*='jobTuple']",
        "[class*='srp-jobtuple']",
        "[class*='cust-job-tuple']",
    ]
    loaded = False
    for sel in WAIT_SELECTORS:
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel))
            )
            loaded = True
            break
        except TimeoutException:
            continue

    if not loaded:
        print("  [!] Timed out waiting for job cards")
        return jobs

    # Scroll to load lazy content
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(0.5)

    # Find cards
    CARD_SELECTORS = [
        ".jobTuple",
        "article.jobTuple",
        "[class*='srp-jobtuple-wrapper']",
        "[class*='cust-job-tuple']",
        ".job-container",
        "[class*='jobCard']",
        "[class*='job-card']",
        "article[class*='job']",
    ]
    cards = []
    for sel in CARD_SELECTORS:
        cards = driver.find_elements(By.CSS_SELECTOR, sel)
        if cards:
            print(f"  Found {len(cards)} cards using selector: {sel}")
            break

    for card in cards:
        company = get_company_name(card)
        job = {
            "job_title":  get_job_title(card),
            "company":    company,            # ← FIXED
            "location":   get_location(card),
            "experience": get_experience(card),
            "salary":     get_salary(card),
            "job_link":   get_job_link(card),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        jobs.append(job)

    return jobs


def build_url(keyword: str, location: str, page: int = 1) -> str:
    keyword_slug  = keyword.replace(" ", "-")
    location_slug = location.replace(" ", "-")
    return (
        f"https://www.naukri.com/{keyword_slug}-jobs-in-{location_slug}"
        f"?k={keyword.replace(' ', '+')}&l={location.replace(' ', '+')}&pageNo={page}"
    )


def save_results(all_jobs: list[dict]):
    if all_jobs:
        keys = all_jobs[0].keys()
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_jobs)
        print(f"\n✓ CSV saved: {OUTPUT_CSV}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    print(f"✓ JSON saved: {OUTPUT_JSON}")


def main():
    print(f"Scraping Naukri for: '{SEARCH_KEYWORD}' in '{SEARCH_LOCATION}'")
    driver = get_driver()
    all_jobs = []

    try:
        for page in range(1, MAX_PAGES + 1):
            url = build_url(SEARCH_KEYWORD, SEARCH_LOCATION, page)
            print(f"\nPage {page}: {url}")
            driver.get(url)
            time.sleep(3)

            jobs = scrape_page(driver)
            if not jobs:
                print("  No jobs found, stopping.")
                break

            all_jobs.extend(jobs)
            print(f"  ✓ {len(jobs)} jobs scraped (total: {len(all_jobs)})")

            # Verify company names
            for j in jobs[:3]:
                company_status = j['company'] if j['company'] != 'N/A' else '⚠ N/A'
                print(f"    → {j['job_title']} | Company: {company_status} | {j['location']}")

    finally:
        driver.quit()

    save_results(all_jobs)

    # Summary
    na_count = sum(1 for j in all_jobs if j['company'] == 'N/A')
    print(f"\nDone. Total jobs: {len(all_jobs)}")
    print(f"Company names found: {len(all_jobs) - na_count}/{len(all_jobs)}")
    if na_count > 0:
        print(f"⚠ {na_count} jobs still have N/A company — Naukri HTML changed, check selectors.")


if __name__ == "__main__":
    main()
