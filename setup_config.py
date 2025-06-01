import os
import shutil

CONFIG_FILE_NAME = ".config"
TEMPLATE_FILE_NAME = ".config.template"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, CONFIG_FILE_NAME)
TEMPLATE_FILE_PATH = os.path.join(PROJECT_ROOT, TEMPLATE_FILE_NAME)

def main():
    """
    Checks for .config file. If not found, copies from .config.template
    and instructs the user.
    """
    print("Checking for configuration file...")

    if not os.path.exists(TEMPLATE_FILE_PATH):
        print(f"ERROR: Template configuration file '{TEMPLATE_FILE_NAME}' not found in project root.")
        print("Please ensure the template file is present to set up the configuration.")
        return

    if os.path.exists(CONFIG_FILE_PATH):
        print(f"Configuration file '{CONFIG_FILE_NAME}' already exists.")
        print("If you need to reset it, please delete or rename the existing .config file and run this script again.")
    else:
        try:
            shutil.copy(TEMPLATE_FILE_PATH, CONFIG_FILE_PATH)
            print(f"Successfully created '{CONFIG_FILE_NAME}' from '{TEMPLATE_FILE_NAME}'.")
            print("\nIMPORTANT:")
            print(f"Please edit the '{CONFIG_FILE_NAME}' file now and replace all placeholder values")
            print("with your actual credentials and settings.")
            print(f"For example, open it with: open {CONFIG_FILE_PATH} (on macOS) or your preferred text editor.")
        except Exception as e:
            print(f"ERROR: Could not create '{CONFIG_FILE_NAME}': {e}")

if __name__ == "__main__":
    main() 