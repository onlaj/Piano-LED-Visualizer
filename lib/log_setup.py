import logging
from logging.handlers import RotatingFileHandler
import sys

# Create a custom logger
logger = logging.getLogger("my_app")

# Set the level of this logger.
logger.setLevel(logging.DEBUG)

# Create handlers
console_handler = logging.StreamHandler()
file_handler = RotatingFileHandler('/home/Piano-LED-Visualizer/visualizer.log', maxBytes=500000, backupCount=10)


# Set the level for handlers
console_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)


# Custom exception handler to log unhandled exceptions
def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    logger.error("Unhandled Exception: ", exc_info=(exc_type, exc_value, exc_traceback))


# Set the custom exception handler
sys.excepthook = log_unhandled_exception

def apply_log_setting(disable_logs):
    if str(disable_logs) == '1' or str(disable_logs).lower() == 'true':
        logger.setLevel(logging.CRITICAL + 1)
        console_handler.setLevel(logging.CRITICAL + 1)
        file_handler.setLevel(logging.CRITICAL + 1)
        logging.disable(logging.CRITICAL)
    else:
        logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.DEBUG)
        logging.disable(logging.NOTSET)
