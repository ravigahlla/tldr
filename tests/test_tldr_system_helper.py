import pytest
import json
from unittest.mock import mock_open, patch
import logging

# Adjust import path
try:
    from src.tldr_system_helper import load_key_from_config_file, ConfigError, load_critical_configs, DEFAULT_CONFIG_PATH
    from src.tldr_logger import logger # Assuming logger is used and we might want to check its output via caplog
except ImportError:
    import sys
    PROJECT_ROOT_FOR_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT_FOR_TESTS not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)
    from src.tldr_system_helper import load_key_from_config_file, ConfigError, load_critical_configs, DEFAULT_CONFIG_PATH
    from src.tldr_logger import logger


# Sample config data for tests
SAMPLE_CONFIG_VALID = {
    "normal_key": "normal_value",
    "gmail_user": "test@example.com",
    "gmail_password": "testpassword",
    "openai_api_key": "sk-testkey",
    "target_email": "target@example.com",
    "stratechery_sender_email": "sender@example.com",
    "int_key": "123"
}
SAMPLE_CONFIG_MISSING_CRITICAL = {"normal_key": "value"} # Missing gmail_user, etc.

# Use a fixed dummy path for config file in tests unless a specific path is needed
DUMMY_CONFIG_PATH = "dummy.config"

def test_load_key_success(mocker):
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_CONFIG_VALID)))
    value = load_key_from_config_file("normal_key", config_file_path=DUMMY_CONFIG_PATH)
    assert value == "normal_value"

def test_load_key_missing_with_default(mocker, caplog):
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_CONFIG_VALID)))
    value = load_key_from_config_file("non_existent_key", default="my_default", config_file_path=DUMMY_CONFIG_PATH)
    assert value == "my_default"
    assert "Key 'non_existent_key' not found" in caplog.text
    assert "Using default value for 'non_existent_key'" in caplog.text

def test_load_key_missing_critical_raises_error(mocker, caplog):
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_CONFIG_VALID)))
    with pytest.raises(ConfigError) as excinfo:
        load_key_from_config_file("critical_missing_key", is_critical=True, config_file_path=DUMMY_CONFIG_PATH)
    assert "Critical key 'critical_missing_key' not found" in str(excinfo.value)
    assert "Critical key 'critical_missing_key' not found" in caplog.text # Check logger output

def test_load_key_file_not_found(mocker, caplog):
    mocker.patch('builtins.open', side_effect=FileNotFoundError("File not here"))
    with pytest.raises(ConfigError) as excinfo:
        load_key_from_config_file("any_key", config_file_path="nonexistent.config")
    assert "Configuration file nonexistent.config not found" in str(excinfo.value)
    assert "Configuration file nonexistent.config not found" in caplog.text

def test_load_key_json_decode_error(mocker, caplog):
    mocker.patch('builtins.open', mock_open(read_data="this is not json"))
    with pytest.raises(ConfigError) as excinfo:
        load_key_from_config_file("any_key", config_file_path="badjson.config")
    assert "Error decoding JSON" in str(excinfo.value)
    assert "Error decoding JSON" in caplog.text

def test_load_key_sensitive_data_logging(mocker, caplog):
    # Ensure caplog captures DEBUG messages from the 'tldr' logger
    caplog.set_level(logging.DEBUG, logger='tldr')
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_CONFIG_VALID)))
    
    load_key_from_config_file("gmail_password", config_file_path=DUMMY_CONFIG_PATH)
    # Check the debug log for the masked value
    assert "Key 'gmail_password' found in config. Value: ******" in caplog.text
    
    # Test with a default sensitive value
    # Clear previous records for a cleaner check of the second call, or use separate tests
    caplog.clear() # Clear records before the next call
    load_key_from_config_file("api_token_key", default="sensitive_default_token", config_file_path=DUMMY_CONFIG_PATH)
    assert "Using default value for 'api_token_key': ******" in caplog.text # This log is INFO level by default in load_key...


def test_load_critical_configs_success(mocker, caplog):
    # Mock load_key_from_config_file to return values from SAMPLE_CONFIG_VALID
    def mock_loader(key_name, default=None, config_file_path=None, is_critical=False):
        # This simplified mock assumes all keys in critical_keys_to_load exist in SAMPLE_CONFIG_VALID
        if key_name in SAMPLE_CONFIG_VALID:
            return SAMPLE_CONFIG_VALID[key_name]
        if is_critical: # Should not happen if all critical keys are in SAMPLE_CONFIG_VALID for this test
             raise ConfigError(f"Critical key '{key_name}' unexpectedly not found in mock setup.")
        return default

    mocker.patch('src.tldr_system_helper.load_key_from_config_file', side_effect=mock_loader)
    
    configs = load_critical_configs(config_file_path=DUMMY_CONFIG_PATH)
    assert configs["gmail_user"] == "test@example.com"
    assert configs["openai_api_key"] == "sk-testkey"
    assert "All specified configurations loaded." in caplog.text # Changed from "All critical configurations loaded successfully."

def test_load_critical_configs_failure_due_to_missing_key(mocker, caplog):
    # Mock load_key_from_config_file to simulate a missing critical key by raising ConfigError
    def mock_loader_failure(key_name, default=None, config_file_path=None, is_critical=False):
        if key_name == "openai_api_key" and is_critical: # Simulate this one failing
            raise ConfigError(f"Critical key '{key_name}' not found and no default value provided.")
        # For other keys, return them if they exist in SAMPLE_CONFIG_VALID (or a modified sample)
        return SAMPLE_CONFIG_VALID.get(key_name, default)

    mocker.patch('src.tldr_system_helper.load_key_from_config_file', side_effect=mock_loader_failure)
    
    with pytest.raises(ConfigError) as excinfo:
        load_critical_configs(config_file_path=DUMMY_CONFIG_PATH)
    
    assert "Failed to load critical configurations" in caplog.text
    # The specific error message from load_key_from_config_file for 'openai_api_key' would also be logged by that function.
    # The message in excinfo.value will be the one from load_critical_configs's re-raise.
    # This depends on the exact structure of critical_keys_to_load in the SUT.
    # Assuming 'openai_api_key' is one of the first critical keys checked.
    assert "Critical key 'openai_api_key' not found" in str(excinfo.value) 