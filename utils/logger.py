import os
import logging
import logging.handlers
from datetime import datetime
import sys
import traceback


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output for console"""

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[91m\033[1m",  # Bold Red
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        log_message = super().format(record)
        if record.levelname in self.COLORS:
            return f"{self.COLORS[record.levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message


def setup_logging(log_dir="logs", log_level=logging.INFO, enable_console=True):
    """Configure application-wide logging with file rotation and optional console output"""

    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create a formatter for file logs
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create a rotating file handler
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10 MB
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Add console handler if enabled
    if enable_console:
        console_formatter = ColoredFormatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Create a separate error log file for warnings and above
    error_file = os.path.join(
        log_dir, f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    )
    error_handler = logging.handlers.RotatingFileHandler(
        error_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"  # 5 MB
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # Log uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt pass through
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        root_logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception

    # Log startup message
    root_logger.info(f"Logging initialized: {log_file}")
    return root_logger


def get_logger(name):
    """Get a logger with the specified name"""
    return logging.getLogger(name)


class LogCapture:
    """Context manager to capture logs during a specific operation"""

    def __init__(self, logger_name=None, level=logging.INFO):
        self.logger = (
            logging.getLogger(logger_name) if logger_name else logging.getLogger()
        )
        self.level = level
        self.captured_records = []
        self.handler = None

    def __enter__(self):
        self.handler = CaptureHandler(self.captured_records)
        self.handler.setLevel(self.level)
        self.logger.addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.handler:
            self.logger.removeHandler(self.handler)

    def get_logs(self):
        """Return captured log messages as a list of strings"""
        return [record.getMessage() for record in self.captured_records]

    def get_formatted_logs(self):
        """Return captured logs as formatted strings"""
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        return [formatter.format(record) for record in self.captured_records]


class CaptureHandler(logging.Handler):
    """Handler that captures log records in a list"""

    def __init__(self, records):
        super().__init__()
        self.records = records

    def emit(self, record):
        self.records.append(record)
