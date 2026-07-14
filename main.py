"""
main.py — SITL orchestrator for the Drone Aerial Detection & Dashboard System.
"""

import time
import logging
import threading
import cv2
import numpy as np
import sys
import json
from pathlib import Path

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main")

def log_flight(stats):
    from config import LOG_DIR
    log_file = LOG_DIR / "flight_logs.jsonl"
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(stats) + "\n")
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

from config import COLORS, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, SIMULATION_MODE, ROS2_IMAGE_TOPIC, GEOFENCE_POLYGON, GRID_CELL_SIZE
from telemetry.mavlink_bridge import MavlinkBridge
from mission.mission_manager import MissionManager
from mission.path_planner import generate_lawnmower_path
from mission.memory_grid import MemoryGrid
from dashboard.server import (
    start_server_in_thread, update_video_frame,
    push_telemetry, push_detection_stats, socketio,
    set_mav_bridge
)

# Dynamic imports based on mode
if SIMULATION_MODE:
    from detection.cpu_detector import CPUYoloDetector as Detector
    try:
        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import Image
        from cv_bridge import CvBridge

        class ROS2Camera(Node):
            def __init__(self, topic):
                super().__init__('pi_drone_camera_sub')
                self.bridge = CvBridge()
                self.latest_frame = None
                self.subscription = self.create_subscription(Image, topic, self.listener_callback, 10)
                
            def listener_callback(self, msg):
                try:
                    self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
                except Exception as e:
                    logger.error(f"Failed to convert image: {e}")
                    
            def get_frame(self):
                return self.latest_frame
    except ImportError:
        logger.warning("rclpy not found, using MockCamera for testing.")
        class MockCamera:
            def __init__(self):
                self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(self.frame, "MOCK CAMERA", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            def get_frame(self):
                return self.frame
        ROS2Camera = lambda topic: MockCamera()
        
        # mock rclpy functions so the thread doesn't crash
        class MockRclpy:
            def init(self): pass
            def spin(self, node): time.sleep(9999)
            def shutdown(self): pass
        rclpy = MockRclpy()
        
else:
    from detection.hailo_detector import HailoDetector as Detector

def annotate_frame(frame: np.ndarray, detections: list) -> np.ndarray:
    """Draw bounding boxes and return annotated frame."""
    out_frame = frame.copy()
    
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        name = det.class_name
        conf = det.confidence
        color = COLORS.get(name, COLORS["unknown"])
        
        cv2.rectangle(out_frame, (x1, y1), (x2, y2), color, 2)
        label = f"{name} {conf:.2f}"
        (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out_frame, (x1, y1-th-bl-4), (x1+tw, y1), color, cv2.FILLED)
        cv2.putText(out_frame, label, (x1, y1-bl-2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1, cv2.LINE_AA)
        
    return out_frame

def main():
    logger.info("Initializing subsystems...")
    
    # 1. Telemetry Bridge
    mav_bridge = MavlinkBridge()
    if not mav_bridge.start():
        logger.error("Failed to start MAVLink bridge.")
        return
        
    mission_mgr = MissionManager(mav_bridge)
    
    # 2. Memory Grid mapping
    memory_grid = MemoryGrid(GEOFENCE_POLYGON, cell_size=GRID_CELL_SIZE)
    
    # 3. Dashboard Server
    set_mav_bridge(mav_bridge)
    server_thread = start_server_in_thread()
    
    # 4. Camera Setup
    cam = None
    ros_thread = None
    if SIMULATION_MODE:
        logger.info("Initializing ROS2 Camera Node...")
        rclpy.init()
        cam = ROS2Camera(ROS2_IMAGE_TOPIC)
        ros_thread = threading.Thread(target=rclpy.spin, args=(cam,), daemon=True)
        ros_thread.start()
        
        logger.info("Waiting for first ROS2 image frame...")
        while cam.get_frame() is None:
            time.sleep(0.1)
    else:
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            cam.configure(cam.create_preview_configuration(
                main={"format": "BGR888", "size": (CAMERA_WIDTH, CAMERA_HEIGHT)},
                controls={"FrameRate": CAMERA_FPS},
            ))
            cam.start()
            time.sleep(1) # warm up
        except ImportError:
            logger.error("picamera2 not found. Run in SIMULATION_MODE.")
            return

    logger.info("Camera started.")

    # 5. Initialize Detector
    try:
        det = Detector()
        from detection.shape_detector import ShapeDetector
        shape_det = ShapeDetector()
    except Exception as e:
        logger.error(f"Detector init failed: {e}")
        return
        
    # Bind dashboard commands to mavlink bridge using callback
    from dashboard.server import set_mission_command_callback
    def handle_dashboard_command(cmd):
        if cmd == 'start':
            from config import GEOFENCE_POLYGON
            wps = generate_lawnmower_path(GEOFENCE_POLYGON)
            if mission_mgr.upload_mission(wps):
                mav_bridge.send_command('start')
        else:
            mav_bridge.send_command(cmd)
            
    set_mission_command_callback(handle_dashboard_command)
            
    # --- Main Loop ---
    logger.info("Starting main loop. Press Ctrl+C to exit.")
    
    last_telemetry_push = 0
    last_detection_push = 0
    fps_timer = time.time()
    frame_count = 0
    
    flight_start_time = None
    max_alt = 0.0
    start_batt = 0
    was_armed = False
    
    try:
        while True:
            # Capture
            if SIMULATION_MODE:
                frame = cam.get_frame()
                if frame is None:
                    continue
                frame = frame.copy() # Avoid threading read/write conflicts
            else:
                frame = cam.capture_array("main")
            
            # Detect
            detections = det.detect(frame)
            if SIMULATION_MODE:
                shape_detections = shape_det.detect(frame)
                detections.extend(shape_detections)
            
            # Mapping (Only if we have drone telemetry)
            tel = mav_bridge.get_telemetry()
            
            for d in detections:
                # Map all detections (person, triangle, square, rectangle, etc.)
                res = memory_grid.add_detection(
                    tel["lat"], tel["lon"], tel["alt"], tel["heading"],
                    frame.shape[1], frame.shape[0], d.bbox, class_name=d.class_name
                )
                if res.get("is_new"):
                    from dashboard.server import push_new_detection
                    # Pass the class_name so the dashboard knows what was detected
                    res["class_name"] = d.class_name
                    push_new_detection(res)
            
            # Annotate
            annotated = annotate_frame(frame, detections)
            update_video_frame(annotated)
            
            # Push updates
            now = time.time()
            if now - last_telemetry_push >= 0.1:
                push_telemetry(tel)
                last_telemetry_push = now
                
            if now - last_detection_push >= 0.2:
                # Send the cumulative unique counts
                counts = memory_grid.get_counts_by_class()
                push_detection_stats({'counts': counts})
                last_detection_push = now
                
            # Flight Logging
            if tel["armed"] and not was_armed:
                flight_start_time = time.time()
                start_batt = tel["battery_pct"]
                max_alt = tel["alt"]
                was_armed = True
            elif not tel["armed"] and was_armed:
                duration = time.time() - flight_start_time
                log_flight({
                    "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": duration,
                    "max_alt": max_alt,
                    "detections": memory_grid.get_unique_count(),
                    "battery_start": start_batt,
                    "battery_end": tel["battery_pct"]
                })
                was_armed = False
                
            if tel["armed"]:
                max_alt = max(max_alt, tel["alt"])
                
            # FPS
            frame_count += 1
            if now - fps_timer >= 2.0:
                fps = frame_count / (now - fps_timer)
                logger.info(f"FPS: {fps:.1f} | Unique Persons Found: {memory_grid.get_unique_count()}")
                frame_count = 0
                fps_timer = now
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if SIMULATION_MODE:
            rclpy.shutdown()
        else:
            cam.stop()
        det.close()
        mav_bridge.stop()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
