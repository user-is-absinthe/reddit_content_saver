import praw
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from modules.logger import logger


class RedditClient:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )

    async def get_liked_posts(self, limit: int = 100):
        """Получает лайкнутые посты текущего пользователя"""
        try:
            me = self.reddit.user.me()
            liked_posts = []

            for post in me.liked(limit=limit):
                try:
                    post_data = {
                        "id": post.id,
                        "title": post.title,
                        "author": str(post.author) if post.author else "[deleted]",
                        "selftext": post.selftext,
                        "url": post.url,
                        "permalink": post.permalink,
                        "full_url": f"https://reddit.com{post.permalink}",
                        "media": self._extract_media(post),
                        "is_deleted": post.removed_by_moderator or post.author is None,
                    }
                    liked_posts.append(post_data)
                except Exception as e:
                    logger.warning(f"Error processing post {post.id}: {e}")
                    continue

            logger.info(f"Fetched {len(liked_posts)} liked posts from Reddit")
            return liked_posts

        except Exception as e:
            logger.error(f"Error fetching liked posts: {e}")
            raise

    def _extract_media(self, post) -> list:
        """Извлекает медиа из поста"""
        media_list = []

        try:
            # Если есть embedded media (видео, гифка)
            if hasattr(post, 'media') and post.media:
                if 'reddit_video' in post.media:
                    video_url = post.media['reddit_video']['fallback_url']
                    media_list.append({
                        "url": video_url,
                        "type": "video",
                        "caption": None
                    })
                elif 'oembed' in post.media:
                    # Для других типов медиа
                    pass

            # Если это gallery пост
            if hasattr(post, 'gallery_data') and post.gallery_data:
                for item in post.gallery_data.get('items', []):
                    media_id = item['media_id']
                    if media_id in post.media_metadata:
                        media_meta = post.media_metadata[media_id]

                        if media_meta['type'] == 'image':
                            url = media_meta['s']['x']
                            caption = item.get('caption', None)
                        elif media_meta['type'] == 'giphy':
                            url = media_meta['s']['x']
                            caption = item.get('caption', None)
                        else:
                            continue

                        media_list.append({
                            "url": url,
                            "type": "image" if media_meta['type'] == 'image' else "gif",
                            "caption": caption
                        })

            # Если это одиночная картинка/видео с URL
            elif post.is_video:
                video_url = post.media['reddit_video']['fallback_url']
                media_list.append({
                    "url": video_url,
                    "type": "video",
                    "caption": None
                })

            elif post.is_gallery:
                # Обработка галереи (см. выше)
                pass

            elif 'imgur' in post.url or 'gfycat' in post.url or \
                    post.url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                media_list.append({
                    "url": post.url,
                    "type": "image",
                    "caption": None
                })

        except Exception as e:
            logger.warning(f"Error extracting media from post {post.id}: {e}")

        return media_list


reddit_client = RedditClient()
