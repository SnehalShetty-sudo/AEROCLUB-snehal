"""
provisioning/profile_manager.py
Manages drone hardware profiles and geofences.
"""
import os
import json
import yaml
import shutil
import logging

logger = logging.getLogger("profile_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(BASE_DIR, "profiles")
ACTIVE_PROFILE_FILE = os.path.join(PROFILE_DIR, ".active_profile.json")

def _get_active_profile_name():
    """Reads the active profile name from the state file."""
    if os.path.exists(ACTIVE_PROFILE_FILE):
        try:
            with open(ACTIVE_PROFILE_FILE, 'r') as f:
                data = json.load(f)
                name = data.get("name", "drone_alpha")
                
                # Check if dir exists
                if os.path.exists(os.path.join(PROFILE_DIR, name)):
                    return name
        except Exception as e:
            logger.error(f"Error reading active profile state: {e}")
            
    # Default fallback
    return "drone_alpha"

def get_active_profile():
    """Returns the parsed profile.yaml for the active profile."""
    name = _get_active_profile_name()
    yaml_path = os.path.join(PROFILE_DIR, name, "profile.yaml")
    
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, 'r') as f:
                profile_data = yaml.safe_load(f)
                profile_data['dir_name'] = name # inject dir name
                return profile_data
        except Exception as e:
            logger.error(f"Failed to load profile YAML {yaml_path}: {e}")
            
    return {"name": "Unknown Profile", "dir_name": name, "details": {}}

def list_profiles():
    """Returns a list of all available profiles."""
    profiles = []
    if not os.path.exists(PROFILE_DIR):
        return profiles
        
    active_name = _get_active_profile_name()
    
    for item in os.listdir(PROFILE_DIR):
        item_path = os.path.join(PROFILE_DIR, item)
        if os.path.isdir(item_path):
            yaml_path = os.path.join(item_path, "profile.yaml")
            if os.path.exists(yaml_path):
                try:
                    with open(yaml_path, 'r') as f:
                        data = yaml.safe_load(f)
                        profiles.append({
                            "id": item,
                            "name": data.get("name", item),
                            "version": data.get("version", "1.0"),
                            "active": item == active_name
                        })
                except Exception as e:
                    logger.warning(f"Could not load {yaml_path}: {e}")
    return profiles

def set_active_profile(name):
    """Sets the active profile."""
    if not os.path.exists(os.path.join(PROFILE_DIR, name)):
        raise ValueError(f"Profile {name} does not exist")
        
    try:
        with open(ACTIVE_PROFILE_FILE, 'w') as f:
            json.dump({"name": name}, f)
        logger.info(f"Active profile set to {name}")
        return True
    except Exception as e:
        logger.error(f"Failed to set active profile: {e}")
        return False

def create_profile(name):
    """Creates a new profile directory with templates."""
    dir_name = name.lower().replace(" ", "_")
    target_dir = os.path.join(PROFILE_DIR, dir_name)
    
    if os.path.exists(target_dir):
        raise ValueError(f"Profile {dir_name} already exists")
        
    os.makedirs(target_dir, exist_ok=True)
    
    # Write template YAML
    yaml_content = f"name: {name}\nversion: '1.0'\nnotes: New profile\n"
    with open(os.path.join(target_dir, "profile.yaml"), 'w') as f:
        f.write(yaml_content)
        
    # Write empty params
    with open(os.path.join(target_dir, "params.param"), 'w') as f:
        f.write("# New parameter file\n")
        
    logger.info(f"Created new profile {name} at {dir_name}")
    return dir_name

def delete_profile(name):
    """Deletes a profile."""
    if name == _get_active_profile_name():
        raise ValueError("Cannot delete the active profile")
        
    target_dir = os.path.join(PROFILE_DIR, name)
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        logger.info(f"Deleted profile {name}")
        return True
    return False

def get_profile_params(name=None):
    """Returns the contents of params.param for a profile."""
    if name is None:
        name = _get_active_profile_name()
        
    param_path = os.path.join(PROFILE_DIR, name, "params.param")
    if os.path.exists(param_path):
        try:
            with open(param_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read params for {name}: {e}")
    return None

def import_params(name, content):
    """Overwrites params.param for a profile."""
    param_path = os.path.join(PROFILE_DIR, name, "params.param")
    try:
        with open(param_path, 'w') as f:
            f.write(content)
        logger.info(f"Imported params for {name}")
        return True
    except Exception as e:
        logger.error(f"Failed to write params for {name}: {e}")
        return False

def export_params(name=None):
    """Alias for get_profile_params, for semantic clarity."""
    return get_profile_params(name)
