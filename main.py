import asyncio
import logging
import os
import re
import shutil
import uuid
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

logger = logging.getLogger("MediaYuklaBot")


# =========================================================
# COOKIE
# =========================================================

def prepare_cookie():

    if not YOUTUBE_COOKIES:
        logger.warning("YOUTUBE_COOKIES mavjud emas.")
        return False

    try:
        text = YOUTUBE_COOKIES.replace("\\n", "\n")

        COOKIE_FILE.write_text(
            text,
            encoding="utf-8"
        )

        logger.info(
            "YouTube cookie tayyorlandi."
        )

        return True

    except Exception as e:

        logger.error(
            "Cookie yaratishda xato: %s",
            e
        )

        return False


prepare_cookie()


# =========================================================
# GLOBAL
# =========================================================

router = Router()

jobs = {}

busy = set()

URL_PATTERN = re.compile(
    r"https?://\S+",
    re.I
)


# =========================================================
# YT-DLP BASE OPTIONS
# =========================================================

def ydl_options():

    opts = {

        "quiet": True,

        "no_warnings": True,

        "noplaylist": True,

        "retries": 5,

        "fragment_retries": 5,

        "extractor_retries": 3,

        "socket_timeout": 30,

        # Hozirgi YouTube reload muammosi uchun
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "default",
                    "web_embedded"
                ]
            }
        },
    }

    if (
        YOUTUBE_COOKIES
        and COOKIE_FILE.exists()
    ):

        opts["cookiefile"] = str(
            COOKIE_FILE
        )

    return opts


# =========================================================
# KEYBOARD
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
# VIDEO INFO
# =========================================================

def get_info(url):

    opts = ydl_options()

    opts.update({
        "skip_download": True
    })

    with YoutubeDL(opts) as ydl:

        data = ydl.extract_info(
            url,
            download=False
        )

    return {
        "title": data.get(
            "title",
            "Video"
        ),

        "duration": data.get(
            "duration"
        ),
    }


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def search_youtube(query):

    opts = ydl_options()

    opts.update({

        "skip_download": True,

        "extract_flat": True,
    })

    with YoutubeDL(opts) as ydl:

        data = ydl.extract_info(
            f"ytsearch5:{query}",
            download=False
        )

    results = []

    for item in (
        data.get("entries") or []
    )[:5]:

        if not item:
            continue

        video_id = item.get("id")

        if not video_id:
            continue

        results.append({

            "title": item.get(
                "title",
                "Natija"
            ),

            "url":
                "https://www.youtube.com/watch?v="
                + video_id
        })

    return results


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_video(
    url,
    folder,
    height
):

    opts = ydl_options()

    opts.update({

        "outtmpl":
            str(
                folder /
                "video.%(ext)s"
            ),

        "format":
            f"bv*[height<={height}]+ba/"
            f"b[height<={height}]/best",

        "merge_output_format":
            "mp4",

    })

    with YoutubeDL(opts) as ydl:

        ydl.extract_info(
            url,
            download=True
        )

    files = [

        f for f in folder.iterdir()

        if f.is_file()

        and f.suffix.lower()
        not in (
            ".part",
            ".ytdl"
        )
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda x:
        x.stat().st_size
    )


# =========================================================
# DOWNLOAD MP3
# =========================================================

def download_mp3(
    url,
    folder
):

    opts = ydl_options()

    opts.update({

        "outtmpl":
            str(
                folder /
                "audio.%(ext)s"
            ),

        "format":
            "bestaudio/best",

        "postprocessors": [

            {
                "key":
                    "FFmpegExtractAudio",

                "preferredcodec":
                    "mp3",

                "preferredquality":
                    "192",
            }
        ],
    })

    with YoutubeDL(opts) as ydl:

        ydl.extract_info(
            url,
            download=True
        )

    mp3_files = list(
        folder.glob("*.mp3")
    )

    if not mp3_files:
        return None

    return mp3_files[0]


# =========================================================
# /START
# =========================================================

