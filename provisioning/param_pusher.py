"""
provisioning/param_pusher.py
Pushes parameters to FC via MAVLink.
"""
import os
from pymavlink import mavutil
import logging

logger = logging.getLogger("param_pusher")

def push_params(mav_bridge):
    if not mav_bridge or not mav_bridge.master:
        logger.error("Cannot push params: no MAVLink connection.")
        return False
        
    from provisioning.profile_manager import PROFILE_DIR, ACTIVE_PROFILE_NAME
    param_path = os.path.join(PROFILE_DIR, ACTIVE_PROFILE_NAME, "params.param")
    
    if not os.path.exists(param_path):
        logger.error(f"Param file not found: {param_path}")
        return False
        
    try:
        with open(param_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    param_id = parts[0].encode('utf-8')
                    param_value = float(parts[1])
                    logger.info(f"Setting param {param_id} to {param_value}")
                    mav_bridge.master.param_set_send(
                        mav_bridge.master.target_system, 
                        mav_bridge.master.target_component,
                        param_id, 
                        param_value, 
                        mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                    )
        return True
    except Exception as e:
        logger.error(f"Failed to push params: {e}")
        return False
