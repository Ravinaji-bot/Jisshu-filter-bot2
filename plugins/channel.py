# --| This code created & optimized by: Jisshu_bots & SilentXBotz |--#
import re
import hashlib
import asyncio
import aiohttp
from typing import Optional
from collections import defaultdict

from info import *
from utils import *
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla",
    "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli",
    "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German",
    "Chinese", "Arabic", "Portuguese", "Russian", "Japanese", "Odia",
    "Assamese", "Urdu"
]

# Web-Preview Layout with Hidden Poster Link
UPDATE_CAPTION = """{}<b>𝐃𝐫𝐚𝐠𝐨𝐧 {} 𝐅𝐢𝐫𝐞 🐉</b>

🎬 <b>{} {}</b>
🔰 <b>Quality:</b> {}
🎧 <b>Audio:</b> {}

<b>✨ Direct Files ✨</b>

{}
<blockquote>〽️ Powered by @MagicOfGroup</blockquote>"""

notified_movies = set()
movie_files = defaultdict(list)
POST_DELAY = 15
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media_obj = getattr(message, message.media.value, None)
    if not media_obj:
        return
        
    if media_obj.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media_obj.file_type = message.media.value
        media_obj.caption = message.caption
        success_sts = await save_file(media_obj)
        if success_sts == "suc" and await db.get_send_movie_update_status(bot_id):
            await queue_movie_file(bot, media_obj)


