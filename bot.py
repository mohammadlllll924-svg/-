import os
import logging
import aiohttp
import asyncio
from urllib.parse import quote_plus, unquote_plus
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

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
RESULTS_PER_PAGE = 5

# ---------- مساعدة في استدعاء Google Custom Search ----------
async def google_search(query: str, count: int = RESULTS_PER_PAGE, start: int = 1):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        raise RuntimeError("GOOGLE_API_KEY or GOOGLE_CX is not set")

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": str(count),
        "start": str(start),
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_ENDPOINT, params=params, timeout=15) as resp:
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
    total_results = int(data.get("searchInformation", {}).get("totalResults", 0))
    return results, total_results

# ---------- أمر البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! هذا بوت بحث شبيه بجوجل. استخدم /search <سؤال> لإجراء بحث ويب عبر Google Custom Search. مثال: /search ما هي أحدث أخبار التقنية؟"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر المتاحة:\n/search <query> - البحث عبر Google Custom Search وإرجاع النتائج العلوية.\n/start - رسالة ترحيبية.\n
ملاحظة: يمكنك التنقل بين الصفحات عبر أزرار التالي/السابق التي تظهر بعد البحث."
    )

async def do_search_and_edit(msg, query: str, start_idx: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        results, total = await google_search(query, count=RESULTS_PER_PAGE, start=start_idx)
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("حدث خطأ أثناء البحث. تأكد من ضبط GOOGLE_API_KEY و GOOGLE_CX وصلاحية الشبكة.")
        return

    if not results:
        await msg.edit_text("لم تُرجع نتائج.")
        return

    page_num = (start_idx - 1) // RESULTS_PER_PAGE + 1
    text = f"نتائج البحث عن: <b>{query}</b> — صفحة {page_num}\n\n"
    buttons = []
    for i, r in enumerate(results, start=1 + start_idx - 1):
        name = r.get("name") or r.get("url")
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        text += f"{i}. {name}\n{snippet}\n\n"
        if url:
            buttons.append([InlineKeyboardButton(str(i), url=url)])

    # أزرار التنقل
    nav_buttons = []
    if start_idx > 1:
        prev_start = max(1, start_idx - RESULTS_PER_PAGE)
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"page:{prev_start}:{quote_plus(query)}"))
    if start_idx + RESULTS_PER_PAGE <= total:
        next_start = start_idx + RESULTS_PER_PAGE
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"page:{next_start}:{quote_plus(query)}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # استخراج الاستعلام وبدء الصفحات (start)
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
    await do_search_and_edit(msg, query, start_idx=1, context=context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_obj = update.callback_query
    await query_obj.answer()
    data = query_obj.data
    if not data:
        return
    if data.startswith("page:"):
        try:
            _, start_str, enc_q = data.split(":", 2)
            start_idx = int(start_str)
            query_text = unquote_plus(enc_q)
        except Exception as e:
            logger.exception(e)
            await query_obj.edit_message_text("حدث خطأ بمعالجة الطلب.")
            return
        await do_search_and_edit(query_obj.message, query_text, start_idx=start_idx, context=context)

# ---------- تشغيل البوت ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Google-like Search bot (with pagination) starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
