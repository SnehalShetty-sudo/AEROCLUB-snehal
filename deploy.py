import paramiko
import sys
import time

host = '10.236.25.244'
user = 'aeroclub123'
password = 'Snehal@7411212400'

pi_streamer_code = """
import io
import time
import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from picamera2 import Picamera2

try:
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480), "format": "BGR888"}))
    picam2.start()
    time.sleep(2)
except Exception as e:
    print(f"Camera init failed: {e}")
    exit(1)

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/?action=stream':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    frame = picam2.capture_array("main")
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    if not ret: continue
                    frame_bytes = jpeg.tobytes()
                    self.wfile.write(b'--FRAME\\r\\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame_bytes))
                    self.end_headers()
                    self.wfile.write(frame_bytes)
                    self.wfile.write(b'\\r\\n')
            except Exception as e:
                pass
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

address = ('', 8080)
server = StreamingServer(address, StreamingHandler)
print("Starting MJPEG stream on port 8080...")
server.serve_forever()
"""

try:
    print(f"Connecting to {host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=5)
    
    # 1. Kill any existing python process on port 8080
    print("Killing any process on port 8080...")
    ssh.exec_command("fuser -k 8080/tcp")
    time.sleep(1)

    # 2. Write the file
    print("Uploading pi_streamer.py...")
    sftp = ssh.open_sftp()
    with sftp.file('/home/aeroclub123/pi_streamer.py', 'w') as f:
        f.write(pi_streamer_code)
    sftp.close()

    # 3. Start the streamer in the background
    print("Starting pi_streamer.py...")
    ssh.exec_command("nohup python3 /home/aeroclub123/pi_streamer.py > /home/aeroclub123/pi_streamer.log 2>&1 &")
    
    print("Deployment complete.")
    ssh.close()
    
except Exception as e:
    print(f"Deployment failed: {e}")
