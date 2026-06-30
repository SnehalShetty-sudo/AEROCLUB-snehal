"""
telemetry/mavlink_bridge.py — MAVLink interface to ArduPilot.

Connects to the Pixhawk via USB or Serial. 
Reads telemetry and exposes it in a thread-safe way.
Sends commands (ARM, MODE, MISSION_START).
Provides a Mock mode for development without hardware.
"""

import time
import math
import logging
import threading
from pymavlink import mavutil

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FC_CONNECTION_STRING, FC_BAUD, FC_MOCK_MODE

logger = logging.getLogger("mavlink_bridge")

class MavlinkBridge:
    def __init__(self, connection_string=None, baud=None, mock=None):
        self.connection_string = connection_string or FC_CONNECTION_STRING
        self.baud = baud or FC_BAUD
        self.mock = mock if mock is not None else FC_MOCK_MODE
        
        self.master = None
        self._thread = None
        self._stop_event = threading.Event()
        self._telemetry_lock = threading.Lock()
        
        # Current drone state
        self._state = {
            "connected": False,
            "armed": False,
            "mode": "UNKNOWN",
            "lat": 0.0,
            "lon": 0.0,
            "alt": 0.0,          # relative altitude (AGL)
            "heading": 0,
            "speed": 0.0,        # ground speed
            "battery_v": 0.0,
            "battery_pct": 0,
            "wp_current": 0,
            "wp_total": 0,
        }

    def start(self):
        if self.mock:
            logger.info("Starting MAVLink bridge in MOCK mode.")
            self._thread = threading.Thread(target=self._mock_loop, daemon=True)
        else:
            logger.info(f"Connecting to FC at {self.connection_string} (baud {self.baud})")
            try:
                self.master = mavutil.mavlink_connection(self.connection_string, baud=self.baud)
                self._thread = threading.Thread(target=self._read_loop, daemon=True)
            except Exception as e:
                logger.error(f"Failed to connect to FC: {e}")
                return False
                
        self._thread.start()
        return True

    def get_telemetry(self) -> dict:
        """Return a copy of the current telemetry state."""
        with self._telemetry_lock:
            return dict(self._state)

    def send_command(self, cmd_name: str):
        """Send a high-level command to the FC."""
        logger.info(f"Sending command: {cmd_name}")
        
        if self.mock:
            with self._telemetry_lock:
                if cmd_name == "start":
                    self._state["armed"] = True
                    self._state["mode"] = "AUTO"
                elif cmd_name == "pause":
                    self._state["mode"] = "GUIDED"
                elif cmd_name == "rtl":
                    self._state["mode"] = "RTL"
            return
            
        if not self.master:
            return
            
        if cmd_name == "start":
            logger.info("Setting mode to GUIDED...")
            self.master.set_mode('GUIDED')
            time.sleep(0.5)
            
            logger.info("Sending ARM command...")
            self.master.mav.command_long_send(
                self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 1, 0, 0, 0, 0, 0, 0
            )
            
            # Wait for arming to complete
            time.sleep(2.0)
            
            # Send TAKEOFF command in GUIDED mode (exactly what the user typed in MAVProxy!)
            logger.info("Commanding takeoff to 10m...")
            self.master.mav.command_long_send(
                self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0, 0, 0, 0, 0, 0, 0, 10.0
            )
            
            # Give it time to spool up and climb
            logger.info("Waiting for drone to climb...")
            time.sleep(5.0)
            
            # Set AUTO mode to fly the rest of the mission
            logger.info("Switching to AUTO mode...")
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                3
            )
        elif cmd_name == "pause":
            # Set GUIDED mode (ArduCopter mode 4)
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                4
            )
        elif cmd_name == "rtl":
            # Set RTL mode (ArduCopter mode 6)
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                6
            )

    def _read_loop(self):
        """Continuously read MAVLink messages from the FC."""
        # Wait for first heartbeat from the drone (ignore MAVProxy GCS heartbeats)
        logger.info("Waiting for heartbeat from drone...")
        while True:
            msg = self.master.wait_heartbeat()
            if msg.get_srcSystem() != 255:
                self.master.target_system = msg.get_srcSystem()
                self.master.target_component = msg.get_srcComponent()
                break
        logger.info(f"Heartbeat received from drone: system {self.master.target_system} component {self.master.target_component}")
        
        # Disable arming checks in SITL to avoid annoying 'Gyros inconsistent' pre-arm failures
        if SIMULATION_MODE:
            logger.info("Disabling arming checks for simulation...")
            self.master.param_set_send(
                self.master.target_system, self.master.target_component,
                b'ARMING_CHECK', 0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
        
        with self._telemetry_lock:
            self._state["connected"] = True
            
        # Request data streams (e.g., GPS, battery, attitude) at 4 Hz
        # Without this, the Pixhawk might only send heartbeats!
        try:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                4, # Rate in Hz
                1  # Start sending
            )
            logger.info("Requested MAVLink data streams at 4Hz.")
        except Exception as e:
            logger.warning(f"Failed to request data streams: {e}")
            
        # ArduCopter mode mapping
        mode_mapping = {
            0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO",
            4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND"
        }

        while not self._stop_event.is_set():
            if getattr(self, 'pause_read', False):
                time.sleep(0.1)
                continue
                
            msg = self.master.recv_match(blocking=True, timeout=1.0)
            if not msg:
                continue
                
            msg_type = msg.get_type()
            
            with self._telemetry_lock:
                if msg_type == "HEARTBEAT":
                    self._state["armed"] = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                    self._state["mode"] = mode_mapping.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
                
                elif msg_type == "GLOBAL_POSITION_INT":
                    self._state["lat"] = msg.lat / 1e7
                    self._state["lon"] = msg.lon / 1e7
                    self._state["alt"] = msg.relative_alt / 1000.0  # mm to m
                    self._state["heading"] = msg.hdg / 100.0
                    # calculate ground speed from vx, vy
                    self._state["speed"] = math.sqrt(msg.vx**2 + msg.vy**2) / 100.0
                    
                elif msg_type == "SYS_STATUS":
                    self._state["battery_v"] = msg.voltage_battery / 1000.0
                    self._state["battery_pct"] = msg.battery_remaining
                    
                elif msg_type == "MISSION_CURRENT":
                    self._state["wp_current"] = msg.seq
                    # wp_total is typically known during upload, we can track it separately

    def _mock_loop(self):
        """Generate fake telemetry for UI testing."""
        with self._telemetry_lock:
            self._state["connected"] = True
            self._state["battery_v"] = 14.8
            self._state["battery_pct"] = 100
            self._state["lat"] = 28.6139
            self._state["lon"] = 77.2090
            self._state["wp_total"] = 10
            
        t = 0
        while not self._stop_event.is_set():
            time.sleep(0.1)
            t += 0.1
            
            with self._telemetry_lock:
                # Slowly drain battery
                self._state["battery_v"] = max(13.5, 14.8 - (t * 0.001))
                self._state["battery_pct"] = int(max(0, 100 - (t * 0.1)))
                
                if self._state["armed"]:
                    # Simulate flying in a circle
                    radius = 0.0005
                    self._state["lat"] = 28.6139 + radius * math.sin(t * 0.1)
                    self._state["lon"] = 77.2090 + radius * math.cos(t * 0.1)
                    
                    if self._state["mode"] == "AUTO":
                        self._state["alt"] = min(15.0, self._state["alt"] + 0.5)
                        self._state["speed"] = 2.0
                        self._state["heading"] = (self._state["heading"] + 1) % 360
                        
                        # Advance waypoints slowly
                        if int(t) % 5 == 0 and self._state["wp_current"] < self._state["wp_total"]:
                            self._state["wp_current"] = int(t / 5) % (self._state["wp_total"] + 1)
                    elif self._state["mode"] == "RTL":
                        self._state["alt"] = max(0.0, self._state["alt"] - 0.5)
                        self._state["speed"] = 0.5
                        if self._state["alt"] <= 0:
                            self._state["armed"] = False
                            self._state["mode"] = "STABILIZE"
                else:
                    self._state["alt"] = 0.0
                    self._state["speed"] = 0.0

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.master:
            self.master.close()
        logger.info("MAVLink bridge stopped.")
