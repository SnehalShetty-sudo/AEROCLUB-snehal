"""
mission/path_planner.py — Generates a boustrophedon (lawnmower) path over a polygon.

Takes 4 GPS coordinates (vertices of a rectangle), converts them to local 
meters, generates parallel sweep lines, and converts the resulting waypoints back to GPS.
"""

import math
import pyproj
from shapely.geometry import Polygon, LineString

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FLIGHT_ALTITUDE, CAMERA_HFOV_DEG, SWATH_OVERLAP

def calculate_swath_width(altitude: float, hfov_deg: float, overlap: float) -> float:
    """
    Calculate the distance between parallel sweep lines based on camera FOV.
    """
    # Half-FOV in radians
    hfov_rad = math.radians(hfov_deg / 2.0)
    
    # Ground footprint width (assuming nadir facing)
    ground_width = 2.0 * altitude * math.tan(hfov_rad)
    
    # Effective swath width accounting for overlap
    swath_width = ground_width * (1.0 - overlap)
    return max(1.0, swath_width)  # ensure it's at least 1m

def generate_lawnmower_path(gps_polygon: list, altitude: float = None) -> list:
    """
    Generate lawnmower waypoints for a given GPS polygon.
    
    Args:
        gps_polygon: list of (lat, lon) tuples defining the scan area.
        altitude: flight altitude (uses config default if None)
        
    Returns:
        list of (lat, lon, alt) tuples for the waypoints.
    """
    if len(gps_polygon) < 3:
        raise ValueError("Polygon must have at least 3 vertices")
        
    alt = altitude if altitude is not None else FLIGHT_ALTITUDE
    swath = calculate_swath_width(alt, CAMERA_HFOV_DEG, SWATH_OVERLAP)
    
    # Setup projections
    # Use a local azimuthal equidistant projection centered on the first point
    center_lat, center_lon = gps_polygon[0]
    proj_wgs84 = pyproj.CRS('EPSG:4326')
    proj_local = pyproj.CRS(f"+proj=aeqd +lat_0={center_lat} +lon_0={center_lon} +units=m")
    
    transformer_to_local = pyproj.Transformer.from_crs(proj_wgs84, proj_local, always_xy=True)
    transformer_to_wgs84 = pyproj.Transformer.from_crs(proj_local, proj_wgs84, always_xy=True)
    
    # Convert GPS to local meters
    local_polygon_pts = []
    for lat, lon in gps_polygon:
        # Note: pyproj always_xy expects (lon, lat)
        x, y = transformer_to_local.transform(lon, lat)
        local_polygon_pts.append((x, y))
        
    poly = Polygon(local_polygon_pts)
    minx, miny, maxx, maxy = poly.bounds
    
    # Generate parallel sweep lines (bottom to top)
    waypoints_local = []
    current_y = miny
    direction = 1  # 1 = left-to-right, -1 = right-to-left
    
    while current_y <= maxy:
        # Create a horizontal line across the entire bounding box
        sweep_line = LineString([(minx - 10, current_y), (maxx + 10, current_y)])
        
        # Intersect with the polygon boundary
        intersection = poly.intersection(sweep_line)
        
        if not intersection.is_empty:
            # For a simple convex polygon, intersection should be a single LineString
            if intersection.geom_type == 'LineString':
                coords = list(intersection.coords)
                if direction == -1:
                    coords.reverse()
                waypoints_local.extend(coords)
                
            elif intersection.geom_type == 'MultiLineString':
                # Handle complex polygons by taking the outermost bounds
                pts = []
                for line in intersection.geoms:
                    pts.extend(list(line.coords))
                pts.sort(key=lambda p: p[0]) # sort by x
                if pts:
                    if direction == 1:
                        waypoints_local.extend([pts[0], pts[-1]])
                    else:
                        waypoints_local.extend([pts[-1], pts[0]])
        
        current_y += swath
        direction *= -1
        
    # Convert back to GPS (lat, lon, alt)
    waypoints_gps = []
    for x, y in waypoints_local:
        lon, lat = transformer_to_wgs84.transform(x, y)
        waypoints_gps.append((lat, lon, alt))
        
    return waypoints_gps

# Simple test if run directly
if __name__ == "__main__":
    # Define a ~30x30m area
    test_poly = [
        (28.6139, 77.2090),
        (28.6139, 77.2093),
        (28.6136, 77.2093),
        (28.6136, 77.2090)
    ]
    
    print(f"Altitude: {FLIGHT_ALTITUDE}m")
    swath = calculate_swath_width(FLIGHT_ALTITUDE, CAMERA_HFOV_DEG, SWATH_OVERLAP)
    print(f"Swath Width: {swath:.1f}m")
    
    wps = generate_lawnmower_path(test_poly)
    print(f"\nGenerated {len(wps)} waypoints:")
    for i, (lat, lon, alt) in enumerate(wps):
        print(f" WP {i}: {lat:.6f}, {lon:.6f} at {alt}m")