@router.message(
    CommandStart()
)
async def start(
    message: Message
):

    name = (
        message.from_user.first_name
        if message.from_user
        else "Do‘stim"
    )

    await message.answer(

        f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"

        "🎬 <b>Media Yuklovchi Bot</b>\n\n"

        "🔗 YouTube yoki Instagram "
        "havolasini yuboring.\n\n"

        "🔎 Qo‘shiq nomini yozsangiz "
        "YouTube'dan qidiraman.\n\n"

        "📥 Video:\n"
        "• 360p\n"
        "• 480p\n"
        "• 720p\n"
        "• 1080p\n\n"

        "🎵 MP3 ham mavjud."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

@router.message(
    F.text
)
async def text_handler(
    message: Message
):

    text = (
        message.text or ""
    ).strip()

    match = URL_PATTERN.search(
        text
    )

    # =====================================================
    # TEXT = MUSIC SEARCH
    # =====================================================

    if not match:

        status = await message.answer(
            "🔎 <b>Qidirilmoqda...</b>"
        )

        try:

            results = (
                await asyncio.to_thread(
                    search_youtube,
                    text
                )
            )

            if not results:

                return await status.edit_text(
                    "😔 Hech narsa topilmadi."
                )

            rows = []

            for number, item in enumerate(
                results,
                1
            ):

                job_id = (
                    uuid.uuid4().hex[:10]
                )

                jobs[job_id] = (
                    item["url"]
                )

                rows.append([

                    InlineKeyboardButton(

                        text=
                        f"{number}. "
                        f"{item['title'][:45]}",

                        callback_data=
                        f"p:{job_id}"
                    )
                ])

            await status.edit_text(

                "🎵 <b>Qidiruv natijalari:</b>\n\n"
                "Keraklisini tanlang:",

                reply_markup=
                InlineKeyboardMarkup(
                    inline_keyboard=rows
                )
            )

        except Exception as e:

            logger.exception(
                "Search error"
            )

            await status.edit_text(

                "❌ <b>Qidiruvda xatolik:</b>\n\n"

                f"<code>{str(e)[-500:]}</code>"
            )

        return


    # =====================================================
    # LINK
    # =====================================================

    url = (
        match.group(0)
        .rstrip(").,]}>")
    )

    allowed = (
        "youtube.com",
        "youtu.be",
        "instagram.com"
    )

    if not any(
        site in url.lower()
        for site in allowed
    ):

        return await message.answer(

            "❌ Hozircha faqat "
            "YouTube va Instagram."
        )

    status = await message.answer(
        "🔎 <b>Video tekshirilmoqda...</b>"
    )

    try:

        data = await asyncio.to_thread(
            get_info,
            url
        )

        job_id = (
            uuid.uuid4().hex[:10]
        )

        jobs[job_id] = url

        duration = (
            data.get("duration")
        )

        duration_text = ""

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
            f"{data['title'][:180]}"
            f"</b>"
            f"{duration_text}\n\n"

            "👇 <b>Sifatni tanlang:</b>",

            reply_markup=
            quality_keyboard(
                job_id
            )
        )

    except Exception as e:

        logger.exception(
            "Info error"
        )

        error = str(e)

        if (
            "page needs to be reloaded"
            in error.lower()
        ):

            msg = (
                "❌ <b>YouTube player xatosi.</b>\n\n"
                "Server YouTube sahifasini "
                "o‘qiy olmadi."
            )

        elif (
            "sign in to confirm"
            in error.lower()
            or
            "not a bot"
            in error.lower()
        ):

            msg = (
                "❌ <b>YouTube autentifikatsiya "
                "xatosi.</b>\n\n"
                "🍪 Cookie eskirgan bo‘lishi mumkin."
            )

        else:

            msg = (
                "❌ <b>Video tekshirilmadi:</b>\n\n"
                f"<code>{error[-500:]}</code>"
            )

        await status.edit_text(
            msg
        )


# =========================================================
# SEARCH RESULT
# =========================================================

