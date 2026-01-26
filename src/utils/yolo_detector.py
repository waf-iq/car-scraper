from ultralytics import YOLO
import cv2
import numpy as np

class YoloDetector:
    def __init__(self, model_path="yolov8n.pt"):
        # Auto-downloads if not found
        self.model = YOLO(model_path)
        # COCO class 2 is 'car' (0-indexed? No, usually 2 in COCO. 'person' is 0. 'bicycle' is 1. 'car' is 2.)
        # Wait, Ultralytics YOLOv8 class 2 is car? let's verify.
        # Yes, usually: 0: person, 1: bicycle, 2: car ...
        self.target_class = 2 

    def detect(self, image_path_or_array):
        """
        Detects cars in an image.
        Returns:
            processed_image (numpy array): The image (maybe cropped or original)
            best_box (list): [x_center, y_center, width, height] normalized
            confidence (float): Confidence score
        """
        results = self.model(image_path_or_array, verbose=False)
        result = results[0]
        
        # Filter for cars
        car_boxes = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id == self.target_class: # Car
                car_boxes.append(box)
                
        if not car_boxes:
            return None, None, 0.0
            
        # "If the yolo model successfully finds two or more cars in the image only take the biggest bounding box"
        best_box = max(car_boxes, key=lambda b: b.xywh[0][2] * b.xywh[0][3]) # Area = w * h
        
        # Get normalized xywh
        # box.xywhn returns [x, y, w, h] normalized
        xywhn = best_box.xywhn[0].tolist()
        conf = float(best_box.conf[0])
        
        # We assume we pass the original image through? 
        # Or do we want to crop?
        # User said "save the image and it's label". The label is the bbox.
        # So we verify it is a car, then we save the ORIGINAL image (or resized generic fit).
        # We'll return the original image array (or load it if path).
        
        if isinstance(image_path_or_array, str):
            img = cv2.imread(image_path_or_array)
        else:
            img = image_path_or_array # Assume numpy array
            
        return img, xywhn, conf
