# Autonomous Aerial Detection System

This repository contains the software stack for an autonomous search-and-rescue drone powered by a Raspberry Pi, Pixhawk flight controller, and YOLOv8 computer vision. The system is capable of flying a pre-defined mathematical lawnmower grid and autonomously detecting humans in real-time.

## 🏗 Architecture
The codebase is designed to be completely modular and supports both real-world deployment on physical hardware and "Digital Twin" simulation using Gazebo and SITL.

* `config.py`: The master configuration file. Toggle `SIMULATION_MODE` to switch between physical hardware and the simulator.
* `main.py`: The central brain that delegates tasks.
* `/vision`: Captures video feeds and runs the YOLOv8 AI model for real-time human detection.
* `/mission`: Generates autonomous search grid patterns (lawnmower method) based on RTK geofences.
* `/telemetry`: The MAVLink bridge that communicates securely with the Pixhawk flight controller.
* `/dashboard`: A lightweight web UI to monitor the live video feed, telemetry, and detection counts.
* `/gazebo`: [Optional] Configuration files and world models for the Gazebo 3D simulator.

## 🚀 Setup Guide (Real-World Raspberry Pi)

### 1. Hardware Requirements
- Raspberry Pi (4 or 5 recommended) running Ubuntu or Raspberry Pi OS
- Pixhawk Flight Controller connected via USB (`/dev/ttyACM0`)
- USB Camera connected via USB (`/dev/video0`)

### 2. Installation
Clone the repository to your Raspberry Pi:
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd pi-drone
pip install -r requirements.txt
```

### 3. Execution
Ensure `SIMULATION_MODE = False` in `config.py`, then run:
```bash
python3 main.py
```
Open a web browser on a device connected to the Pi's network and navigate to `http://<PI_IP_ADDRESS>:5000` to access the Dashboard.

## 💻 Setup Guide (Simulation & Testing)
You can test the entire software stack on your PC without real hardware by using ArduPilot SITL and Gazebo.

1. Install ArduPilot SITL and Gazebo on an Ubuntu machine (or WSL for Windows).
2. Set `SIMULATION_MODE = True` in `config.py`.
3. Launch the Gazebo world:
   ```bash
   gz sim gazebo/isro_mars.sdf
   ```
4. Launch the ArduCopter SITL:
   ```bash
   sim_vehicle.py -v ArduCopter -f JSON --add-param-file=gazebo-iris-gimbal.parm --console
   ```
5. Run the Python stack:
   ```bash
   python3 main.py
   ```
