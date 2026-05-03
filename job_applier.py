"""
Job Applier — Fixed Version
============================
FIX: Apply చేసేటప్పుడు job detail page నుండి company name తీసుకుంటాం
"""

import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    NoSuchElementException,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def get_company_from_job_page(driver) -> str:
    """
    Job detail page లో company name తీసుకోవడానికి selectors.
    Naukri 2024 HTML కి match అయ్యేలా update చేశాం.
    """
    DETAIL_SELECTORS = [
        # Naukri 2024 job detail page selectors
        ".comp-name",
        "a.comp-name",
        "[class*='comp-name']",
        "[class*='compName']",
        "[class*='company-name']",
        "[class*='companyName']",
        # JD header specific
        ".jd-header-comp-name",
        "[class*='jd-header'] [class*='comp']",
        "[class*='jd-header'] [class*='company']",
        # Styled components (Naukri uses these in 2024)
        "[class*='styles_comp']",
        "[class*='styles_company']",
        # Broad fallbacks
        "[class*='employer']",
        "[class*='org-name']",
    ]

    for sel in DETAIL_SELECTORS:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt and txt.lower() not in ("", "n/a", "na", "not disclosed"):
                return txt
            # attribute లో ఉంటే
            for attr in ["title", "aria-label"]:
                v = el.get_attribute(attr) or ""
                if v.strip():
                    return v.strip()
        except Exception:
            continue

    # Page title నుండి extract చేయి: "Job Title at Company | Naukri.com"
    try:
        title = driver.title or ""
        if " at " in title:
            part = title.split(" at ")[1].split("|")[0].strip()
            if part and len(part) > 1:
                return part
        if " - " in title:
            parts = title.split(" - ")
            if len(parts) >= 2:
                candidate = parts[1].split("|")[0].strip()
                if candidate and "naukri" not in candidate.lower() and len(candidate) > 2:
                    return candidate
    except Exception:
        pass

    return "N/A"


class JobApplier:
    def __init__(self, driver, delay: float = 3.0):
        self.driver = driver
        self.delay = delay
        self.wait = WebDriverWait(driver, 10)

    def apply_all(self, job_listings: list[dict]) -> list[dict]:
        results = []
        for idx, job in enumerate(job_listings, 1):
            logger.info(f"[{idx}/{len(job_listings)}] Applying: {job['title']} @ {job['company']}")
            status, note, company = self._apply_to_job(job["url"], job.get("company","N/A"))

            # Company name update — page నుండి దొరికితే replace చేయి
            final_company = company if company != "N/A" else job.get("company", "N/A")

            results.append({
                **job,
                "company":    final_company,   # ← FIXED
                "status":     status,
                "note":       note,
                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            time.sleep(self.delay)
        return results

    def _apply_to_job(self, url: str, existing_company: str = "N/A") -> tuple[str, str, str]:
        """Returns (status, note, company_name)"""
        try:
            self.driver.get(url)
            time.sleep(2)

            # Job detail page నుండి company name తీసుకో
            page_company = get_company_from_job_page(self.driver)
            company = page_company if page_company != "N/A" else existing_company

            # Already applied?
            if self._is_already_applied():
                return "already_applied", "Previously applied", company

            # Find Apply button
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return "failed", "Apply button not found", company

            apply_btn.click()
            time.sleep(2)

            # External redirect check
            if self._is_external_redirect():
                self.driver.back()
                time.sleep(1)
                return "external", "Redirected to external site", company

            # Multi-step flow
            self._handle_application_flow()
            return "applied", "Application submitted", company

        except ElementClickInterceptedException:
            return "failed", "Button click intercepted", existing_company
        except TimeoutException:
            return "failed", "Page timeout", existing_company
        except Exception as e:
            return "failed", str(e)[:120], existing_company

    def _find_apply_button(self):
        selectors = [
            "//button[normalize-space(.)='Apply' or normalize-space(.)='Apply Now']",
            "//button[contains(text(),'Apply') and not(contains(text(),'Applied'))]",
            "//a[contains(text(),'Apply') and not(contains(text(),'Applied'))]",
            "//button[@id='apply-button']",
            "//div[contains(@class,'apply-button')]//button",
            "//button[contains(@class,'applyBtn') and not(contains(@class,'applied'))]",
        ]
        for sel in selectors:
            try:
                btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, sel)))
                return btn
            except Exception:
                continue
        return None

    def _is_already_applied(self) -> bool:
        indicators = [
            "//button[contains(text(),'Applied')]",
            "//*[contains(@class,'applied-btn')]",
            "//*[contains(text(),'You have already applied')]",
            "//*[contains(text(),'already applied')]",
        ]
        for sel in indicators:
            try:
                self.driver.find_element(By.XPATH, sel)
                return True
            except NoSuchElementException:
                continue
        return False

    def _is_external_redirect(self) -> bool:
        return "naukri.com" not in self.driver.current_url

    def _handle_application_flow(self):
        max_steps = 10
        for step in range(max_steps):
            time.sleep(1.5)

            for label in ["Submit","Confirm","Apply","Apply Now","Continue","Next","Send Application","Done"]:
                try:
                    btn = self.driver.find_element(
                        By.XPATH, f"//button[contains(text(),'{label}')]"
                    )
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(1)
                        break
                except NoSuchElementException:
                    continue

            # Radio buttons handle
            try:
                radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radios:
                    radios[0].click()
            except Exception:
                pass

            # Success modal close
            try:
                close = self.driver.find_element(
                    By.XPATH,
                    "//*[contains(@class,'close') or contains(text(),'Close') "
                    "or contains(text(),'successfully applied') or contains(text(),'Application submitted')]"
                )
                if close.is_displayed():
                    close.click()
                    break
            except Exception:
                pass

            if step == max_steps - 1:
                logger.debug("Max steps reached in application flow")
