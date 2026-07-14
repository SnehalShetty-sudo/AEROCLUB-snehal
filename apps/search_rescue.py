"""
apps/search_rescue.py — Search & Rescue Mission App.

Autonomous lawnmower search pattern with real-time YOLO human detection
and geometric shape detection. Uses MemoryGrid for deduplication.

This is the original main.py detection logic, now encapsulated as a
pluggable mission app.
"""

import cv2
import logging
import numpy as np
from apps.base_app import BaseMissionApp

logger = logging.getLogger("app.search_rescue")


class SearchRescueApp(BaseMissionApp):
    name = "Search & Rescue"
    description = "Autonomous lawnmower search with AI-powered human and shape detection. Generates GPS-tagged target coordinates for competition reporting."
    version = "1.0"
    icon = "fa-solid fa-binoculars"

    def __init__(self):
        super().__init__()
        self._detector = None
        self._shape_detector = None
        self._memory_grid = None
        self._mission_mgr = None
        self._mav_bridge = None
        self._new_detections = []  # buffer for pushing to dashboard

    def get_default_config(self):
        return {
            "confidence_threshold": {
                "value": 0.45,
                "type": "float",
                "min": 0.1,
                "max": 1.0,
                "label": "Confidence Threshold"
            },
            "search_altitude": {
                "value": 15,
                "type": "int",
                "min": 5,
                "max": 50,
                "label": "Search Altitude (m)"
            },
            "enable_shapes": {
                "value": True,
                "type": "bool",
                "label": "Detect Shapes"
            },
        }

    def on_start(self, mav_bridge, config=None):
        super().on_start(mav_bridge, config)
        self._mav_bridge = mav_bridge

        # Initialize detector (use CPU detector which may be mocked)
        try:
            from detection.cpu_detector import CPUYoloDetector
            self._detector = CPUYoloDetector()
            logger.info("YOLO detector initialized.")
        except Exception as e:
            logger.error(f"Failed to load YOLO detector: {e}")
            # Create a dummy detector that returns empty
            class DummyDetector:
                def detect(self, frame): return []
                def close(self): pass
            self._detector = DummyDetector()

        # Shape detector
        if self._config.get("enable_shapes", {}).get("value", True):
            try:
                from detection.shape_detector import ShapeDetector
                self._shape_detector = ShapeDetector()
                logger.info("Shape detector initialized.")
            except Exception as e:
                logger.warning(f"Shape detector unavailable: {e}")
                self._shape_detector = None

        # Memory Grid for deduplication
        try:
            from config import GEOFENCE_POLYGON, GRID_CELL_SIZE
            from mission.memory_grid import MemoryGrid
            self._memory_grid = MemoryGrid(GEOFENCE_POLYGON, cell_size=GRID_CELL_SIZE)
            logger.info("Memory grid initialized.")
        except Exception as e:
            logger.warning(f"Memory grid unavailable: {e}")

        # Mission Manager for uploading waypoints
        try:
            from mission.mission_manager import MissionManager
            self._mission_mgr = MissionManager(mav_bridge)
        except Exception as e:
            logger.warning(f"Mission manager unavailable: {e}")

    def process_frame(self, frame, telemetry):
        """Run YOLO + shape detection, map to grid, annotate frame."""
        detections = []

        # YOLO detection
        if self._detector:
            detections = self._detector.detect(frame)

        # Shape detection
        if self._shape_detector:
            shape_dets = self._shape_detector.detect(frame)
            detections.extend(shape_dets)

        # Map detections to memory grid
        if self._memory_grid and detections:
            for d in detections:
                res = self._memory_grid.add_detection(
                    telemetry.get("lat", 0), telemetry.get("lon", 0),
                    telemetry.get("alt", 0), telemetry.get("heading", 0),
                    frame.shape[1], frame.shape[0],
                    d.bbox, class_name=d.class_name
                )
                if res.get("is_new"):
                    res["class_name"] = d.class_name
                    self._new_detections.append(res)

        # Annotate frame
        annotated = self._annotate(frame, detections)
        return annotated

    def _annotate(self, frame, detections):
        """Draw bounding boxes on the frame."""
        from config import COLORS
        out = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            name = det.class_name
            conf = det.confidence
            color = COLORS.get(name, COLORS.get("unknown", (128, 128, 128)))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{name} {conf:.2f}"
            (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(out, (x1, y1 - th - bl - 4), (x1 + tw, y1), color, cv2.FILLED)
            cv2.putText(out, label, (x1, y1 - bl - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return out

    def get_widgets(self):
        return [
            {
                "type": "stat_grid",
                "title": "Detection Summary",
                "stats": [
                    {"id": "person", "label": "Persons", "icon": "fa-solid fa-person", "color": "#34d399"},
                    {"id": "triangle", "label": "Triangles", "icon": "fa-solid fa-play", "color": "#f5a623", "icon_style": "transform: rotate(-90deg);"},
                    {"id": "square", "label": "Squares", "icon": "fa-solid fa-square", "color": "#3d8bfd"},
                    {"id": "rectangle", "label": "Rectangles", "icon": "fa-solid fa-square", "color": "#a78bfa"},
                ]
            },
            {
                "type": "log",
                "title": "Detection Log",
                "id": "app-detection-log"
            }
        ]

    def get_stats(self):
        stats = {}
        if self._memory_grid:
            counts = self._memory_grid.get_counts_by_class()
            stats = {
                "person": counts.get("person", 0),
                "triangle": counts.get("triangle", 0),
                "square": counts.get("square", 0),
                "rectangle": counts.get("rectangle", 0),
                "total": self._memory_grid.get_unique_count(),
            }
        return stats

    def pop_new_detections(self):
        """Pop new detections for pushing to the dashboard."""
        dets = self._new_detections[:]
        self._new_detections.clear()
        return dets

    def on_command(self, command, mav_bridge=None):
        super().on_command(command, mav_bridge)
        bridge = mav_bridge or self._mav_bridge
        if not bridge:
            return

        if command == 'start':
            # Generate lawnmower path and upload
            try:
                from config import GEOFENCE_POLYGON
                from mission.path_planner import generate_lawnmower_path
                wps = generate_lawnmower_path(GEOFENCE_POLYGON)
                if self._mission_mgr and self._mission_mgr.upload_mission(wps):
                    bridge.send_command('start')
                    logger.info("SAR mission started.")
                else:
                    logger.error("Failed to upload mission waypoints.")
            except Exception as e:
                logger.error(f"Failed to start SAR mission: {e}")
        else:
            bridge.send_command(command)

    def on_stop(self):
        if self._detector:
            self._detector.close()
        super().on_stop()
