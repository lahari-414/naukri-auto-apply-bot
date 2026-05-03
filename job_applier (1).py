"""
Job Applier
- Opens each job URL
- Clicks "Apply" button
- Handles chatbot / questionnaire screens
- Records result: applied / already_applied / failed
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


class JobApplier:
    def __init__(self, driver, delay: float = 3.0):
        self.driver = driver
        self.delay = delay
        self.wait = WebDriverWait(driver, 10)

    def apply_all(self, job_listings: list[dict]) -> list[dict]:
        results = []
        for idx, job in enumerate(job_listings, 1):
            logger.info(f"[{idx}/{len(job_listings)}] Applying: {job['title']} @ {job['company']}")
            status, note = self._apply_to_job(job["url"])
            results.append({
                **job,
                "status": status,
                "note": note,
                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            time.sleep(self.delay)
        return results

    def _apply_to_job(self, url: str) -> tuple[str, str]:
        try:
            self.driver.get(url)
            time.sleep(2)

            # ── Already applied? ────────────────────────────────────────
            if self._is_already_applied():
                return "already_applied", "Previously applied"

            # ── Find Apply button ───────────────────────────────────────
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return "failed", "Apply button not found"

            apply_btn.click()
            time.sleep(2)

            # ── Handle external application redirect ────────────────────
            if self._is_external_redirect():
                self.driver.back()
                time.sleep(1)
                return "external", "Redirected to external site"

            # ── Handle multi-step / chatbot application ─────────────────
            self._handle_application_flow()

            return "applied", "Application submitted"

        except ElementClickInterceptedException:
            return "failed", "Button click intercepted"
        except TimeoutException:
            return "failed", "Page timeout"
        except Exception as e:
            return "failed", str(e)[:120]

    def _find_apply_button(self):
        selectors = [
            "//button[contains(text(),'Apply')]",
            "//a[contains(text(),'Apply')]",
            "//button[@id='apply-button']",
            "//div[contains(@class,'apply-button')]//button",
            "//button[contains(@class,'applyBtn')]",
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
        ]
        for sel in indicators:
            try:
                self.driver.find_element(By.XPATH, sel)
                return True
            except NoSuchElementException:
                continue
        return False

    def _is_external_redirect(self) -> bool:
        current = self.driver.current_url
        return "naukri.com" not in current

    def _handle_application_flow(self):
        """
        Handle multi-step apply flow:
        - Chatbot questions → click appropriate answers / submit
        - Profile confirmation → click Confirm / Submit
        - Success modal → dismiss
        """
        max_steps = 10
        for step in range(max_steps):
            time.sleep(1.5)

            # Submit / Confirm buttons
            for label in ["Submit", "Confirm", "Apply", "Continue", "Next", "Send Application"]:
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

            # Chatbot: pick first radio option if present
            try:
                radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radios:
                    radios[0].click()
            except Exception:
                pass

            # Check for success/close modal
            try:
                close = self.driver.find_element(
                    By.XPATH, "//*[contains(@class,'close') or contains(text(),'Close')]"
                )
                if close.is_displayed():
                    close.click()
                    break
            except Exception:
                pass

            if step == max_steps - 1:
                logger.debug("Max steps reached in application flow")
