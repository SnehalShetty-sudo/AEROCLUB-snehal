"""
dashboard/server.py — Flask + Socket.IO server for the dashboard.
Serves the web UI, the MJPEG video stream, and real-time telemetry via WebSockets.
"""

import time
import logging
import threading
import cv2
import numpy as np
from flask import Flask, render_template, Response
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
    return render_template('index.html')

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
