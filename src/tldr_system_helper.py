import os
import json

def load_key_from_config_file(key):
    """
    Get the value from the key in the hidden .config file
    Args:
        key: what you're trying to look up

    Returns: the value in the key-value pair from the config file

    """
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the .config file
    config_path = os.path.join(script_dir, '../.config')

    with open(config_path, 'r') as file:
        config = json.load(file)
        return config[key]

# fetch the emails


def check_if_file_exists(file):
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the .config file
    file_path = os.path.join(script_dir, file)

    if os.path.exists(file_path):
        print(f"{file} exists")
        try:
            with open(file_path, 'r') as file:
                config = json.load(file)
                print(f"{file} loaded successfully")
        except Exception as e:
            print(f"Error reading {file}: {e}")
    else:
        print(f"{file} does not exist")
