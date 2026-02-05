import asyncio
from config import RETRY_CONFIG
from modules.logger import logger


async def retry_with_backoff(coro, attachment_id: int, send_admin_alert_func):
    """
    Повторяет корутину с экспоненциальной задержкой
    Возвращает результат если успех, иначе None
    """
    max_retries = RETRY_CONFIG["max_retries"]
    alert_after_retry = RETRY_CONFIG["alert_after_retry"]
    initial_delay = RETRY_CONFIG["initial_delay"]
    backoff_multiplier = RETRY_CONFIG["backoff_multiplier"]

    for attempt in range(1, max_retries + 1):
        try:
            result = await coro

            # Если успех после 5+ попыток, уведомляем админа
            if attempt > alert_after_retry:
                await send_admin_alert_func(
                    f"✅ Задача {attachment_id} успешно восстановлена после {attempt} попыток"
                )

            logger.info(f"Success on attempt {attempt} for attachment {attachment_id}")
            return result

        except Exception as e:
            if attempt == alert_after_retry:
                # После 5 попыток отправляем первый алерт
                await send_admin_alert_func(
                    f"⚠️ Задача {attachment_id} имеет проблемы после {attempt} попыток: {str(e)[:100]}"
                )

            if attempt == max_retries:
                # После 15 попыток — финальный алерт
                await send_admin_alert_func(
                    f"❌ Задача {attachment_id} исчерпала все попытки ({max_retries}): {str(e)[:100]}"
                )
                logger.error(f"Failed after {max_retries} attempts for attachment {attachment_id}: {e}")
                return None

            # Рассчитываем задержку с backoff
            delay = initial_delay * (backoff_multiplier ** (attempt - 1))
            logger.warning(f"Attempt {attempt}/{max_retries} failed for attachment {attachment_id}. "
                           f"Retrying in {delay:.0f}s: {e}")

            await asyncio.sleep(delay)

    return None
