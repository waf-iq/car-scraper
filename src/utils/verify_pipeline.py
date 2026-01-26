import sys
from unittest.mock import MagicMock

# MOCK YOLO BEFORE IMPORTING PIPELINE
# This prevents the real YoloDetector from trying to download weights
mock_yolo_module = MagicMock()
mock_detector_class = MagicMock()
mock_yolo_module.YoloDetector = mock_detector_class
sys.modules["src.utils.yolo_detector"] = mock_yolo_module

import cv2
import numpy as np
import shutil
from src.core.pipeline import Pipeline
from src.core.maps_manager import MapsManager
from src.core.config_loader import ConfigLoader

# Setup the mock instance to return valid values
mock_instance = mock_detector_class.return_value
# Return img, normalized box, confidence
mock_instance.detect.return_value = (None, [0.5, 0.5, 0.2, 0.1], 0.99)

# Mock Scraper
class MockScraper:
    def __init__(self):
        pass
    def run(self):
        # Yield one candidate
        img = np.zeros((640, 640, 3), dtype=np.uint8)
        # We need to ensure detect receives this img. 
        # But since we mocked detect, it returns None as image (per line above).
        # Pipeline expects valid image back.
        # Let's verify what detect is supposed to return: (img, bbox, conf)
        # So we should update the mock return value to return the input image? 
        # Too complex to mock valid pass-through.
        # Let's just return a dummy array
        global mock_instance
        mock_instance.detect.return_value = (img, [0.5, 0.5, 0.2, 0.1], 0.99)
        yield (img, "Toyota", "Camry", "2012")

def verify():
    print("Running verification (Mocked YOLO)...")
    # Clean up previous run
    shutil.rmtree("Dataset", ignore_errors=True)
    shutil.rmtree("maps_test", ignore_errors=True)
    
    # 1. Setup Maps
    mm = MapsManager("maps_test")
    mm.generations = {
        "Toyota": {
            "Camry": [{"range": "2011-2014", "start": 2011, "end": 2014}]
        }
    }
    mm.save_all()
    
    # 2. Setup Pipeline
    # Pipeline thinks it's using the real detector class, which is now our MagicMock
    pipeline = Pipeline(ConfigLoader(), mm)
    
    # 3. Run
    scr = MockScraper()
    pipeline.process_scraper(scr)
    
    # 4. Check results
    import os
    expected_path = "Dataset/images/Toyota/Camry/2011-2014"
    if os.path.exists(expected_path) and len(os.listdir(expected_path)) > 0:
        print("SUCCESS: Image saved in correct folder.")
    else:
        print("FAILURE: Image not found.")
        
    # 5. Check Limit Logic
    pipeline.saver.is_full = lambda m, mo, r: True # Force full
    print("Testing limit logic (forced full)...")
    pipeline.process_scraper(scr) # Should print skipping
    
if __name__ == "__main__":
    verify()
