"""
config.py — Centralized configuration for the drone detection system.
All tunable parameters live here. Change values here, not in individual modules.
"""

import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
# Set the DRONE_MODEL_PATH environment variable to override this for your system.
# Default path is for the Raspberry Pi deployment.
MODEL_PATH = Path(os.environ.get("DRONE_MODEL_PATH", "/home/aeroclub123/models/yolov8n.hef"))
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Camera ──────────────────────────────────────────────────────────
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
INFERENCE_WIDTH = 640      # YOLOv8 expects 640x640
INFERENCE_HEIGHT = 640

# ─── Hailo Detection ────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.45
# COCO classes we care about from the air
# Person is the primary target; others are optional bonus detections
DETECT_CLASSES = {
    0: "person",
}
# Full COCO class list for the YOLOv8 model (80 classes)
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
    "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
    "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

# ─── Shape Detection ──────────────────────────────────────────────────
# NOTE: Shape detection is currently DISABLED in main.py to focus on
# human detection and prevent false positives. These values are kept here
# so that detection/shape_detector.py can still be imported and tested
# independently without crashing.
SHAPE_MIN_AREA = 500
SHAPE_MAX_AREA = 50000
SHAPE_COLORS = {
    "red_low":  {"lower": (0, 100, 100),   "upper": (10, 255, 255)},
    "red_high": {"lower": (160, 100, 100),  "upper": (180, 255, 255)},
    "blue":     {"lower": (100, 100, 80),   "upper": (130, 255, 255)},
}

# ─── Streaming ───────────────────────────────────────────────────────
JPEG_QUALITY = 70          # 0-100, lower = smaller/faster, higher = better quality
STREAM_MAX_FPS = 20        # Cap streaming FPS to save bandwidth

# ─── Dashboard Server ───────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
TELEMETRY_UPDATE_HZ = 10   # WebSocket telemetry push rate
DETECTION_UPDATE_HZ = 5    # WebSocket detection stats push rate

# ─── Simulation Mode ──────────────────────────────────────────────────
SIMULATION_MODE = True     # If True, bypasses Pi hardware (uses ROS2 camera + CPU YOLO)
ROS2_IMAGE_TOPIC = "/down_camera/image"

# ─── MAVLink / Flight Controller ────────────────────────────────────
if SIMULATION_MODE:
    FC_CONNECTION_STRING = "tcp:127.0.0.1:5763"
    FC_MOCK_MODE = False
else:
    FC_CONNECTION_STRING = "/dev/ttyACM0"
    FC_MOCK_MODE = False
    
FC_BAUD = 115200

# ─── Mission Planning & Memory Grid ─────────────────────────────────
FLIGHT_ALTITUDE = 15.0     # meters AGL
SCAN_SPEED = 2.0           # m/s ground speed during scan
CAMERA_HFOV_DEG = 66.0     # Camera Module 3 horizontal FOV
SWATH_OVERLAP = 0.20       # 20% overlap between adjacent passes
GRID_CELL_SIZE = 1.0       # Memory Grid cell size in meters (1x1m)

# Default geofence polygon (arbitrary 30x30m box for testing)
GEOFENCE_POLYGON = [
    (28.61390, 77.20900),
    (28.61390, 77.20930),
    (28.61360, 77.20930),
    (28.61360, 77.20900)
]

# ─── Colors for Drawing ─────────────────────────────────────────────
COLORS = {
    "person":    (0, 255, 0),     # Green
    "triangle":  (0, 165, 255),   # Orange
    "square":    (255, 0, 0),     # Blue (BGR)
    "rectangle": (255, 0, 255),   # Magenta
    "circle":    (0, 255, 255),   # Yellow
    "unknown":   (128, 128, 128), # Gray
}
