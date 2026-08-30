import os
import time
import logging
import threading
from .wsl_launcher import WSLProcessStep

logger = logging.getLogger("addc_launcher")

class ADDCSitlLauncher:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.steps = {}
        
    def create_steps(self):
        # We define a helper that captures the step_id
        def make_on_ready(step_id):
            def on_ready():
                if self.socketio:
                    self.socketio.emit('addc_step_ready', {'step_id': step_id})
            return on_ready

        def make_on_output(step_id):
            def on_output(line):
                # Print directly to the terminal running python main.py
                print(f"\033[93m[{step_id.upper()}]\033[0m {line}")
            return on_output
            
        self.steps = {
            "gazebo": WSLProcessStep(
                name="Gazebo Simulator",
                wsl_command="export PYTHONUNBUFFERED=1 && gz sim -s -v4 -r iris_runway.sdf",
                ready_pattern=r"Serving world|World .* initialized",
                on_ready=make_on_ready("gazebo"),
                on_output=make_on_output("gazebo")
            ),
            "sitl": WSLProcessStep(
                name="ArduPilot SITL",
                wsl_command="cd ~/ardupilot/ArduCopter && export PYTHONUNBUFFERED=1 && sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --out=udp:127.0.0.1:14550 --out=udp:127.0.0.1:14551",
                ready_pattern=r"Flight battery|GPS lock|EKF3 IMU0 is using GPS|Received .* parameters",
                on_ready=make_on_ready("sitl"),
                on_output=make_on_output("sitl")
            ),
            "ros_bridge": WSLProcessStep(
                name="ROS 2 Bridge",
                wsl_command="export PYTHONUNBUFFERED=1 && ros2 run ros_gz_bridge parameter_bridge /world/iris_runway/model/iris_with_ardupilot/model/iris_with_standoffs/link/base_link/sensor/camera/image@sensor_msgs/msg/Image[gz.msgs.Image",
                ready_pattern=r"Creating GZ.*ROS Bridge",
                on_ready=make_on_ready("ros_bridge"),
                on_output=make_on_output("ros_bridge")
            ),
            "mjpeg_bridge": WSLProcessStep(
                name="MJPEG Bridge",
                wsl_command="export PYTHONUNBUFFERED=1 && cd '/mnt/c/Users/sonui/.gemini/antigravity/scratch/Aeroclub ADDC/addc_mission' && python3 ros_mjpeg_bridge.py",
                ready_pattern=r"Starting Flask MJPEG server",
                on_ready=make_on_ready("mjpeg_bridge"),
                on_output=make_on_output("mjpeg_bridge")
            )
        }
        
    def start_step(self, step_id):
        if step_id not in self.steps:
            logger.error(f"Unknown step {step_id}")
            return False
        
        step = self.steps[step_id]
        if step.process and step.process.poll() is None:
            logger.warning(f"Step {step_id} is already running.")
            if self.socketio and step.ready:
                self.socketio.emit('addc_step_ready', {'step_id': step_id})
            return True
            
        logger.info(f"Starting {step_id}...")
        step.start()
        return True

    def kill_step(self, step_id):
        if step_id in self.steps:
            self.steps[step_id].kill()

    def kill_all(self):
        for step_id in ["mjpeg_bridge", "ros_bridge", "sitl", "gazebo"]:
            self.kill_step(step_id)

