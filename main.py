# MediaYuklaBot v2
# To'liq kodni ishga tushirish uchun shu ZIPdagi README ni o'qing.
import asyncio, os, re, logging, shutil, uuid
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from yt_dlp import YoutubeDL

load_dotenv()
TOKEN=os.getenv("BOT_TOKEN","").strip()
MAX_MB=int(os.getenv("MAX_FILE_MB","49"))
D=Path("downloads"); D.mkdir(exist_ok=True)
r=Router(); jobs={}; busy=set()
URL=re.compile(r"https?://\S+",re.I)
logging.basicConfig(level=logging.INFO)

def keyboard(j):
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="360p",callback_data=f"d:{j}:360"),InlineKeyboardButton(text="480p",callback_data=f"d:{j}:480"),InlineKeyboardButton(text="720p",callback_data=f"d:{j}:720")],
      [InlineKeyboardButton(text="1080p",callback_data=f"d:{j}:1080"),InlineKeyboardButton(text="🎵 MP3",callback_data=f"d:{j}:mp3")]
    ])

def info(url):
    with YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True,"noplaylist":True}) as y:
        x=y.extract_info(url,download=False); return x.get("title","Video"),x.get("duration")

def search(q):
    with YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True,"extract_flat":True}) as y:
        x=y.extract_info("ytsearch5:"+q,download=False)
    return [(e.get("title","Natija"),"https://www.youtube.com/watch?v="+e["id"]) for e in x.get("entries",[]) if e and e.get("id")]

def dl(url,folder,mode):
    if mode=="mp3":
        o={"outtmpl":str(folder/"audio.%(ext)s"),"format":"bestaudio/best","quiet":True,"no_warnings":True,"noplaylist":True,
           "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]}
    else:
        o={"outtmpl":str(folder/"video.%(ext)s"),"format":f"bv*[height<={mode}]+ba/b[height<={mode}]/best",
           "merge_output_format":"mp4","quiet":True,"no_warnings":True,"noplaylist":True}
    with YoutubeDL(o) as y:y.extract_info(url,download=True)
    fs=[p for p in folder.iterdir() if p.is_file() and p.suffix not in (".part",".ytdl")]
    return max(fs,key=lambda p:p.stat().st_size) if fs else None

@r.message(CommandStart())
async def start(m:Message):
    await m.answer("👋 <b>Media Yuklovchi Bot v2</b>\n\n🔗 YouTube/Instagram link yuboring.\n🔎 Qo‘shiq nomini yozsangiz YouTube'dan qidiradi.\n🎬 Sifat: 360/480/720/1080 yoki MP3.")

@r.message(F.text)
async def text(m:Message):
    t=m.text.strip(); u=URL.search(t)
    if not u:
        s=await m.answer("🔎 Qidirilmoqda...")
        try:
            rs=await asyncio.to_thread(search,t); rows=[]
            for n,(title,url) in enumerate(rs,1):
                j=uuid.uuid4().hex[:10]; jobs[j]=url
                rows.append([InlineKeyboardButton(text=f"{n}. {title[:48]}",callback_data=f"p:{j}")])
            return await s.edit_text("🎵 Natijani tanlang:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception as e:return await s.edit_text(f"❌ <code>{str(e)[-350:]}</code>")
    url=u.group(0).rstrip(").,]}>")
    if not any(x in url.lower() for x in ("youtube.com","youtu.be","instagram.com")):return await m.answer("❌ Faqat YouTube/Instagram.")
    s=await m.answer("🔎 Tekshirilmoqda...")
    try:
        title,dur=await asyncio.to_thread(info,url); j=uuid.uuid4().hex[:10]; jobs[j]=url
        await s.edit_text(f"🎬 <b>{title[:180]}</b>\n\nSifatni tanlang:",reply_markup=keyboard(j))
    except Exception as e:await s.edit_text(f"❌ <code>{str(e)[-350:]}</code>")

@r.callback_query(F.data.startswith("p:"))
async def pick(c:CallbackQuery):
    j=c.data.split(":")[1]; await c.answer()
    await c.message.edit_text("Formatni tanlang:",reply_markup=keyboard(j))

@r.callback_query(F.data.startswith("d:"))
async def down(c:CallbackQuery):
    _,j,mode=c.data.split(":"); url=jobs.get(j); uid=c.from_user.id
    if not url:return await c.answer("So‘rov eskirgan",show_alert=True)
    if uid in busy:return await c.answer("Oldingi yuklash tugasin",show_alert=True)
    busy.add(uid); await c.answer(); folder=D/f"{uid}_{j}";folder.mkdir(exist_ok=True)
    await c.message.edit_text("⏳ Yuklanmoqda...")
    try:
        p=await asyncio.to_thread(dl,url,folder,mode)
        if not p:return await c.message.edit_text("❌ Fayl yaratilmadi.")
        mb=p.stat().st_size/1048576
        if mb>MAX_MB:return await c.message.edit_text(f"⚠️ Fayl {mb:.1f} MB. Pastroq sifat tanlang.",reply_markup=keyboard(j))
        await c.message.edit_text(f"📤 Telegramga yuborilmoqda... {mb:.1f} MB")
        if mode=="mp3":await c.message.answer_audio(FSInputFile(p),request_timeout=900)
        else:
            try:await c.message.answer_video(FSInputFile(p),supports_streaming=True,request_timeout=900)
            except Exception:await c.message.answer_document(FSInputFile(p),request_timeout=900)
        await c.message.edit_text("✅ Tayyor!")
    except Exception as e:
        msg="❌ Telegram upload timeout. Pastroq sifatni tanlang." if "timeout" in str(e).lower() else f"❌ <code>{str(e)[-350:]}</code>"
        await c.message.edit_text(msg,reply_markup=keyboard(j))
    finally:
        busy.discard(uid);shutil.rmtree(folder,ignore_errors=True)

async def main():
    if not TOKEN:raise RuntimeError("BOT_TOKEN .env da yo‘q")
    bot=Bot(TOKEN,session=AiohttpSession(timeout=900),default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher();dp.include_router(r);await dp.start_polling(bot)
if __name__=="__main__":asyncio.run(main())
