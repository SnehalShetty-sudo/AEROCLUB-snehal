"""
apps/base_app.py — Abstract base class for all Mission Apps.

Every mission app (Search & Rescue, Mapping, Inspection, etc.) must inherit
from BaseMissionApp and implement the required methods. The GCS orchestrator
calls these methods at the appropriate times in its lifecycle.
"""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("base_app")


class BaseMissionApp(ABC):
    """Base class for pluggable mission applications."""

    # --- Metadata (override in subclass) ---
    name = "Unnamed App"
    description = "No description."
    version = "0.0"
    icon = "fa-solid fa-plug"  # FontAwesome icon class for the UI

    def __init__(self):
        self._running = False
        self._config = self.get_default_config()

    # --- Configuration ---
    def get_default_config(self):
        """Return a dict of configurable settings with their defaults.
        
        Example:
            return {
                "confidence_threshold": {"value": 0.45, "type": "float", "min": 0.1, "max": 1.0, "label": "Confidence"},
                "search_altitude": {"value": 15, "type": "int", "min": 5, "max": 50, "label": "Altitude (m)"},
                "enable_shapes": {"value": True, "type": "bool", "label": "Detect Shapes"},
            }
        """
        return {}

    def get_config(self):
        """Return the current configuration."""
        return self._config

    def set_config(self, key, value):
        """Update a config value."""
        if key in self._config:
            self._config[key]["value"] = value

    # --- Lifecycle ---
    def on_start(self, mav_bridge, config=None):
        """Called when the app is loaded/activated.
        
        Use this to initialize heavy resources (ML models, planners, grids).
        
        Args:
            mav_bridge: The MavlinkBridge instance for sending commands.
            config: Optional dict to override default config.
        """
        if config:
            for k, v in config.items():
                self.set_config(k, v)
        self._running = True
        logger.info(f"App '{self.name}' started.")

    def on_stop(self):
        """Called when the app is unloaded or swapped out.
        
        Use this to release resources (close models, flush logs).
        """
        self._running = False
        logger.info(f"App '{self.name}' stopped.")

    @property
    def is_running(self):
        return self._running

    # --- Per-Frame Processing ---
    @abstractmethod
    def process_frame(self, frame, telemetry):
        """Process a single camera frame.
        
        This is called on every iteration of the main loop.
        The app should perform its detection/analysis and return an annotated frame.
        
        Args:
            frame: numpy.ndarray (BGR image from camera)
            telemetry: dict with current drone state (lat, lon, alt, heading, etc.)
            
        Returns:
            numpy.ndarray: The (optionally annotated) frame to display on the dashboard.
        """
        pass

    # --- Dashboard Widgets ---
    @abstractmethod
    def get_widgets(self):
        """Return a list of widget definitions for the dashboard side panel.
        
        Each widget is a dict describing what the frontend should render.
        
        Supported widget types:
        - "stat_grid": A grid of stat boxes (like the current detection summary)
        - "text": A simple text display
        - "progress": A progress bar
        - "log": A scrollable log list
        
        Example:
            return [
                {
                    "type": "stat_grid",
                    "title": "Detection Summary",
                    "stats": [
                        {"id": "persons", "label": "Persons", "icon": "fa-solid fa-person", "color": "green"},
                        {"id": "shapes", "label": "Shapes", "icon": "fa-solid fa-shapes", "color": "orange"},
                    ]
                },
                {
                    "type": "log",
                    "title": "Detection Log",
                    "id": "detection-log"
                }
            ]
        """
        pass

    @abstractmethod
    def get_stats(self):
        """Return current statistics to push to the dashboard.
        
        The keys should match the stat IDs defined in get_widgets().
        
        Example:
            return {"persons": 4, "shapes": 2, "total": 6}
        """
        pass

    # --- Mission Commands ---
    def on_command(self, command, mav_bridge=None):
        """Handle a mission command from the dashboard.
        
        Override this to implement custom behavior for start/pause/rtl.
        
        Args:
            command: str — 'start', 'pause', 'rtl', etc.
            mav_bridge: The MavlinkBridge instance.
        """
        logger.info(f"App '{self.name}' received command: {command}")

    # --- Serialization ---
    def to_dict(self):
        """Serialize app metadata for the API."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "icon": self.icon,
            "running": self._running,
            "config": self._config,
        }
