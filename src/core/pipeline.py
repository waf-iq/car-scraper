import cv2
import numpy as np
import time
from src.utils.yolo_detector import YoloDetector
from src.core.data_saver import DataSaver

class Pipeline:
    def __init__(self, config_loader, maps_manager):
        self.config_loader = config_loader
        self.maps_manager = maps_manager
        self.detector = YoloDetector()
        self.saver = DataSaver("Dataset", maps_manager)
        
    def process_scraper(self, scraper_instance):
        """
        Runs the scraper and processes yielded images.
        """
        print(f"Starting pipeline for {scraper_instance.__class__.__name__}...")
        
        count = 0
        saved_count = 0
        
        for item in scraper_instance.run():
            count += 1
            # item is (image_source, make, model, year)
            image_source, make, model, year = item
            
            # Resolve generation first to check limit
            range_str = self.maps_manager.resolve_generation(make, model, year)
            
            if self.saver.is_full(make, model, range_str):
                 print(f"Skipping {make} {model} {range_str} - Limit Reached.")
                 continue
            
            print(f"Processing candidate {count}: {make} {model} {year} ({range_str})")
            
            # 1. Get Image
            img_array = None
            if isinstance(image_source, bytes):
                nparr = np.frombuffer(image_source, np.uint8)
                img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            elif isinstance(image_source, str):
                # Assume URL if starts with http, else path
                if image_source.startswith("http"):
                    # Scraper should have downloaded it, but if it returned URL:
                    pass
                else: 
                     img_array = cv2.imread(image_source)
            elif isinstance(image_source, np.ndarray):
                 img_array = image_source
                     
            if img_array is None:
                print("  Failed to load image")
                continue
                
            # 2. YOLO
            final_img, bbox, conf = self.detector.detect(img_array)
            
            if bbox:
                print(f"  Car detected ({conf:.2f}). Saving...")
                # 3. Save
                img_path, lbl_path = self.saver.save(final_img, bbox, make, model, range_str)
                print(f"  Saved to {img_path}")
                saved_count += 1
            else:
                print("  No car detected or multiple cars not handled. Dropping.")
                
        print(f"Pipeline finished. Processed {count}, Saved {saved_count}.")
