import subprocess
import threading
import cv2
import logging
import os
from .base_app import BaseMissionApp

logger = logging.getLogger("addc_app")

class ADDCReconApp(BaseMissionApp):
    name = "ADDC Reconnaissance"
    description = "Autonomous search and rescue mission for ADDC 2026-27."
    version = "1.0"
    icon = "fa-solid fa-crosshairs"

    def __init__(self):
        super().__init__()
        self._mission_process = None
        self._latest_state = {
            "state": "INIT",
            "wp_current": "-",
            "wp_total": "-",
            "qr_status": "Idle",
            "time_remaining": 300
        }
        self.pid_file = "/tmp/addc_mission.pid"

    def process_frame(self, frame, telemetry):
        if frame is None:
            return frame
        # Draw simple HUD for the GCS
        state_str = f"Phase: {self._latest_state.get('state', 'Unknown')}"
        timer_str = f"Time: {self._latest_state.get('time_remaining', 0)}s"
        qr_str = f"QR: {self._latest_state.get('qr_status', 'Idle')}"
        
        cv2.putText(frame, state_str, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, timer_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, qr_str, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return frame

    def get_widgets(self):
        return [
            {
                "type": "stat_grid",
                "title": "Mission Status",
                "stats": [
                    {"id": "addc_state", "label": "Phase", "icon": "fa-solid fa-plane", "color": "#3d8bfd"},
                    {"id": "addc_wp", "label": "Waypoint", "icon": "fa-solid fa-map-marker-alt", "color": "#34d399"},
                    {"id": "addc_qr", "label": "QR Status", "icon": "fa-solid fa-qrcode", "color": "#f5a623"},
                    {"id": "addc_time", "label": "Time Left", "icon": "fa-solid fa-stopwatch", "color": "#ef4444"},
                ]
            }
        ]

    def get_stats(self):
        # We rely on WebSocket direct pushes for this in app_v2.js, but provide fallback here
        return {}

    def on_command(self, command, mav_bridge=None):
        logger.info(f"ADDC App received command: {command}")
        
        if command == "start":
            if self._mission_process and self._mission_process.poll() is None:
                logger.warning("Mission is already running!")
                return
            
            logger.info("Spawning ADDC mission subprocess inside WSL...")
            mission_dir = "/mnt/c/Users/sonui/.gemini/antigravity/scratch/Aeroclub ADDC/addc_mission"
            
            # Using same PID capture trick as launcher
            cmd = f"echo $$ > {self.pid_file} && cd '{mission_dir}' && python3 main.py"
            self._mission_process = subprocess.Popen(
                ["wsl", "-e", "bash", "-lic", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
        elif command == "rtl":
            if mav_bridge:
                logger.info("Sending RTL command via MAVLink...")
                mav_bridge.send_command("rtl")
            
            if self._mission_process and self._mission_process.poll() is None:
                logger.info("Killing mission subprocess...")
                try:
                    subprocess.run(
                        ["wsl", "-e", "bash", "-c", f"if [ -f {self.pid_file} ]; then kill -9 $(cat {self.pid_file}) 2>/dev/null; rm -f {self.pid_file}; fi"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
                self._mission_process.terminate()

