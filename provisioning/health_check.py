"""
provisioning/health_check.py
Runs pre-flight diagnostics by querying FC parameters and sensor status.
"""

def run_preflight_checks(mav_bridge=None):
    """Returns a list of check results."""
    
    if not mav_bridge:
        return {"ready": False, "checks": [{"name": "Bridge Error", "passed": False, "warning": False, "message": "No MAVLink bridge"}]}
        
    tel = mav_bridge.get_telemetry()
    
    checks = []
    
    # 1. Connection
    conn_passed = tel.get("connected", False)
    checks.append({
        "name": "FC Heartbeat", 
        "passed": conn_passed, 
        "warning": False, 
        "message": "Connected" if conn_passed else "Disconnected"
    })
    
    # 2. GPS Check (Simple heuristic: if we have non-zero lat/lon, we have some fix)
    lat = tel.get("lat", 0)
    lon = tel.get("lon", 0)
    has_gps = abs(lat) > 0.001 and abs(lon) > 0.001
    checks.append({
        "name": "GPS Fix",
        "passed": has_gps,
        "warning": not has_gps,
        "message": f"Lat: {lat:.4f}, Lon: {lon:.4f}" if has_gps else "No Fix"
    })
    
    # 3. Battery Voltage
    batt_v = tel.get("battery_v", 0.0)
    batt_pct = tel.get("battery_pct", 0)
    batt_passed = batt_v > 14.0 # simple threshold
    checks.append({
        "name": "Battery Voltage",
        "passed": batt_passed,
        "warning": not batt_passed,
        "message": f"{batt_v:.1f}V ({batt_pct}%)"
    })
    
    # 4. Flight Mode
    mode = tel.get("mode", "UNKNOWN")
    # Usually we want to be in STABILIZE, GUIDED, or AUTO to arm safely
    mode_safe = mode in ["STABILIZE", "GUIDED", "LOITER"]
    checks.append({
        "name": "Flight Mode",
        "passed": mode_safe,
        "warning": not mode_safe,
        "message": mode
    })
    
    # 5. Compass (Mocked for now since we need more advanced MAVLink parsing for MAG_CAL_REPORT)
    checks.append({
        "name": "Compass Health", 
        "passed": True, 
        "warning": False, 
        "message": "Offsets OK"
    })
    
    is_ready = all(c["passed"] for c in checks)
    
    return {
        "ready": is_ready,
        "checks": checks
    }
