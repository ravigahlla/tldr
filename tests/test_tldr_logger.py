import logging
import os
import pytest
from logging.handlers import RotatingFileHandler

# Adjust the import path based on how you run pytest.
# If running pytest from the project root, 'src.tldr_logger' should work.
try:
    from src.tldr_logger import setup_logger, LOG_FILE_PATH
except ImportError: # Fallback if running tests from within 'tests' dir or specific paths
    import sys
    # Add project root to sys.path to allow src imports
    PROJECT_ROOT_FOR_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT_FOR_TESTS not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)
    from src.tldr_logger import setup_logger, LOG_FILE_PATH


# Fixture to ensure log file is cleaned up after tests
@pytest.fixture(autouse=True)
def cleanup_log_file():
    # Store the original LOG_FILE_PATH if tests modify it (though current setup_logger doesn't)
    original_log_path = LOG_FILE_PATH 
    yield
    # Use the potentially modified path if setup_logger was called with a different path for a test
    # However, our current setup_logger always uses the global LOG_FILE_PATH from its module
    path_to_check = original_log_path 
    if os.path.exists(path_to_check):
        try:
            # Ensure all handlers are closed before trying to remove
            # This is tricky as the logger instance might be shared or reconfigured.
            # For simplicity, we'll just try to remove. If it fails, it might be due to open handlers.
            # A more robust cleanup might involve getting the logger and closing its file handlers.
            logging.shutdown() # Attempt to shutdown logging system to release file locks
            os.remove(path_to_check)
        except OSError as e:
            print(f"Warning: Could not remove log file {path_to_check}: {e}")


def test_setup_logger_creates_logger_with_handlers():
    # Using a unique name for this test logger to avoid interference if tests run in parallel
    # or if the default logger is modified by other tests.
    test_logger_name = "test_logger_handlers_unique"
    # Define a unique log file path for this test to avoid conflicts.
    test_log_file = f"{LOG_FILE_PATH}_testhandlers.log" 

    logger = setup_logger(name=test_logger_name, log_level=logging.DEBUG, log_file=test_log_file)
    
    assert isinstance(logger, logging.Logger)
    assert logger.name == test_logger_name
    assert len(logger.handlers) >= 1 # Should have at least console
    
    # Check for specific handler types
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    
    # File handler creation depends on permissions.
    # If the test_log_file was successfully created by setup_logger:
    file_handler_exists = any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    if file_handler_exists:
        assert os.path.exists(test_log_file)
    
    # Clean up the specific test log file
    if os.path.exists(test_log_file):
        try:
            # Close handlers associated with this specific logger before removing
            for handler in list(logger.handlers): # Iterate over a copy
                handler.close()
                logger.removeHandler(handler)
            os.remove(test_log_file)
        except OSError:
            pass # Ignore if it can't be removed


def test_logger_logs_messages_to_console_and_file(caplog):
    test_logger_name = "test_logger_messages_unique"
    test_log_file = f"{LOG_FILE_PATH}_testmessages.log"
    
    # Ensure log level is low enough to capture INFO messages
    logger = setup_logger(name=test_logger_name, log_level=logging.INFO, console_log_level=logging.INFO, log_file=test_log_file)
    
    with caplog.at_level(logging.INFO, logger=test_logger_name): # Specify logger for caplog
        logger.info("This is an info test message for console and file.")
        logger.warning("This is a warning test message for console and file.")

    assert "This is an info test message for console and file." in caplog.text
    assert "This is a warning test message for console and file." in caplog.text
    assert "INFO" in caplog.text # Check log level string in console output
    assert "WARNING" in caplog.text

    # Check if log file was created and contains the message
    file_handler_present = any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    if file_handler_present and os.path.exists(test_log_file):
        with open(test_log_file, 'r') as f:
            log_content = f.read()
            assert "This is an info test message for console and file." in log_content
            assert "This is a warning test message for console and file." in log_content
    
    # Clean up
    if os.path.exists(test_log_file):
        try:
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)
            os.remove(test_log_file)
        except OSError:
            pass


def test_logger_handles_file_permission_error_gracefully(mocker, caplog):
    test_logger_name = "test_permission_error_logger_unique"
    # Mock RotatingFileHandler's __init__ to raise a PermissionError
    # Patch where RotatingFileHandler is actually imported and used by setup_logger
    mock_rfh_init = mocker.patch('logging.handlers.RotatingFileHandler.__init__', side_effect=PermissionError("Test permission denied for log file"))
    
    with caplog.at_level(logging.ERROR): # Capture ERROR level logs
        # Call setup_logger, which will attempt to create the file handler
        # Use a dummy log file path, as it won't be created anyway
        logger_instance = setup_logger(name=test_logger_name, log_level=logging.INFO, log_file="dummy_path_for_permission_test.log")
    
    assert "Failed to set up file logging" in caplog.text
    assert "Test permission denied for log file" in caplog.text
    # Console handler should still exist
    assert any(isinstance(h, logging.StreamHandler) for h in logger_instance.handlers)
    # No file handler should have been added if the permission error occurred
    assert not any(isinstance(h, RotatingFileHandler) for h in logger_instance.handlers)
    mock_rfh_init.assert_called_once() # Ensure our mock was indeed called 