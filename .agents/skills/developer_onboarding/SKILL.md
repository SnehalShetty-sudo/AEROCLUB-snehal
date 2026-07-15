---
name: developer_onboarding
description: Automatically sets up a local Python virtual environment, installs dependencies, and boots the GCS dashboard in mock/simulation mode for frontend development.
---

# Developer Onboarding & Local GCS Simulation Setup

This skill is designed for the Antigravity developer agent. When this repository is cloned onto a new developer machine (e.g. a frontend developer's laptop with no external drone hardware), follow these instructions to set up a fully functioning local mock environment.

## 🛠️ Step-by-Step Agent Setup Automation

### 1. Initialize Python Virtual Environment
Check if a virtual environment exists. If not, create and activate it:
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 2. Install Project Dependencies
Run pip install to bring in Flask, Socket.IO, OpenCV, and other core libraries:
```bash
pip install -r requirements.txt
```

### 3. Force Mock Configuration for Frontend Testing
To allow the developer to test frontend changes without needing a physical drone or a full ROS2 Gazebo simulator, configure the GCS to run in **Local Mock Telemetry Mode**:
- Open [config.py](file:///config.py).
- Set `SIMULATION_MODE = True`.
- Ensure `FC_MOCK_MODE` evaluates to `True` (this is automatically triggered when `DRONE_MOCK` env variable is set to `true`).
- To make this robust, set the environment variable:
  - **Windows (PowerShell):** `$env:DRONE_MOCK="true"`
  - **macOS / Linux:** `export DRONE_MOCK="true"`

### 4. Boot the Dashboard Server
Start the Flask server on the local machine:
```bash
python main.py
```
This starts the dashboard on `http://10.236.25.244:5000` (or `http://localhost:5000` locally).

Once the server is running, inform the developer that they can access the dashboard in their browser.

## 💡 Frontend Developer Workflow Guidance
- All frontend source files live in `/dashboard/templates/index.html` (layout), `/dashboard/static/css/style.css` (design and animations), and `/dashboard/static/js/app_v2.js` (UI logic).
- When the developer makes changes to the CSS/JS/HTML, they should do a **Hard Refresh (`Ctrl + F5` or `Cmd + Shift + R`)** in the browser to bypass caching.
