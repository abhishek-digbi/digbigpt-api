import logging
import os
from logging.handlers import RotatingFileHandler

# Define log file paths
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Create a global logger
logger = logging.getLogger("digbi_logger")
logger.setLevel(logging.INFO)  # Set default logging level

# Create formatters
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Console Handler (for real-time logs)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Rotating File Handler (for app logs)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Rotating Error File Handler (for error logs)
error_handler = RotatingFileHandler(ERROR_LOG_FILE, maxBytes=2*1024*1024, backupCount=3)
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)

# Attach handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.addHandler(error_handler)
