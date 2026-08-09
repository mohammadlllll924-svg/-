import os
import logging
import aiohttp
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")

if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على متغير البيئة TELEGRAM_TOKEN. عيّن TELEGRAM_TOKEN ثم أعد التشغيل.")
    raise SystemExit(1)

if not GOOGLE_API_KEY or not GOOGLE_CX:
    logger.warning("GOOGLE_API_KEY أو GOOGLE_CX غير مضبوطين. أوامر البحث ستفشل حتى تضيف المفاتيح.")

GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# ---------- مساعدة في استدعاء Google Custom Search ----------
async def google_search(query: str, count: int = 5):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        raise RuntimeError("GOOGLE_API_KEY or GOOGLE_CX is not set")

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": str(count),
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_ENDPOINT, params=params, timeout=10) as resp:
            text = await resp.text()
            if resp.status != 200:
                logger.error("Google CSE API error %s: %s", resp.status, text)
                raise RuntimeError(f"Google CSE returned {resp.status}")
            data = await resp.json()

    results = []
    for item in data.get("items", []):
        results.append({
            "name": item.get("title"),
            "snippet": item.get("snippet"),
            "url": item.get("link"),
        })
    return results

# ---------- أمر البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! هذا بوت بحث شبيه بجوجل. استخدم /search <سؤال> لإجراء بحث ويب عبر Google Custom Search. مثال: /search ما هي أحدث أخبار التقنية؟"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر المتاحة:\n/search <query> - البحث عبر Google Custom Search وإرجاع النتائج العلوية.\n/start - رسالة ترحيبية."
    )

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        query = " ".join(context.args).strip()
    else:
        txt = update.message.text or ""
        parts = txt.split(" ", 1)
        query = parts[1].strip() if len(parts) > 1 else ""

    if not query:
        await update.message.reply_text("الرجاء وضع نص البحث بعد الأمر. مثال: /search كرة القدم")
        return

    msg = await update.message.reply_text(f"جارٍ البحث عن: {query} ...")

    try:
        results = await google_search(query, count=5)
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("حدث خطأ أثناء البحث. تأكد من ضبط GOOGLE_API_KEY و GOOGLE_CX وصلاحية الشبكة.")
        return

    if not results:
        await msg.edit_text("لم تُرجع نتائج.")
        return

    text = f"نتائج البحث عن: <b>{query}</b>\n\n"
    buttons = []
    for i, r in enumerate(results, start=1):
        name = r.get("name") or r.get("url")
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        text += f"{i}. {name}\n{snippet}\n\n"
        if url:
            buttons.append([InlineKeyboardButton(str(i), url=url)])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    await msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)

# ---------- تشغيل البوت ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("search", search_cmd))

    logger.info("Google-like Search bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
