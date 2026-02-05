import aiosqlite
from datetime import datetime, timedelta
from config import DATABASE_PATH
from modules.logger import logger


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init(self):
        """Инициализирует БД и создаёт таблицы"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                                   CREATE TABLE IF NOT EXISTS posts
                                   (
                                       reddit_post_id
                                       TEXT
                                       PRIMARY
                                       KEY,
                                       reddit_user
                                       TEXT,
                                       title
                                       TEXT,
                                       content
                                       TEXT,
                                       source_url
                                       TEXT,
                                       status
                                       TEXT
                                       CHECK (
                                       status
                                       IN
                                   (
                                       'fetched',
                                       'downloaded',
                                       'uploaded',
                                       'deleted',
                                       'skipped_deleted',
                                       'skipped_size_exceeded',
                                       'download_failed',
                                       'telegram_failed',
                                       'failed'
                                   )),
                                       retry_count INTEGER DEFAULT 0,
                                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                       error_message TEXT,
                                       fetched_at TIMESTAMP
                                       );

                                   CREATE TABLE IF NOT EXISTS attachments
                                   (
                                       attachment_id
                                       INTEGER
                                       PRIMARY
                                       KEY
                                       AUTOINCREMENT,
                                       reddit_post_id
                                       TEXT
                                       NOT
                                       NULL,
                                       file_url
                                       TEXT
                                       NOT
                                       NULL,
                                       file_type
                                       TEXT,
                                       file_size_bytes
                                       INTEGER,
                                       local_path
                                       TEXT,
                                       telegram_file_id
                                       TEXT,
                                       caption
                                       TEXT,
                                       status
                                       TEXT
                                       CHECK (
                                       status
                                       IN
                                   (
                                       'pending',
                                       'downloaded',
                                       'uploaded',
                                       'deleted',
                                       'failed',
                                       'deferred_disk_full'
                                   )),
                                       retry_count INTEGER DEFAULT 0,
                                       last_retry_attempt TIMESTAMP,
                                       first_retry_at TIMESTAMP,
                                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                       FOREIGN KEY
                                   (
                                       reddit_post_id
                                   ) REFERENCES posts
                                   (
                                       reddit_post_id
                                   )
                                       );

                                   CREATE TABLE IF NOT EXISTS telegram_messages
                                   (
                                       message_id
                                       INTEGER
                                       PRIMARY
                                       KEY,
                                       reddit_post_id
                                       TEXT
                                       NOT
                                       NULL,
                                       telegram_chat_id
                                       INTEGER
                                       NOT
                                       NULL,
                                       message_type
                                       TEXT,
                                       status
                                       TEXT
                                       CHECK (
                                       status
                                       IN
                                   (
                                       'sent',
                                       'failed'
                                   )),
                                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                       FOREIGN KEY
                                   (
                                       reddit_post_id
                                   ) REFERENCES posts
                                   (
                                       reddit_post_id
                                   )
                                       );

                                   CREATE TABLE IF NOT EXISTS disk_usage
                                   (
                                       id
                                       INTEGER
                                       PRIMARY
                                       KEY
                                       AUTOINCREMENT,
                                       total_bytes
                                       INTEGER
                                       DEFAULT
                                       0,
                                       updated_at
                                       TIMESTAMP
                                       DEFAULT
                                       CURRENT_TIMESTAMP
                                   );

                                   CREATE TABLE IF NOT EXISTS stats
                                   (
                                       id
                                       INTEGER
                                       PRIMARY
                                       KEY
                                       AUTOINCREMENT,
                                       posts_uploaded
                                       INTEGER
                                       DEFAULT
                                       0,
                                       files_uploaded
                                       INTEGER
                                       DEFAULT
                                       0,
                                       bytes_uploaded
                                       INTEGER
                                       DEFAULT
                                       0,
                                       posts_failed
                                       INTEGER
                                       DEFAULT
                                       0,
                                       posts_skipped
                                       INTEGER
                                       DEFAULT
                                       0,
                                       recorded_at
                                       TIMESTAMP
                                       DEFAULT
                                       CURRENT_TIMESTAMP
                                   );

                                   INSERT
                                   OR IGNORE INTO disk_usage (total_bytes) VALUES (0);
                                   """)
            await db.commit()

        logger.info("Database initialized")

    # ===== POSTS =====
    async def add_post(self, reddit_post_id: str, reddit_user: str, title: str,
                       content: str, source_url: str):
        """Добавляет пост в БД"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT
                OR IGNORE INTO posts 
                (reddit_post_id, reddit_user, title, content, source_url, status, fetched_at)
                VALUES (?, ?, ?, ?, ?, 'fetched', ?)""",
                (reddit_post_id, reddit_user, title, content, source_url, datetime.now())
            )
            await db.commit()

    async def get_post(self, reddit_post_id: str):
        """Получает пост из БД"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM posts WHERE reddit_post_id = ?",
                (reddit_post_id,)
            )
            return await cursor.fetchone()

    async def update_post_status(self, reddit_post_id: str, status: str, error_msg: str = None):
        """Обновляет статус поста"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE posts
                   SET status        = ?,
                       updated_at    = ?,
                       error_message = ?
                   WHERE reddit_post_id = ?""",
                (status, datetime.now(), error_msg, reddit_post_id)
            )
            await db.commit()

    # ===== ATTACHMENTS =====
    async def add_attachment(self, reddit_post_id: str, file_url: str,
                             file_type: str, file_size: int, caption: str = None):
        """Добавляет вложение"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO attachments
                       (reddit_post_id, file_url, file_type, file_size_bytes, caption, status)
                   VALUES (?, ?, ?, ?, ?, 'pending')""",
                (reddit_post_id, file_url, file_type, file_size, caption)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_attachments_by_post(self, reddit_post_id: str, status: str = None):
        """Получает все вложения поста"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM attachments WHERE reddit_post_id = ? AND status = ?",
                    (reddit_post_id, status)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM attachments WHERE reddit_post_id = ?",
                    (reddit_post_id,)
                )
            return await cursor.fetchall()

    async def get_attachment(self, attachment_id: int):
        """Получает одно вложение"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM attachments WHERE attachment_id = ?",
                (attachment_id,)
            )
            return await cursor.fetchone()

    async def update_attachment_status(self, attachment_id: int, status: str,
                                       local_path: str = None, telegram_file_id: str = None):
        """Обновляет статус вложения"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE attachments
                   SET status           = ?,
                       local_path       = ?,
                       telegram_file_id = ?,
                       updated_at       = CURRENT_TIMESTAMP
                   WHERE attachment_id = ?""",
                (status, local_path, telegram_file_id, attachment_id)
            )
            await db.commit()

    async def update_attachment_retry(self, attachment_id: int, retry_count: int):
        """Обновляет счётчик попыток вложения"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE attachments
                   SET retry_count        = ?,
                       last_retry_attempt = ?,
                       first_retry_at     = COALESCE(first_retry_at, CURRENT_TIMESTAMP)
                   WHERE attachment_id = ?""",
                (retry_count, datetime.now(), attachment_id)
            )
            await db.commit()

    # ===== DISK USAGE =====
    async def get_disk_usage(self) -> int:
        """Получает текущее использование диска в байтах"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT total_bytes FROM disk_usage LIMIT 1")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_disk_usage(self, bytes_delta: int):
        """Обновляет использование диска (положительное или отрицательное значение)"""
        async with aiosqlite.connect(self.db_path) as db:
            current = await self.get_disk_usage()
            new_total = max(0, current + bytes_delta)
            await db.execute(
                "UPDATE disk_usage SET total_bytes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (new_total,)
            )
            await db.commit()

    # ===== TELEGRAM MESSAGES =====
    async def add_telegram_message(self, message_id: int, reddit_post_id: str,
                                   chat_id: int, message_type: str):
        """Добавляет запись о сообщении в ТГ"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO telegram_messages
                       (message_id, reddit_post_id, telegram_chat_id, message_type, status)
                   VALUES (?, ?, ?, ?, 'sent')""",
                (message_id, reddit_post_id, chat_id, message_type)
            )
            await db.commit()

    # ===== STATS =====
    async def record_stats(self, posts_uploaded: int = 0, files_uploaded: int = 0,
                           bytes_uploaded: int = 0, posts_failed: int = 0,
                           posts_skipped: int = 0):
        """Записывает статистику"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO stats
                   (posts_uploaded, files_uploaded, bytes_uploaded, posts_failed, posts_skipped)
                   VALUES (?, ?, ?, ?, ?)""",
                (posts_uploaded, files_uploaded, bytes_uploaded, posts_failed, posts_skipped)
            )
            await db.commit()

    async def get_stats(self, period: str = None) -> dict:
        """Получает статистику за период (all, month, week, today)"""
        async with aiosqlite.connect(self.db_path) as db:
            if period == "today":
                days = 1
            elif period == "week":
                days = 7
            elif period == "month":
                days = 30
            else:  # all
                days = None

            if days:
                cutoff = datetime.now() - timedelta(days=days)
                cursor = await db.execute(
                    """SELECT SUM(posts_uploaded) as posts_uploaded,
                              SUM(files_uploaded) as files_uploaded,
                              SUM(bytes_uploaded) as bytes_uploaded,
                              SUM(posts_failed)   as posts_failed,
                              SUM(posts_skipped)  as posts_skipped
                       FROM stats
                       WHERE recorded_at > ?""",
                    (cutoff,)
                )
            else:
                cursor = await db.execute(
                    """SELECT SUM(posts_uploaded) as posts_uploaded,
                              SUM(files_uploaded) as files_uploaded,
                              SUM(bytes_uploaded) as bytes_uploaded,
                              SUM(posts_failed)   as posts_failed,
                              SUM(posts_skipped)  as posts_skipped
                       FROM stats"""
                )

            row = await cursor.fetchone()
            return {
                "posts_uploaded": row[0] or 0,
                "files_uploaded": row[1] or 0,
                "bytes_uploaded": row[2] or 0,
                "posts_failed": row[3] or 0,
                "posts_skipped": row[4] or 0,
            }


db = Database()
