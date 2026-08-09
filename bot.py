import os
import logging
import aiohttp
import asyncio
from urllib.parse import quote_plus, unquote_plus
from uuid import uuid4
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes,
)

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")
ADMIN_ID = os.environ.get("ADMIN_ID")

if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على متغير البيئة TELEGRAM_TOKEN")
    raise SystemExit(1)

if not GOOGLE_API_KEY or not GOOGLE_CX:
    logger.warning("GOOGLE_API_KEY أو GOOGLE_CX غير مضبوطين")

GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
RESULTS_PER_PAGE = 5

# ---------- Google Custom Search ----------
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
            if resp.status != 200:
                logger.error("Google CSE API error %s", resp.status)
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

# ---------- الأوامر ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! هذا بوت بحث شبيه بجوجل.\n\n"
        "استخدم /search <سؤال> للبحث\n\n"
        "مثال: /search ما هي أحدث أخبار التكنولوجيا"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر:\n"
        "/search <query> - البحث\n"
        "/start - البداية\n"
        "/help - المساعدة"
    )

async def do_search_and_edit(msg, query: str, start_idx: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        results, total = await google_search(query, count=RESULTS_PER_PAGE, start=start_idx)
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("حدث خطأ في البحث")
        return

    if not results:
        await msg.edit_text("لم تُرجع نتائج")
        return

    page_num = (start_idx - 1) // RESULTS_PER_PAGE + 1
    text = f"النتائج: <b>{query}</b> - صفحة {page_num}\n\n"
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
    if context.args:
        query = " ".join(context.args).strip()
    else:
        txt = update.message.text or ""
        parts = txt.split(" ", 1)
        query = parts[1].strip() if len(parts) > 1 else ""

    if not query:
        await update.message.reply_text("مثال: /search كرة القدم")
        return

    msg = await update.message.reply_text(f"جارٍ البحث عن: {query}...")
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
            await query_obj.edit_message_text("خطأ في الطلب")
            return
        await do_search_and_edit(query_obj.message, query_text, start_idx=start_idx, context=context)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.inline_query.query or ""
    if not query_text:
        await update.inline_query.answer([], cache_time=1)
        return

    try:
        results, total = await google_search(query_text, count=5, start=1)
    except Exception as e:
        logger.exception(e)
        await update.inline_query.answer([], cache_time=1)
        return

    items = []
    for r in results:
        title = r.get("name") or r.get("url")
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        msg_text = f"{title}\n{snippet}\n{url}"
        input_content = InputTextMessageContent(msg_text, parse_mode="HTML")
        item = InlineQueryResultArticle(
            id=str(uuid4()),
            title=title,
            input_message_content=input_content,
            description=snippet,
            url=url,
        )
        items.append(item)

    await update.inline_query.answer(items, cache_time=300, is_personal=False)

# ---------- تشغيل البوت ----------

async def post_init(app):
    """تشغيل عند بدء البوت"""
    logger.info("=" * 50)
    logger.info("✅ البوت يعمل الآن!")
    logger.info("=" * 50)
    
    # إرسال رسالة للمسؤول
    if ADMIN_ID:
        try:
            await app.bot.send_message(
                chat_id=int(ADMIN_ID),
                text="✅ <b>البوت يعمل الآن!</b>\n\n"
                     "🚀 تم تشغيل البوت بنجاح\n"
                     "استخدم /search للبحث"
            )
            logger.info(f"✅ تم إرسال رسالة للمسؤول {ADMIN_ID}")
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    
    # تعيين دالة التهيئة
    app.post_init = post_init
    
    logger.info("🚀 جاري تشغيل البوت...")
    app.run_polling()

if __name__ == "__main__":
    main()
