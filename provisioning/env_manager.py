"""
provisioning/env_manager.py — Environment Manager

Handles launching external simulators (Gazebo, ArduPilot SITL) via scripts
and configures the MAVLink/Camera connections accordingly.
"""

import os
import subprocess
import threading
import logging
import time

logger = logging.getLogger("env_manager")

class EnvironmentManager:
    def __init__(self):
        self.active_mode = None
        self.subprocesses = []
        self._lock = threading.Lock()

    def get_scripts_dir(self):
        """Return the absolute path to the scripts directory."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "scripts")

    def start_env(self, mode, port=None, baud=None):
        """
        Launch the required background processes for the given mode.
        mode can be: 'SITL', 'HITL', 'LIVE'
        """
        with self._lock:
            if self.active_mode is not None:
                logger.warning(f"Environment {self.active_mode} is already running. Stopping it first.")
                self.stop_all()

            logger.info(f"Starting environment: {mode}")
            scripts_dir = self.get_scripts_dir()
            
            try:
                if mode == 'SITL':
                    # Launch Gazebo + SITL + ROS
                    script_path = os.path.join(scripts_dir, "start_sitl.bat")
                    if os.path.exists(script_path):
                        # Use creationflags=subprocess.CREATE_NEW_CONSOLE on Windows to open a new terminal window
                        # so the user can see the simulator output (or errors if WSL is missing).
                        creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        p = subprocess.Popen([script_path], creationflags=creationflags)
                        self.subprocesses.append(p)
                        logger.info("Executed start_sitl.bat in a new console.")
                    
                    # Give it a moment to boot
                    time.sleep(2)
                    
                    # Configure for SITL (TCP connection, Mock camera for now until ROS2 is back)
                    os.environ["DRONE_MOCK"] = "true"  # Force mock camera since ROS2 relies on Ubuntu
                    os.environ["MAV_CONNECTION"] = "tcp:127.0.0.1:5760"

                elif mode == 'HITL':
                    # Launch Gazebo for HITL
                    script_path = os.path.join(scripts_dir, "start_hitl.bat")
                    if os.path.exists(script_path):
                        creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        p = subprocess.Popen([script_path], creationflags=creationflags)
                        self.subprocesses.append(p)
                        logger.info("Executed start_hitl.bat in a new console.")
                    
                    time.sleep(2)
                    
                    # Configure for HITL (Serial connection to Pixhawk, Mock camera)
                    os.environ["DRONE_MOCK"] = "true"
                    # Default Windows COM port placeholder; user can override via env var
                    os.environ["MAV_CONNECTION"] = os.environ.get("MAV_HITL_PORT", "COM3") 

                elif mode == 'LIVE':
                    # No simulators to launch. Just configure for live hardware.
                    logger.info("Configuring for Live Flight (Pi 5 + 433MHz Telemetry).")
                    os.environ["DRONE_MOCK"] = "false"
                    os.environ["MAV_CONNECTION"] = port or os.environ.get("MAV_LIVE_PORT", "/dev/ttyUSB0")
                    os.environ["MAV_BAUD"] = str(baud) if baud else os.environ.get("MAV_LIVE_BAUD", "57600")

                else:
                    logger.error(f"Unknown environment mode: {mode}")
                    return False

                self.active_mode = mode
                return True

            except Exception as e:
                logger.error(f"Failed to start environment {mode}: {e}")
                self.stop_all()
                return False

    def stop_all(self):
        """Kill any spawned subprocesses."""
        with self._lock:
            if not self.active_mode:
                return

            logger.info(f"Stopping environment: {self.active_mode}")
            
            for p in self.subprocesses:
                try:
                    p.terminate()
                except Exception as e:
                    logger.error(f"Error terminating subprocess: {e}")
            
            self.subprocesses.clear()
            self.active_mode = None
            logger.info("Environment stopped.")
