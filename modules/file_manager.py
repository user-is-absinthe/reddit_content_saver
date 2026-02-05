import aiohttp
import asyncio
from pathlib import Path
from config import TEMP_DIR, MAX_FILE_SIZE_BYTES
from modules.logger import logger
from modules.database import db


class FileManager:
    def __init__(self):
        self.temp_dir = TEMP_DIR
        self.max_file_size = MAX_FILE_SIZE_BYTES

    async def download_file(self, url: str, file_type: str) -> tuple[str, int]:
        """
        Скачивает файл с URL
        Возвращает (local_path, file_size_bytes) или (None, 0) если ошибка
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download {url}: HTTP {resp.status}")
                        return None, 0

                    # Получаем размер файла
                    file_size = int(resp.headers.get('Content-Length', 0))

                    if file_size > self.max_file_size:
                        logger.warning(f"File too large ({file_size} bytes): {url}")
                        return None, file_size

                    # Генерируем имя файла
                    file_ext = self._get_extension(file_type, url)
                    filename = f"{asyncio.current_task().get_name()}_{Path(url).stem}{file_ext}"
                    local_path = self.temp_dir / filename

                    # Скачиваем файл
                    async with open(local_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)

                    actual_size = local_path.stat().st_size
                    logger.info(f"Downloaded {actual_size} bytes to {local_path}")

                    return str(local_path), actual_size

        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading {url}")
            return None, 0
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return None, 0

    async def delete_file(self, local_path: str) -> bool:
        """Удаляет файл с диска"""
        try:
            path = Path(local_path)
            if path.exists():
                file_size = path.stat().st_size
                path.unlink()
                await db.update_disk_usage(-file_size)
                logger.info(f"Deleted file: {local_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {local_path}: {e}")
            return False

    def _get_extension(self, file_type: str, url: str) -> str:
        """Определяет расширение файла"""
        if file_type == "image":
            if "imgur" in url:
                return ".jpg"
            elif ".png" in url:
                return ".png"
            elif ".gif" in url:
                return ".gif"
            else:
                return ".jpg"
        elif file_type in ["video", "gif"]:
            return ".mp4"
        else:
            return ".bin"


file_manager = FileManager()
