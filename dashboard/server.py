"""
dashboard/server.py — Flask + Socket.IO server for the dashboard.
Serves the web UI, the MJPEG video stream, and real-time telemetry via WebSockets.
"""

import time
import logging
import threading
import cv2
import numpy as np
from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DASHBOARD_HOST, DASHBOARD_PORT, JPEG_QUALITY, STREAM_MAX_FPS

logger = logging.getLogger("dashboard_server")

app = Flask(__name__)
# use threading async mode to support standard background threads natively
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Shared state for video stream
_latest_frame = None
_frame_lock = threading.Lock()
_frame_ready_event = threading.Event()

def update_video_frame(frame: np.ndarray):
    """Called by the main loop to update the stream frame."""
    global _latest_frame
    with _frame_lock:
        _latest_frame = frame
    _frame_ready_event.set()

def generate_mjpeg_stream():
    """Generator for the MJPEG stream."""
    min_frame_time = 1.0 / STREAM_MAX_FPS
    last_frame_time = 0

    while True:
        # Wait for a new frame
        _frame_ready_event.wait(timeout=0.5)
        _frame_ready_event.clear()

        with _frame_lock:
            frame = _latest_frame

        if frame is None:
            time.sleep(0.01)
            continue

        now = time.time()
        if (now - last_frame_time) < min_frame_time:
            time.sleep(min_frame_time - (now - last_frame_time))
            
        last_frame_time = time.time()

        # Encode to JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ret:
            continue
            
        frame_bytes = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """Serve the dashboard HTML."""
    from config import GEOFENCE_POLYGON
    import json
    return render_template('index.html', geofence=json.dumps(GEOFENCE_POLYGON))

@app.route('/video_feed')
def video_feed():
    """MJPEG stream endpoint."""
    return Response(generate_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# WebSocket events
@socketio.on('connect')
def handle_connect():
    logger.info("Dashboard client connected.")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Dashboard client disconnected.")

_mission_command_callback = None
_mav_bridge = None

def set_mav_bridge(bridge):
    global _mav_bridge
    _mav_bridge = bridge

def set_mission_command_callback(cb):
    global _mission_command_callback
    _mission_command_callback = cb

@socketio.on('mission_command')
def handle_mission_command(data):
    """Handle commands from the dashboard (e.g., start, pause, abort)."""
    cmd = data.get('command')
    logger.info(f"Received mission command: {cmd}")
    if _mission_command_callback:
        _mission_command_callback(cmd)
    socketio.emit('command_ack', {'command': cmd, 'status': 'received'})

@app.route('/api/preflight')
def api_preflight():
    from provisioning.health_check import run_preflight_checks
    return jsonify(run_preflight_checks(_mav_bridge))

@app.route('/api/profiles')
def api_profiles():
    from provisioning.profile_manager import list_profiles
    return jsonify({"profiles": list_profiles()})

@app.route('/api/profiles/active')
def api_profiles_active():
    from provisioning.profile_manager import get_active_profile
    return jsonify({"profile": get_active_profile()})

from flask import request
@app.route('/api/profiles/switch', methods=['POST'])
def api_profiles_switch():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({"success": False, "error": "No name provided"})
    from provisioning.profile_manager import set_active_profile
    success = set_active_profile(name)
    return jsonify({"success": success})

@app.route('/api/profiles/push', methods=['POST'])
def api_profiles_push():
    from provisioning.param_pusher import push_params
    result = push_params(_mav_bridge)
    return jsonify(result)

@app.route('/api/logs')
def api_logs():
    from config import LOG_DIR
    import json
    log_file = LOG_DIR / "flight_logs.jsonl"
    logs = []
    if log_file.exists():
        with open(log_file, "r") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except:
                    pass
    return jsonify({"logs": list(reversed(logs))})

_calibrator = None

@socketio.on('start_calibration')
def handle_start_calibration(data):
    global _calibrator
    cal_type = data.get('type')
    
    from provisioning.calibrator import Calibrator
    if not _calibrator:
        _calibrator = Calibrator(_mav_bridge)
        
    if cal_type == 'compass':
        def progress_cb(pct):
            socketio.emit('calibration_progress', {'type': 'compass', 'progress': pct})
        threading.Thread(target=_calibrator.start_compass_calibration, args=(progress_cb,)).start()
        
    elif cal_type == 'accel':
        def progress_cb(pct):
            socketio.emit('calibration_progress', {'type': 'accel', 'progress': pct})
        def step_cb(step, text, wait_for_user=False):
            socketio.emit('calibration_step', {'type': 'accel', 'step': step, 'text': text, 'wait_for_user': wait_for_user})
        threading.Thread(target=_calibrator.start_accel_calibration, args=(progress_cb, step_cb)).start()
        
    elif cal_type == 'esc':
        def step_cb(step, text, wait_for_user=False):
            socketio.emit('calibration_step', {'type': 'esc', 'step': step, 'text': text, 'wait_for_user': wait_for_user})
        threading.Thread(target=_calibrator.start_esc_calibration, args=(step_cb,)).start()

@app.route('/api/calibration/continue', methods=['POST'])
def api_calibration_continue():
    global _calibrator
    if _calibrator:
        _calibrator.continue_calibration()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No calibration running"})

def push_telemetry(data: dict):
    """Push telemetry data to connected clients."""
    socketio.emit('telemetry_update', data)

def push_detection_stats(data: dict):
    """Push detection statistics to connected clients."""
    socketio.emit('detection_update', data)

def push_new_detection(detection_data: dict):
    """Push detailed new detection data (Lat/Lon/Cell) to connected clients."""
    # Add a timestamp so the frontend doesn't have to calculate it
    import datetime
    detection_data["time"] = datetime.datetime.now().strftime("%H:%M:%S")
    socketio.emit('new_detection', detection_data)

def start_server_in_thread():
    """Start the Flask-SocketIO server in a background thread."""
    def run():
        # turn off flask logging to avoid spam
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        socketio.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)
        
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"Dashboard server started on {DASHBOARD_HOST}:{DASHBOARD_PORT}")
    return thread

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    start_server_in_thread().join()
