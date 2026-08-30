# Handoff Report: GCS & ADDC Mission Flight Troublesheet

This document outlines the core functional issues currently blocking the ADDC Autonomous Mission from starting. **Claude** (or any subsequent developer/AI agent) should use this guide to address these specific flight behaviors and UI requirements.

---

## 🛑 Problem Symptom Checklist & Handoff Goals

### 1. The Gazebo GUI Window is Required (No Headless)
*   **The Symptom:** Currently, Gazebo is configured to run headless (`gz sim -s`) in the background because the GUI window was causing a WSLg Weston compositor crash (the Linux Penguin taskbar icon showed `[WARN: COPY MODE]` and the 3D GUI window froze or refused to open).
*   **The User Requirement:** **Headless mode is not acceptable.** The user wants to see the visual 3D Gazebo simulator environment window.
*   **Claude Task:** Restore the Gazebo GUI window (remove `-s` from the launch command in `provisioning/addc_launcher.py`) and solve the WSLg display server hang.
*   **Recommended Troubleshooting for Claude:**
    - The `[WARN: COPY MODE]` hang occurs when WSLg tries to map hardware-accelerated OpenGL onto the Windows GPU driver and fails.
    - You can bypass hardware rendering conflicts and force Mesa to use CPU-based software rendering inside WSL by exporting these environment variables before starting Gazebo:
      ```bash
      export LIBGL_ALWAYS_SOFTWARE=1
      export GALLIUM_DRIVER=llvmpipe
      ```
    - Modify the Gazebo launch step in `addc_launcher.py` to include these exports.

---

### 2. Arming & Frame Checks Fail when Clicking "Execute"
*   **The Symptom:** All 4 steps in the modal start and turn green. The video feed loads on the GCS. The connection pill says **CONNECTED**. But when you click **Execute**, the drone fails to arm and fly, printing:
    `[SITL] AP: Arm: Motors: Check frame class and type`
*   **The Causes:**
    - **Timing/Initialization Lag:** ArduPilot SITL takes 20-30 seconds after booting to get a GPS lock and align the EKF. If **Execute** is clicked immediately before the GPS coordinates load (which shows as `0.000000, 0.000000` on the GCS dashboard), the autopilot rejects the arm command.
    - **Parameter Reboot Loop:** We removed the `-w` (wipe parameters) flag because ArduPilot requires a reboot after setting the frame class parameters to initialize its motors. Without a reboot, the active run remains in `Frame: UNSUPPORTED` mode.
*   **Claude Task:**
    - Add a guard/retry logic in GCS to check that the GPS coordinates are valid (non-zero) before permitting the arm command.
    - Standardize the parameter initialization flow so that the frame class defaults (`FRAME_CLASS = 1`, `FRAME_TYPE = 1`) are loaded correctly without locking the drone in an un-rebooted `UNSUPPORTED` state.

---

### 3. "Abort" Logic Flaw (Sending RTL on Disarmed/Ground Drone)
*   **The Symptom:** If the mission fails to start (drone is still disarmed on the ground), and you click **Abort**, the GCS warns `Mission is already running!`, prints `Sending RTL command via MAVLink...`, and tries to trigger Return-to-Launch mode on a drone that hasn't even taken off.
*   **The Cause:**
    - The GCS backend (`apps/addc_app.py`) tracks the mission state simply by checking if the WSL subprocess is alive (`self._mission_process.poll() is None`). It does not check the actual telemetry state (armed/disarmed, altitude, flight mode) of the drone.
    - When you click **Abort**, the backend blindly sends the MAVLink RTL command to the autopilot regardless of whether the drone is in the air.
*   **Claude Task:**
    - Update `addc_app.py` and the GCS frontend to check the drone's telemetry state. 
    - If the drone is disarmed/on the ground, clicking **Abort** should simply terminate the `main.py` mission process and disarm/reset the simulator state, without sending a MAVLink RTL command.

---

### 4. Random Video Feed Dropout
*   **The Symptom:** After resetting, restarting, or running multiple execution loops, the MJPEG video feed randomly goes black or fails to reconnect.
*   **The Cause:**
    - The Flask-based MJPEG bridge (`ros_mjpeg_bridge.py`) inside WSL might not be cleaning up its camera subscriptions or port bindings when the step is killed, or the GCS backend's camera thread gets orphaned on reload.
*   **Claude Task:**
    - Implement robust connection retry logic in GCS `main.py`'s `MJPEGCamera` class.
    - Ensure `ros_mjpeg_bridge.py` cleans up its ROS 2 node and releases its socket bindings gracefully upon receiving termination signals.

---

## 5. Technical Context for Claude (Reference)

### WSL Port & IP Mapping:
*   WSL2 runs in a VM. To allow the Windows GCS host to receive MAVLink packets from WSL, the GCS backend connects using:
    `os.environ["MAV_CONNECTION"] = "udp:0.0.0.0:14550"`
*   The mission script inside WSL communicates locally with SITL on:
    `udp:127.0.0.1:14551`
*   The MJPEG bridge streams at:
    `http://127.0.0.1:8080/stream`

### Files to Edit:
1.  [`dashboard/server.py`](file:///c:/Users/sonui/.gemini/antigravity/scratch/Aeroclub%20ADDC/AEROCLUB-snehal/dashboard/server.py): Handles the env connections and API routes.
2.  [`apps/addc_app.py`](file:///c:/Users/sonui/.gemini/antigravity/scratch/Aeroclub%20ADDC/AEROCLUB-snehal/apps/addc_app.py): Handles mission start/stop execution commands.
3.  [`provisioning/addc_launcher.py`](file:///c:/Users/sonui/.gemini/antigravity/scratch/Aeroclub%20ADDC/AEROCLUB-snehal/provisioning/addc_launcher.py): Defines command lists and ready logs for Gazebo/SITL.
