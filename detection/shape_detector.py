"""
detection/shape_detector.py — OpenCV-based geometric shape detection.

Detects colored shapes (triangles, squares, rectangles) on the ground
using HSV color filtering and contour analysis. Runs on CPU — negligible cost.
"""

import cv2
import logging
import numpy as np
from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SHAPE_COLORS, SHAPE_MIN_AREA, SHAPE_MAX_AREA, COLORS

logger = logging.getLogger("shape_detector")


class Detection:
    """Matches the Detection class from hailo_detector for consistency."""
    def __init__(self, class_name, confidence, bbox, source="opencv"):
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox
        self.source = source


class ShapeDetector:
    """
    Detects geometric shapes (triangle, square, rectangle) using OpenCV.
    
    Works by:
    1. Convert frame to HSV
    2. Filter for target colors (red, blue)
    3. Find contours
    4. Approximate polygon → classify by vertex count
    
    Usage:
        detector = ShapeDetector()
        detections = detector.detect(frame_bgr)
    """

    def __init__(self, min_area=None, max_area=None, color_ranges=None):
        self.min_area = min_area or SHAPE_MIN_AREA
        self.max_area = max_area or SHAPE_MAX_AREA
        self.color_ranges = color_ranges or SHAPE_COLORS
        logger.info(
            f"Shape detector ready: min_area={self.min_area}, "
            f"max_area={self.max_area}, colors={list(self.color_ranges.keys())}"
        )

    def detect(self, frame_bgr: np.ndarray) -> List[Detection]:
        """
        Detect geometric shapes in a BGR frame.
        Returns list of Detection objects.
        """
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        # Create combined mask for all target colors
        combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for color_name, ranges in self.color_ranges.items():
            lower = np.array(ranges["lower"], dtype=np.uint8)
            upper = np.array(ranges["upper"], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            combined_mask = cv2.bitwise_or(combined_mask, mask)

        # Clean up mask: remove noise, fill small gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

        # Apply slight blur to smooth contour edges
        combined_mask = cv2.GaussianBlur(combined_mask, (5, 5), 0)
        _, combined_mask = cv2.threshold(combined_mask, 127, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(
            combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area or area > self.max_area:
                continue

            # Approximate polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
            num_vertices = len(approx)

            # Classify shape
            shape_name = self._classify_shape(approx, num_vertices)
            if shape_name is None:
                continue

            # Bounding box
            x, y, w, h = cv2.boundingRect(approx)

            # Confidence based on how "clean" the shape is
            # Compare contour area to bounding rect area
            rect_area = w * h
            fill_ratio = area / rect_area if rect_area > 0 else 0
            confidence = min(0.95, fill_ratio + 0.3)

            detections.append(Detection(
                class_name=shape_name,
                confidence=round(confidence, 3),
                bbox=[x, y, x + w, y + h],
                source="opencv",
            ))

        return detections

    def _classify_shape(self, approx, num_vertices):
        """Classify a polygon by its vertex count and geometry."""
        if num_vertices == 3:
            return "triangle"
        elif num_vertices == 4:
            # Distinguish square from rectangle
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h) if h > 0 else 0
            if 0.8 <= aspect_ratio <= 1.2:
                return "square"
            else:
                return "rectangle"
        elif num_vertices == 5:
            return "pentagon"
        elif num_vertices > 5:
            # Could be a circle — check circularity
            area = cv2.contourArea(approx)
            peri = cv2.arcLength(approx, True)
            circularity = (4 * np.pi * area) / (peri * peri) if peri > 0 else 0
            if circularity > 0.7:
                return "circle"
        return None

    def close(self):
        """No resources to clean up for OpenCV."""
        pass
