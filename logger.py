import logging
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent / "fitness-ai.log"

logger = logging.getLogger("fitness-ai")
logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"
        )
    )

    logger.addHandler(file_handler)

for handler in logger.handlers:
    handler.flush()