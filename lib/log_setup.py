import logging
import os
from logging.handlers import RotatingFileHandler
import sys

# Create a custom logger
logger = logging.getLogger("my_app")

# Set the level of this logger.
logger.setLevel(logging.DEBUG)

# Log next to the deployed install when it exists (the Pi image path), otherwise
# next to this checkout so the app also runs from a dev clone.
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_CANDIDATES = [
    os.environ.get("PLV_LOG_FILE"),
    "/home/Piano-LED-Visualizer/visualizer.log",
    os.path.join(REPO_DIR, "visualizer.log"),
]


def _open_log_handler():
    for candidate in LOG_CANDIDATES:
        if not candidate:
            continue
        # Never create the directory: an absent /home/Piano-LED-Visualizer just
        # means this is not the deployed install, so fall through to the clone.
        if not os.path.isdir(os.path.dirname(candidate)):
            continue
        try:
            return RotatingFileHandler(candidate, maxBytes=500000, backupCount=10)
        except OSError:
            continue
    return None


# Create handlers
console_handler = logging.StreamHandler()
file_handler = _open_log_handler()


# Set the level for handlers
console_handler.setLevel(logging.DEBUG)
if file_handler:
    file_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
if file_handler:
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# Custom exception handler to log unhandled exceptions
def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    logger.error("Unhandled Exception: ", exc_info=(exc_type, exc_value, exc_traceback))


# Set the custom exception handler
sys.excepthook = log_unhandled_exception
