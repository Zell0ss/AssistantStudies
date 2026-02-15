# tests/test_config.py
import pytest
from utils.config import load_config, get_config

def test_load_config_returns_dict():
    """Test that load_config returns a dictionary"""
    config = load_config()
    assert isinstance(config, dict)
    assert 'telegram_apikey' in config
    assert 'anthropic_apikey' in config
    assert 'mariadb' in config

def test_get_config_singleton():
    """Test that get_config returns cached config"""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2
