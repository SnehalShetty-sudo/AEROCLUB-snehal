"""
mission/memory_grid.py — Maps local pixel detections to global grid cells for unique tracking.
"""

import math
import pyproj
import logging

logger = logging.getLogger("memory_grid")

class MemoryGrid:
    def __init__(self, geofence_polygon, cell_size=1.0):
        self.geofence = geofence_polygon
        self.cell_size = cell_size
        self.detected_cells = set() # Set of unique (grid_x, grid_y) tuples where a person was seen
        
        if len(geofence_polygon) < 3:
            return
            
        # Set up local projection centered on the first vertex
        self.center_lat, self.center_lon = geofence_polygon[0]
        self.proj_wgs84 = pyproj.CRS('EPSG:4326')
        self.proj_local = pyproj.CRS(f"+proj=aeqd +lat_0={self.center_lat} +lon_0={self.center_lon} +units=m")
        self.transformer_to_local = pyproj.Transformer.from_crs(self.proj_wgs84, self.proj_local, always_xy=True)
        
    def add_detection(self, drone_lat, drone_lon, drone_alt, drone_heading, img_width, img_height, bbox):
        """
        Calculates the real-world ground coordinate of the bounding box centroid,
        and adds it to the memory grid. Returns True if this is a NEW unique person.
        """
        if drone_lat == 0 and drone_lon == 0:
            # No GPS lock, can't map
            return False
            
        # Centroid of the bounding box
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        
        # In a real pinhole camera model, we would use intrinsics.
        # For SITL approximation, we assume camera is pointing perfectly straight down (nadir).
        # HFOV = 66 deg.
        hfov_rad = math.radians(66.0)
        vfov_rad = hfov_rad * (img_height / img_width) # approximation
        
        ground_width = 2.0 * drone_alt * math.tan(hfov_rad / 2.0)
        ground_height = 2.0 * drone_alt * math.tan(vfov_rad / 2.0)
        
        # Pixel offsets from center (-0.5 to +0.5)
        nx = (cx / img_width) - 0.5
        ny = (cy / img_height) - 0.5
        
        # Ground offsets in meters (relative to drone)
        offset_x = nx * ground_width
        offset_y = ny * ground_height
        
        # Rotate by drone heading (heading is 0 = North, 90 = East)
        # offset_x is Right, offset_y is Down
        heading_rad = math.radians(drone_heading)
        
        # Rotate vector
        world_dx = offset_x * math.cos(heading_rad) - offset_y * math.sin(heading_rad)
        world_dy = offset_x * math.sin(heading_rad) + offset_y * math.cos(heading_rad)
        
        # Convert drone GPS to local meters
        drone_local_x, drone_local_y = self.transformer_to_local.transform(drone_lon, drone_lat)
        
        # Target local meters
        target_local_x = drone_local_x + world_dx
        target_local_y = drone_local_y + world_dy
        
        # Discretize into grid cell
        grid_x = int(target_local_x // self.cell_size)
        grid_y = int(target_local_y // self.cell_size)
        
        cell = (grid_x, grid_y)
        
        if cell not in self.detected_cells:
            self.detected_cells.add(cell)
            logger.info(f"New person discovered at grid {cell}! Total unique: {len(self.detected_cells)}")
            return True
            
        return False
        
    def get_unique_count(self):
        return len(self.detected_cells)
