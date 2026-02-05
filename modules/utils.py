from modules.logger import logger


def format_file_size(bytes_val: int) -> str:
    """Преобразует размер файла в читаемый формат"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


async def defer_attachment_in_queue(queue, attachment_data: dict, defer_count: int) -> bool:
    """Отодвигает задачу в очереди на N позиций"""
    try:
        # Добавляем в конец очереди N раз
        for _ in range(defer_count):
            await queue.put(attachment_data)

        logger.debug(f"Deferred attachment to queue ({defer_count} times)")
        return True
    except Exception as e:
        logger.error(f"Error deferring attachment: {e}")
        return False
