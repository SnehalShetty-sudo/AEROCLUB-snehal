"""
mission/mission_manager.py — Uploads and manages missions on ArduPilot via MAVLink.
"""

import time
import logging
from pymavlink import mavutil

logger = logging.getLogger("mission_manager")

class MissionManager:
    def __init__(self, mavlink_bridge):
        self.bridge = mavlink_bridge
        
    def upload_mission(self, waypoints: list):
        """
        Upload a list of waypoints to the FC.
        waypoints: list of (lat, lon, alt)
        """
        if self.bridge.mock:
            logger.info(f"[MOCK] Uploaded {len(waypoints)} waypoints.")
            with self.bridge._telemetry_lock:
                self.bridge._state["wp_total"] = len(waypoints)
            return True
            
        master = self.bridge.master
        if not master:
            logger.error("No FC connection.")
            return False
            
        self.bridge.pause_read = True
        time.sleep(1.2) # Guarantee the 1.0s timeout in _read_loop has expired
        try:
            # 1. Clear existing mission
            logger.info("Clearing mission...")
            master.mav.mission_clear_all_send(master.target_system, master.target_component)
            time.sleep(0.5) # Blindly wait for FC to clear, bypass MAVProxy interception
            
            # 2. Tell FC how many items we will send
            # Add a dummy waypoint 0 (home) + Takeoff (seq=1) + the actual waypoints
            num_items = len(waypoints) + 2
            master.mav.mission_count_send(master.target_system, master.target_component, num_items)
            
            # 3. Send waypoints
            for seq in range(num_items):
                logger.info(f"Waiting for mission request seq {seq}...")
                start_wait = time.time()
                msg = None
                while time.time() - start_wait < 3.0:
                    m = master.recv_match(blocking=True, timeout=0.5)
                    if not m:
                        continue
                    if m.get_type() in ['MISSION_REQUEST_INT', 'MISSION_REQUEST']:
                        msg = m
                        break
                    elif m.get_type() == 'MISSION_ACK':
                        logger.error(f"Received MISSION_ACK error: {m.type}")
                        return False
                
                if not msg:
                    logger.error(f"No mission request for seq {seq}")
                    return False
                    
                if seq == 0:
                    # Add a dummy waypoint 0 (home) using the first waypoint's coordinates to prevent ArduCopter from glitching!
                    home_lat = int(waypoints[0][0] * 1e7) if waypoints else 0
                    home_lon = int(waypoints[0][1] * 1e7) if waypoints else 0
                    
                    master.mav.mission_item_int_send(
                        master.target_system, master.target_component, seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                        0, 1, 0, 0, 0, 0,
                        home_lat, home_lon, 0.0
                    )
                elif seq == 1:
                    # Automatic Takeoff Waypoint
                    _, _, alt = waypoints[0] # Takeoff to the altitude of the first waypoint
                    home_lat = int(waypoints[0][0] * 1e7) if waypoints else 0
                    home_lon = int(waypoints[0][1] * 1e7) if waypoints else 0
                    
                    master.mav.mission_item_int_send(
                        master.target_system, master.target_component, seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                        0, 1, 0, 0, 0, 0,
                        home_lat, home_lon, float(alt)
                    )
                else:
                    lat, lon, alt = waypoints[seq - 2]
                    master.mav.mission_item_int_send(
                        master.target_system, master.target_component, seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                        0, 1, # current, autocontinue
                        0, 0, 0, 0, # p1, p2, p3, p4 (delay, radius, pass_radius, yaw)
                        int(lat * 1e7), int(lon * 1e7), alt
                    )
                
            msg = master.recv_match(type=['MISSION_ACK'], blocking=True, timeout=3)
            if msg and msg.type == 0:
                logger.info(f"Successfully uploaded {len(waypoints)} waypoints.")
                with self.bridge._telemetry_lock:
                    self.bridge._state["wp_total"] = len(waypoints)
                return True
            else:
                logger.error("Mission upload failed at the end.")
                return False
                
        finally:
            self.bridge.pause_read = False
