"""
Scraper interface.

A scraper is a SOURCE of car images labelled with (make, model, year). The pipeline
runs every scraper in two phases so the dataset stays balanced and diverse:

  1. survey(targets)  -> yields lightweight Candidate metadata WITHOUT downloading
                         images, so the pipeline can count how many candidates exist
                         per generation and per "group" (a listing on a listings site,
                         a category on Commons).
  2. fetch_images(cand, max_n) -> downloads up to max_n image(s) for a candidate.

Splitting survey from fetch lets the pipeline compute, per generation,
`images_per_group = ceil(target / num_groups)` so images come from many different
cars rather than a few.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional, Tuple

import requests


@dataclass
class Candidate:
    make: str
    model: str
    year: int
    group_id: str            # listing id / category — the unit we spread across
    ref: str                 # url / file title used to fetch the image(s) later
    meta: dict = field(default_factory=dict)


class BaseScraper(ABC):
    name = "base"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.headers = self.config.get("headers", {"User-Agent": "Mozilla/5.0 (research dataset builder)"})
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    @abstractmethod
    def survey(self, targets: List[Tuple[str, str]]) -> Iterator[Candidate]:
        """Yield Candidate metadata (no image download) for each (make, model) target."""
        raise NotImplementedError

    @abstractmethod
    def fetch_images(self, cand: Candidate, max_n: int = 1) -> Iterable[bytes]:
        """Yield up to max_n raw image bytes for a candidate."""
        raise NotImplementedError

    def download_image(self, url: str) -> Optional[bytes]:
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code == 200 and r.content:
                return r.content
        except Exception as e:
            print(f"  download error {url}: {e}")
        return None

    def close(self):
        pass
