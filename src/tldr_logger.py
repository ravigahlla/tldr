import logging
import sys
from logging.handlers import RotatingFileHandler
import os # For making LOG_FILE_PATH relative to project root

# Determine project root (assuming tldr_logger.py is in src folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "tldr_app.log")

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- Configuration for log level ---
# You can make this configurable later via .config or environment variable
# For now, we'll set defaults.
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_CONSOLE_LOG_LEVEL = logging.INFO
# Example: To get level from an environment variable:
# import os
# LOG_LEVEL_ENV = os.environ.get("TLDR_LOG_LEVEL", "INFO").upper()
# DEFAULT_LOG_LEVEL = getattr(logging, LOG_LEVEL_ENV, logging.INFO)


def setup_logger(name="tldr", log_level=DEFAULT_LOG_LEVEL, console_log_level=DEFAULT_CONSOLE_LOG_LEVEL, log_file=LOG_FILE_PATH):
    """
    Configures and returns a logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level) # Set the base level for the logger

    # Prevent adding multiple handlers if called more than once,
    # especially important in interactive sessions or if this function is called multiple times.
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (Rotating)
    # Rotates logs, keeping 5 files of 5MB each.
    try:
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setLevel(log_level) # Log all messages at or above this level to the file
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging can't be set up, log to console and continue
        # This can happen due to permissions issues for the log file
        logger.error(f"Failed to set up file logging to {log_file}: {e}. Logging to console only.", exc_info=True)


    logger.debug(f"Logger '{name}' initialized with file logging to '{log_file}' at level {logging.getLevelName(log_level)} and console logging at level {logging.getLevelName(console_log_level)}.")
    return logger

# Initialize one logger instance to be imported by other modules
# The name 'tldr' will be the parent logger for any loggers created with 'tldr.module_name'
logger = setup_logger()

# Example of how to create a child logger (useful for more granular control if needed)
# def get_logger(module_name):
#    return logging.getLogger(f"tldr.{module_name}") 