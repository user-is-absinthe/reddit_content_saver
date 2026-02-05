import asyncio
from pathlib import Path
from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, LinkPreviewOptions
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, MAX_TELEGRAM_MEDIA_GROUP
from modules.logger import logger
from modules.database import db


class TelegramClient:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.channel_id = TELEGRAM_CHANNEL_ID

    async def send_media_groups(self, attachments: list, post_data: dict) -> list:
        """
        Отправляет медиа в ТГ группами
        Если все одного типа — группирует до 10 в одном сообщении
        Если разные типы — разделяет по типам
        Возвращает список message_ids
        """
        message_ids = []

        try:
            # Группируем медиа по типам
            by_type = {}
            for att in attachments:
                file_type = att['file_type']
                if file_type not in by_type:
                    by_type[file_type] = []
                by_type[file_type].append(att)

            # Все одного типа?
            if len(by_type) == 1:
                file_type = list(by_type.keys())[0]
                files = by_type[file_type]
                msg_ids = await self._send_grouped_media(files, post_data)
                message_ids.extend(msg_ids)
            else:
                # Разные типы — отправляем по порядку: видео, гифки, фото, документы
                type_order = ['video', 'gif', 'image', 'document']
                for ftype in type_order:
                    if ftype in by_type:
                        files = by_type[ftype]
                        msg_ids = await self._send_grouped_media(files, post_data if ftype == type_order[-1] else None)
                        message_ids.extend(msg_ids)

            logger.info(f"Sent {len(message_ids)} messages for post {post_data['id']}")
            return message_ids

        except Exception as e:
            logger.error(f"Error sending media to Telegram: {e}")
            raise

    async def _send_grouped_media(self, attachments: list, post_data: dict = None) -> list:
        """
        Отправляет одну группу медиа (до 10 файлов)
        Если post_data переданы — добавляет описание в последнее медиа
        """
        message_ids = []

        # Разбиваем на группы по 10
        chunks = [attachments[i:i + MAX_TELEGRAM_MEDIA_GROUP]
                  for i in range(0, len(attachments), MAX_TELEGRAM_MEDIA_GROUP)]

        for chunk_idx, chunk in enumerate(chunks):
            media_group = []

            for file_idx, att in enumerate(chunk):
                # Последний файл в последней группе — с описанием поста
                caption = None

                if post_data and chunk_idx == len(chunks) - 1 and file_idx == len(chunk) - 1:
                    # Добавляем описание поста
                    post_text = post_data.get('selftext', '').strip()
                    if post_text:
                        # Ограничиваем длину описания
                        if len(post_text) > 1000:
                            post_text = post_text[:997] + "..."
                        caption = post_text
                    else:
                        caption = ""

                    # Добавляем ссылку на пост
                    caption += f"\n\n🔗 [Исходный пост](https://reddit.com{post_data['permalink']})"

                elif att.get('caption'):
                    caption = att['caption']

                # Ограничиваем длину caption
                if caption and len(caption) > 1024:
                    caption = caption[:1021] + "..."

                # Создаём InputMedia в зависимости от типа
                file_type = att['file_type']
                local_path = att['local_path']

                if file_type == 'image':
                    media = InputMediaPhoto(media=local_path, caption=caption)
                elif file_type in ['video', 'gif']:
                    media = InputMediaVideo(media=local_path, caption=caption)
                else:
                    media = InputMediaDocument(media=local_path, caption=caption)

                media_group.append(media)

            try:
                # Отправляем группу
                messages = await self.bot.send_media_group(self.channel_id, media_group)
                message_ids.extend([msg.message_id for msg in messages])

                logger.info(f"Sent media group with {len(media_group)} files")
                await asyncio.sleep(0.5)  # Избегаем flood-контроля

            except Exception as e:
                logger.error(f"Error sending media group: {e}")
                raise

        return message_ids

    async def send_text_message(self, text: str, disable_preview: bool = True) -> int:
        """
        Отправляет текстовое сообщение в канал
        Возвращает message_id
        """
        try:
            # Разбиваем текст на части (макс 4096 символов в ТГ)
            max_length = 4096
            message_ids = []

            if len(text) <= max_length:
                msg = await self.bot.send_message(
                    self.channel_id,
                    text,
                    parse_mode="HTML",
                    link_preview_options=LinkPreviewOptions(is_disabled=disable_preview)
                )
                return msg.message_id
            else:
                # Разбиваем на несколько сообщений
                parts = [text[i:i + max_length] for i in range(0, len(text), max_length)]
                for part in parts:
                    msg = await self.bot.send_message(
                        self.channel_id,
                        part,
                        parse_mode="HTML",
                        link_preview_options=LinkPreviewOptions(is_disabled=disable_preview)
                    )
                    message_ids.append(msg.message_id)
                    await asyncio.sleep(0.5)

                return message_ids[0]

        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            raise

    async def send_admin_message(self, text: str) -> bool:
        """Отправляет сообщение администратору"""
        try:
            from config import TELEGRAM_ADMIN_ID
            await self.bot.send_message(
                TELEGRAM_ADMIN_ID,
                text,
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            return True
        except Exception as e:
            logger.error(f"Error sending admin message: {e}")
            return False


telegram_client = TelegramClient()
