"""
detection/hailo_detector.py — YOLOv8 inference on Hailo-8 NPU.

Takes camera frames, runs YOLOv8n on the Hailo-8, returns detections.
The inference pipeline is created ONCE and reused across all frames.
"""

import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import List

from hailo_platform import (
    HEF, VDevice, HailoStreamInterface,
    InferVStreams, ConfigureParams,
    InputVStreamParams, OutputVStreamParams, FormatType,
)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MODEL_PATH, CONFIDENCE_THRESHOLD, COCO_CLASSES

logger = logging.getLogger("hailo_detector")


@dataclass
class Detection:
    """A single detection result."""
    class_name: str
    confidence: float
    bbox: list  # [x1, y1, x2, y2] in pixel coordinates of the original frame
    source: str = "hailo"  # "hailo" or "opencv"


class HailoDetector:
    """
    YOLOv8 object detector running on Hailo-8 NPU.
    
    Usage:
        detector = HailoDetector()
        detections = detector.detect(frame_bgr)
        detector.close()
    """

    def __init__(self, model_path=None, confidence_threshold=None):
        self.model_path = str(model_path or MODEL_PATH)
        self.conf_thresh = confidence_threshold or CONFIDENCE_THRESHOLD
        
        logger.info(f"Loading HEF model: {self.model_path}")
        self.hef = HEF(self.model_path)

        # Create virtual device and configure network
        self.vdevice = VDevice()
        configure_params = ConfigureParams.create_from_hef(
            self.hef, interface=HailoStreamInterface.PCIe
        )
        self.network_groups = self.vdevice.configure(self.hef, configure_params)
        self.network_group = self.network_groups[0]

        # Create stream parameters ONCE
        self.network_group_params = self.network_group.create_params()
        self.input_vstream_params = InputVStreamParams.make(
            self.network_group, format_type=FormatType.UINT8
        )
        self.output_vstream_params = OutputVStreamParams.make(
            self.network_group, format_type=FormatType.FLOAT32
        )

        # Get input info
        self.input_vstream_info = self.hef.get_input_vstream_infos()[0]
        self.input_name = self.input_vstream_info.name
        input_shape = self.input_vstream_info.shape
        if len(input_shape) == 3:
            self.input_h = input_shape[0]
            self.input_w = input_shape[1]
        else:
            self.input_h = input_shape[1]
            self.input_w = input_shape[2]

        # Log output info for debugging
        output_infos = self.hef.get_output_vstream_infos()
        for info in output_infos:
            logger.info(f"Output stream: {info.name}, shape: {info.shape}")

        # Keep the pipeline context open for reuse
        self._pipeline = InferVStreams(
            self.network_group,
            self.input_vstream_params,
            self.output_vstream_params,
        )
        self._pipeline.__enter__()

        self._activated = self.network_group.activate(self.network_group_params)
        self._activated.__enter__()

        logger.info(
            f"Hailo detector ready: input {self.input_w}x{self.input_h}, "
            f"confidence threshold {self.conf_thresh}"
        )

    def detect(self, frame_bgr: np.ndarray) -> List[Detection]:
        """
        Run YOLOv8 detection on a BGR frame.
        Returns list of Detection objects with bbox in original frame coordinates.
        """
        orig_h, orig_w = frame_bgr.shape[:2]

        # Preprocess: BGR → RGB, resize to model input, normalize to [0, 1]
        import cv2
        # Convert BGR to RGB and resize
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_w, self.input_h))
        
        # Keep as uint8 [0, 255]
        tensor = np.expand_dims(resized, axis=0)

        # Run inference (pipeline stays open)
        raw_outputs = self._pipeline.infer({self.input_name: tensor})

        # Parse YOLOv8 outputs
        detections = self._parse_outputs(raw_outputs, orig_w, orig_h)
        return detections

    def _parse_outputs(self, raw_outputs: dict, orig_w: int, orig_h: int) -> List[Detection]:
        """
        Parse the raw output from YOLOv8n HEF.
        The output is a jagged list of shape (Batch, 80_classes, num_detections, 5)
        """
        detections = []
        from config import DETECT_CLASSES

        for name, val in raw_outputs.items():
            # Remove batch dimension if present
            if isinstance(val, list) and len(val) == 1:
                val = val[0]
            elif isinstance(val, np.ndarray) and val.shape[0] == 1:
                val = val[0].tolist()
            elif isinstance(val, np.ndarray):
                val = val.tolist()

            num_classes = len(val)
            for cls_id in range(num_classes):
                if cls_id >= len(COCO_CLASSES):
                    continue
                
                # Skip classes we don't want to detect
                if cls_id not in DETECT_CLASSES:
                    continue
                
                class_dets = val[cls_id]
                for det in class_dets:
                    # Hailo NMS output format: [ymin, xmin, ymax, xmax, score]
                    # Sometimes it's less than 5 elements if invalid, but usually 5.
                    if len(det) < 5:
                        continue
                        
                    ymin, xmin, ymax, xmax, conf = det[:5]
                    
                    if conf < self.conf_thresh:
                        continue

                    x1 = max(0, int(xmin * orig_w))
                    y1 = max(0, int(ymin * orig_h))
                    x2 = min(orig_w, int(xmax * orig_w))
                    y2 = min(orig_h, int(ymax * orig_h))

                    # Skip tiny boxes (likely false positives)
                    if (x2 - x1) < 5 or (y2 - y1) < 5:
                        continue

                    detections.append(Detection(
                        class_name=COCO_CLASSES[cls_id],
                        confidence=round(conf, 3),
                        bbox=[x1, y1, x2, y2],
                        source="hailo",
                    ))

        return detections

    def close(self):
        """Clean up Hailo resources."""
        try:
            self._activated.__exit__(None, None, None)
            self._pipeline.__exit__(None, None, None)
            logger.info("Hailo detector closed.")
        except Exception as e:
            logger.warning(f"Error closing Hailo detector: {e}")
