# utils/config.py
"""
Configuration loader with singleton pattern.
"""
import yaml
from logcentral_client import get_logger

logger = get_logger("sebastian")

_config = None

def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {config_path}")
    return config

def get_config():
    """Get cached configuration (singleton)"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
