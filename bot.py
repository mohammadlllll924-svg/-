import os
import logging
import aiohttp
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NONE = None

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BING_API_KEY = os.environ.get("BING_API_KEY")

if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على متغير البيئة TELEGRAM_TOKEN. عيّن TELEGRAM_TOKEN ثم أعد التشغيل.")
    raise SystemExit(1)

if not BING_API_KEY:
    logger.warning("لم يتم العثور على متغير البيئة BING_API_KEY. أوامر البحث ستفشل حتى تضيف المفتاح.")

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

# ---------- مساعدة في استدعاء Bing ----------
async def bing_search(query: str, count: int = 5):
    if not BING_API_KEY:
        raise RuntimeError("BING_API_KEY is not set")
    headers = {
        "Ocp-Apim-Subscription-Key": BING_API_KEY,
        "User-Agent": "TelegramSearchBot/1.0",
    }
    params = {"q": query, "count": str(count), "textDecorations": "true", "textFormat": "HTML"}
    async with aiohttp.ClientSession() as session:
        async with session.get(BING_ENDPOINT, headers=headers, params=params, timeout=10) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("Bing API error %s: %s", resp.status, text)
                raise RuntimeError(f"Bing API returned {resp.status}")
            data = await resp.json()
    # نتوقع webPages.value
    results = []
    web = data.get("webPages", {}).get("value", [])
    for item in web:
        results.append({
            "name": item.get("name"),
            "snippet": item.get("snippet"),
            "url": item.get("url"),
        })
    return results

# ---------- أمر البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! هذا بوت بحث بسيط. استخدم /search <سؤال> لإجراء بحث ويب. مثال: /search ما هي أحدث أخبار التقنية؟"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر المتاحة:\n/search <query> - البحث على الويب وإرجاع النتائج العلوية.\n/start - رسالة ترحيبية."
    )

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        query = " ".join(context.args).strip()
    else:
        # حاول أخذ النص بعد الأمر إن لم توجد args
        txt = update.message.text or ""
        parts = txt.split(" ", 1)
        query = parts[1].strip() if len(parts) > 1 else ""

    if not query:
        await update.message.reply_text("الرجاء وضع نص البحث بعد الأمر. مثال: /search كرة القدم")
        return

    msg = await update.message.reply_text(f"جارٍ البحث عن: {query} ...")

    try:
        results = await bing_search(query, count=5)
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("حدث خطأ أثناء البحث. تأكد من ضبط BING_API_KEY وصلاحية الشبكة.")
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
        # لكل نتيجة زر يفتح الرابط
        if url:
            buttons.append([InlineKeyboardButton(str(i), url=url)])

    # زر لفتح جميع النتائج في نافذة (غير ممكن في تليجرام مباشرة)، لذا نقدم أزرار فردية
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    await msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)

# ---------- تشغيل البوت ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("search", search_cmd))

    logger.info("Search bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
