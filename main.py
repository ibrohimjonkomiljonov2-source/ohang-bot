import asyncio
import logging
import os
import re
import shutil
import uuid
import json
import urllib.parse
import urllib.request
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from dotenv import load_dotenv
from yt_dlp import YoutubeDL


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_MB = int(os.getenv("MAX_FILE_MB", "49"))
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES", "")

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

COOKIE_FILE = Path("/tmp/youtube_cookies.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("OhangBot")

router = Router()

jobs = {}
busy = set()

URL_PATTERN = re.compile(r"https?://\S+", re.I)


# =========================================================
# COOKIE
# =========================================================

def prepare_cookie():
    if not YOUTUBE_COOKIES:
        logger.warning("YOUTUBE_COOKIES mavjud emas.")
        return

    try:
        cookie_text = YOUTUBE_COOKIES.replace("\\n", "\n")

        COOKIE_FILE.write_text(
            cookie_text,
            encoding="utf-8"
        )

        logger.info("YouTube cookie tayyorlandi.")

    except Exception as e:
        logger.error("Cookie xatosi: %s", e)


prepare_cookie()


# =========================================================
# PLATFORM ANIQLASH
# =========================================================

def is_youtube(url):
    url = url.lower()

    return (
        "youtube.com" in url
        or "youtu.be" in url
    )


def is_instagram(url):
    return "instagram.com" in url.lower()


# =========================================================
# YT-DLP
# =========================================================

def ydl_base(use_cookie=False):

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }

    # Cookie faqat YouTube uchun
    if (
        use_cookie
        and YOUTUBE_COOKIES
        and COOKIE_FILE.exists()
    ):
        options["cookiefile"] = str(COOKIE_FILE)

    return options


# =========================================================
# VIDEO INFO
# =========================================================

def get_media_info(url):

    youtube = is_youtube(url)

    opts = ydl_base(
        use_cookie=youtube
    )

    opts["skip_download"] = True

    # YouTube uchun alohida sozlama
    if youtube:
        opts["extractor_args"] = {
            "youtube": {
                "player_client": [
                    "default",
                    "web_embedded"
                ]
            }
        }

    with YoutubeDL(opts) as ydl:
        data = ydl.extract_info(
            url,
            download=False
        )

    return {
        "title": data.get("title", "Video"),
        "duration": data.get("duration"),
    }


# =========================================================
# VIDEO DOWNLOAD
# =========================================================

def download_video(url, folder, height):

    youtube = is_youtube(url)

    opts = ydl_base(
        use_cookie=youtube
    )

    opts.update({
        "outtmpl": str(
            folder / "video.%(ext)s"
        ),

        "format":
            f"bv*[height<={height}]+ba/"
            f"b[height<={height}]/best",

        "merge_output_format": "mp4",
    })

    if youtube:
        opts["extractor_args"] = {
            "youtube": {
                "player_client": [
                    "default",
                    "web_embedded"
                ]
            }
        }

    with YoutubeDL(opts) as ydl:
        ydl.extract_info(
            url,
            download=True
        )

    files = [
        f for f in folder.iterdir()
        if f.is_file()
        and f.suffix.lower()
        not in (".part", ".ytdl")
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda f: f.stat().st_size
    )


# =========================================================
# MP3 DOWNLOAD
# =========================================================

def download_mp3(url, folder):

    youtube = is_youtube(url)

    opts = ydl_base(
        use_cookie=youtube
    )

    opts.update({
        "outtmpl": str(
            folder / "audio.%(ext)s"
        ),

        "format": "bestaudio/best",

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    })

    if youtube:
        opts["extractor_args"] = {
            "youtube": {
                "player_client": [
                    "default",
                    "web_embedded"
                ]
            }
        }

    with YoutubeDL(opts) as ydl:
        ydl.extract_info(
            url,
            download=True
        )

    files = list(
        folder.glob("*.mp3")
    )

    return files[0] if files else None


# =========================================================
# MUSTAQIL MUSIQA QIDIRUV
# YouTube ishlatilmaydi!
# =========================================================

def search_music(query):

    params = urllib.parse.urlencode({
        "term": query,
        "entity": "song",
        "limit": 5,
        "country": "US",
    })

    url = (
        "https://itunes.apple.com/search?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=15
    ) as response:

        data = json.loads(
            response.read().decode("utf-8")
        )

    results = []

    for item in data.get(
        "results",
        []
    ):

        results.append({
            "artist":
                item.get(
                    "artistName",
                    "Noma'lum"
                ),

            "title":
                item.get(
                    "trackName",
                    "Noma'lum"
                ),

            "album":
                item.get(
                    "collectionName",
                    ""
                ),

            "preview":
                item.get(
                    "previewUrl"
                ),

            "artwork":
                item.get(
                    "artworkUrl100"
                ),

            "link":
                item.get(
                    "trackViewUrl"
                ),
        })

    return results


# =========================================================
# PREVIEW DOWNLOAD
# =========================================================

