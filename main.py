# MediaYuklaBot v3
# YouTube + Instagram downloader
# YouTube search + MP3 + Railway YOUTUBE_COOKIES support

import asyncio
import os
import re
import logging
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
# SOZLAMALAR
# =========================================================

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_MB = int(os.getenv("MAX_FILE_MB", "49"))

# Railway Variables ichidagi YOUTUBE_COOKIES
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES", "")

# Railway/Linux uchun vaqtinchalik cookie fayl
COOKIE_FILE = Path("/tmp/youtube_cookies.txt")

if YOUTUBE_COOKIES:
    try:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Ba'zan variable ichida \n matn ko'rinishida kelishi mumkin
        cookie_text = YOUTUBE_COOKIES.replace("\\n", "\n")

        COOKIE_FILE.write_text(
            cookie_text,
            encoding="utf-8"
        )

        print("✅ YouTube cookies yuklandi.")

    except Exception as e:
        print(f"⚠️ Cookie fayl yaratilmadi: {e}")
else:
    print("⚠️ YOUTUBE_COOKIES topilmadi.")


# =========================================================
# DOWNLOAD PAPKA
# =========================================================

D = Path("downloads")
D.mkdir(exist_ok=True)


# =========================================================
# BOT
# =========================================================

r = Router()

jobs = {}
busy = set()

URL = re.compile(r"https?://\S+", re.I)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================================================
# COOKIE OPTIONS
# =========================================================

def cookie_options():

    if YOUTUBE_COOKIES and COOKIE_FILE.exists():
        return {
            "cookiefile": str(COOKIE_FILE)
        }

    return {}


# =========================================================
# FORMAT TUGMALARI
# =========================================================

def keyboard(j):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 360p",
                    callback_data=f"d:{j}:360"
                ),
                InlineKeyboardButton(
                    text="📺 480p",
                    callback_data=f"d:{j}:480"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔥 720p",
                    callback_data=f"d:{j}:720"
                ),
                InlineKeyboardButton(
                    text="💎 1080p",
                    callback_data=f"d:{j}:1080"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎵 MP3",
                    callback_data=f"d:{j}:mp3"
                )
            ]
        ]
    )


# =========================================================
# VIDEO MA'LUMOTINI OLISH
# =========================================================

def info(url):

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,

        **cookie_options(),
    }

    with YoutubeDL(options) as y:

        x = y.extract_info(
            url,
            download=False
        )

        title = x.get(
            "title",
            "Video"
        )

        duration = x.get(
            "duration"
        )

        return title, duration


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def search(q):

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,

        **cookie_options(),
    }

    with YoutubeDL(options) as y:

        x = y.extract_info(
            "ytsearch5:" + q,
            download=False
        )

    results = []

    for e in x.get("entries", []):

        if not e:
            continue

        video_id = e.get("id")

        if not video_id:
            continue

        title = e.get(
            "title",
            "Natija"
        )

        url = (
            "https://www.youtube.com/watch?v="
            + video_id
        )

        results.append(
            (title, url)
        )

    return results


# =========================================================
# DOWNLOAD
# =========================================================

def dl(url, folder, mode):

    # -------------------------
    # MP3
    # -------------------------

    if mode == "mp3":

        options = {

            "outtmpl": str(
                folder / "audio.%(ext)s"
            ),

            "format": "bestaudio/best",

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],

            **cookie_options(),
        }

    # -------------------------
    # VIDEO
    # -------------------------

    else:

        options = {

            "outtmpl": str(
                folder / "video.%(ext)s"
            ),

            "format":
                f"bv*[height<={mode}]+ba/"
                f"b[height<={mode}]/best",

            "merge_output_format": "mp4",

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            **cookie_options(),
        }

    with YoutubeDL(options) as y:

        y.extract_info(
            url,
            download=True
        )

    files = [
        p
        for p in folder.iterdir()

        if p.is_file()

        and p.suffix not in (
            ".part",
            ".ytdl"
        )
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda p: p.stat().st_size
    )


# =========================================================
# /START
# =========================================================

