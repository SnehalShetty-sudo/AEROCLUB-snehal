# The Ultimate GCS & AI Companion Developer Guide 🚁🤖
### A Comprehensive Manual for Systems Architecture, Spatial Mathematics, and Onboarding

Welcome to the official developer guide for the **Autonomous Search & Rescue Ground Control Station (GCS)**. This document serves as an exhaustive reference manual for developers, pilots, and system engineers. It covers everything from high-level network topology to the mathematical equations governing coordinate triangulation, and provides a step-by-step setup guide for a complete beginner setting up a development machine from scratch at home.

---

## 📖 Table of Contents
1. **System Vision & Core Concept**
2. **Technical Architecture & Data Flows**
   - The Hybrid Communications Topology
   - Multithreaded Orchestration Model
   - The Pluggable App Lifecycle
3. **The Mathematics of Autonomous Flight & Computer Vision**
   - Lawnmower Path Planning Algorithms
   - Ray-Casting & Pinhole Camera Coordinate Geotagging
   - Spatial Memory Grid Allocation
4. **Backend Telemetry & Hardware Control**
   - Thread-Safe MAVLink Bridging
   - State Boundaries (SITL vs. LIVE)
5. **Computer Vision & Inference Pipeline**
   - Real-time YOLOv8 Execution
   - OpenCV Traditional Math Contour & Shape Classifiers
6. **Exhaustive Onboarding & Installation Guide**
   - Step 1: Base Operating System Prerequisites (Windows/macOS)
   - Step 2: Setting up Git and Downloading the Repository
   - Step 3: Isolating Python Environments (Virtual Environments)
   - Step 4: Installing Core Dependencies
   - Step 5: Booting GCS in Local Mock Mode (No Hardware Required)
7. **Frontend Customization & UI Developer Reference**
   - Where the Code Lives (HTML/CSS/JS Maps)
   - Real-time HUD and Leaflet.js Map Bindings
   - Socket.IO WebSockets Protocol Reference

---

## 1. System Vision & Core Concept

During autonomous drone competitions (like ADDC) or real-world search-and-rescue operations, operators face high-stress environments. Traditionally, piloting a drone while running AI computer vision required:
1. A commercial Ground Control Station (like Mission Planner or QGroundControl) to upload flight paths.
2. A separate terminal window running SSH connections to the drone’s companion computer (Raspberry Pi) to monitor custom AI scripts.
3. Multiple standalone terminal scripts running video streaming wrappers.

If a script crashed mid-flight, or if a parameter had to be tweaked, the pilot had to juggle terminal screens, command lines, and GCS windows. This layout was highly vulnerable to configuration drift (where settings change between tests) and pilot distraction.

This project solves this by merging **flight operations, computer vision, geolocated mapping, and companion computer status into a single, cohesive, web-based dashboard**. The user interacts with the system using simple, modular "apps" (e.g. Manual Flight vs. Search & Rescue). Swapping apps changes the telemetry display and active AI algorithms instantly with a single click.

---

## 2. Technical Architecture & Data Flows

### The Hybrid Communications Topology

