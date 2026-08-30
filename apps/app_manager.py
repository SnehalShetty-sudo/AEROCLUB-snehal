"""
apps/app_manager.py — Central App Registry & Manager.

Discovers available mission apps and manages the active app lifecycle.
This is the bridge between the GCS core and the pluggable mission logic.
"""

import logging
import threading

logger = logging.getLogger("app_manager")


class AppManager:
    """Manages the lifecycle of mission apps."""

    def __init__(self):
        self._available_apps = {}  # {app_id: app_class}
        self._active_app = None
        self._active_app_id = None
        self._lock = threading.Lock()
        self._mav_bridge = None

        # Auto-discover built-in apps
        self._discover_apps()

    def _discover_apps(self):
        """Register all known apps."""
        # Import and register each app
        try:
            from apps.idle_app import IdleApp
            self._available_apps["idle"] = IdleApp
        except ImportError as e:
            logger.error(f"Failed to load IdleApp: {e}")

        try:
            from apps.search_rescue import SearchRescueApp
            self._available_apps["search_rescue"] = SearchRescueApp
        except ImportError as e:
            logger.warning(f"SearchRescueApp not available: {e}")
            
        try:
            from apps.addc_app import ADDCReconApp
            self._available_apps["addc_reconnaissance"] = ADDCReconApp
        except ImportError as e:
            logger.warning(f"ADDCReconApp not available: {e}")

        logger.info(f"Discovered {len(self._available_apps)} apps: {list(self._available_apps.keys())}")

    def set_mav_bridge(self, bridge):
        """Set the MAVLink bridge reference."""
        self._mav_bridge = bridge

    def list_apps(self):
        """Return metadata for all available apps."""
        apps = []
        for app_id, app_cls in self._available_apps.items():
            # Create a temporary instance to read metadata
            temp = app_cls()
            info = temp.to_dict()
            info["id"] = app_id
            info["active"] = (app_id == self._active_app_id)
            apps.append(info)
        return apps

    def get_active_app(self):
        """Return the currently active app instance, or None."""
        return self._active_app

    def get_active_app_id(self):
        """Return the ID of the currently active app."""
        return self._active_app_id

    def get_active_app_info(self):
        """Return metadata + widgets for the active app."""
        with self._lock:
            if self._active_app:
                info = self._active_app.to_dict()
                info["id"] = self._active_app_id
                info["widgets"] = self._active_app.get_widgets()
                return info
            return None

    def load_app(self, app_id, config=None):
        """Load an app by ID. Stops the current app first.
        
        Args:
            app_id: str — the registered app ID (e.g., 'search_rescue')
            config: dict — optional config overrides
            
        Returns:
            bool — True if successfully loaded
        """
        with self._lock:
            if app_id not in self._available_apps:
                logger.error(f"Unknown app: {app_id}")
                return False

            # Stop current app
            if self._active_app:
                try:
                    logger.info(f"Stopping current app: {self._active_app_id}")
                    self._active_app.on_stop()
                except Exception as e:
                    logger.error(f"Error stopping app: {e}")

            # Create and start new app
            try:
                app_cls = self._available_apps[app_id]
                self._active_app = app_cls()
                self._active_app.on_start(self._mav_bridge, config)
                self._active_app_id = app_id
                logger.info(f"App '{self._active_app.name}' loaded successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to load app '{app_id}': {e}")
                # Fall back to idle
                self._active_app = self._available_apps.get("idle", lambda: None)()
                if self._active_app:
                    self._active_app.on_start(self._mav_bridge)
                    self._active_app_id = "idle"
                return False

    def process_frame(self, frame, telemetry):
        """Delegate frame processing to the active app.
        
        Returns:
            annotated frame (numpy array)
        """
        if self._active_app:
            try:
                return self._active_app.process_frame(frame, telemetry)
            except Exception as e:
                logger.error(f"App frame processing error: {e}")
                return frame
        return frame

    def get_stats(self):
        """Get stats from the active app."""
        if self._active_app:
            try:
                return self._active_app.get_stats()
            except Exception as e:
                logger.error(f"App stats error: {e}")
        return {}

    def handle_command(self, command):
        """Forward a mission command to the active app."""
        if self._active_app:
            try:
                self._active_app.on_command(command, self._mav_bridge)
            except Exception as e:
                logger.error(f"App command error: {e}")

    def stop(self):
        """Stop the active app (called on shutdown)."""
        with self._lock:
            if self._active_app:
                try:
                    self._active_app.on_stop()
                except Exception as e:
                    logger.error(f"Error during app shutdown: {e}")
                self._active_app = None
                self._active_app_id = None