async def queue_movie_file(bot, media_obj):
    file_name = await movie_name_format(media_obj.file_name or "")
    caption = await movie_name_format(media_obj.caption or "")
    
    year_match = re.search(r"\b(19|20)\d{2}\b", caption) or re.search(r"\b(19|20)\d{2}\b", file_name)
    year = year_match.group(0) if year_match else None
    
    season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption) or re.search(
        r"(?i)(?:s|season)0*(\d{1,2})", file_name
    )
    
    clean_title = file_name
    if year and file_name.find(year) != -1:
        clean_title = file_name[: file_name.find(year) + 4].strip()
    elif season_match and file_name.find(season_match.group(1)) != -1:
        clean_title = file_name[: file_name.find(season_match.group(1)) + 1].strip()

    quality = await get_qualities(caption) or "HDRip"
    jisshuquality = await Jisshu_qualities(caption, media_obj.file_name or "") or "720p"
    language = (
        ", ".join([lang for lang in CAPTION_LANGUAGES if lang.lower() in caption.lower()])
        or "Hindi"
    )
    
    file_size_str = format_file_size(media_obj.file_size)
    file_id, _ = unpack_new_file_id(media_obj.file_id)
    
    movie_files[clean_title].append(
        {
            "quality": quality,
            "jisshuquality": jisshuquality,
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
        await asyncio.sleep(POST_DELAY)
        if clean_title in movie_files:
            await send_movie_update(bot, clean_title, movie_files[clean_title])
            del movie_files[clean_title]
    except Exception as e:
        print(f"Queue Error: {e}")
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
        
        year_match = re.search(r"\b(19|20)\d{2}\b", file_name)
        year = year_match.group(0) if year_match else (files[0]["year"] if files and files[0].get("year") else "")
        
        poster = await fetch_movie_poster(title, year)
        kind = imdb_data.get("kind", "").strip().upper().replace(" ", "_") if imdb_data else ""
        if kind in ["TV_SERIES", "SERIES"]:
            kind = "#SERIES"
        else:
            kind = "#MOVIE"

        languages = set()
        for file in files:
            if file["language"] != "Not Idea":
                languages.update(file["language"].split(", "))
        language = ", ".join(sorted(languages)) or "Hindi"

        episode_pattern = re.compile(r"S(\d{1,2})E(\d{1,2})", re.IGNORECASE)
        combined_pattern = re.compile(r"S(\d{1,2})\s*E(\d{1,2})[-~]E?(\d{1,2})", re.IGNORECASE)
        episode_map = defaultdict(dict)
        combined_links = []

        for file in files:
            caption = file["caption"]
            quality = file.get("jisshuquality") or file.get("quality") or "Unknown"
            size = file["file_size"]
            file_id = file['file_id']
            match = episode_pattern.search(caption)
            combined_match = combined_pattern.search(caption)

            if match:
                ep = f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"
                episode_map[ep][quality] = file
            elif combined_match:
                season = f"S{int(combined_match.group(1)):02d}"
                ep_range = f"E{int(combined_match.group(2)):02d}-{int(combined_match.group(3)):02d}"
                ep = f"{season}{ep_range}"
                combined_links.append(f"📦 {ep} ({quality}) : <a href='https://t.me/{temp.U_NAME}?start=file_0_{file_id}'>{size}</a>")
            elif re.search(r"complete|completed|batch|combined", caption, re.IGNORECASE):
                combined_links.append(f"📦 ({quality}) : <a href='https://t.me/{temp.U_NAME}?start=file_0_{file_id}'>{size}</a>")

        quality_text = ""

        for ep, qualities in sorted(episode_map.items()):
            parts = []
            for quality in sorted(qualities.keys()):
                f = qualities[quality]
                link = f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{quality}</a>"
                parts.append(link)
            joined = " - ".join(parts)
            quality_text += f"📦 {ep} : {joined}\n"

        if combined_links:
            quality_text += "\n<b>COMBiNED</b> ✅\n\n"
            quality_text += "\n".join(combined_links) + "\n"
            
        if not quality_text:
            quality_groups = defaultdict(list)
            for file in files:
                q = file.get("jisshuquality") or file.get("quality") or "Unknown"
                quality_groups[q].append(file)

            for quality, q_files in sorted(quality_groups.items()):
                links = [f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['file_size']}</a>" for f in q_files]
                line = f"📦 {quality} : " + " | ".join(links)
                quality_text += line + "\n"

        image_url = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"
        
        # Hidden Link for Web Page Preview Image Attachment
        hidden_image_link = f'<a href="{image_url}">&#8203;</a>'
        
        full_caption = UPDATE_CAPTION.format(
            hidden_image_link,
            kind,
            title,
            year,
            files[0]['quality'],
            language,
            quality_text
        )

        movie_update_channel = await db.movies_update_channel_id()
        raw_target = movie_update_channel if movie_update_channel else MOVIE_UPDATE_CHANNEL
        target_chat_id = int(raw_target) if str(raw_target).replace('-', '').isdigit() else raw_target

        # Sending Text Message with Web Page Preview ON
        await bot.send_message(
            chat_id=target_chat_id,
            text=full_caption,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=False
        )

    except Exception as e:
        print('Failed to send movie update. Error - ', e)


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
        print(f"IMDB fetch error: {e}")
        return {}


async def fetch_movie_poster(title: str, year: Optional[str] = None) -> Optional[str]:
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


async def get_qualities(text):
    qualities = [
        "480p", "720p", "720p HEVC", "1080p", "ORG", "org", "hdcam", "HDCAM",
        "HQ", "hq", "HDRip", "hdrip", "camrip", "WEB-DL", "CAMRip", "hdtc",
        "predvd", "DVDscr", "dvdscr", "dvdrip", "HDTC", "dvdscreen", "HDTS", "hdts"
    ]
    found_qualities = [q for q in qualities if q.lower() in text.lower()]
    return ", ".join(found_qualities) or "HDRip"


async def Jisshu_qualities(text, file_name):
    qualities = ["480p", "720p", "720p HEVC", "1080p", "1080p HEVC", "2160p"]
    combined_text = (text.lower() + " " + file_name.lower()).strip()
    if "hevc" in combined_text:
        for quality in qualities:
            if "HEVC" in quality and quality.split()[0].lower() in combined_text:
                return quality
    for quality in qualities:
        if "HEVC" not in quality and quality.lower() in combined_text:
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
