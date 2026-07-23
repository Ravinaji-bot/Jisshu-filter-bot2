# --| Code Updated & Optimized for Dragon Fire Master |--#
import re
import hashlib
import asyncio
from info import *
from utils import *
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
import aiohttp
from typing import Optional
from collections import defaultdict

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu",
    "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati",
    "Korean", "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic",
    "Portuguese", "Russian", "Japanese", "Odia", "Assamese", "Urdu"
]

# NEW HIGH-LOOK AESTHETIC CAPTION
UPDATE_CAPTION = """🍿 <b>Movie / Series :- {} ({})</b>

────•˚•── ✦ ──•˚•────
🎭 <b>ɢᴇɴʀᴇs :</b> {}
⭐ <b>ʀᴀᴛɪɴɢ :</b> HD
🔊 <b>ᴀᴜᴅɪᴏ  :</b> {}
🚀 <b>ǫᴜᴀʟɪᴛʏ :</b> WEB-DL
────•˚•── ✦ ──•˚•────
{}
────•˚•── ✦ ──•˚•────
🧿 <b>How to open link tutorial 👉</b> https://t.me/How_to_Open_Link_33/29
────•˚•── ✦ ──•˚•────

<blockquote><b>Powered by @DragonFireWords 🤞</b></blockquote>"""

notified_movies = set()
movie_files = defaultdict(list)

# 30 Seconds Delay to Collect All Uploaded Qualities Completely
POST_DELAY = 30
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)
    if media and media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.file_type = message.media.value
        media.caption = message.caption
        success_sts = await save_file(media)
        if success_sts == "suc" and await db.get_send_movie_update_status(bot_id):
            await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    file_name = await movie_name_format(media.file_name or "")
    caption = await movie_name_format(media.caption or "")
    
    # Clean Title extraction to prevent splitting qualities into different posts
    year_match = re.search(r"\b(19|20)\d{2}\b", caption) or re.search(r"\b(19|20)\d{2}\b", file_name)
    year = year_match.group(0) if year_match else None
    
    clean_title = file_name
    if year and file_name.find(year) != -1:
        clean_title = file_name[: file_name.find(year) + 4].strip()

    quality = await Jisshu_qualities(caption, media.file_name or "") or "720p"
    file_size_str = format_file_size(media.file_size)
    file_id, file_ref = unpack_new_file_id(media.file_id)
    
    language = (
        ", ".join([lang for lang in CAPTION_LANGUAGES if lang.lower() in caption.lower()])
        or "Hindi"
    )

    movie_files[clean_title].append(
        {
            "quality": quality,
            "file_id": file_id,
            "file_size": file_size_str,
            "caption": caption,
            "language": language,
            "year": year,
        }
    )
    
    if clean_title in processing_movies:
        return
        
    processing_movies.add(clean_title)
    
    try:
        # Collects all 4 qualities in 30 seconds buffer
        await asyncio.sleep(POST_DELAY)
        if clean_title in movie_files:
            await send_movie_update(bot, clean_title, movie_files[clean_title])
            del movie_files[clean_title]
    except Exception as e:
        print(f"Queue Exception: {e}")
    finally:
        if clean_title in processing_movies:
            processing_movies.remove(clean_title)


async def send_movie_update(bot, file_name, files):
    try:
        if file_name in notified_movies:
            return
        notified_movies.add(file_name)

        imdb_data = await get_imdb(file_name)
        title = imdb_data.get("title", file_name)
        year = imdb_data.get("year") or (files[0]['year'] if files and files[0].get('year') else "2026")
        poster = await fetch_movie_poster(title, year)
        kind = imdb_data.get("kind", "Action, Drama").strip().upper().replace(" ", "_") if imdb_data else "Action, Drama"
        
        if kind in ["TV_SERIES", "MOVIE", "", "NONE"]:
           kind = "Action, Drama"
           
        languages = set()
        for file in files:
            if file["language"] != "Not Idea":
                languages.update(file["language"].split(", "))
        language = ", ".join(sorted(languages)) or "Hindi"

        # Quality Links Construction
        quality_groups = defaultdict(list)
        for file in files:
            q = file.get("quality", "720p")
            quality_groups[q].append(file)

        quality_text = ""
        for quality, q_files in sorted(quality_groups.items()):
            links = []
            for f in q_files:
                link_url = f"https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}"
                links.append(f"<a href='{link_url}'>(Click Here)</a> <b>{f['file_size']}</b>")
            
            line = f"🔗 <b>{quality} :-</b> " + " | ".join(links)
            quality_text += line + "\n"

        image_url = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"
        
        # Exact 5 Parameters for UPDATE_CAPTION
        full_caption = UPDATE_CAPTION.format(title, year, kind, language, quality_text)

        movie_update_channel = await db.movies_update_channel_id()
        raw_target = movie_update_channel if movie_update_channel else MOVIE_UPDATE_CHANNEL
        
        target_chat_id = int(raw_target) if str(raw_target).replace('-', '').isdigit() else raw_target

        # Clean single-send call
        await bot.send_photo(
            chat_id=target_chat_id,
            photo=image_url,
            caption=full_caption,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        print('Error sending movie update:', e)


async def get_imdb(file_name):
    try:
        formatted_name = await movie_name_format(file_name)
        imdb = await get_poster(formatted_name)
        if not imdb:
            return {}
        return {
            "title": imdb.get("title", formatted_name),
            "kind": imdb.get("kind", "Movie"),
            "year": imdb.get("year"),
            "url": imdb.get("url"),
        }
    except Exception as e:
        print(f"IMDB error: {e}")
        return {}


async def fetch_movie_poster(title: str, year: Optional[int] = None) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        query = title.strip().replace(" ", "+")
        url = f"https://jisshuapis.vercel.app/api.php?query={query}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as res:
                if res.status != 200:
                    return None
                data = await res.json()
                for key in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                    posters = data.get(key)
                    if posters and isinstance(posters, list) and posters:
                        return posters[0]
                return None
        except Exception:
            return None


def generate_unique_id(movie_name):
    return hashlib.md5(movie_name.encode("utf-8")).hexdigest()[:5]


async def Jisshu_qualities(text, file_name):
    qualities = ["480p", "720p HEVC", "720p", "1080p HEVC", "1080p", "2160p", "ORG", "HDTS", "HDRip"]
    combined_text = (text.lower() + " " + file_name.lower()).strip()
    
    for quality in qualities:
        if quality.lower() in combined_text:
            return quality
    return "720p"


async def movie_name_format(file_name):
    filename = re.sub(
        r"http\S+",
        "",
        re.sub(r"@\w+|#\w+", "", file_name)
        .replace("_", " ")
        .replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
        .replace("{", "")
        .replace("}", "")
        .replace(".", " ")
        .replace("@", "")
        .replace(":", "")
        .replace(";", "")
        .replace("'", "")
        .replace("-", "")
        .replace("!", ""),
    ).strip()
    return filename


def format_file_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"
