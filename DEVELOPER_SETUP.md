# Frontend Developer Setup & Onboarding Guide 🎨💻

Welcome Rajkishori! This guide is designed to get you up and running with the Ground Control Station (GCS) dashboard on your laptop, even if you have never worked with drones, Pixhawks, or Gazebo simulators before.

Depending on what you want to do, you can access and test the GCS using two different methods:

---

## 🚀 Method 1: Zero-Installation (Direct Wi-Fi Access)
If the backend code is running on the pilot's laptop, and both of you are connected to the **same Wi-Fi hotspot**, you do not need to install anything on your machine!

1. Ask the pilot for their laptop's local IP address (e.g. `10.236.25.123`).
2. Open any web browser on your laptop (Chrome, Safari, Firefox).
3. Navigate to:
   ```text
   http://<PILOT_LAPTOP_IP>:5000
   ```
4. You will instantly see the fully functioning dashboard, telemetry, and live camera feed! Any changes the pilot makes to the backend will show up on your screen.

*Note: This is perfect for quick testing, review sessions, or live monitoring, but you cannot edit the code this way.*

---

## 💻 Method 2: Local Development & Mock Simulation (For coding UI changes)
If you want to edit the HTML, CSS, or JavaScript on your own laptop, you will need to run the GCS locally. Since you don't have a physical drone plugged into your laptop, we will run the GCS in **Mock Mode**, which simulates drone telemetry and camera streams locally.

### 1. Prerequisite
Ensure you have **Python 3.10+** installed on your laptop. You can download it from [python.org](https://www.python.org/downloads/).

### 2. Clone the Repository
Clone the codebase to your laptop and open the directory:
```bash
git clone https://github.com/SnehalShetty-sudo/AEROCLUB-snehal.git
cd AEROCLUB-snehal
```

### 3. Setup Virtual Environment & Install Libraries
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
- **macOS / Linux (Terminal):**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### 4. Run GCS in Mock Mode
We need to tell the Python server to bypass the physical hardware checks.
- Set the environment variable `DRONE_MOCK` to `true`:
  - **Windows (PowerShell):** `$env:DRONE_MOCK="true"`
  - **macOS / Linux:** `export DRONE_MOCK="true"`
- Launch the server:
  ```bash
  python main.py
  ```
- Open your browser and navigate to:
  ```text
  http://localhost:5000
  ```
- Click **MOCK SIMULATION** on the dashboard. The system will start generating simulated telemetry (altitude changes, battery updates) and display a mock video screen so you can inspect your UI designs in real-time.

---

## 🎨 Where to make Frontend Changes
The dashboard is built using standard Flask WebSockets, HTML, Vanilla CSS, and JavaScript. You only need to edit files in these folders:
* **HTML Structure:** `dashboard/templates/index.html`
* **CSS Styling / Themes / Animations:** `dashboard/static/css/style.css`
* **UI Interactions / WebSocket hooks:** `dashboard/static/js/app_v2.js`

*Tip: When you make a change to the CSS or JavaScript files, perform a **Hard Refresh (`Ctrl + F5` on Windows / `Cmd + Shift + R` on Mac)** in your browser to bypass the cache and see the changes instantly.*
