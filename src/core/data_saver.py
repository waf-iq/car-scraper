import os
from pathlib import Path
import cv2
import uuid

class DataSaver:
    def __init__(self, base_dir="Dataset", maps_manager=None, target=150):
        self.base_dir = Path(base_dir)
        self.images_dir = self.base_dir / "images"
        self.labels_dir = self.base_dir / "labels"
        self.maps_manager = maps_manager
        self.target = target  # images per generation
        
    def get_folder_path(self, make, model, range_str):
        s_make = make.replace(" ", "-")
        s_model = model.replace(" ", "-")
        s_range = range_str.replace(" ", "-")
        return self.images_dir / s_make / s_model / s_range

    def count(self, make, model, range_str):
        folder = self.get_folder_path(make, model, range_str)
        if not folder.exists():
            return 0
        return len(list(folder.glob("*.jpg")))

    def is_full(self, make, model, range_str, limit=None):
        """Checks if the generation folder has reached the per-generation target."""
        if limit is None:
            limit = self.target
        return self.count(make, model, range_str) >= limit

    def save(self, image_array, bbox_xywhn, make, model, range_str):
        """
        Saves image and label.
        Directory structure: Dataset/images/Make/Model/Year-Range/
        """
        if self.maps_manager is None:
            raise ValueError("MapsManager not initialized in DataSaver")
            
        # Resolve IDs (Note: range_str is passed in now, resolved by caller preferably, or we resolve here?)
        # To avoid double resolution, let's assume the caller passes the resolved range_str, 
        # BUT the original signature took `year_string`.
        # Let's adjust usage in Pipeline to resolve first, then pass range_str here.
        # We still need IDs though. MapsManager.get_year_id takes year_string OR range.
        
        make_id = self.maps_manager.get_make_id(make)
        model_id = self.maps_manager.get_model_id(make, model)
        year_id, _ = self.maps_manager.get_year_id(make, model, range_str)
        
        # Get paths using helper
        img_path_dir = self.get_folder_path(make, model, range_str)
        # Replicate logic for labels
        s_make = make.replace(" ", "-")
        s_model = model.replace(" ", "-")
        s_range = range_str.replace(" ", "-")
        lbl_path_dir = self.labels_dir / s_make / s_model / s_range
        
        img_path_dir.mkdir(parents=True, exist_ok=True)
        lbl_path_dir.mkdir(parents=True, exist_ok=True)
        
        unique_name = str(uuid.uuid4())
        
        # Save Image
        img_file = img_path_dir / f"{unique_name}.jpg"
        cv2.imwrite(str(img_file), image_array)
        
        # Save Label
        # Format: <MakeID>.<ModelID>.<YearID> <x> <y> <w> <h>
        class_id_str = f"{make_id}.{model_id}.{year_id}"
        label_content = f"{class_id_str} {bbox_xywhn[0]:.6f} {bbox_xywhn[1]:.6f} {bbox_xywhn[2]:.6f} {bbox_xywhn[3]:.6f}\n"
        
        lbl_file = lbl_path_dir / f"{unique_name}.txt"
        with open(lbl_file, 'w') as f:
            f.write(label_content)
            
        return str(img_file), str(lbl_file)
