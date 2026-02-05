import os
from pathlib import Path

# ===== REDDIT =====
REDDIT_CLIENT_ID = "your_reddit_client_id"
REDDIT_CLIENT_SECRET = "your_reddit_client_secret"
REDDIT_USER_AGENT = "RedditArchiver/1.0 (by user-is-absinthe)"

# ===== TELEGRAM =====
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHANNEL_ID = -100123456789  # Отрицательный ID канала
TELEGRAM_ADMIN_ID = 987654321  # Твой ID в ТГ

# ===== PATHS =====
BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp_files"
LOG_DIR = BASE_DIR / "logs"
DATABASE_PATH = BASE_DIR / "archive.db"

TEMP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ===== LIMITS =====
MAX_DISK_USAGE_BYTES = 3 * 1024 * 1024 * 1024  # 3 GB
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024   # 2 GB
MAX_TELEGRAM_MEDIA_GROUP = 10                   # Макс файлов в группе

# ===== RETRY CONFIG =====
RETRY_CONFIG = {
    "max_retries": 15,
    "alert_after_retry": 5,
    "initial_delay": 60,  # 1 минута
    "backoff_multiplier": 1.5,
}

# ===== PROCESSING =====
CHECK_INTERVAL = 3600  # 1 час между проходами Реддита
THREAD_COUNT = 4       # Количество параллельных воркеров
QUEUE_DEFER_POSITION = 10  # На сколько позиций отодвигаем при переполнении диска

# ===== LOGGING =====
LOG_FILE = LOG_DIR / "bot.log"
LOG_LEVEL = "INFO"