The system is split into two physical nodes: the **Air Unit** (Drone carrying a Pixhawk and Raspberry Pi) and the **Ground Unit** (Operator's Laptop). 

Because streaming high-definition video requires heavy network bandwidth, and transmitting flight telemetry requires absolute stability, the GCS uses a **split-link hybrid architecture**:

```text
+-------------------------------------------------------------------------+
|                         GROUND UNIT (LAPTOP)                            |
|                                                                         |
|  +--------------------+   WebSockets   +----------------------------+   |
|  |                    | <------------> |                            |   |
|  |  Glassmorphism UI  |                |  Flask + Socket.IO Server  |   |
|  |     (Browser)      | <------------  |        (main.py)           |   |
|  |                    |   MJPEG Video  +----------------------------+   |
|  +--------------------+                              ^                  |
|                                                      |                  |
|                                                      v                  |
|                                            +------------------------+   |
|                                            |   MAVLink Controller   |   |
|                                            | (mavlink_bridge.py)    |   |
|                                            +------------------------+   |
+-------------------------------------------------------^-----------------+
                      ^                                 |
                      | Wi-Fi Hotspot                   | 433MHz Radio
                      | (MJPEG video stream)            | (MAVLink telemetry)
                      v                                 v
+------------------------------------------+ +----------------------------+
|        COMPANION COMPUTER (PI 5)         | |      FLIGHT CONTROLLER     |
|                                          | |        (PIXHAWK 6C)        |
|  +-------------------+                   | |                            |
|  |   pi_streamer.py  |                   | |  +----------------------+  |
|  | (Background Daemon)|                  | |  |  ArduPilot Firmware  |  |
|  +-------------------+                   | |  +----------------------+  |
|           ^                              | |            ^               |
|           | Camera Ribbon                | |            | CAN Bus       |
|           v                              | |            v               |
|  +-------------------+                   | |  +----------------------+  |
|  | Pi Camera Module 3|                   | |  |   DroneCAN M8N GPS   |  |
|  +-------------------+                   | |  +----------------------+  |
|                                          | |                            |
|                            USB / Serial  | |                            |
|                            (Optional Connection: /dev/ttyACM0)          |
|                            <------------->                              |
+------------------------------------------+ +----------------------------+
```

1. **Flight Telemetry (433MHz Serial Link):** The laptop GCS establishes a direct connection with the Pixhawk flight controller using a 433MHz telemetry radio transceiver (connected via USB COM port). Telemetry data is parsed via the MAVLink protocol. This frequency propagates long distances and behaves reliably even when Wi-Fi is lost.
2. **Video & AI Processing (Wi-Fi Hotspot Link):** The Raspberry Pi on the drone acts as a Wi-Fi hotspot. The Pi camera captures raw frames, and a lightweight Python daemon (`pi_streamer.py`) serves them as an HTTP MJPEG multipart stream on port `8080`. The laptop connects to the Pi's Wi-Fi, retrieves the stream over HTTP, and passes the frames directly into the YOLOv8 neural network.

### Multithreaded GCS Orchestrator Model

To prevent visual rendering, AI inference, and flight-critical telemetry from blocking one another, the GCS operates a multithreaded backend (`main.py`):

1. **GCS Main Thread:** Runs the primary control loop. It grabs camera frames from the active camera source (MJPEGCamera, ROS2Camera, or MockCamera), delegates them to the active App for computer vision analysis, compiles flight logs, and handles clean shutdowns.
2. **Flask Server Thread:** Executes the Flask micro-framework and listens on `0.0.0.0:5000` to serve the web interface files (HTML, CSS, JS) to the client.
3. **Socket.IO Thread:** Manages bi-directional WebSocket channels, broadcasting JSON telemetry packets at 10Hz and AI detection events immediately to any connected web client.
4. **Telemetry Thread:** Maintained inside `mavlink_bridge.py`. It continually loops, reading raw bytes from the serial COM port, parsing them into high-level MAVLink messages, updating a thread-safe telemetry state dictionary, and sending heartbeat signals back to the autopilot.
5. **Camera Buffer Thread:** Standard OpenCV `cv2.VideoCapture` calls buffer frames sequentially. If processing takes longer than the framerate, the buffer lags. The camera modules spawn an independent thread that constantly clears the buffer and holds only the *latest* frame for the GCS loop.

### The Pluggable App Lifecycle

All modular functionalities are governed by the `AppManager` (`apps/app_manager.py`). The GCS main loop does not hardcode target detection or path compilation. Instead, it interacts with an abstract lifecycle interface defined in `apps/base_app.py`:

```python
class BaseMissionApp:
    def on_start(self, mav_bridge, config=None):
        """Triggered when the app is selected. Sets up models/caches."""
        pass
        
    def process_frame(self, frame, telemetry):
        """Called every camera loop. Analyzes frame, adds overlays, returns annotated image."""
        return frame
        
    def handle_command(self, cmd_name, data=None):
        """Processes Socket.IO UI signals sent specifically to this app."""
        pass
        
    def on_stop(self):
        """Triggered when switching away from this app. Frees memory."""
        pass
```

- When the pilot selects **Manual Flight**, the GCS loads `idle_app.py`, which performs zero processing and simply draws text overlays (Altitude, Speed) onto the screen.
- When the pilot selects **Search & Rescue**, the GCS swaps the active reference to `search_rescue.py`. The system immediately starts running YOLOv8, detects target shapes, runs coordinate calculations, and populates the Map.

---

## 3. The Mathematics of Autonomous Flight & Vision

### Lawnmower Path Planning Algorithms

To survey a search area completely, the GCS compiles a lawnmower flight path inside `mission/path_planner.py`.

```text
Geofence Boundary (User Polygon)
  +---------------------------------+
  |  \   Pass 1                     |
  |   \                             |
  |    \                            |
  |     \                           |
  |      \________                  |
  |               \                 |
  |  Pass 2        \                |
  |                 \               |
  |                  \              |
  |                   \             |
  +--------------------+------------+
```

1. **Bounding Box Calculation:** We define the minimum bounding box that encapsulates the user's geofence polygon coordinates:
   $$\text{MinLat}, \text{MaxLat}, \text{MinLon}, \text{MaxLon}$$
2. **Swath Width ($W$):** The width of the area the camera can see on the ground depends on the drone's relative altitude ($H$), the camera's horizontal field of view ($\theta_{\text{HFOV}}$), and a safety overlap factor ($O$):
   $$W = 2 \cdot H \cdot \tan\left(\frac{\theta_{\text{HFOV}}}{2}\right) \cdot (1 - O)$$
3. **Transect Spacing:** The bounding box is divided into parallel transects (sweep lines) spaced at interval $W$.
4. **Polygon Intersection:** The planner calculates the intersection points of these parallel lines with the user's geofence boundaries.
5. **Path Construction:** The intersections are ordered in a zig-zag sequence (alternating directions) to minimize drone yaw rotations. The generated coordinates are converted to MAVLink waypoints.

### Ray-Casting & Pinhole Camera Coordinate Geotagging

When the vision model locates a target at pixel coordinates $(x, y)$ in an image of resolution $W \times H$, the system projects a vector from the drone's camera down to the ground plane to calculate the target's exact GPS coordinates.

```text
                Drone (GPS: lat_d, lon_d, alt_d)
                       / | \
                      /  |  \
                     /   |   \  Ray Vector (v_ecef)
                    /    |    \
                   /     |     \
                  v      v      v
      --------------------------------- Ground (Altitude = 0 AGL)
                  Target GPS: (lat_t, lon_t)
```

#### 1. Pixel-to-Camera Frame Representation
Under the pinhole camera model, we map the pixel coordinate to an idealized camera ray vector $\mathbf{v}_{\text{cam}}$:
$$\mathbf{v}_{\text{cam}} = \begin{bmatrix} \frac{x - c_x}{f_x} \\ \frac{y - c_y}{f_y} \\ 1 \end{bmatrix}$$
Where:
- $c_x, c_y$ are the optical center coordinates (typically half the image width and height).
- $f_x, f_y$ are the focal lengths of the camera lens expressed in pixels:
  $$f = \frac{\text{Resolution in pixels}}{2 \cdot \tan\left(\frac{\text{FOV}}{2}\right)}$$

#### 2. Rotation to Earth Reference Frame
The camera vector is rotated into the Earth-Centered, Earth-Fixed (ECEF) reference frame. We construct rotation matrices based on the drone's telemetry:
- **Camera Mount Offset ($\mathbf{R}_{\text{mount}}$):** Rotates the vector to align with the drone body (e.g. downward-facing gimbal).
- **Drone Attitude ($\mathbf{R}_{\text{attitude}}$):** Rotates the vector based on the drone's live Roll ($\phi$), Pitch ($\theta$), and Yaw ($\psi$):
  $$\mathbf{R}_{\text{attitude}} = \mathbf{R}_z(\psi) \cdot \mathbf{R}_y(\theta) \cdot \mathbf{R}_x(\phi)$$
The total rotated vector is:
$$\mathbf{v}_{\text{world}} = \mathbf{R}_{\text{attitude}} \cdot \mathbf{R}_{\text{mount}} \cdot \mathbf{v}_{\text{cam}}$$

#### 3. Ground Intersection
Let the drone's altitude above ground level be $H$. The ray vector has components:
$$\mathbf{v}_{\text{world}} = \begin{bmatrix} v_x \\ v_y \\ v_z \end{bmatrix}$$
The horizontal distance scale factor $S$ to intersect the ground plane ($z = 0$) is:
$$S = \frac{-H}{v_z}$$
The horizontal offset distance on the ground is:
$$\Delta N = S \cdot v_x \quad \text{(North offset in meters)}$$
$$\Delta E = S \cdot v_y \quad \text{(East offset in meters)}$$

#### 4. Latitude/Longitude Transformation
Using the WGS-84 coordinate model, we convert these offsets from the drone’s current GPS coordinates $(\text{Lat}_d, \text{Lon}_d)$ to the target coordinates $(\text{Lat}_t, \text{Lon}_t)$:
$$\text{Lat}_t = \text{Lat}_d + \frac{\Delta N}{R_M}$$
$$\text{Lon}_t = \text{Lon}_d + \frac{\Delta E}{R_N \cdot \cos(\text{Lat}_d)}$$
Where $R_M$ is the Earth's meridional radius of curvature and $R_N$ is the Earth's prime vertical radius of curvature.

### Spatial Memory Grid Allocation

To prevent the GCS from recording the same object multiple times (for example, if the drone circles back over a target it already found), `mission/memory_grid.py` maintains a coordinate cache:

1. The search area is segmented into a virtual grid of $1\text{m} \times 1\text{m}$ cells.
2. The calculated target coordinate is mapped to a unique index based on its position in the grid:
   $$\text{GridX} = \lfloor \frac{\Delta E}{\text{CellSize}} \rfloor, \quad \text{GridY} = \lfloor \frac{\Delta N}{\text{CellSize}} \rfloor$$
3. If `(GridX, GridY)` is not present in the database, the system creates a new record, adds the marker to the Leaflet map, and saves the target's image. If it already exists, the detection is ignored as a duplicate.

---

## 4. Backend Telemetry & Hardware Control

### Thread-Safe MAVLink Bridging

The Pixhawk communication stack (`telemetry/mavlink_bridge.py`) relies on **Pymavlink**, a Python wrapper for the MAVLink protocol. 

The bridge runs an independent thread that loops continuously:
```python
def _read_loop(self):
    while self.running:
        msg = self.master.recv_match(blocking=True, timeout=1.0)
        if msg is None:
            continue
        
        msg_type = msg.get_type()
        if msg_type == 'GLOBAL_POSITION_INT':
            with self._telemetry_lock:
                self._state["lat"] = msg.lat / 1e7
                self._state["lon"] = msg.lon / 1e7
                self._state["alt"] = msg.relative_alt / 1000.0  # mm to meters
        elif msg_type == 'VFR_HUD':
            with self._telemetry_lock:
                self._state["speed"] = msg.groundspeed
                self._state["heading"] = msg.heading
        elif msg_type == 'SYS_STATUS':
            with self._telemetry_lock:
                self._state["battery_v"] = msg.voltage_battery / 1000.0  # mV to V
                self._state["battery_pct"] = msg.battery_remaining
```

- **Locking:** All reads and writes to the `self._state` dictionary are protected by a Python `threading.Lock()` to prevent race conditions when the Flask API thread reads values while the telemetry thread is writing them.
- **Commands:** Commands sent from the dashboard (like TAKE OFF or RTL) run synchronously on the Flask request thread by calling `master.mav.command_long_send()`. The thread waits for a `COMMAND_ACK` confirmation packet from the flight controller before returning a success message to the browser.

### State Boundaries (SITL vs. LIVE)

To protect the drone from incorrect commands, the software uses a strict configuration variable:
* **`DRONE_ENVIRONMENT`**: Set to `'SITL'` (Simulation), `'HITL'` (Hardware In The Loop), or `'LIVE'` (Real Flight).

This configuration acts as a security boundary:
- **Simulation/SITL Mode:** The telemetry bridge automatically runs helper scripts on startup to disable pre-arm safety checks (`ARMING_CHECK = 0`). This prevents development delays from sensors (like compasses or lidars) failing to initialize indoors.
- **LIVE Mode:** The GCS **suppresses all pre-arm override commands**. The drone must pass its own physical safety checks. Even if a user-supplied connection string is passed as a simulation port (like `udp:10.236.25.123` via a hacked API call), the GCS verifies that the environment is `'LIVE'` and refuses to disable safety checks.

---

## 5. Computer Vision & Inference Pipeline

The vision pipeline processes images in real-time. Depending on the environment, it uses different modules.

### Real-time YOLOv8 Execution

When running locally on a laptop or on a Pi with a hardware accelerator, the GCS loads `detection/cpu_detector.py` or `detection/hailo_detector.py`:
- **Model:** YOLOv8n (YOLOv8 Nano, optimized for fast speed).
- **Processing:** Raw BGR frames are resized to $640 \times 640$ (the model's expected input dimension). The frame is normalized, passed through the model layers, and returns a bounding box array:
  $$\text{Box} = [x_1, y_1, x_2, y_2, \text{Confidence}, \text{ClassID}]$$
- **Class Filtering:** If $\text{ClassID} == 0$ (Person) and the confidence exceeds `CONFIDENCE_THRESHOLD` (set in `config.py`), it triggers a detection event.

*Note: For testing on standard laptop CPUs without running out of memory (OOM), the codebase includes a mock detector that simulates detections, preventing system crashes during development.*

### OpenCV Contour & Shape Classifiers

For targeted shape detection (like finding colored tiles or cards on the ground), the GCS uses `detection/shape_detector.py` to perform traditional geometric contour analysis:

```text
    Raw Frame -> RGB to HSV -> Color Masking -> Blur & Threshold -> Contour Detection
                                                                           |
   +------------------ Triangle (3 vertices) <-----------------------------+
   |
   +------------------ Rectangle / Square (4 vertices)
   |
   +------------------ Circle / Oval (ellipse fit)
```

1. **HSV Color Filtering:** Convert the frame from BGR space to HSV (Hue, Saturation, Value) space. HSV is robust to shadows and changing sunlight. We apply a color threshold mask:
   ```python
   mask = cv2.inRange(hsv, lower_color_range, upper_color_range)
   ```
2. **Noise Reduction:** Apply morphological opening and closing (erosion followed by dilation) to remove random noise and fill in hollow spots within the shape.
3. **Contour Extraction:** Use `cv2.findContours` to locate the boundaries of the shapes.
4. **Douglas-Peucker Approximation:** To classify the geometry, we simplify the contour shape using the Ramer-Douglas-Peucker algorithm:
   ```python
   epsilon = 0.04 * cv2.arcLength(contour, True)
   approx = cv2.approxPolyDP(contour, epsilon, True)
   ```
   We count the number of vertices in `approx`:
   - **3 Vertices:** Classified as a **Triangle**.
   - **4 Vertices:** Calculate the bounding box aspect ratio. If it is close to 1.0, it is a **Square**; otherwise, it is a **Rectangle**.
   - **5 Vertices:** Classified as a **Pentagon**.
   - **>5 Vertices:** Classified as a **Circle** or **Oval**.

---

## 6. Exhaustive Onboarding & Installation Guide

This section is a step-by-step setup guide for a beginner setting up a clean laptop from scratch.

### Step 1: Base Operating System Prerequisites

First, we must install Python and Git on your laptop.

#### For Windows
1. **Download Python:**
   - Go to the official download page: [Python 3.10.11 Windows Installer](https://www.python.org/downloads/release/python-31011/).
   - Download the **Windows Installer (64-bit)**.
   - **CRITICAL:** Launch the installer, and at the very bottom of the first window, check the box that says: **"Add Python 3.10 to PATH"**. If you skip this, your terminal will not recognize Python commands.
   - Click **Install Now**.
2. **Download Git:**
   - Go to [git-scm.com/download/win](https://git-scm.com/download/win).
   - Download the standalone 64-bit installer.
   - Run the installer and click **Next** on all default selections.

#### For macOS
1. **Open Terminal:** Press `Cmd + Space` on your keyboard, type `Terminal`, and press `Enter`.
2. **Install Command Line Tools (includes Python & Git):**
   - In the Terminal window, type the following command and press `Enter`:
     ```bash
     xcode-select --install
     ```
   - Click **Install** on the prompt that pops up and accept the license terms.

---

### Step 2: Clone the Project Repository

Now we will download the code from GitHub to your local machine.

1. **Open your Terminal:**
   - **Windows:** Search for `PowerShell` in the Start Menu, right-click it, and select **Run as Administrator**.
   - **macOS:** Open the `Terminal` application.
2. **Create a Projects Folder & Navigate into it:**
   ```powershell
   mkdir C:\Projects
   cd C:\Projects
   ```
   *(On macOS, just type `cd ~` then `mkdir Projects && cd Projects`)*
3. **Clone the Repository:**
   Run the following command to download the code:
   ```bash
   git clone https://github.com/SnehalShetty-sudo/AEROCLUB-snehal.git
   cd AEROCLUB-snehal
   ```

---

### Step 3: Set Up a Virtual Environment (`venv`)

A virtual environment is a self-contained directory that holds all the python packages for this project, preventing conflict with other python tools on your computer.

#### On Windows (PowerShell)
1. **Enable Script Execution:** Windows blocks scripts by default. Run this command to allow the virtual environment script to run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   *(Type `Y` and press `Enter` if prompted)*
2. **Create the Environment:**
   ```powershell
   python -m venv venv
   ```
3. **Activate the Environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   You should now see `(venv)` prepended to your command prompt line!

#### On macOS
1. **Create the Environment:**
   ```bash
   python3 -m venv venv
   ```
2. **Activate the Environment:**
   ```bash
   source venv/bin/activate
   ```
   You should see `(venv)` prepended to your terminal command prompt!

---

### Step 4: Install Dependencies

With the virtual environment active, install all the python libraries:

1. **Upgrade Pip:**
   ```bash
   python -m pip install --upgrade pip
   ```
2. **Install Libraries:**
   ```bash
   pip install -r requirements.txt
   ```
   This will automatically download and install Flask, Pymavlink, OpenCV, and all other required packages.

---

### Step 5: Configure and Run in Local Mock Mode

Since you are running this on a development machine at home with no drone hardware attached, we need to launch the server in **Mock Mode** so the dashboard can generate simulated telemetry and mock camera frames.

1. **Configure Environment Variables:**
   Tell the software to run in simulation/mock mode.
   - **Windows (PowerShell):**
     ```powershell
     $env:DRONE_MOCK="true"
     ```
   - **macOS (Terminal):**
     ```bash
     export DRONE_MOCK="true"
     ```
2. **Launch the GCS Server:**
   ```bash
   python main.py
   ```
3. **Open the Web Page:**
   - Open your web browser (Chrome, Edge, Safari, or Firefox).
   - Go to this address: **`http://localhost:5000`**
4. **Initiate the Simulation:**
   - In the launcher modal, click **MOCK SIMULATION**.
   - Watch the dashboard initialize. You will see mock video frames appear, the map load, and simulated telemetry values (battery, altitude) update automatically!

---

## 7. Frontend Customization & Reference

As a frontend developer, you will be modifying the GCS layout, styling, map markers, and WebSocket connections. Here is the layout maps of the dashboard code:

```text
/dashboard
├── /templates
│   └── index.html         # Main HTML layout, structure, modals, HUD overlay
└── /static
    ├── /css
    │   └── style.css      # Core styles: dark mode palettes, neon glows, glass panels
    └── /js
        └── app_v2.js      # Controls WebSocket updates, Map rendering, Leaflet tracking
```

### Where to Make Common UI Modifications

| Target Modification | Target File | Line range/Details |
| :--- | :--- | :--- |
| **Change Colors/Themes** | `dashboard/static/css/style.css` | Look at the `:root` variables block at the very top. Changing `--accent-blue` or `--panel-bg` will update colors sitewide. |
| **Modify Map Markers / Layers** | `dashboard/static/js/app_v2.js` | Locate the `initMap()` function. You can change the map zoom limits, layer provider (e.g. swap to OpenStreetMap satellite view), or customize the drone marker SVG. |
| **Add a New Telemetry Value** | `dashboard/templates/index.html` & `app_v2.js` | 1. Add a layout element in `index.html` with a unique ID (e.g. `<div id="tel-custom">`).<br>2. In `app_v2.js`, catch the value inside the `telemetry_update` socket callback: `document.getElementById('tel-custom').textContent = data.custom`. |
| **Tweak HUD Elements** | `dashboard/templates/index.html` | Look for the `<div class="hud-overlay">` element inside `index.html`. This block overlays flight parameters directly on top of the live video stream canvas. |

### Socket.IO WebSocket Event Reference

The frontend JavaScript communicates with the Python backend server using the following events:

#### Outbound Events (JavaScript to Python)
* **`connect`**: Triggered automatically when the page opens. Hands off a WebSocket initialization.
* **`mission_command`**: Triggered when the user clicks control buttons. Sent as:
  ```json
  { "command": "arm" } 
  // Commands supported: "arm", "disarm", "takeoff", "rtl", "start", "pause"
  ```
* **`load_app`**: Swaps the active mission app in the GCS. Sent as:
  ```json
  { "id": "search_rescue" }
  ```

#### Inbound Events (Python to JavaScript)
* **`telemetry_update`**: Pushes live flight status at 10Hz. Contains:
  ```json
  {
    "lat": 15.377060,
    "lon": 75.119966,
    "alt": 15.4,
    "speed": 2.4,
    "heading": 94,
    "battery_v": 22.4,
    "battery_pct": 89,
    "armed": true,
    "mode": "GUIDED"
  }
  ```
* **`new_detection`**: Emitted instantly when YOLO or Shape Detector finds a target. Contains:
  ```json
  {
    "id": 12,
    "type": "triangle",
    "color": "blue",
    "lat": 15.377062,
    "lon": 75.119965,
    "grid": "ZN3528702",
    "image_url": "/static/detections/det_12.jpg"
  }
  ```
