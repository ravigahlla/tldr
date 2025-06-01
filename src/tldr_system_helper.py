import os
import json
# Import the logger instance from our new tldr_logger module
from .tldr_logger import logger

CONFIG_FILE_NAME = ".config"
# Assuming .config is in the project root, like the log file
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # src -> project root
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, CONFIG_FILE_NAME)

class ConfigError(Exception):
    """Custom exception for configuration related errors."""
    pass

def load_key_from_config_file(key_name: str, default=None, config_file_path: str = DEFAULT_CONFIG_PATH, is_critical: bool = False):
    """
    Loads a specific key from the JSON configuration file.

    Args:
        key_name: The name of the key to load.
        default: The default value to return if the key is not found.
        config_file_path: Path to the configuration file.
        is_critical: If True and key is not found (and no default), raises ConfigError.

    Returns:
        The value of the key, or the default value.

    Raises:
        ConfigError: If the config file is not found, cannot be decoded,
                     or if a critical key is missing and no default is provided.
    """
    try:
        logger.debug(f"Attempting to load key '{key_name}' from config file: {config_file_path}")
        with open(config_file_path, 'r') as f:
            config_data = json.load(f)
        
        value = config_data.get(key_name)

        if value is not None:
            # Basic check to avoid logging sensitive values directly if they contain common keywords
            log_value = '******' if isinstance(value, str) and ('password' in key_name.lower() or 'key' in key_name.lower() or 'token' in key_name.lower()) else value
            logger.debug(f"Key '{key_name}' found in config. Value: {log_value}")
            return value
        else: # Key not in config_data or its value is literally null
            if key_name not in config_data: # Key truly absent
                logger.warning(f"Key '{key_name}' not found in {config_file_path}.")
            else: # Key is present but its value is null (json 'null')
                logger.info(f"Key '{key_name}' found in {config_file_path} but its value is null.")

            if default is not None:
                # Also mask default if it looks sensitive
                log_default = '******' if isinstance(default, str) and ('password' in key_name.lower() or 'key' in key_name.lower() or 'token' in key_name.lower()) else default
                logger.info(f"Using default value for '{key_name}': {log_default}")
                return default
            elif is_critical:
                err_msg = f"Critical key '{key_name}' not found in {config_file_path} and no default value provided."
                logger.error(err_msg)
                raise ConfigError(err_msg)
            else:
                # Not critical, no default, key not found or null, return None
                return None

    except FileNotFoundError:
        err_msg = f"Configuration file {config_file_path} not found."
        logger.error(err_msg)
        raise ConfigError(err_msg) from None # Using 'from None' to break the exception chain
    except json.JSONDecodeError as e:
        err_msg = f"Error decoding JSON from configuration file {config_file_path}: {e}"
        logger.error(err_msg)
        raise ConfigError(err_msg) from e
    except Exception as e: # Catch any other unexpected errors
        err_msg = f"An unexpected error occurred while loading key '{key_name}' from {config_file_path}: {e}"
        logger.exception(err_msg) # .exception logs the stack trace
        raise ConfigError(err_msg) from e

# Example of how you might add a function to load all critical configs at once
def load_critical_configs(config_file_path: str = DEFAULT_CONFIG_PATH):
    """
    Loads all critical configuration keys.
    Raises ConfigError if any critical key is missing.
    """
    logger.info("Loading critical configurations...")
    critical_keys_to_load = {
        "gmail_user": True,
        "gmail_app_pass": True,
        "openai_api_key": True,
        "target_email": True,
        "stratechery_sender_email": True,
        # Add other essential keys here with True if critical, False or default if not
        "forward_original_email": False,
        "openai_model_name": False,
        "system_prompt": False
    }
    
    configs = {}
    try:
        for key, is_critical in critical_keys_to_load.items():
            configs[key] = load_key_from_config_file(key, config_file_path=config_file_path, is_critical=is_critical)
        
        # Load non-critical keys with defaults if needed, e.g.:
        # configs["imap_host"] = load_key_from_config_file("imap_host", default="imap.gmail.com", config_file_path=config_file_path)
        # configs["smtp_server"] = load_key_from_config_file("smtp_server", default="smtp.gmail.com", config_file_path=config_file_path)
        # configs["smtp_port"] = int(load_key_from_config_file("smtp_port", default="465", config_file_path=config_file_path))
        # configs["openai_model"] = load_key_from_config_file("openai_model", default="gpt-4o", config_file_path=config_file_path)
        # configs["prompt_focus"] = load_key_from_config_file("prompt_focus", default="Summarize this article.", config_file_path=config_file_path)


        logger.info("All specified configurations loaded.")
        return configs
    except ConfigError as e:
        # Already logged in load_key_from_config_file, but we re-raise to signal failure to the caller
        logger.critical(f"Failed to load critical configurations: {e}")
        raise # Re-raise ConfigError to be handled by main application logic


# Add any other system utility functions here, using the logger as needed.
