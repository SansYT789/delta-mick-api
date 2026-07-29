import aiohttp
import discord
import asyncio
import logging
from discord import app_commands
from discord.ext import commands
from typing import Optional, Tuple
from functools import lru_cache
import urllib.parse

logger = logging.getLogger('wiki_cog')
WIKI_LANGS_TRY_ORDER = ["vi", "en"]
REQUEST_TIMEOUT_SEC = 8
MAX_RETRIES = 2

class WikiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour
    
    def _get_cache_key(self, query: str) -> str:
        return query.lower().strip()
    
    def _get_cached(self, key: str) -> Optional[Tuple[dict, str]]:
        if key in self._cache:
            data, lang, timestamp = self._cache[key]
            if asyncio.get_event_loop().time() - timestamp < self._cache_ttl:
                return data, lang
            del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: dict, lang: str):
        self._cache[key] = (data, lang, asyncio.get_event_loop().time())
    
    async def _wiki_search_title(self, session: aiohttp.ClientSession, lang: str, query: str) -> Optional[str]:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    results = data.get("query", {}).get("search", [])
                    return results[0]["title"] if results else None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == MAX_RETRIES - 1:
                    logger.warning(f"Failed to search {lang} Wikipedia for '{query}': {e}")
                    return None
                await asyncio.sleep(0.5 * (attempt + 1))
        return None
    
    async def _wiki_get_summary(self, session: aiohttp.ClientSession, lang: str, title: str) -> Optional[dict]:
        encoded_title = urllib.parse.quote(title.replace(" ", "_"))
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if data.get("type") == "disambiguation":
                        return None
                    return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == MAX_RETRIES - 1:
                    logger.warning(f"Failed to get summary from {lang} Wikipedia for '{title}': {e}")
                    return None
                await asyncio.sleep(0.5 * (attempt + 1))
        return None
    
    def _truncate_extract(self, extract: str, max_length: int = 400) -> str:
        if len(extract) <= max_length:
            return extract
        
        # Cut at sentence boundaries
        for separator in ['. ', '? ', '! ', '\n', ', ']:
            truncated = extract[:max_length].rsplit(separator, 1)[0]
            if truncated and len(truncated) > max_length * 0.6:
                return truncated + '...'
        
        # Fallback: cut at space
        truncated = extract[:max_length].rsplit(' ', 1)[0]
        return truncated + '...' if truncated else extract[:max_length] + '...'
    
    async def fetch_wiki_result(self, query: str) -> Tuple[Optional[dict], Optional[str]]:
        cache_key = self._get_cache_key(query)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        async with aiohttp.ClientSession() as session:
            for lang in WIKI_LANGS_TRY_ORDER:
                # Try direct summary first
                data = await self._wiki_get_summary(session, lang, query)
                if data:
                    self._set_cache(cache_key, data, lang)
                    return data, lang
                
                # Search for title
                found_title = await self._wiki_search_title(session, lang, query)
                if found_title:
                    data = await self._wiki_get_summary(session, lang, found_title)
                    if data:
                        self._set_cache(cache_key, data, lang)
                        return data, lang
            
            return None, None

    @app_commands.command(name="wiki", description="Tìm kiếm từ khoá trên Wikipedia")
    @app_commands.describe(
        query="Từ khoá cần tìm kiếm",
        full="Hiển thị nội dung đầy đủ thay vì tóm tắt"
    )
    async def wiki(self, interaction: discord.Interaction, query: str, full: bool = False):
        # Validate query
        if len(query.strip()) < 2:
            await interaction.response.send_message(
                "❌ Từ khoá tìm kiếm quá ngắn (cần ít nhất 2 ký tự).",
                ephemeral=True
            )
            return
        
        if len(query) > 200:
            await interaction.response.send_message(
                "❌ Từ khoá tìm kiếm quá dài (tối đa 200 ký tự).",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            data, lang = await self.fetch_wiki_result(query.strip())
        except Exception as e:
            logger.error(f"Error fetching Wikipedia: {e}")
            await interaction.followup.send(
                "❌ Đã xảy ra lỗi khi tìm kiếm trên Wikipedia. Vui lòng thử lại sau."
            )
            return
        
        if data is None:
            await interaction.followup.send(
                f"❌ Không tìm thấy kết quả nào cho **{query}** trên Wikipedia."
            )
            return
        
        title = data.get("title", query)
        extract = data.get("extract", "")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page")
        thumbnail = data.get("thumbnail", {}).get("source")
        
        if not full:
            extract = self._truncate_extract(extract)
        
        embed = discord.Embed(
            title=f"📖 {title}",
            description=extract or "Không có mô tả tóm tắt.",
            color=discord.Color.blue(),
            url=page_url,
        )
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        lang_label = "Tiếng Việt" if lang == "vi" else "Tiếng Anh"
        embed.set_footer(
            text=f"Nguồn: Wikipedia ({lang_label})",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/8/80/Wikipedia-logo-v2.svg"
        )
        
        view = discord.ui.View(timeout=300)
        if page_url:
            view.add_item(discord.ui.Button(
                label="Đọc thêm trên Wikipedia",
                style=discord.ButtonStyle.link,
                url=page_url
            ))
        
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(WikiCog(bot))