@r.message(CommandStart())
async def start(m: Message):

    name = m.from_user.first_name or "Do'stim"

    await m.answer(

        f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"

        "🎬 <b>Media Yuklovchi Bot</b>\n\n"

        "🔗 YouTube yoki Instagram havolasini yuboring.\n\n"

        "🔎 Qo‘shiq nomini yozsangiz "
        "YouTube'dan qidiraman.\n\n"

        "📥 Video sifatlari:\n"

        "• 360p\n"
        "• 480p\n"
        "• 720p\n"
        "• 1080p\n\n"

        "🎵 Videoni MP3 qilib ham "
        "yuklab olishingiz mumkin."
    )


# =========================================================
# TEXT / LINK
# =========================================================

@r.message(F.text)
async def text(m: Message):

    t = m.text.strip()

    u = URL.search(t)

    # =====================================================
    # AGAR LINK EMAS BO'LSA -> YOUTUBE SEARCH
    # =====================================================

    if not u:

        s = await m.answer(
            "🔎 <b>Qidirilmoqda...</b>"
        )

        try:

            rs = await asyncio.to_thread(
                search,
                t
            )

            if not rs:

                return await s.edit_text(
                    "❌ Hech narsa topilmadi."
                )

            rows = []

            for n, (title, url) in enumerate(
                rs,
                1
            ):

                j = uuid.uuid4().hex[:10]

                jobs[j] = url

                rows.append(
                    [
                        InlineKeyboardButton(
                            text=f"{n}. {title[:48]}",
                            callback_data=f"p:{j}"
                        )
                    ]
                )

            return await s.edit_text(

                "🎵 <b>Natijani tanlang:</b>",

                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=rows
                )
            )

        except Exception as e:

            logging.exception(
                "YouTube search xatosi"
            )

            return await s.edit_text(

                "❌ <b>Qidirishda xatolik:</b>\n\n"

                f"<code>{str(e)[-500:]}</code>"
            )

    # =====================================================
    # LINK
    # =====================================================

    url = u.group(0).rstrip(
        ").,]}>"
    )

    # Faqat YouTube / Instagram
    if not any(
        x in url.lower()
        for x in (
            "youtube.com",
            "youtu.be",
            "instagram.com"
        )
    ):

        return await m.answer(
            "❌ Hozircha faqat "
            "YouTube va Instagram qo‘llab-quvvatlanadi."
        )

    s = await m.answer(
        "🔎 <b>Video tekshirilmoqda...</b>"
    )

    try:

        title, dur = await asyncio.to_thread(
            info,
            url
        )

        j = uuid.uuid4().hex[:10]

        jobs[j] = url

        # Davomiylik
        duration_text = ""

        if dur:

            minutes = int(dur // 60)

            seconds = int(dur % 60)

            duration_text = (
                f"\n⏱ {minutes}:"
                f"{seconds:02d}"
            )

        await s.edit_text(

            f"🎬 <b>{title[:180]}</b>"
            f"{duration_text}\n\n"

            "📥 <b>Kerakli sifatni tanlang:</b>",

            reply_markup=keyboard(j)
        )

    except Exception as e:

        logging.exception(
            "Video info xatosi"
        )

        error = str(e)

        if (
            "Sign in to confirm" in error
            or "not a bot" in error.lower()
        ):

            msg = (
                "❌ <b>YouTube autentifikatsiya xatosi.</b>\n\n"
                "🍪 Serverdagi YouTube cookie "
                "eskirgan yoki ishlamayapti."
            )

        else:

            msg = (
                "❌ <b>Videoni tekshirib bo‘lmadi.</b>\n\n"
                f"<code>{error[-500:]}</code>"
            )

        await s.edit_text(msg)


# =========================================================
# SEARCH NATIJASINI TANLASH
# =========================================================

@r.callback_query(
    F.data.startswith("p:")
)
async def pick(c: CallbackQuery):

    j = c.data.split(":")[1]

    await c.answer()

    if j not in jobs:

        return await c.message.edit_text(
            "❌ So‘rov eskirgan."
        )

    await c.message.edit_text(

        "🎬 <b>Formatni tanlang:</b>",

        reply_markup=keyboard(j)
    )


# =========================================================
# DOWNLOAD CALLBACK
# =========================================================

@r.callback_query(
    F.data.startswith("d:")
)
async def down(c: CallbackQuery):

    _, j, mode = c.data.split(":")

    url = jobs.get(j)

    uid = c.from_user.id

    # -------------------------
    # URL yo'q
    # -------------------------

    if not url:

        return await c.answer(
            "So‘rov eskirgan.",
            show_alert=True
        )

    # -------------------------
    # User boshqa download qilmoqda
    # -------------------------

    if uid in busy:

        return await c.answer(
            "⏳ Oldingi yuklash tugashini kuting.",
            show_alert=True
        )

    busy.add(uid)

    await c.answer()

    folder = D / f"{uid}_{j}"

    folder.mkdir(
        exist_ok=True
    )

    await c.message.edit_text(

        "⏳ <b>Yuklanmoqda...</b>\n\n"

        "Video katta bo‘lsa biroz kuting."
    )

    try:

        # =================================================
        # YT-DLP DOWNLOAD
        # =================================================

        p = await asyncio.to_thread(
            dl,
            url,
            folder,
            mode
        )

        if not p:

            return await c.message.edit_text(
                "❌ Fayl yaratilmadi.",
                reply_markup=keyboard(j)
            )

        # =================================================
        # FILE SIZE
        # =================================================

        mb = (
            p.stat().st_size
            / 1048576
        )

        # =================================================
        # TELEGRAM LIMIT
        # =================================================

        if mb > MAX_MB:

            return await c.message.edit_text(

                f"⚠️ <b>Fayl juda katta.</b>\n\n"

                f"📦 Hajmi: {mb:.1f} MB\n"
                f"📏 Limit: {MAX_MB} MB\n\n"

                "👇 Pastroq sifatni tanlang.",

                reply_markup=keyboard(j)
            )

        # =================================================
        # UPLOAD
        # =================================================

        await c.message.edit_text(

            "📤 <b>Telegramga yuborilmoqda...</b>\n\n"

            f"📦 {mb:.1f} MB"
        )

        # -------------------------
        # MP3
        # -------------------------

        if mode == "mp3":

            await c.message.answer_audio(

                FSInputFile(p),

                request_timeout=900
            )

        # -------------------------
        # VIDEO
        # -------------------------

        else:

            try:

                await c.message.answer_video(

                    FSInputFile(p),

                    supports_streaming=True,

                    request_timeout=900
                )

            except Exception:

                logging.exception(
                    "Video sifatida yuborilmadi. "
                    "Document sifatida yuborilmoqda."
                )

                await c.message.answer_document(

                    FSInputFile(p),

                    request_timeout=900
                )

        await c.message.edit_text(
            "✅ <b>Tayyor!</b>"
        )

    # =====================================================
    # ERROR
    # =====================================================

    except Exception as e:

        logging.exception(
            "Download xatosi"
        )

        error = str(e)

        # YouTube cookie xatosi
        if (
            "Sign in to confirm" in error
            or "not a bot" in error.lower()
        ):

            msg = (
                "❌ <b>YouTube yuklashni blokladi.</b>\n\n"
                "🍪 YouTube cookie eskirgan yoki "
                "server uni qabul qilmayapti."
            )

        # Telegram timeout
        elif "timeout" in error.lower():

            msg = (
                "❌ <b>Telegram upload timeout.</b>\n\n"
                "👇 Pastroq sifatni tanlab ko‘ring."
            )

        else:

            msg = (
                "❌ <b>Yuklashda xatolik:</b>\n\n"
                f"<code>{error[-500:]}</code>"
            )

        try:

            await c.message.edit_text(

                msg,

                reply_markup=keyboard(j)
            )

        except Exception:

            pass

    # =====================================================
    # CLEANUP
    # =====================================================

    finally:

        busy.discard(uid)

        shutil.rmtree(
            folder,
            ignore_errors=True
        )


# =========================================================
# BOT START
# =========================================================

async def main():

    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN topilmadi. "
            "Railway Variables ichiga BOT_TOKEN kiriting."
        )

    session = AiohttpSession(
        timeout=900
    )

    bot = Bot(
        TOKEN,
        session=session,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    dp.include_router(r)

    print("🤖 MediaYuklaBot ishga tushdi.")

    try:

        await dp.start_polling(bot)

    finally:

        await bot.session.close()


if __name__ == "__main__":

    asyncio.run(main())
