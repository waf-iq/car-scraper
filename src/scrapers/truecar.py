"""
TrueCar listings scraper.

TrueCar runs PerimeterX bot protection. A normal residential IP is fine (it is not an
IP problem); the block is automation fingerprinting, so we drive Chrome via
`undetected-chromedriver` which patches those leaks. Verified working against the live
site. Selectors below are taken from the live DOM.

Strategy: collect ONE thumbnail per listing across many listings. Each listing is a
distinct car, so one image per listing maximises diversity -- exactly what the pipeline's
survey/spread wants. (Detail-page galleries exist but are lazily rendered and flaky; not
needed when listings are plentiful.)

  survey()       -> one Candidate per listing card (year + thumbnail url), paginated.
  fetch_images() -> downloads that listing's thumbnail.
"""
import re
import time
import random
from typing import Iterator, Iterable, List, Tuple, Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from .base import BaseScraper, Candidate
from .driver_utils import create_uc_driver, create_driver

YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")


class TrueCarScraper(BaseScraper):
    name = "truecar"

    def __init__(self, config=None):
        super().__init__(config)
        self.base_url = self.config.get("base_url", "https://www.truecar.com")
        self.headless = self.config.get("headless", False)
        self.engine = self.config.get("engine", "undetected")  # 'undetected' or 'selenium'
        self.chrome_version = self.config.get("chrome_version")  # None -> auto-detect
        self.proxy = self.config.get("proxy")
        self.user_data_dir = self.config.get("user_data_dir")  # persistent profile for PX clearance
        self.max_pages = self.config.get("max_pages", 10)
        self.max_per_listing = self.config.get("max_images_per_listing", 5)
        self.image_width = self.config.get("image_width", 1280)
        # Human-like dwell (seconds) on each page before clicking to the next one.
        self.page_dwell = self.config.get("page_dwell", [5, 11])
        sel = self.config.get("selectors", {})
        self.card_sel = sel.get("card", '[data-test="vehicleListingCard"]')
        self.ymm_sel = sel.get("ymm", '[data-test="vehicleListingCardYearMakeModel"]')
        self.img_sel = sel.get("img", '[data-test="listingCardImage"]')
        self.next_sel = sel.get("next", 'a[data-test="Pagination-directional-next"]')
        self.model_slug = self.config.get("model_slug", {})
        self._driver = None

    def _drv(self):
        if self._driver is None:
            if self.engine == "undetected":
                self._driver = create_uc_driver(self.headless, self.chrome_version,
                                                self.proxy, self.user_data_dir)
            else:
                self._driver = create_driver(self.headless)
        return self._driver

    def close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass  # uc raises a harmless WinError on quit (Windows)
            self._driver = None

    def _slug(self, name: str) -> str:
        return self.model_slug.get(name, name.lower().replace(" ", "-"))

    def _blocked(self, d) -> bool:
        return "denied" in (d.title or "").lower() or "are you a robot" in d.page_source.lower()

    def _human_scroll(self, settle: float):
        d = self._drv()
        time.sleep(settle)
        for y in range(0, 6000, random.randint(600, 900)):
            d.execute_script(f"window.scrollTo(0,{y});")
            time.sleep(random.uniform(0.3, 0.7))
        time.sleep(1.0)

    def _page_vins(self):
        return set(re.findall(r"/listing/([A-HJ-NPR-Z0-9]{11,17})/", self._drv().page_source))

    def _load(self, url: str, settle: float = 7.0, retries: int = 1) -> Optional[BeautifulSoup]:
        """Initial (first-page) load by URL. Pagination afterwards is done by clicking."""
        d = self._drv()
        for attempt in range(retries + 1):
            d.get(url)
            self._human_scroll(settle)
            if not self._blocked(d):
                return BeautifulSoup(d.page_source, "html.parser")
            wait = 10 * (attempt + 1) + random.uniform(0, 5)
            print(f"  [truecar] challenge at {url} (attempt {attempt+1}); waiting {wait:.0f}s...")
            time.sleep(wait)
        print(f"  [truecar] BLOCKED on first load. Run with headless=false and a persistent "
              f"'user_data_dir' so you can solve the PerimeterX challenge once; the cleared "
              f"cookie then persists for later pages/runs.")
        return None

    def _click_next(self) -> bool:
        """Click the 'next page' control like a human; return True once new listings load."""
        d = self._drv()
        before = self._page_vins()
        try:
            btn = d.find_element(By.CSS_SELECTOR, self.next_sel)
        except NoSuchElementException:
            return False  # no further pages
        d.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(random.uniform(1.0, 2.5))
        try:
            ActionChains(d).move_to_element(btn).pause(0.4).click().perform()
        except WebDriverException:
            try:
                d.execute_script("arguments[0].click();", btn)
            except WebDriverException:
                return False
        # Poll for the listing set to change (or a challenge to appear).
        for _ in range(18):
            time.sleep(1.0)
            if self._blocked(d):
                print("  [truecar] PerimeterX challenge during pagination -- solve it once in the "
                      "visible window (persistent profile) and re-run to continue.")
                return False
            if self._page_vins() - before:
                self._human_scroll(1.5)
                return True
        return False

    @staticmethod
    def _vin_from_href(href: str) -> str:
        m = re.search(r"/listing/([A-HJ-NPR-Z0-9]{11,17})/", href or "")
        return m.group(1) if m else (href or "")

    # --- interface ----------------------------------------------------------
    def _parse_cards(self, soup, make, model, seen) -> Iterator[Candidate]:
        for card in soup.select(self.card_sel):
            a = card.select_one("a[href]")
            href = a.get("href") if a else None
            if not href:
                continue
            vin = self._vin_from_href(href)
            if vin in seen:
                continue
            ymm = card.select_one(self.ymm_sel)
            text = ymm.get_text(" ", strip=True) if ymm else card.get_text(" ", strip=True)
            ym = YEAR_RE.search(text) or YEAR_RE.search(href)
            img = card.select_one(self.img_sel) or card.select_one("img")
            src = (img.get("src") or img.get("data-src")) if img else None
            if not ym or not src or not src.startswith("http"):
                continue
            seen.add(vin)
            yield Candidate(make=make, model=model, year=int(ym.group(1)),
                            group_id=vin, ref=src, meta={"href": href})

    def survey(self, targets: List[Tuple[str, str]]) -> Iterator[Candidate]:
        seen = set()
        for make, model in targets:
            url = (f"{self.base_url}/used-cars-for-sale/listings/"
                   f"{self._slug(make)}/{self._slug(model)}/")
            soup = self._load(url)
            if not soup:
                continue
            page = 1
            while True:
                got = 0
                for cand in self._parse_cards(soup, make, model, seen):
                    got += 1
                    yield cand
                print(f"  [truecar] {make} {model} page {page}: +{got} listings (total {len(seen)})")
                if page >= self.max_pages:
                    break
                # Dwell like a human reading the page before paging.
                time.sleep(random.uniform(*self.page_dwell))
                if not self._click_next():
                    break  # no more pages, or a challenge we can't clear automatically
                page += 1
                soup = BeautifulSoup(self._drv().page_source, "html.parser")

    def _photo_url(self, base_img: str, index: int) -> Optional[str]:
        """
        TrueCar listing photos share one timestamp and differ only by a 3-digit index:
        .../{VIN}/001_<ts>.jpg, .../002_<ts>.jpg, ...  We also upscale the requested
        size (the card thumbnail is only ~360px).
        """
        m = re.search(r"/(\d{3})_(\d+)\.jpg", base_img)
        if not m:
            return None
        url = re.sub(r"/\d{3}_(\d+)\.jpg", f"/{index:03d}_{m.group(2)}.jpg", base_img, count=1)
        # imgix-style params: ask for a larger image, keep aspect (fit=max).
        url = re.sub(r"([?&])h=\d+", r"\1", url)
        url = re.sub(r"([?&])w=\d+", rf"\1w={self.image_width}", url)
        return url

    def fetch_images(self, cand: Candidate, max_n: int = 1) -> Iterable[bytes]:
        """Yield up to min(max_n, max_per_listing) photos, probing the index until a gap."""
        limit = min(max_n, self.max_per_listing)
        for i in range(1, limit + 1):
            url = self._photo_url(cand.ref, i)
            if not url:
                if i == 1:
                    data = self.download_image(cand.ref)
                    if data:
                        yield data
                return
            data = self.download_image(url)
            if not data:
                return  # 404 / gap -> this listing has no more photos
            yield data
