import functools
import logging
import time
from logging.handlers import RotatingFileHandler
import sys
from agent_core.config.logging_config import logger


def configure_logging(app, log_file='app.log', log_level=logging.INFO):
    """
    Configures logging for a Flask app.

    - Logs to a rotating file handler (prevents excessive log size).
    - Logs to the console for visibility during development.
    - Uses appropriate logging levels based on the environment.
    """

    # Remove existing handlers to prevent duplicate logs
    app.logger.handlers.clear()

    # Create log formatter
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    # File handler with rotation (10MB per file, 5 backups)
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level)

    # Console handler for real-time logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(log_level)

    # Attach handlers to Flask logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # Ensure logs are not propagated to Flask's default handler
    app.logger.propagate = False

    logger.info("Logging is successfully configured.")


def log_execution_time_with_args(func):
    """
    Decorator to log execution time along with class name, function name, and arguments.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        # Capture function arguments
        func_args = [repr(arg) for arg in args[1:]]  # Skip self (args[0])
        func_kwargs = [f"{k}={v!r}" for k, v in kwargs.items()]
        all_args = ", ".join(func_args + func_kwargs)

        result = func(*args, **kwargs)  # Execute the function
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Auto-detect class name from `self`
        class_name = args[0].__class__.__name__ if args else "UnknownClass"

        def sanitize_args(args):
            args_str = str(args)
            if len(args_str) > 100:
                return args_str[:97] + '...'
            return args_str.replace('\n', '\\n').replace('\r', '\\r')

        log_message = f"[{class_name}.{func.__name__}] executed in {elapsed_time:.4f} seconds | Args: ({sanitize_args(all_args)})"

        logger.info(log_message)

        return result

    return wrapper


def log_execution_time(func):
    """
    Decorator to log execution time along with class name, function name.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        result = func(*args, **kwargs)  # Execute the function
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Auto-detect class name from `self`
        class_name = args[0].__class__.__name__ if args else "UnknownClass"

        log_message = f"[{class_name}.{func.__name__}] executed in {elapsed_time:.4f} seconds"
        logger.info(log_message)

        return result

    return wrapper
