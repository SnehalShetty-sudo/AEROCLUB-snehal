"""
provisioning/param_pusher.py
Pushes parameters to FC via MAVLink.
"""
import os
import time
import threading
from pymavlink import mavutil
import logging

logger = logging.getLogger("param_pusher")

def push_params(mav_bridge):
    result = {"success": False, "pushed": 0, "failed": 0, "errors": []}
    
    if not mav_bridge:
        logger.error("Cannot push params: no MAVLink bridge.")
        result["errors"].append("No MAVLink bridge")
        return result

    # Read active profile param file
    from provisioning.profile_manager import get_profile_params, get_active_profile
    active_profile = get_active_profile()
    if not active_profile:
        result["errors"].append("No active profile")
        return result
        
    profile_name = active_profile.get("name", "").lower().replace(" ", "_").replace("—_", "")
    # Actually, active_profile name isn't exactly the directory name. 
    # Let's just use the profile manager's method that knows the active dir.
    # Wait, get_active_profile() returns the yaml content. Let's do this directly.
    from provisioning.profile_manager import _get_active_profile_name, get_profile_params
    profile_dir_name = _get_active_profile_name()
    param_content = get_profile_params(profile_dir_name)
    
    if param_content is None:
        logger.error("Param file not found or empty.")
        result["errors"].append("Param file not found")
        return result

    if getattr(mav_bridge, 'mock', False):
        logger.info("MOCK MODE: Simulating parameter push.")
        lines = param_content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    result["pushed"] += 1
                    time.sleep(0.01)
        result["success"] = True
        return result

    if not mav_bridge.master:
        logger.error("Cannot push params: no MAVLink connection.")
        result["errors"].append("No connection")
        return result

    lines = param_content.split('\n')
    
    # We will use an event to wait for PARAM_VALUE
    param_event = threading.Event()
    last_param_received = {}

    def param_callback(msg):
        if msg.get_type() == 'PARAM_VALUE':
            param_id = msg.param_id
            if isinstance(param_id, bytes):
                param_id = param_id.decode('utf-8', errors='ignore')
            # null-terminated strings
            param_id = param_id.split('\x00')[0]
            last_param_received['id'] = param_id
            last_param_received['value'] = msg.param_value
            param_event.set()

    # Register callback (will be implemented in mavlink_bridge.py)
    if hasattr(mav_bridge, 'register_message_callback'):
        mav_bridge.register_message_callback('PARAM_VALUE', param_callback)
    
    try:
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                param_id = parts[0]
                param_value = float(parts[1])
                logger.info(f"Setting param {param_id} to {param_value}")
                
                param_event.clear()
                last_param_received.clear()
                
                mav_bridge.master.param_set_send(
                    mav_bridge.master.target_system, 
                    mav_bridge.master.target_component,
                    param_id.encode('utf-8'), 
                    param_value, 
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                )
                
                # Wait for ACK if callback system is active
                if hasattr(mav_bridge, 'register_message_callback'):
                    accepted = param_event.wait(timeout=2.0)
                    if accepted and last_param_received.get('id') == param_id:
                        logger.info(f"Param {param_id} accepted.")
                        result["pushed"] += 1
                    else:
                        logger.warning(f"Param {param_id} timeout or mismatch.")
                        result["failed"] += 1
                        result["errors"].append(param_id)
                else:
                    # Fallback if no callback system
                    result["pushed"] += 1
                
                time.sleep(0.1) # 100ms delay to prevent overwhelming FC
                
        result["success"] = result["failed"] == 0
        
    except Exception as e:
        logger.error(f"Failed to push params: {e}")
        result["errors"].append(str(e))
    finally:
        if hasattr(mav_bridge, 'unregister_message_callback'):
            mav_bridge.unregister_message_callback('PARAM_VALUE', param_callback)

    return result
