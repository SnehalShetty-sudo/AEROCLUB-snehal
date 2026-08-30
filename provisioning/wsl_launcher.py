import subprocess
import threading
import re
import os
import time

class WSLProcessStep:
    def __init__(self, name, wsl_command, ready_pattern, on_ready, on_output=None):
        self.name = name
        self.command = wsl_command
        self.ready_pattern = re.compile(ready_pattern) if ready_pattern else None
        self.on_ready = on_ready
        self.on_output = on_output
        self.process = None
        self.ready = False
        self._stop_event = threading.Event()
        self.pid_file = f"/tmp/addc_{name.lower().replace(' ', '_')}.pid"

    def start(self):
        # We wrap the command to capture its PID and write to a file before executing
        wrapped_command = f"echo $$ > {self.pid_file} && {self.command}"
        
        self.process = subprocess.Popen(
            ["wsl", "-e", "bash", "-lic", wrapped_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.ready = False
        self._stop_event.clear()
        
        # Start watching output if we have a pattern or on_output callback
        if self.on_output or self.ready_pattern:
            threading.Thread(target=self._watch_output, daemon=True).start()

    def _watch_output(self):
        try:
            for line in self.process.stdout:
                if self._stop_event.is_set():
                    break
                line_clean = line.strip()
                if self.on_output:
                    self.on_output(line_clean)
                
                if not self.ready and self.ready_pattern and self.ready_pattern.search(line_clean):
                    self.ready = True
                    if self.on_ready:
                        self.on_ready()
        except Exception as e:
            if self.on_output:
                self.on_output(f"Error reading stdout: {e}")

    def kill(self):
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            # Kill the actual process inside WSL via its PID
            try:
                subprocess.run(
                    ["wsl", "-e", "bash", "-c", f"if [ -f {self.pid_file} ]; then kill -9 $(cat {self.pid_file}) 2>/dev/null; rm -f {self.pid_file}; fi"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
            
            # Kill the windows wrapper process
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.ready = False