def download_preview(
    preview_url,
    destination
):

    request = urllib.request.Request(
        preview_url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        destination.write_bytes(
            response.read()
        )

    return destination


# =========================================================
# VIDEO QUALITY BUTTON
# =========================================================

def quality_keyboard(job_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 360p",
                    callback_data=f"d:{job_id}:360"
                ),
                InlineKeyboardButton(
                    text="📺 480p",
                    callback_data=f"d:{job_id}:480"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔥 720p",
                    callback_data=f"d:{job_id}:720"
                ),
                InlineKeyboardButton(
                    text="💎 1080p",
                    callback_data=f"d:{job_id}:1080"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎵 MP3",
                    callback_data=f"d:{job_id}:mp3"
                )
            ]
        ]
    )


# =========================================================
# /START
# =========================================================

@router.message(CommandStart())
async def start(message: Message):

    name = (
        message.from_user.first_name
        if message.from_user
        else "Do‘stim"
    )

    await message.answer(
        f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"

        "🎵 <b>Ohang Bot</b>\n\n"

        "🔎 <b>Musiqa qidirish:</b>\n"
        "Qo‘shiq yoki ijrochi nomini yozing.\n"
        "Masalan:\n"
        "<code>Konsta Odamlar nima deydi</code>\n\n"

        "▶️ <b>YouTube:</b>\n"
        "YouTube link yuboring.\n\n"

        "📸 <b>Instagram:</b>\n"
        "Reels yoki post link yuboring.\n\n"

        "🎬 360p / 480p / 720p / 1080p\n"
        "🎧 MP3 format mavjud."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

@router.message(F.text)
async def text_handler(message: Message):

    text = message.text.strip()

    match = URL_PATTERN.search(text)

    # =====================================================
    # LINK YO'Q = MUSIQA QIDIRUV
    # =====================================================

    if not match:

        status = await message.answer(
            "🎵 <b>Musiqa qidirilmoqda...</b>"
        )

        try:

            results = await asyncio.to_thread(
                search_music,
                text
            )

            if not results:

                return await status.edit_text(
                    "😔 Musiqa topilmadi.\n\n"
                    "Qo‘shiqchi va qo‘shiq "
                    "nomini aniqroq yozib ko‘ring."
                )

            rows = []

            result_text = (
                "🎵 <b>Topilgan musiqalar:</b>\n\n"
            )

            for number, item in enumerate(
                results,
                1
            ):

                music_id = (
                    uuid.uuid4().hex[:10]
                )

                jobs[music_id] = {
                    "type": "music",
                    "data": item
                }

                result_text += (
                    f"<b>{number}. "
                    f"{item['artist']} — "
                    f"{item['title']}</b>\n"
                )

                if item["album"]:
                    result_text += (
                        f"💿 {item['album']}\n"
                    )

                result_text += "\n"

                if item["preview"]:

                    rows.append([
                        InlineKeyboardButton(
                            text=
                            f"🎧 {number}. Eshitish",
                            callback_data=
                            f"music:{music_id}"
                        )
                    ])

            if rows:

                markup = InlineKeyboardMarkup(
                    inline_keyboard=rows
                )

            else:

                markup = None

            await status.edit_text(
                result_text,
                reply_markup=markup
            )

        except Exception as e:

            logger.exception(
                "Music search error"
            )

            await status.edit_text(
                "❌ Musiqa qidirishda "
                "xatolik yuz berdi.\n\n"
                f"<code>{str(e)[-300:]}</code>"
            )

        return


    # =====================================================
    # LINK
    # =====================================================

    url = match.group(0).rstrip(
        ").,]}>"
    )

    if not (
        is_youtube(url)
        or is_instagram(url)
    ):

        return await message.answer(
            "❌ Hozircha faqat "
            "YouTube va Instagram linklari."
        )

    # Platformani ko'rsatamiz
    if is_youtube(url):

        status = await message.answer(
            "▶️ <b>YouTube video "
            "tekshirilmoqda...</b>"
        )

    else:

        status = await message.answer(
            "📸 <b>Instagram media "
            "tekshirilmoqda...</b>"
        )

    try:

        info = await asyncio.to_thread(
            get_media_info,
            url
        )

        job_id = (
            uuid.uuid4().hex[:10]
        )

        jobs[job_id] = {
            "type": "media",
            "url": url
        }

        duration_text = ""

        duration = info.get(
            "duration"
        )

        if isinstance(
            duration,
            (int, float)
        ):

            duration = int(
                duration
            )

            duration_text = (
                f"\n⏱ "
                f"{duration // 60}:"
                f"{duration % 60:02d}"
            )

        await status.edit_text(
            f"🎬 <b>"
            f"{info['title'][:180]}"
            f"</b>"
            f"{duration_text}\n\n"

            "👇 Formatni tanlang:",

            reply_markup=
            quality_keyboard(
                job_id
            )
        )

    except Exception as e:

        logger.exception(
            "Media info error"
        )

        error = str(e)

        if is_youtube(url):

            await status.edit_text(
                "❌ <b>YouTube videoni "
                "ocholmadi.</b>\n\n"

                "Bu xato faqat YouTube "
                "bo‘limiga tegishli.\n\n"

                "🎵 Musiqa qidirish va "
                "📸 Instagram ishlashda "
                "davom etadi."
            )

        else:

            await status.edit_text(
                "❌ <b>Instagram media "
                "ochilmadi.</b>\n\n"

                f"<code>{error[-300:]}</code>"
            )


# =========================================================
# MUSIC PREVIEW
# =========================================================

@router.callback_query(
    F.data.startswith("music:")
)
async def music_preview(
    callback: CallbackQuery
):

    music_id = (
        callback.data.split(":")[1]
    )

    job = jobs.get(
        music_id
    )

    if (
        not job
        or job.get("type") != "music"
    ):

        return await callback.answer(
            "Natija eskirgan.",
            show_alert=True
        )

    item = job["data"]

    preview = item.get(
        "preview"
    )

    if not preview:

        return await callback.answer(
            "Preview mavjud emas.",
            show_alert=True
        )

    await callback.answer()

    status = await callback.message.answer(
        "🎧 Preview yuklanmoqda..."
    )

    folder = (
        DOWNLOAD_DIR /
        f"music_{music_id}"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        path = (
            folder /
            "preview.m4a"
        )

        await asyncio.to_thread(
            download_preview,
            preview,
            path
        )

        await callback.message.answer_audio(
            FSInputFile(path),
            title=item["title"],
            performer=item["artist"],
            request_timeout=120
        )

        await status.delete()

    except Exception as e:

        logger.exception(
            "Preview error"
        )

        await status.edit_text(
            "❌ Preview yuklanmadi.\n\n"
            f"<code>{str(e)[-300:]}</code>"
        )

    finally:

        shutil.rmtree(
            folder,
            ignore_errors=True
        )


# =========================================================
# MEDIA DOWNLOAD
# =========================================================

@router.callback_query(
    F.data.startswith("d:")
)
async def media_download(
    callback: CallbackQuery
):

    _, job_id, mode = (
        callback.data.split(":")
    )

    job = jobs.get(
        job_id
    )

    if (
        not job
        or job.get("type") != "media"
    ):

        return await callback.answer(
            "So‘rov eskirgan.",
            show_alert=True
        )

    url = job["url"]

    user_id = (
        callback.from_user.id
    )

    if user_id in busy:

        return await callback.answer(
            "⏳ Oldingi yuklash "
            "tugashini kuting.",
            show_alert=True
        )

    busy.add(
        user_id
    )

    await callback.answer()

    folder = (
        DOWNLOAD_DIR /
        f"{user_id}_{job_id}"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    await callback.message.edit_text(
        "⏳ <b>Yuklanmoqda...</b>"
    )

    try:

        if mode == "mp3":

            path = await asyncio.to_thread(
                download_mp3,
                url,
                folder
            )

        else:

            path = await asyncio.to_thread(
                download_video,
                url,
                folder,
                int(mode)
            )

        if not path:

            raise RuntimeError(
                "Fayl yaratilmadi."
            )

        size_mb = (
            path.stat().st_size
            / 1024
            / 1024
        )

        if size_mb > MAX_MB:

            return await callback.message.edit_text(
                f"⚠️ Fayl: "
                f"<b>{size_mb:.1f} MB</b>\n\n"

                f"Limit: "
                f"<b>{MAX_MB} MB</b>\n\n"

                "👇 Pastroq sifatni tanlang.",

                reply_markup=
                quality_keyboard(
                    job_id
                )
            )

        await callback.message.edit_text(
            "📤 <b>Telegramga "
            "yuborilmoqda...</b>\n\n"
            f"📦 {size_mb:.1f} MB"
        )

        if mode == "mp3":

            await callback.message.answer_audio(
                FSInputFile(path),
                request_timeout=900
            )

        else:

            try:

                await callback.message.answer_video(
                    FSInputFile(path),
                    supports_streaming=True,
                    request_timeout=900
                )

            except Exception:

                await callback.message.answer_document(
                    FSInputFile(path),
                    request_timeout=900
                )

        await callback.message.edit_text(
            "✅ <b>Tayyor!</b>"
        )

    except Exception as e:

        logger.exception(
            "Media download error"
        )

        if is_youtube(url):

            msg = (
                "❌ <b>YouTube yuklashda "
                "xatolik.</b>\n\n"

                "YouTube server so‘rovini "
                "cheklayotgan bo‘lishi mumkin.\n\n"

                "🎵 Musiqa qidirish va "
                "📸 Instagram bundan "
                "mustaqil ishlaydi."
            )

        else:

            msg = (
                "❌ <b>Instagram yuklashda "
                "xatolik:</b>\n\n"

                f"<code>{str(e)[-300:]}</code>"
            )

        try:

            await callback.message.edit_text(
                msg,
                reply_markup=
                quality_keyboard(
                    job_id
                )
            )

        except Exception:

            pass

    finally:

        busy.discard(
            user_id
        )

        shutil.rmtree(
            folder,
            ignore_errors=True
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN topilmadi."
        )

    bot = Bot(
        BOT_TOKEN,

        session=AiohttpSession(
            timeout=900
        ),

        default=
        DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    dp.include_router(
        router
    )

    me = await bot.get_me()

    logger.info(
        "Bot ishga tushdi: @%s",
        me.username
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
