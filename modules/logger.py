import logging
from logging.handlers import RotatingFileHandler
from config import LOG_FILE, LOG_LEVEL


def setup_logger(name: str) -> logging.Logger:
    """Инициализирует логгер с ротацией"""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Формат лога
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый обработчик (ротация по 10MB)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger("reddit_archiver")