@router.callback_query(
    F.data.startswith("p:")
)
async def pick_result(
    callback: CallbackQuery
):

    job_id = (
        callback.data.split(":")[1]
    )

    await callback.answer()

    if job_id not in jobs:

        return await callback.message.edit_text(
            "❌ So‘rov eskirgan."
        )

    await callback.message.edit_text(

        "🎬 <b>Formatni tanlang:</b>",

        reply_markup=
        quality_keyboard(
            job_id
        )
    )


# =========================================================
# DOWNLOAD
# =========================================================

@router.callback_query(
    F.data.startswith("d:")
)
async def download_handler(
    callback: CallbackQuery
):

    _, job_id, mode = (
        callback.data.split(":")
    )

    url = jobs.get(
        job_id
    )

    user_id = (
        callback.from_user.id
    )

    if not url:

        return await callback.answer(
            "So‘rov eskirgan.",
            show_alert=True
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

        "⏳ <b>Yuklanmoqda...</b>\n\n"
        "Iltimos kuting."
    )

    try:

        # =================================================
        # DOWNLOAD
        # =================================================

        if mode == "mp3":

            file_path = (
                await asyncio.to_thread(
                    download_mp3,
                    url,
                    folder
                )
            )

        else:

            file_path = (
                await asyncio.to_thread(
                    download_video,
                    url,
                    folder,
                    int(mode)
                )
            )

        if (
            not file_path
            or
            not file_path.exists()
        ):

            return await callback.message.edit_text(

                "❌ Fayl yaratilmadi.",

                reply_markup=
                quality_keyboard(
                    job_id
                )
            )

        # =================================================
        # SIZE
        # =================================================

        size_mb = (
            file_path.stat().st_size
            / 1024
            / 1024
        )

        if size_mb > MAX_MB:

            return await callback.message.edit_text(

                "⚠️ <b>Fayl juda katta.</b>\n\n"

                f"📦 {size_mb:.1f} MB\n"
                f"📏 Limit: {MAX_MB} MB\n\n"

                "👇 Pastroq sifatni tanlang.",

                reply_markup=
                quality_keyboard(
                    job_id
                )
            )

        # =================================================
        # TELEGRAM UPLOAD
        # =================================================

        await callback.message.edit_text(

            "📤 <b>Telegramga "
            "yuborilmoqda...</b>\n\n"

            f"📦 {size_mb:.1f} MB"
        )

        if mode == "mp3":

            await callback.message.answer_audio(

                FSInputFile(
                    file_path
                ),

                request_timeout=900
            )

        else:

            try:

                await callback.message.answer_video(

                    FSInputFile(
                        file_path
                    ),

                    supports_streaming=True,

                    request_timeout=900
                )

            except Exception:

                logger.exception(
                    "answer_video failed"
                )

                await callback.message.answer_document(

                    FSInputFile(
                        file_path
                    ),

                    request_timeout=900
                )

        await callback.message.edit_text(
            "✅ <b>Tayyor!</b>"
        )

    except Exception as e:

        logger.exception(
            "Download error"
        )

        error = str(e)

        if (
            "page needs to be reloaded"
            in error.lower()
        ):

            msg = (
                "❌ <b>YouTube player xatosi.</b>\n\n"
                "YouTube ushbu server so‘rovini "
                "qabul qilmadi."
            )

        elif (
            "sign in to confirm"
            in error.lower()
            or
            "not a bot"
            in error.lower()
        ):

            msg = (
                "❌ <b>YouTube autentifikatsiya "
                "xatosi.</b>\n\n"
                "🍪 Cookie yangilash talab "
                "qilinishi mumkin."
            )

        elif (
            "timeout"
            in error.lower()
        ):

            msg = (
                "❌ <b>Telegram upload timeout.</b>\n\n"
                "👇 Pastroq sifatni tanlang."
            )

        else:

            msg = (
                "❌ <b>Xatolik:</b>\n\n"
                f"<code>{error[-500:]}</code>"
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
            "BOT_TOKEN Railway Variables ichida yo‘q."
        )

    session = AiohttpSession(
        timeout=900
    )

    bot = Bot(

        BOT_TOKEN,

        session=session,

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

    asyncio.run(
        main()
    )
