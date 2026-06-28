"""
Fast offline smoke test of the pipeline with a mocked YOLO and a mocked scraper
(no network, no model weights). Verifies survey -> spread -> save + the per-generation
limit logic. Run: python -m src.utils.verify_pipeline
"""
import sys
import shutil
from unittest.mock import MagicMock

import numpy as np

# Mock YOLO before Pipeline imports it, so no weights are needed.
mock_yolo_module = MagicMock()
mock_detector_class = MagicMock()
mock_yolo_module.YoloDetector = mock_detector_class
sys.modules["src.utils.yolo_detector"] = mock_yolo_module

from src.core.pipeline import Pipeline           # noqa: E402
from src.core.maps_manager import MapsManager    # noqa: E402
from src.core.config_loader import ConfigLoader  # noqa: E402
from src.scrapers.base import Candidate          # noqa: E402

# detect() returns (image, normalized bbox, confidence)
_img = np.zeros((640, 640, 3), dtype=np.uint8)
mock_detector_class.return_value.detect.return_value = (_img, [0.5, 0.5, 0.2, 0.1], 0.99)


class MockScraper:
    """Two listings (groups) for one generation; each yields several images."""
    def survey(self, targets):
        for i in range(2):
            yield Candidate(make="Toyota", model="Camry", year=2015,
                            group_id=f"listing-{i}", ref=f"listing-{i}")

    def fetch_images(self, cand, max_n=1):
        for _ in range(max_n):
            yield b"fake"  # decoded by mocked detector path -> _img

    def close(self):
        pass


def verify():
    print("Running mocked pipeline verification...")
    shutil.rmtree("Dataset_test", ignore_errors=True)

    mm = MapsManager("maps_test")
    mm.generations = {"Toyota": {"Camry": [{"range": "2014-2016", "start": 2014, "end": 2016, "name": "XV50"}]}}
    mm.save_all()

    pipe = Pipeline(ConfigLoader(), mm, target=6, dataset_dir="Dataset_test")
    # Pipeline decodes bytes via cv2; for the mock, bypass decode to return our image.
    pipe._decode = staticmethod(lambda src: _img)
    pipe.process_scraper(MockScraper(), [("Toyota", "Camry")])

    import os
    path = "Dataset_test/images/Toyota/Camry/2014-2016"
    n = len(os.listdir(path)) if os.path.exists(path) else 0
    print(f"\nImages saved: {n} (expected 6, capped at target)")
    print("SUCCESS" if n == 6 else "CHECK: unexpected count")
    shutil.rmtree("Dataset_test", ignore_errors=True)
    shutil.rmtree("maps_test", ignore_errors=True)


if __name__ == "__main__":
    verify()
