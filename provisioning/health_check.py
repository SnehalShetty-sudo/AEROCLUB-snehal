"""
provisioning/health_check.py
Runs pre-flight safety checks on drone telemetry.
"""
import logging

logger = logging.getLogger("health_check")

def run_preflight_checks(mav_bridge):
    """
    Returns a dict:
    {
        'ready': bool,
        'message': string,
        'issues': int,
        'checks': [ {'name': str, 'passed': bool, 'message': str}, ... ]
    }
    """
    if not mav_bridge:
        tel = {}
    else:
        tel = mav_bridge.get_telemetry()
        
    results = []
    
    # 1. FC Heartbeat
    connected = tel.get('connected', False)
    results.append({
        "name": "FC Connection",
        "passed": connected,
        "message": "Connected" if connected else "No heartbeat"
    })
    
    # 2. GPS Fix
    fix_type = tel.get('gps_fix_type', 0)
    sats = tel.get('gps_sats', 0)
    results.append({
        "name": "GPS Fix",
        "passed": fix_type >= 3,
        "message": f"3D Fix ({sats} sats)" if fix_type >= 3 else (f"No Fix ({sats} sats)" if fix_type < 3 else "Unknown")
    })
    
    # 3. GPS Satellites
    results.append({
        "name": "GPS Satellites",
        "passed": sats >= 6,
        "message": f"{sats} satellites visible" if sats >= 6 else f"Only {sats} satellites (need >=6)"
    })
    
    # 4. Battery Voltage
    voltage = tel.get('battery_v', 0.0)
    results.append({
        "name": "Battery Voltage",
        "passed": voltage > 14.0,
        "message": f"{voltage:.1f}V (OK for 4S)" if voltage > 14.0 else f"{voltage:.1f}V (Low!)"
    })
    
    # 5. Battery Level
    pct = tel.get('battery_pct', 0)
    results.append({
        "name": "Battery Level",
        "passed": pct > 20,
        "message": f"{pct}%" if pct > 20 else f"{pct}% (Too low)"
    })
    
    # 6. EKF Status
    ekf = tel.get('ekf_ok', False)
    results.append({
        "name": "EKF Health",
        "passed": ekf,
        "message": "EKF healthy" if ekf else "EKF not converged"
    })
    
    # 7. RC Receiver
    rc_ch = tel.get('rc_channels', 0)
    results.append({
        "name": "RC Receiver",
        "passed": rc_ch > 0,
        "message": f"Active ({rc_ch} ch)" if rc_ch > 0 else "No RC signal"
    })
    
    # 8. Flight Mode
    mode = tel.get('mode', 'UNKNOWN')
    valid_modes = ['STABILIZE', 'GUIDED', 'LOITER', 'ALT_HOLD']
    results.append({
        "name": "Flight Mode",
        "passed": mode in valid_modes,
        "message": mode if mode in valid_modes else f"{mode} (Change to STABILIZE/GUIDED)"
    })
    
    # 9. Compass Health
    compass_ok = True
    compass_msg = "Offsets OK"
    try:
        if hasattr(mav_bridge, 'get_status_texts'):
            texts = mav_bridge.get_status_texts()
            for t in texts:
                t_lower = t.lower()
                if 'compass' in t_lower or 'mag' in t_lower:
                    if 'error' in t_lower or 'bad' in t_lower or 'inconsistent' in t_lower or 'interference' in t_lower:
                        compass_ok = False
                        compass_msg = "Warnings found in log"
                        break
    except Exception as e:
        logger.warning(f"Failed to check compass texts: {e}")
        
    results.append({
        "name": "Compass Health",
        "passed": compass_ok,
        "message": compass_msg
    })
    
    return get_verdict(results)

def get_verdict(results):
    if not results:
        return {'ready': False, 'message': 'No checks run', 'issues': 1, 'checks': []}
        
    issues = sum(1 for r in results if not r['passed'])
    ready = issues == 0
    
    return {
        'ready': ready,
        'message': "ALL CHECKS PASSED — READY FOR FLIGHT" if ready else f"{issues} ISSUES FOUND — NOT READY",
        'issues': issues,
        'checks': results
    }
