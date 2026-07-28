import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

WIKI_LANGS_TRY_ORDER = ["vi", "en"]
REQUEST_TIMEOUT_SEC = 8

async def _wiki_search_title(session: aiohttp.ClientSession, lang: str, query: str) -> str | None:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": 1,
    }
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            results = data.get("query", {}).get("search", [])
            if not results:
                return None
            return results[0]["title"]
    except (aiohttp.ClientError, TimeoutError):
        return None

async def _wiki_get_summary(session: aiohttp.ClientSession, lang: str, title: str) -> dict | None:
    import urllib.parse
    encoded_title = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if data.get("type") == "disambiguation":
                return None
            return data
    except (aiohttp.ClientError, TimeoutError):
        return None

async def fetch_wiki_result(query: str) -> tuple[dict | None, str | None]:
    async with aiohttp.ClientSession() as session:
        for lang in WIKI_LANGS_TRY_ORDER:
            data = await _wiki_get_summary(session, lang, query)
            if data:
                return data, lang

            found_title = await _wiki_search_title(session, lang, query)
            if found_title:
                data = await _wiki_get_summary(session, lang, found_title)
                if data:
                    return data, lang

        return None, None

class WikiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="wiki", description="Tìm kiếm từ khoá trên Wikipedia")
    @app_commands.describe(query="Từ khoá cần tìm kiếm")
    async def wiki(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        data, lang = await fetch_wiki_result(query)

        if data is None:
            await interaction.followup.send(
                f"Không tìm thấy kết quả nào cho **{query}** trên Wikipedia."
            )
            return

        title = data.get("title", query)
        extract = data.get("extract", "")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page")
        thumbnail = data.get("thumbnail", {}).get("source")

        if len(extract) > 400:
            extract = extract[:400].rsplit(".", 1)[0] + "..."

        embed = discord.Embed(
            title=f"📖 {title}",
            description=extract or "Không có mô tả tóm tắt.",
            color=discord.Color.blue(),
            url=page_url,
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        lang_label = "Tiếng Việt" if lang == "vi" else "Tiếng Anh"
        embed.set_footer(text=f"Nguồn: Wikipedia ({lang_label})")

        view = discord.ui.View(timeout=60)
        if page_url:
            view.add_item(discord.ui.Button(label="Đọc thêm trên Wikipedia", style=discord.ButtonStyle.link, url=page_url))

        await interaction.followup.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(WikiCog(bot))