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
        self.transformer_to_wgs84 = pyproj.Transformer.from_crs(self.proj_local, self.proj_wgs84, always_xy=True)
        
    def add_detection(self, drone_lat, drone_lon, drone_alt, drone_heading, img_width, img_height, bbox):
        """
        Calculates the real-world ground coordinate of the bounding box centroid,
        and adds it to the memory grid. Returns detailed detection info.
        """
        if drone_lat == 0 and drone_lon == 0:
            return {"is_new": False}
            
        # Centroid of the bounding box
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        
        # Pinhole model approximation (HFOV = 66 deg)
        hfov_rad = math.radians(66.0)
        vfov_rad = hfov_rad * (img_height / img_width)
        
        ground_width = 2.0 * drone_alt * math.tan(hfov_rad / 2.0)
        ground_height = 2.0 * drone_alt * math.tan(vfov_rad / 2.0)
        
        nx = (cx / img_width) - 0.5
        ny = (cy / img_height) - 0.5
        
        offset_x = nx * ground_width
        offset_y = ny * ground_height
        
        heading_rad = math.radians(drone_heading)
        
        world_dx = offset_x * math.cos(heading_rad) - offset_y * math.sin(heading_rad)
        world_dy = offset_x * math.sin(heading_rad) + offset_y * math.cos(heading_rad)
        
        drone_local_x, drone_local_y = self.transformer_to_local.transform(drone_lon, drone_lat)
        
        target_local_x = drone_local_x + world_dx
        target_local_y = drone_local_y + world_dy
        
        # Discretize into grid cell
        grid_x = int(target_local_x // self.cell_size)
        grid_y = int(target_local_y // self.cell_size)
        
        # Inverse transform to get exact Lat/Lon of the human
        target_lon, target_lat = self.transformer_to_wgs84.transform(target_local_x, target_local_y)
        
        # Generate cell label (e.g. A1, B4)
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        col_letter = alphabet[grid_x % 26] if grid_x >= 0 else "Z" + alphabet[abs(grid_x) % 26]
        cell_id = f"{col_letter}{grid_y}"
        
        cell = (grid_x, grid_y)
        is_new = False
        
        if cell not in self.detected_cells:
            self.detected_cells.add(cell)
            logger.info(f"New person discovered at grid {cell_id} ({target_lat:.6f}, {target_lon:.6f})! Total: {len(self.detected_cells)}")
            is_new = True
            
        return {
            "is_new": is_new,
            "cell_id": cell_id,
            "lat": round(target_lat, 6),
            "lon": round(target_lon, 6)
        }
        
    def get_unique_count(self):
        return len(self.detected_cells)
