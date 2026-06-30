# Aerial Detection System Walkthrough

The drone detection system is now fully deployed and actively running on your Raspberry Pi! 🚀

## System Architecture

We successfully implemented a highly modular architecture that fixes the issues from your previous attempts:

1. **Hailo Detection Engine**: Running a pre-compiled YOLOv8n HEF model on the Hailo-8 NPU. By reusing the inference context, we eliminated the bottleneck and are now consistently hitting **~30 FPS** (which is the camera cap).
2. **OpenCV Shape Detector**: A hyper-fast contour detector that identifies triangles, squares, and rectangles based on HSV color thresholds. (Currently tuned to search for Red and Blue sheets).
3. **Flask + Socket.IO Dashboard**: A beautiful, dark-mode, glassmorphic UI that serves an MJPEG stream while asynchronously pushing telemetry and detection stats via WebSocket.
4. **MAVLink Bridge**: Currently running in Mock mode to simulate drone telemetry while the FC is disconnected. 

## How to use the Dashboard

You can access the real-time dashboard from any device on your local LAN network:

🔗 **[http://10.250.199.244:5000](http://10.250.199.244:5000)**

### What you'll see:
- **Live Video Feed**: The raw camera stream with bounding boxes and confidence scores overlaid in real-time.
- **Detection Summary**: Animated counters tracking the number of Persons, Triangles, Squares, and Rectangles spotted during the mission.
- **Telemetry Panel**: (Currently simulating) Altitude, Speed, GPS, Heading, and Battery voltage.
- **Mission Controls**: Buttons to trigger `Start Mission`, `Pause`, and `RTL (Abort)`.

## Tuning for the Real World

Since we are using HSV color thresholding for shape detection, we may need to tune the values slightly depending on the exact color of the sheets and the lighting conditions outdoors.
You can adjust these settings in your new `config.py` file located at `c:\Users\ASUS\Documents\PI\pi-drone\config.py`:

```python
# config.py
SHAPE_COLORS = {
    "red_low":  {"lower": (0, 100, 100),   "upper": (10, 255, 255)},
    "red_high": {"lower": (160, 100, 100),  "upper": (180, 255, 255)},
    "blue":     {"lower": (100, 100, 80),   "upper": (130, 255, 255)},
}
```

## Next Steps

Tomorrow, once you connect the Pixhawk 6C to the Pi via USB:
1. Open `config.py`
2. Change `FC_MOCK_MODE = False`
3. Restart the main script on the Pi: `python3 ~/pi-drone/main.py`
4. The dashboard will automatically reconnect and start streaming live telemetry from the flight controller!
