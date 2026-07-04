import logging
import sys

from app.config import settings

def setup_logger():
    logger = logging.getLogger("FrigoMonitor")
    if logger.handlers:
        return logger
    logger.setLevel(settings.LOG_LEVEL)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(h)
    return logger

logger = setup_logger()
