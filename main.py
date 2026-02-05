import asyncio
import signal
from aiogram import Dispatcher, Bot, F
from aiogram.types import Update
from config import (
    TELEGRAM_BOT_TOKEN, CHECK_INTERVAL, THREAD_COUNT,
    MAX_DISK_USAGE_BYTES, QUEUE_DEFER_POSITION, RETRY_CONFIG
)
from modules.logger import logger
from modules.database import db
from modules.telegram_client import telegram_client
from modules.reddit_client import reddit_client
from modules.file_manager import file_manager
from modules.handlers import admin_router
from modules.retry_logic import retry_with_backoff
from modules.utils import format_file_size, defer_attachment_in_queue


# Глобальное состояние
class AppState:
    running = True
    queue = asyncio.Queue()


app_state = AppState()


async def send_admin_alert(text: str):
    """Отправляет алерт администратору"""
    await telegram_client.send_admin_message(f"🚨 {text}")


async def fetch_reddit_likes():
    """Получает лайки с Реддита и добавляет в очередь"""
    logger.info("Fetching liked posts from Reddit...")

    try:
        posts = await asyncio.to_thread(reddit_client.get_liked_posts)

        added = 0
        skipped = 0

        for post in posts:
            # Проверяем, уже ли этот пост загружали
            existing = await db.get_post(post['id'])

            if existing:
                logger.debug(f"Post {post['id']} already processed")
                skipped += 1
                continue

            # Добавляем пост в БД
            await db.add_post(
                post['id'],
                post['author'],
                post['title'],
                post['selftext'],
                post['full_url']
            )

            # Если пост удалён — пропускаем
            if post['is_deleted']:
                await db.update_post_status(post['id'], 'skipped_deleted')
                skipped += 1
                continue

            # Добавляем вложения в очередь
            for media in post.get('media', []):
                await app_state.queue.put({
                    "type": "download",
                    "post_id": post['id'],
                    "post_data": post,
                    "media": media,
                })
                added += 1

            # Если нет медиа — отправляем просто текст
            if not post.get('media'):
                await app_state.queue.put({
                    "type": "text",
                    "post_id": post['id'],
                    "post_data": post,
                })
                added += 1

        logger.info(f"Fetched {added} new tasks, {skipped} already processed")
        await db.record_stats(posts_skipped=skipped)

    except Exception as e:
        logger.error(f"Error fetching Reddit likes: {e}")
        await send_admin_alert(f"Ошибка при получении лайков с Реддита: {str(e)[:100]}")


async def process_download_task(task: dict):
    """Обрабатывает задачу скачивания файла"""
    post_id = task['post_id']
    post_data = task['post_data']
    media = task['media']

    logger.info(f"Processing download task for post {post_id}")

    try:
        # Проверяем размер диска
        current_disk_usage = await db.get_disk_usage()
        file_size_bytes = media.get('file_size', 0) or 0

        if not file_size_bytes:
            # Если размер не известен, пытаемся скачать и проверить
            logger.debug(f"File size unknown, attempting download: {media['url']}")

        if current_disk_usage + file_size_bytes > MAX_DISK_USAGE_BYTES:
            # Диск переполнен — отодвигаем в конец очереди
            logger.warning(f"Disk full ({format_file_size(current_disk_usage)} used). Deferring task.")

            task['retry_count'] = task.get('retry_count', 0) + 1

            if task['retry_count'] < 5:  # Не отодвигаем бесконечно
                await defer_attachment_in_queue(app_state.queue, task, QUEUE_DEFER_POSITION)
            else:
                logger.error(f"Post {post_id} deferred too many times. Skipping.")
                await db.update_post_status(post_id, 'skipped_size_exceeded')
                await db.record_stats(posts_skipped=1)

            return

        # Создаём задачу скачивания в БД
        attachment_id = await db.add_attachment(
            post_id,
            media['url'],
            media['type'],
            file_size_bytes,
            media.get('caption')
        )

        # Скачиваем файл с повторами
        async def download_coro():
            local_path, actual_size = await file_manager.download_file(
                media['url'],
                media['type']
            )

            if not local_path:
                raise Exception(f"Failed to download {media['url']}")

            if actual_size > file_manager.max_file_size:
                raise Exception(f"File too large: {format_file_size(actual_size)}")

            return local_path, actual_size

        result = await retry_with_backoff(download_coro(), attachment_id, send_admin_alert)

        if not result:
            # Ошибка после всех попыток
            await db.update_attachment_status(attachment_id, 'failed')
            await db.update_post_status(post_id, 'download_failed')
            await db.record_stats(posts_failed=1)
            return

        local_path, actual_size = result

        # Обновляем БД и использование диска
        await db.update_attachment_status(attachment_id, 'downloaded', local_path=local_path)
        await db.update_disk_usage(actual_size)

        # Добавляем в очередь загрузки в ТГ
        await app_state.queue.put({
            "type": "upload",
            "post_id": post_id,
            "post_data": post_data,
            "attachment_id": attachment_id,
            "local_path": local_path,
        })

    except Exception as e:
        logger.error(f"Error in download task: {e}")
        await send_admin_alert(f"Ошибка скачивания для поста {post_id}: {str(e)[:100]}")


