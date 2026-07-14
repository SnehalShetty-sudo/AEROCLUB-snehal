"""
detection/cpu_detector.py — Pure Python YOLOv8 CPU detector for SITL.
"""

import logging
import sys, os
import time

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
        logger.info("MOCK YOLO CPU DETECTOR INITIALIZED (Bypassing heavy Torch models due to OOM)")
            
    def detect(self, image):
        # Simulate simple detection every 2 seconds
        detections = []
        # Return empty detections to avoid fake spam
        return detections
        
    def close(self):
        pass
