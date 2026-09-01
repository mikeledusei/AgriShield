"""Central logging for the AgriShield backend."""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("agrishield")


def info(message: str) -> None:
    logger.info(message)


def warning(message: str) -> None:
    logger.warning(message)


def error(message: str) -> None:
    logger.error(message)