async def process_upload_task(task: dict):
    """Обрабатывает задачу загрузки в ТГ"""
    post_id = task['post_id']
    attachment_id = task['attachment_id']
    local_path = task['local_path']
    post_data = task['post_data']

    logger.info(f"Processing upload task for attachment {attachment_id}")

    try:
        # Подготавливаем данные для отправки
        attachment_data = await db.get_attachment(attachment_id)

        att_info = {
            'file_type': attachment_data['file_type'],
            'local_path': local_path,
            'caption': attachment_data['caption'],
        }

        # Загружаем с повторами
        async def upload_coro():
            message_id = await telegram_client.send_media_groups(
                [att_info],
                post_data
            )
            return message_id

        result = await retry_with_backoff(upload_coro(), attachment_id, send_admin_alert)

        if not result:
            # Ошибка после всех попыток
            await db.update_attachment_status(attachment_id, 'failed')
            await db.update_post_status(post_id, 'telegram_failed')
            await db.record_stats(posts_failed=1)
            return

        # Успешно загружено
        message_ids = result if isinstance(result, list) else [result]

        await db.update_attachment_status(attachment_id, 'uploaded')

        # Записываем message_ids
        for msg_id in message_ids:
            await db.add_telegram_message(msg_id, post_id, telegram_client.channel_id, 'media')

        # Удаляем файл с диска
        await file_manager.delete_file(local_path)

        await db.update_attachment_status(attachment_id, 'deleted')

        # Проверяем, все ли вложения для этого поста загружены
        pending = await db.get_attachments_by_post(post_id, status='uploaded')
        if not pending:
            await db.update_post_status(post_id, 'uploaded')
            await db.record_stats(posts_uploaded=1, files_uploaded=1,
                                  bytes_uploaded=0)  # TODO: отслеживать размер

    except Exception as e:
        logger.error(f"Error in upload task: {e}")
        await send_admin_alert(f"Ошибка загрузки вложения {attachment_id}: {str(e)[:100]}")


async def process_text_task(task: dict):
    """Обрабатывает задачу отправки текстового поста"""
    post_id = task['post_id']
    post_data = task['post_data']

    logger.info(f"Processing text task for post {post_id}")

    try:
        text = post_data.get('selftext', '').strip()

        if not text:
            await db.update_post_status(post_id, 'skipped_size_exceeded')
            await db.record_stats(posts_skipped=1)
            return

        # Добавляем ссылку на пост
        text += f"\n\n🔗 [Исходный пост](https://reddit.com{post_data['permalink']})"

        # Отправляем с повторами
        async def send_coro():
            msg_id = await telegram_client.send_text_message(text)
            return msg_id

        result = await retry_with_backoff(send_coro(), post_id, send_admin_alert)

        if result:
            await db.add_telegram_message(result, post_id, telegram_client.channel_id, 'text')
            await db.update_post_status(post_id, 'uploaded')
            await db.record_stats(posts_uploaded=1)
        else:
            await db.update_post_status(post_id, 'telegram_failed')
            await db.record_stats(posts_failed=1)

    except Exception as e:
        logger.error(f"Error in text task: {e}")
        await send_admin_alert(f"Ошибка отправки текста поста {post_id}: {str(e)[:100]}")


async def worker():
    """Воркер — обрабатывает задачи из очереди"""
    while app_state.running:
        try:
            # Получаем задачу с таймаутом
            task = await asyncio.wait_for(app_state.queue.get(), timeout=10)
        except asyncio.TimeoutError:
            continue

        try:
            task_type = task.get('type')

            if task_type == 'download':
                await process_download_task(task)
            elif task_type == 'upload':
                await process_upload_task(task)
            elif task_type == 'text':
                await process_text_task(task)
            else:
                logger.warning(f"Unknown task type: {task_type}")

        except Exception as e:
            logger.error(f"Error processing task: {e}")

        finally:
            app_state.queue.task_done()


async def reddit_fetcher():
    """Фоновая задача — периодически получает лайки с Реддита"""
    while app_state.running:
        try:
            await fetch_reddit_likes()
        except Exception as e:
            logger.error(f"Error in reddit fetcher: {e}")
            await send_admin_alert(f"Ошибка в фоновом процессе Реддита: {str(e)[:100]}")

        # Ждём перед следующей попыткой
        await asyncio.sleep(CHECK_INTERVAL)


async def telegram_polling():
    """Запускает polling для ТГ бота"""
    dp = Dispatcher()
    dp.include_router(admin_router)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logger.info("Starting Telegram bot polling...")
    await dp.start_polling(bot)


async def main():
    """Главная функция"""
    logger.info("Reddit Archiver Bot starting...")

    # Инициализируем БД
    await db.init()

    # Создаём задачи
    tasks = [
        asyncio.create_task(telegram_polling(), name="telegram_polling"),
        asyncio.create_task(reddit_fetcher(), name="reddit_fetcher"),
    ]

    # Добавляем воркеры
    for i in range(THREAD_COUNT):
        tasks.append(asyncio.create_task(worker(), name=f"worker_{i}"))

    # Обработчик сигналов для graceful shutdown
    def handle_signal(sig):
        logger.info(f"Received signal {sig}. Shutting down...")
        app_state.running = False

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, handle_signal, signal.SIGTERM)
    loop.add_signal_handler(signal.SIGINT, handle_signal, signal.SIGINT)

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    finally:
        app_state.running = False
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
