import os
import sys
import time
import logging
from pathlib import Path
from functools import wraps

# Project Root Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
POWERBI_EXPORT_DIR = WAREHOUSE_DIR / "powerbi_export"
DOCS_DIR = PROJECT_ROOT / "docs"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with standard formatting."""
    return logging.getLogger(name)

def time_it(stage_name: str):
    """Decorator to time pipeline functions and log execution details."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger("PipelineTimer")
            logger.info(f"==> [START] {stage_name}")
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"<== [COMPLETED] {stage_name} in {duration:.2f} seconds")
            return result
        return wrapper
    return decorator
