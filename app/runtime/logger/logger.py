from runtime.config.settings import settings
import logging

def get_logger(name: str)-> logging.Logger:
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger
    
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger