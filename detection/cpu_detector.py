"""
detection/cpu_detector.py — Pure Python YOLOv8 CPU detector for SITL.
"""

import logging
from ultralytics import YOLO
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CONFIDENCE_THRESHOLD, DETECT_CLASSES

logger = logging.getLogger("cpu_detector")

class Detection:
    def __init__(self, bbox, confidence, class_id, class_name):
        self.bbox = bbox
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name

class CPUYoloDetector:
    def __init__(self, model_name="yolov8n.pt"):
        logger.info(f"Loading CPU YOLO model: {model_name}")
        try:
            self.model = YOLO(model_name)
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise e
            
    def detect(self, image):
        # Run inference
        results = self.model(image, verbose=False)
        
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Filter by confidence and class (only person)
                if conf >= CONFIDENCE_THRESHOLD and cls_id in DETECT_CLASSES:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    class_name = DETECT_CLASSES[cls_id]
                    detections.append(Detection((x1, y1, x2, y2), conf, cls_id, class_name))
                    
        return detections
        
    def close(self):
        pass
