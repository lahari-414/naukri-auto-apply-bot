"""
debug_selector.py
─────────────────
Run this on any job listing page to find the correct CSS selector
for the company name. Open the output and look for which element
contains the real company name.

Usage:
    python debug_selector.py --url "https://www.naukri.com/python-jobs"
"""

import argparse
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


COMPANY_KEYWORDS = ["company", "employer", "org", "comp", "brand", "recruiter"]


def get_driver(headless=False):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def find_company_selectors(driver, url):
    print(f"\nOpening: {url}")
    driver.get(url)
    time.sleep(4)

    print("\n── Searching for elements whose class contains company keywords ──\n")

    found = []
    all_elements = driver.find_elements(By.XPATH, "//*[@class]")

    for el in all_elements:
        try:
            classes = el.get_attribute("class") or ""
            text = el.text.strip()

            if not text or len(text) > 100:
                continue

            classes_lower = classes.lower()
            if any(kw in classes_lower for kw in COMPANY_KEYWORDS):
                tag = el.tag_name
                found.append({
                    "tag": tag,
                    "class": classes,
                    "text": text[:80],
                })
        except Exception:
            continue

    # Deduplicate by class
    seen = set()
    unique = []
    for item in found:
        key = item["class"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if unique:
        print(f"Found {len(unique)} candidate elements:\n")
        for i, item in enumerate(unique[:30], 1):
            print(f"  [{i:02d}] <{item['tag']} class='{item['class']}'>")
            print(f"        Text: \"{item['text']}\"")
            print()
    else:
        print("No elements found with company-related class names.")
        print("Try inspecting the page manually in DevTools.\n")

    # Also try common known selectors
    print("\n── Testing known selectors ──\n")
    known = [
        ".comp-name",
        "a.comp-name",
        ".company-name",
        ".companyName",
        ".employer-name",
        "[data-company]",
        "[itemprop='name']",
        "a[data-tn-element='companyName']",
        ".jobs-unified-top-card__company-name",
        ".topcard__org-name-link",
        "[data-testid='job-poster-name']",
        "[class*='compName']",
        "[class*='CompanyName']",
    ]
    for sel in known:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                texts = [e.text.strip() for e in els[:3] if e.text.strip()]
                print(f"  ✓ FOUND  {sel!r:50s} → {texts}")
            else:
                print(f"  ✗ miss   {sel!r}")
        except Exception as e:
            print(f"  ! error  {sel!r}: {e}")

    print("\n── Done. Copy the working selector into your scraper ──\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.naukri.com/python-jobs-in-hyderabad")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    driver = get_driver(headless=args.headless)
    try:
        find_company_selectors(driver, args.url)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
