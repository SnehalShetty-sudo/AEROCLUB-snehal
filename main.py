"""
main.py — GCS Orchestrator.

This is the core engine of the Ground Control Station. It manages:
1. MAVLink telemetry bridge
2. Camera input (ROS2 / PiCamera / Mock)
3. Dashboard web server
4. Pluggable Mission Apps (via AppManager)

The orchestrator is mission-agnostic — it pipes camera frames and telemetry
to whatever Mission App is currently loaded, and pushes the results to the
dashboard.
"""

import time
import os
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
    """Append flight stats to the JSONL log file."""
    from config import LOG_DIR
    log_file = LOG_DIR / "flight_logs.jsonl"
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(stats) + "\n")
    except Exception as e:
        logger.error(f"Failed to write log: {e}")


# --- Camera Setup (mode-dependent imports) ---
from config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, SIMULATION_MODE, ROS2_IMAGE_TOPIC

if SIMULATION_MODE:
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
                cv2.putText(self.frame, "MOCK CAMERA", (200, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            def get_frame(self):
                return self.frame

        ROS2Camera = lambda topic: MockCamera()
        
        class MJPEGCamera:
            def __init__(self, stream_url):
                self.stream_url = stream_url
                self.cap = cv2.VideoCapture(stream_url)
                self.latest_frame = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
                self.thread = threading.Thread(target=self._update, daemon=True)
                self.thread.start()

            def _update(self):
                while True:
                    ret, frame = self.cap.read()
                    if ret:
                        self.latest_frame = frame
                    else:
                        time.sleep(0.1)

            def get_frame(self):
                return self.latest_frame

        class MockRclpy:
            def init(self): pass
            def spin(self, node): time.sleep(9999)
            def shutdown(self): pass

        rclpy = MockRclpy()


# Global references for dynamic hardware swapping
global_mav_bridge = None
global_cam = None
global_ros_thread = None

def start_hardware():
    """Initializes MAVLink and Camera based on the environment variables set by EnvManager."""
    global global_mav_bridge, global_cam, global_ros_thread
    
    # Check what mode we are in based on env vars set by EnvManager
    is_mock = os.environ.get("DRONE_MOCK", "false").lower() == "true"
    mav_conn = os.environ.get("MAV_CONNECTION", "tcp:127.0.0.1:5760")
    mav_baud = int(os.environ.get("MAV_BAUD", "57600"))
    
    logger.info(f"Initializing Hardware. Mock: {is_mock}, MAVLink: {mav_conn} @ {mav_baud}")
    
    # ── 1. MAVLink Bridge ──
    from telemetry.mavlink_bridge import MavlinkBridge
    global_mav_bridge = MavlinkBridge(connection_string=mav_conn, baud=mav_baud)

    try:
        if not global_mav_bridge.start():
            logger.error("Failed to start MAVLink bridge.")
            global_mav_bridge = None
            return False
    except Exception as e:
        logger.error(f"MAVLink bridge connection exception: {e}")
        global_mav_bridge = None
        return False

    # ── 2. Camera Setup ──
    if is_mock or ("tcp" in mav_conn or "udp" in mav_conn):
        logger.info("Initializing MJPEG Camera from WSL bridge (localhost:8080)...")
        global_cam = MJPEGCamera("http://127.0.0.1:8080/stream")
        time.sleep(1)
    else:
        try:
            from picamera2 import Picamera2
            global_cam = Picamera2()
            global_cam.configure(global_cam.create_preview_configuration(
                main={"format": "BGR888", "size": (CAMERA_WIDTH, CAMERA_HEIGHT)},
                controls={"FrameRate": CAMERA_FPS},
            ))
            global_cam.start()
            time.sleep(1)
        except ImportError:
            from config import MJPEG_STREAM_URL
            logger.warning(f"picamera2 not found. Falling back to Wi-Fi MJPEG stream at {MJPEG_STREAM_URL}")
            try:
                global_cam = MJPEGCamera(MJPEG_STREAM_URL)
                time.sleep(1) # wait for first frame
            except Exception as e:
                logger.error(f"Failed to start MJPEGCamera: {e}")
                global_mav_bridge.stop()
                global_mav_bridge = None
                return False

    logger.info("Hardware initialized successfully.")
    return True

def stop_hardware():
    """Stops MAVLink and Camera."""
    global global_mav_bridge, global_cam, global_ros_thread
    
    logger.info("Stopping Hardware...")
    if global_mav_bridge:
        global_mav_bridge.stop()
        global_mav_bridge = None
        
    if global_cam:
        if hasattr(global_cam, 'stop'):
            global_cam.stop()
        global_cam = None
        
    if global_ros_thread and rclpy:
        try:
            rclpy.shutdown()
        except:
            pass
        global_ros_thread = None


def main():
    logger.info("═══════════════════════════════════════════════")
    logger.info("  GCS Orchestrator Starting in STANDBY mode...")
    logger.info("═══════════════════════════════════════════════")

    # ── 1. App Manager ──
    from apps.app_manager import AppManager
    app_mgr = AppManager()
    
    # ── 2. Environment Manager ──
    from provisioning.env_manager import EnvironmentManager
    env_mgr = EnvironmentManager()

    # Load the default app
    app_mgr.load_app("idle")
    logger.info("App Manager initialized. Default app: Manual Flight")

    # ── 3. Dashboard Server ──
    from dashboard.server import (
        start_server_in_thread, update_video_frame,
        push_telemetry, push_app_stats, push_new_detection,
        set_mav_bridge, set_app_manager, set_mission_command_callback,
        set_env_manager, set_hardware_callbacks
    )
    
    # Provide the server with a way to trigger hardware start/stop from the API
    def on_hardware_start():
        success = start_hardware()
        if success:
            app_mgr.set_mav_bridge(global_mav_bridge)
            set_mav_bridge(global_mav_bridge)
        return success

    def on_hardware_stop():
        stop_hardware()
        app_mgr.set_mav_bridge(None)
        set_mav_bridge(None)
        
    set_env_manager(env_mgr)
    set_hardware_callbacks(on_hardware_start, on_hardware_stop)
    set_app_manager(app_mgr)
    
    server_thread = start_server_in_thread()

    # ── 5. Wire Dashboard Commands ──
    def handle_dashboard_command(cmd):
        """Forward dashboard commands to the active app."""
        app_mgr.handle_command(cmd)

    set_mission_command_callback(handle_dashboard_command)

    # ── Main Loop ──
    logger.info("Starting main loop. Press Ctrl+C to exit.")

    last_telemetry_push = 0
    last_stats_push = 0
    fps_timer = time.time()
    frame_count = 0

    # Flight logging state
    flight_start_time = None
    max_alt = 0.0
    start_batt = 0
    was_armed = False

    try:
        while True:
            # If hardware is not running, just sleep and yield
            if not global_mav_bridge or not global_cam:
                # Provide a blank standby frame to the stream
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "GCS STANDBY - Awaiting Environment", (80, 240), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)
                update_video_frame(blank)
                time.sleep(0.5)
                continue

            # Capture frame
            if SIMULATION_MODE or os.environ.get("DRONE_MOCK", "false").lower() == "true":
                frame = global_cam.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                frame = frame.copy()
            else:
                frame = global_cam.capture_array("main")

            # Get telemetry
            tel = global_mav_bridge.get_telemetry()

            # ── Delegate to Active App ──
            annotated = app_mgr.process_frame(frame, tel)
            update_video_frame(annotated)

            # ── Push new detections (if app supports it) ──
            active_app = app_mgr.get_active_app()
            if active_app and hasattr(active_app, 'pop_new_detections'):
                for det in active_app.pop_new_detections():
                    push_new_detection(det)

            # ── Push updates at controlled rates ──
            now = time.time()
            if now - last_telemetry_push >= 0.1:
                push_telemetry(tel)
                last_telemetry_push = now

            if now - last_stats_push >= 0.2:
                stats = app_mgr.get_stats()
                if stats:
                    push_app_stats(stats)
                last_stats_push = now

            # ── Flight Logging ──
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
                    "app": app_mgr.get_active_app_id() or "unknown",
                    "battery_start": start_batt,
                    "battery_end": tel["battery_pct"]
                })
                was_armed = False

            if tel["armed"]:
                max_alt = max(max_alt, tel["alt"])

            # FPS counter
            frame_count += 1
            if now - fps_timer >= 2.0:
                fps = frame_count / (now - fps_timer)
                app_name = app_mgr.get_active_app().name if app_mgr.get_active_app() else "None"
                logger.info(f"FPS: {fps:.1f} | Active App: {app_name}")
                frame_count = 0
                fps_timer = now

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        app_mgr.stop()
        stop_hardware()
        env_mgr.stop_all()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
