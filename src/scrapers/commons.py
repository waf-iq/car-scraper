"""
Wikimedia Commons scraper.

Commons exposes an open, unauthenticated API (no bot-blocking) and organises car
photos into year/generation categories. We use it to (a) validate the full pipeline
on real images and (b) as a license-clean supplementary image source.

For a target (make, model) we walk the model's category tree to leaf image files,
extract the model YEAR from the nearest ancestor category name or the file name,
and yield one Candidate per image file. The pipeline then resolves year -> generation.
"""
import re
from typing import Iterator, Iterable, List, Tuple

from .base import BaseScraper, Candidate

API = "https://commons.wikimedia.org/w/api.php"
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}


class CommonsScraper(BaseScraper):
    name = "commons"

    def __init__(self, config=None):
        super().__init__(config)
        self.max_depth = self.config.get("max_depth", 3)
        self.per_model_cap = self.config.get("per_model_cap", 60)

    # --- category traversal -------------------------------------------------
    def _cat_members(self, cat: str, cmtype: str, limit: int = 200):
        out, cont = [], {}
        while True:
            params = {"action": "query", "list": "categorymembers",
                      "cmtitle": f"Category:{cat}", "cmtype": cmtype,
                      "cmlimit": limit, "format": "json"}
            params.update(cont)
            r = self.session.get(API, params=params, timeout=25).json()
            out += r.get("query", {}).get("categorymembers", [])
            if "continue" in r:
                cont = r["continue"]
            else:
                break
        return out

    def _root_category(self, make: str, model: str) -> str:
        # Prefer an exact "Make Model" category; fall back to a category search.
        cand = f"{make} {model}"
        r = self.session.get(API, params={"action": "query", "list": "search",
                "srsearch": cand, "srnamespace": 14, "srlimit": 1, "format": "json"},
                timeout=25).json()
        hits = r.get("query", {}).get("search", [])
        return hits[0]["title"].replace("Category:", "") if hits else cand

    def _walk(self, cat: str, inherited_year, depth: int, seen: set) -> Iterator[Tuple[str, int]]:
        """Yield (file_title, year) pairs from cat and its subcategories."""
        if depth < 0 or cat in seen:
            return
        seen.add(cat)
        year_here = inherited_year
        ym = YEAR_RE.search(cat)
        if ym:
            year_here = int(ym.group(1))

        for f in self._cat_members(cat, "file"):
            title = f["title"]
            y = year_here
            fm = YEAR_RE.search(title)
            if fm:
                y = int(fm.group(1))
            if y is not None:
                yield title, y

        if depth > 0:
            for sub in self._cat_members(cat, "subcat"):
                subcat = sub["title"].replace("Category:", "")
                yield from self._walk(subcat, year_here, depth - 1, seen)

    # --- interface ----------------------------------------------------------
    def survey(self, targets: List[Tuple[str, str]]) -> Iterator[Candidate]:
        for make, model in targets:
            root = self._root_category(make, model)
            count = 0
            for title, year in self._walk(root, None, self.max_depth, set()):
                yield Candidate(make=make, model=model, year=year,
                                group_id=f"{make}/{model}/{year}", ref=title)
                count += 1
                if count >= self.per_model_cap:
                    break

    def fetch_images(self, cand: Candidate, max_n: int = 1) -> Iterable[bytes]:
        # Resolve the file's direct URL + mime, then download if it is a raster image.
        r = self.session.get(API, params={"action": "query", "titles": cand.ref,
                "prop": "imageinfo", "iiprop": "url|mime", "format": "json"},
                timeout=25).json()
        pages = r.get("query", {}).get("pages", {})
        for pg in pages.values():
            info = (pg.get("imageinfo") or [{}])[0]
            if info.get("mime") in IMAGE_MIME and info.get("url"):
                data = self.download_image(info["url"])
                if data:
                    yield data
            return
