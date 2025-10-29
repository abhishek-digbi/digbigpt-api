"""Helper to import utils.env_loader from various contexts."""

import sys
from pathlib import Path


def ensure_utils_in_path():
    """Ensure the utils directory is in sys.path."""
    # Find the ai-agent-service-staging directory
    current_file = Path(__file__).resolve()
    
    # This file is in ai-agent-service-staging/utils/
    # So the staging directory is one level up
    staging_dir = current_file.parent.parent
    
    if staging_dir.name == "ai-agent-service-staging" and str(staging_dir) not in sys.path:
        sys.path.insert(0, str(staging_dir))


def import_env_loader():
    """Import and return env_loader module."""
    ensure_utils_in_path()
    
    try:
        import utils.env_loader as env_loader
        return env_loader
    except ImportError:
        # If it still fails, try direct file import
        import importlib.util
        env_loader_path = Path(__file__).parent / "env_loader.py"
        spec = importlib.util.spec_from_file_location("env_loader", str(env_loader_path))
        env_loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(env_loader)
        return env_loader


# Auto-ensure path when this module is imported
ensure_utils_in_path()



