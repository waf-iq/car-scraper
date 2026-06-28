"""
Selenium helpers adapted from the proven car-schemas scraper. Listing sites
(TrueCar etc.) 403 plain requests, so we drive a headless Chrome with
anti-detection options.
"""
import logging
import time
import random
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

PAGE_LOAD_DELAY = 3.5
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def detect_chrome_major() -> Optional[int]:
    """Best-effort detection of the installed Chrome major version (Windows)."""
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                k = winreg.OpenKey(hive, r"Software\Google\Chrome\BLBeacon")
                ver, _ = winreg.QueryValueEx(k, "version")
                return int(ver.split(".")[0])
            except OSError:
                continue
    except Exception:
        pass
    return None


def create_uc_driver(headless: bool = False, chrome_version: Optional[int] = None,
                     proxy: Optional[str] = None, user_data_dir: Optional[str] = None):
    """
    undetected-chromedriver — defeats PerimeterX/Cloudflare/DataDome fingerprinting.
    Use for protected listings sites (TrueCar). `proxy` like 'http://user:pass@host:port'
    is only needed at scale or on a flagged IP; a normal residential IP usually does not
    need one.

    `user_data_dir` gives a PERSISTENT profile: solve a PerimeterX challenge once in the
    visible window and the clearance cookie is reused on later pages/runs — this is what
    makes paginated scraping behind PerimeterX reliable.
    """
    import undetected_chromedriver as uc
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    if user_data_dir:
        import os
        os.makedirs(user_data_dir, exist_ok=True)
        opts.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
    if chrome_version is None:
        chrome_version = detect_chrome_major()
    return uc.Chrome(options=opts, version_main=chrome_version, use_subprocess=True)


def create_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(f"user-agent={USER_AGENT}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    })
    return driver


def fetch_soup(url: str, driver: webdriver.Chrome,
               wait_css: Optional[str] = None, settle: float = PAGE_LOAD_DELAY) -> Optional[BeautifulSoup]:
    """Navigate and return BeautifulSoup, or None on block/error."""
    time.sleep(random.uniform(2.0, 4.0))
    try:
        driver.get(url)
        time.sleep(settle)
        title = (driver.title or "").lower()
        src = driver.page_source
        if "403 forbidden" in title or "access denied" in src.lower() or "are you a robot" in src.lower():
            logging.warning(f"Blocked/denied for {url}")
            return None
        return BeautifulSoup(src, "html.parser")
    except WebDriverException as e:
        logging.error(f"WebDriver error for {url}: {e}")
        return None
