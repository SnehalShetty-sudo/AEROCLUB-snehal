"""
apps/idle_app.py — Default "No Mission" App.

This is the default app loaded when no specific mission is active.
It passes through the raw camera feed and provides basic telemetry widgets.
The GCS still works for manual flying, monitoring, and calibration.
"""

import cv2
import numpy as np
from apps.base_app import BaseMissionApp


class IdleApp(BaseMissionApp):
    name = "Manual Flight"
    description = "No autonomous mission loaded. GCS provides raw video feed, telemetry, and manual control. Use this for manual flights, testing, and basic monitoring."
    version = "1.0"
    icon = "fa-solid fa-gamepad"

    def on_start(self, mav_bridge, config=None):
        super().on_start(mav_bridge, config)

    def process_frame(self, frame, telemetry):
        """Pass through the raw frame with a small HUD overlay."""
        out = frame.copy()
        
        # Draw a subtle "MANUAL" indicator in the top-left
        h, w = out.shape[:2]
        cv2.putText(out, "MANUAL MODE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 255), 2, cv2.LINE_AA)
        
        # Draw altitude and speed HUD if available
        alt = telemetry.get("alt", 0)
        speed = telemetry.get("speed", 0)
        heading = telemetry.get("heading", 0)
        
        hud_text = f"ALT: {alt:.1f}m | SPD: {speed:.1f}m/s | HDG: {heading}"
        cv2.putText(out, hud_text, (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        
        return out

    def get_widgets(self):
        """Minimal widgets for manual flight."""
        return [
            {
                "type": "info_card",
                "title": "Status",
                "id": "idle-status",
                "content": "No mission app loaded. Select an app from the Apps tab to begin autonomous operations."
            }
        ]

    def get_stats(self):
        return {}

    def on_command(self, command, mav_bridge=None):
        """Forward basic commands directly to the MAVLink bridge."""
        super().on_command(command, mav_bridge)
        if mav_bridge and command in ('rtl', 'pause'):
            mav_bridge.send_command(command)
