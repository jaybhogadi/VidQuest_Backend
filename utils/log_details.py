import logging
import os

# --------- Logging ---------
LOG_DIR = "logs"
LOG_FILE = "app.log"

# Ensure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler(os.path.join(LOG_DIR, LOG_FILE)),  # Logs to file
    ],
)

logger = logging.getLogger("video-mcq")