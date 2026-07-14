"""
provisioning/calibrator.py
Handles sensor calibration routines (Compass, Accel, ESC).
"""
import time
import threading
import logging
from pymavlink import mavutil

logger = logging.getLogger("calibrator")

class Calibrator:
    def __init__(self, mav_bridge):
        self.mav_bridge = mav_bridge
        self._user_continue_event = threading.Event()
        
    def continue_calibration(self):
        """Called by the frontend when user acknowledges a step."""
        self._user_continue_event.set()

    def start_compass_calibration(self, progress_callback):
        """Starts compass calibration and monitors progress."""
        if getattr(self.mav_bridge, 'mock', False):
            logger.info("MOCK: Starting compass calibration.")
            for i in range(10, 101, 10):
                time.sleep(0.5)
                progress_callback(i)
            return True

        if not self.mav_bridge.master:
            return False

        logger.info("Starting compass calibration.")
        self.mav_bridge.master.mav.command_long_send(
            self.mav_bridge.master.target_system,
            self.mav_bridge.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_START_MAG_CAL,
            0, 0, 0, 0, 0, 0, 0, 0
        )

        cal_done_event = threading.Event()
        success = [False]

        def mag_progress_cb(msg):
            # completion_pct is 0-100
            if hasattr(msg, 'completion_pct'):
                progress_callback(msg.completion_pct)

        def mag_report_cb(msg):
            if hasattr(msg, 'cal_status'):
                if msg.cal_status == 4: # MAG_CAL_SUCCESS
                    logger.info("Compass calibration succeeded.")
                    success[0] = True
                    # Accept calibration
                    self.mav_bridge.master.mav.command_long_send(
                        self.mav_bridge.master.target_system,
                        self.mav_bridge.master.target_component,
                        mavutil.mavlink.MAV_CMD_DO_ACCEPT_MAG_CAL,
                        0, 0, 0, 0, 0, 0, 0, 0
                    )
                else:
                    logger.error(f"Compass calibration failed with status: {msg.cal_status}")
                cal_done_event.set()

        self.mav_bridge.register_message_callback('MAG_CAL_PROGRESS', mag_progress_cb)
        self.mav_bridge.register_message_callback('MAG_CAL_REPORT', mag_report_cb)

        try:
            cal_done_event.wait(timeout=60.0)
        finally:
            self.mav_bridge.unregister_message_callback('MAG_CAL_PROGRESS', mag_progress_cb)
            self.mav_bridge.unregister_message_callback('MAG_CAL_REPORT', mag_report_cb)

        return success[0]

    def start_accel_calibration(self, progress_callback, step_callback=None):
        """Starts accelerometer calibration."""
        if getattr(self.mav_bridge, 'mock', False):
            logger.info("MOCK: Starting accel calibration.")
            steps = ["Level", "Left", "Right", "Nose Down", "Nose Up", "Back"]
            for i, step in enumerate(steps):
                if step_callback:
                    step_callback(i+1, f"Place vehicle {step}", wait_for_user=False)
                progress_callback(int((i/6)*100))
                time.sleep(1)
            progress_callback(100)
            return True
            
        if not self.mav_bridge.master:
            return False
            
        logger.info("Starting accel calibration.")
        self.mav_bridge.master.mav.command_long_send(
            self.mav_bridge.master.target_system,
            self.mav_bridge.master.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
            0, 0, 0, 0, 1, 0, 0  # param5=1 for accel cal
        )

        cal_done_event = threading.Event()
        success = [False]

        def ack_cb(msg):
            if hasattr(msg, 'command') and msg.command == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION:
                if msg.result == 0:
                    success[0] = True
                else:
                    logger.error(f"Accel cal command rejected: result {msg.result}")
                cal_done_event.set()

        def text_cb(msg):
            if hasattr(msg, 'text'):
                text = msg.text
                if isinstance(text, bytes):
                    text = text.decode('utf-8', errors='ignore')
                text = text.split('\x00')[0]
                # Forward texts like "Place vehicle level and press any key"
                if "Place vehicle" in text and step_callback:
                    step_callback(0, text, wait_for_user=False)
                    # Fake progress just to show something
                    progress_callback(50)

        self.mav_bridge.register_message_callback('COMMAND_ACK', ack_cb)
        self.mav_bridge.register_message_callback('STATUSTEXT', text_cb)

        try:
            cal_done_event.wait(timeout=120.0)
            if success[0]:
                progress_callback(100)
        finally:
            self.mav_bridge.unregister_message_callback('COMMAND_ACK', ack_cb)
            self.mav_bridge.unregister_message_callback('STATUSTEXT', text_cb)

        return success[0]

    def start_esc_calibration(self, step_callback):
        """Guides user through ESC calibration."""
        mock = getattr(self.mav_bridge, 'mock', False)
        
        def wait_user(step, text):
            self._user_continue_event.clear()
            step_callback(step, text, wait_for_user=True)
            if mock:
                time.sleep(1) # Fake user clicking continue
            else:
                self._user_continue_event.wait(timeout=300) # Wait up to 5 mins

        logger.info("Starting ESC calibration.")
        
        wait_user(1, 'Remove all propellers for safety')
        wait_user(2, 'Disconnect the battery')
        
        if not mock and self.mav_bridge.master:
            self.mav_bridge.master.mav.command_long_send(
                self.mav_bridge.master.target_system,
                self.mav_bridge.master.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
                0,
                0, 0, 0, 0, 0, 0, 1  # param7=1 for ESC cal
            )
            
        wait_user(3, 'Connect the battery. You should hear the ESC initialization tones.')
        
        step_callback(4, 'Wait for the musical tone indicating calibration is complete...', wait_for_user=False)
        time.sleep(5)
        
        wait_user(5, 'ESC Calibration complete! Disconnect and reconnect battery to exit cal mode.')
        
        return True
