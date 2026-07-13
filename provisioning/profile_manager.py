"""
provisioning/profile_manager.py
Loads/saves/switches YAML drone profiles.
"""
import yaml
import os

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "profiles")
ACTIVE_PROFILE_NAME = "drone_alpha" # Mock active selection

def get_active_profile():
    """Load active profile from yaml."""
    profile_path = os.path.join(PROFILE_DIR, ACTIVE_PROFILE_NAME, "profile.yaml")
    
    if not os.path.exists(profile_path):
        return {"name": "No Profile Found", "details": {}}
        
    try:
        with open(profile_path, 'r') as f:
            data = yaml.safe_load(f)
            return {
                "name": f"{data.get('name', 'Unknown')} — {data.get('version', 'v0')}",
                "details": data.get('details', {})
            }
    except Exception as e:
        return {"name": "Error Loading Profile", "details": {"error": str(e)}}
