"""Configuration package for the valuation engine."""

import importlib.util
from pathlib import Path

# Get the path to the parent config.py file
parent_dir = Path(__file__).parent.parent
config_file = parent_dir / "config.py"

# Load the config.py module directly
spec = importlib.util.spec_from_file_location("config_module", config_file)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load configuration module from {config_file}")

config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)

# Re-export the necessary items
Settings = config_module.Settings
get_settings = config_module.get_settings
resolve_default_server_host = config_module.resolve_default_server_host
settings = config_module.settings

# Re-export for convenience
__all__ = ["Settings", "get_settings", "resolve_default_server_host", "settings"]
