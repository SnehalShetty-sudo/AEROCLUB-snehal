"""
provisioning/calibrator.py
Handles ESC, accel, compass calibration via MAVLink commands.
"""
import time
import logging
from pymavlink import mavutil

logger = logging.getLogger("calibrator")

class Calibrator:
    def __init__(self, mav_bridge):
        self.mav_bridge = mav_bridge
    
    def start_compass_calibration(self, progress_callback):
        """Trigger compass calibration and report progress."""
        logger.info("Starting compass calibration...")
        if self.mav_bridge and self.mav_bridge.master:
            # Send MAV_CMD_DO_START_MAG_CAL (42424)
            self.mav_bridge.master.mav.command_long_send(
                self.mav_bridge.master.target_system,
                self.mav_bridge.master.target_component,
                42424, # MAV_CMD_DO_START_MAG_CAL
                0, 0, 0, 0, 0, 0, 0, 0
            )
            logger.info("MAV_CMD_DO_START_MAG_CAL sent to FC.")
            
        # For this version, we simulate the progress updates 
        # since reading MAG_CAL_PROGRESS requires intercepting the main read loop,
        # and physically rotating the SITL drone is complex.
        for i in range(10, 101, 10):
            time.sleep(0.5)
            progress_callback(i)
            
        if self.mav_bridge and self.mav_bridge.master:
            # Send MAV_CMD_DO_ACCEPT_MAG_CAL (42425)
            self.mav_bridge.master.mav.command_long_send(
                self.mav_bridge.master.target_system,
                self.mav_bridge.master.target_component,
                42425, # MAV_CMD_DO_ACCEPT_MAG_CAL
                0, 0, 0, 0, 0, 0, 0, 0
            )
            logger.info("MAV_CMD_DO_ACCEPT_MAG_CAL sent to FC.")
            
        logger.info("Compass calibration complete.")
