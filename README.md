# Next-Gen Autonomous Aerial Search & Rescue System (GCS & AI Companion) 🚁🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![ArduPilot](https://img.shields.io/badge/ArduPilot-SITL%20%2F%20Hardware-green.svg)](https://ardupilot.org/)
[![UI: Modern Glassmorphism](https://img.shields.io/badge/UI-Glassmorphism%20Dark-purple.svg)]()

Welcome to the **Next-Gen Autonomous Aerial Search & Rescue System**, an industry-grade, highly optimized software stack built to turn a Raspberry Pi companion computer and a Pixhawk flight controller into a fully autonomous, real-time AI-powered robotic platform.

This system is engineered specifically for autonomous sweeping search patterns, real-time human detection, traditional color/shape classification, and instant coordinate triangulation (geotagging) mapped onto an interactive, custom-built web dashboard.

---

## 🏗️ System & Network Architecture

This codebase is built around a **Decentralized Hybrid Network Topology** designed to maximize range and protect flight safety by separating critical flight operations from bandwidth-heavy video streams.

```mermaid
graph TD
    subgraph Laptop (Ground Station)
        GCS_Server[Flask + Socket.IO Backend]
        GCS_UI[Glassmorphism Web Dashboard]
        YOLO_Engine[YOLOv8 & OpenCV Detection Pipeline]
        GCS_Server -->|WebSockets| GCS_UI
        YOLO_Engine -->|Rendered Frames| GCS_Server
    end

    subgraph Raspberry Pi 5 (Companion Computer)
        Pi_Streamer[pi_streamer.py Camera Daemon]
        Pi_Cam[Pi Camera Module 3]
        Pi_Cam -->|Raw Frames| Pi_Streamer
    end

    subgraph Drone Hardware (Air Unit)
        Pixhawk[Pixhawk 6C Flight Controller]
        GPS[DroneCAN M8N GPS]
        GPS -->|CAN Bus| Pixhawk
    end

    %% Network Connections
    Pi_Streamer -->|Wi-Fi Hotspot: MJPEG @ Port 8080| YOLO_Engine
    GCS_Server -->|433MHz Telemetry Radio COM5 @ 57600 baud| Pixhawk
```

### 1. Flight Control & Telemetry Link (Long-Range, Bulletproof)
* **Hardware:** 433MHz Air & Ground Telemetry Radios.
* **Protocol:** MAVLink 2.0 over Serial (e.g., `COM5` on Windows at `57600` baud).
* **Role:** The Ground Control Station (GCS) server running on the laptop communicates directly with the Pixhawk over the air. Telemetry packets (altitude, GPS coordinates, heading, roll/pitch/yaw, battery voltage, and satellite counts) are read at 10Hz and sent to the UI via WebSockets. Commands (Arm, Disarm, Takeoff, Guided, Auto, RTL) are injected back into this stream.
* **Design Philosophy:** By isolating flight control onto the sub-GHz radio spectrum, we ensure the drone never loses connection to the GCS, even if high-frequency Wi-Fi ranges are exceeded.

### 2. High-Bandwidth Video & Vision Link (Medium-Range, High-Speed)
* **Hardware:** Raspberry Pi 5 + Pi Camera Module 3 + Local Wi-Fi Hotspot.
* **Protocol:** HTTP MJPEG Multipart Stream.
* **Role:** The Pi runs a lightweight background daemon (`pi_streamer.py`) that captures raw frames from the camera, wraps them in an HTTP MJPEG stream, and broadcasts them over the shared Wi-Fi hotspot on port `8080`. The GCS backend on the laptop catches this network stream, runs YOLOv8 and traditional OpenCV shape detection on the laptop's CPU/GPU, and renders the output onto the dashboard.
* **Benefits:** Video compression and AI crunching occur independently. The Pi stays cool and has minimal processing overhead, leaving CPU cycles free for other tasks, while the laptop acts as the primary AI inference engine executing frames at **80+ FPS**.

---

## 📂 Repository Deep Dive

```text
/
├── config.py                 # Core configurations (Baud, IPs, Topics, Geofences)
├── main.py                   # GCS Orchestrator (starts threads, binds camera/MAVLink)
├── deploy.py                 # Remote deployment script (SSH/SFTP to push files to the Pi)
├── requirements.txt          # Python dependencies
│
├── /apps                     # Modular, pluggable GCS application layers
│   ├── app_manager.py        # Dynamic app loading, lifecycle controller
│   ├── base_app.py           # Base abstraction layer for custom apps
│   ├── idle_app.py           # Manual Flight Mode (raw stream, raw HUD overlay)
│   └── search_rescue.py      # Autonomous Search & Rescue (YOLO, geotagging, memory grids)
│
├── /dashboard                # Ground Control Station UI Files
│   ├── server.py             # Flask + Socket.IO Server & WebSocket API
│   ├── /templates
│   │   └── index.html        # Glassmorphism HTML layout
│   └── /static
│       ├── /css
│       │   └── style.css     # Responsive CSS styling & animations
│       └── /js
│           └── app_v2.js     # WebSocket hooks, Map routing, UI update handlers
│
├── /detection                # AI & Computer Vision Subsystem
│   ├── cpu_detector.py       # High-speed YOLOv8 pipeline for CPUs
│   ├── hailo_detector.py     # Hardware accelerated YOLOv8 for Hailo-8L
│   └── shape_detector.py     # OpenCV contour math color/geometry classifier
│
├── /mission                  # Navigation & Mathematical Spatial Math
│   ├── path_planner.py       # Zig-zag lawnmower sweep coordinate generator
│   ├── mission_manager.py    # Waypoint packaging and MAVLink FTP upload manager
│   └── memory_grid.py        # Ray-casting coordinate mapping & grid matching
│
├── /telemetry                # Pixhawk MAVLink Communication Stack
│   └── mavlink_bridge.py     # Thread-safe telemetry reader and command injector
│
└── /profiles                 # Drone-specific YAML parameters & configs
```

### 🧠 Core Subsystems Breakdown

#### 1. Pluggable App Engine (`/apps`)
We threw away standard, monolithic script architectures. The GCS features a modular **App Manager** that allows the operator to swap the entire software behavior on the fly:
* **`base_app.py`**: Defines the lifecycle hooks (`on_start`, `process_frame`, `on_stop`, `get_widgets`).
* **`idle_app.py`**: Puts the drone in raw feed mode. It bypasses heavy neural nets and overlays a simple flight HUD (Alt, Speed, Heading) on the screen.
* **`search_rescue.py`**: Spins up the YOLOv8 and Shape classifiers, initializes the Memory Grid, coordinates real-time tagging, and tracks autonomous sweeping progression.

#### 2. Ray-Casting & Geotagging Engine (`/mission/memory_grid.py`)
This is the core mathematical powerhouse. When a target is detected in a camera frame, we don't just crop the image. The system performs dynamic **Pinhole Camera Ray Projection**:
1. **Pixel-to-Camera Coordinate Conversion:** Map the object's pixel coordinates $(x_{pixel}, y_{pixel})$ to camera space using the camera's field of view (FOV) and image sensor dimensions.
2. **Camera-to-Body Transformation:** Account for the camera's physical mounting angle (pitch/roll/yaw offsets).
3. **Body-to-Earth Transformation:** Rotate the coordinate vector into the Earth-Centered, Earth-Fixed (ECEF) frame using the drone's live compass heading, roll, and pitch telemetry.
4. **Altitude Intersection:** Intersect this rotated vector with the ground plane using the drone's relative altitude (above ground level, or AGL).
5. **GPS Triangulation:** Convert the resulting ground offset back to a precise Latitude/Longitude coordinate.
6. **Grid Matching:** Partition the coordinate into a structured, unique alphanumeric coordinate (e.g. `ZN3528702`). If the coordinate is already occupied in the grid database, it filters it out to prevent duplicates.

#### 3. Thread-Safe MAVLink Bridge (`/telemetry/mavlink_bridge.py`)
Manages communication with the flight controller:
* **Read Loop:** Spawns a background thread that polls for incoming MAVLink packets, parses them, updates a thread-safe dictionary, and handles system heartbeats.
* **Command Injection:** Safely queue write-commands (arm, mode selection, waypoint navigation) without blocking telemetry collection.
* **SITL Autodetect:** Intelligently detects if the target system is a simulator (TCP/UDP connection) or real hardware. If it is a simulator, it automatically executes parameters to override pre-arm checks (like compass consistency and lidar blocks) to streamline development. If it's a real drone, it suppresses these parameters to ensure safety checks are never bypassed.

---

## 🛠️ Setup & Installation

### 1. Laptop Setup (Ground Control Station)
Clone the repository and install the dependencies:
```bash
git clone https://github.com/SnehalShetty-sudo/AEROCLUB-snehal.git
cd AEROCLUB-snehal
pip install -r requirements.txt
```

Run the dashboard server:
```bash
python main.py
```

Open a browser and navigate to `http://localhost:5000`.

### 2. Raspberry Pi 5 Setup (Companion Camera)
Connect your laptop to the Pi via SSH:
```bash
ssh aeroclub123@10.236.25.244
```

We built a custom utility `deploy.py` that runs on the laptop to automatically clean old code and push the latest updates to the Pi via SFTP.
To push updates and start the camera stream daemon on the Pi:
```bash
python deploy.py
```
This script will:
1. SSH into the Pi and kill any process occupying the video port (`8080`).
2. Upload the updated `pi_streamer.py` directly to the Pi.
3. Start `pi_streamer.py` in a detached background state (`nohup`) that outputs logs to `/home/aeroclub123/pi_streamer.log` and stays running even if the SSH session closes.

---

## 🏎️ Running a Mission (Step-by-Step)

### Step 1: Establish Connections
1. Boot the drone and the companion Raspberry Pi.
2. Connect your laptop to the Raspberry Pi's Wi-Fi hotspot.
3. Connect your Ground Telemetry Radio to a USB port on your laptop.

### Step 2: Launch GCS
1. Run `python main.py` on your laptop.
2. Navigate your web browser to `http://localhost:5000`.
3. In the environment launcher, select **LIVE FLIGHT**.
4. In the expanded connection panel, select the telemetry **Serial Port** (e.g. `COM5` or `/dev/ttyUSB0`) and set the baud rate to **`57600 (Telemetry)`**.
5. Hit **CONNECT TO HARDWARE**.

### Step 3: Trigger Mission Apps
1. The GCS will handshake with the Pixhawk and check pre-arm status.
2. Under the **Apps** panel, click **Search & Rescue**.
3. The dashboard will automatically fetch the camera feed from the Pi and display the live video stream.
4. Upload your Geofence boundaries.
5. Hit **Start Mission** to compile the lawnmower sweeping pattern, load it to the Pixhawk, arm, and fly autonomously! Target logs will start populating with precise coordinates as targets are found.
