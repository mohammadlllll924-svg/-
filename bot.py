import os
import json
import logging
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta

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

DB_PATH = "db.sqlite3"
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("لم يتم العثور على متغير البيئة TELEGRAM_TOKEN")
    raise SystemExit(1)

# تحميل الأسئلة من ملف JSON
with open("data/questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

# حالات الألعاب المفتوحة في الذاكرة: keyed by chat_id
GAMES = {}

# ========== قاعدة البيانات ==========

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            points INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )
    conn.commit()
    conn.close()


def add_points(chat_id: int, user_id: int, username: str, points: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO scores(chat_id,user_id,username,points) VALUES(?,?,?,?)"
        "ON CONFLICT(chat_id,user_id) DO UPDATE SET points=points+excluded.points",
        (chat_id, user_id, username, points),
    )
    conn.commit()
    conn.close()


def get_leaderboard(chat_id: int, limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT username, points FROM scores WHERE chat_id=? ORDER BY points DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows

# ========== منطق اللعبة ==========

class Game:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.players = {}  # user_id -> username
        self.current_q = None
        self.answers = {}  # user_id -> (answer_index, timestamp)
        self.started = False
        self.question_msg_id = None
        self.deadline = None

    def add_player(self, user_id: int, username: str):
        self.players[user_id] = username

    def remove_player(self, user_id: int):
        if user_id in self.players:
            del self.players[user_id]

    def pick_question(self):
        self.current_q = random.choice(QUESTIONS)
        self.answers = {}
        return self.current_q

    def time_left(self):
        if not self.deadline:
            return None
        return max(0, int((self.deadline - datetime.utcnow()).total_seconds()))

# ========== handlers ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! هذه لعبة بديلة لجواكر. ادعُ أصدقائك إلى مجموعة، ثم استخدم /join للانضمام، و /startgame لبدء اللعبة. اكتب /help للمزيد."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "/join - الانضمام للعبة في هذه المجموعة\n"
        "/leave - الخروج من قائمة اللاعبين\n"
        "/startgame - بدء اللعبة (المستخدم الذي يبدأ يعتبر مضيفًا)\n"
        "/next - تخطي السؤال الحالي (للمضيف)\n"
        "/leaderboard - عرض أفضل 10 لاعبين للمجموعة\n"
    )
    await update.message.reply_text(txt)

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("هذه الخاصية مُصممة للمجموعات. أضف البوت إلى مجموعة واستخدم /join هناك.")
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = GAMES.setdefault(chat_id, Game(chat_id))
    game.add_player(user.id, user.full_name)
    await update.message.reply_text(f"انضممت يا {user.full_name} ✅")

async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = GAMES.get(chat_id)
    if not game or user.id not in game.players:
        await update.message.reply_text("أنت لست من اللاعبين حالياً.")
        return
    game.remove_player(user.id)
    await update.message.reply_text("تمت إزالتك من قائمة اللاعبين.")

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("عذراً، ابدأ اللعبة داخل مجموعة.")
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = GAMES.setdefault(chat_id, Game(chat_id))
    if len(game.players) < 1:
        await update.message.reply_text("لا يوجد لاعبين. اجعل اللاعبين يكتبون /join للانضمام.")
        return
    game.started = True
    await send_question(update, context, chat_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = GAMES[chat_id]
    q = game.pick_question()

    kb = []
    for i, c in enumerate(q["choices"]):
        kb.append([InlineKeyboardButton(c, callback_data=f"ans:{i}")])
    # إضافة زر جوكر 50/50
    kb.append([
        InlineKeyboardButton("جوكر 50/50", callback_data="joker:5050")
    ])

    reply_markup = InlineKeyboardMarkup(kb)
    msg = await context.bot.send_message(chat_id, q["text"], reply_markup=reply_markup)
    game.question_msg_id = msg.message_id
    game.deadline = datetime.utcnow() + timedelta(seconds=20)

    # انتظر حتى انتهاء المهلة ثم أحسب النقاط
    await asyncio.create_task(question_timer(context, chat_id, msg.message_id))

async def question_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, msg_id: int):
    await asyncio.sleep(20)
    game = GAMES.get(chat_id)
    if not game or not game.current_q:
        return
    # حساب النتائج
    q = game.current_q
    correct_idx = q["answer_index"]
    # نقاط: 10 للنقطة الأساسية + مكافأة للسرعة
    results = []
    for uid, (ans_idx, ts) in game.answers.items():
        username = game.players.get(uid, "لاعب")
        if ans_idx == correct_idx:
            # سرعة: أقل وقت => مزيد نقاط
            # ts هو توقيت الإجابة (timestamp float)
            # نمنح نقاط أساس 10
            add_points(chat_id, uid, username, 10)
            results.append((username, True))
        else:
            results.append((username, False))
    # افتراض: لاعبين لم يجيبوا -> لا نقاط
    # إرسال ملخص
    txt = f"انتهت المهلة! الإجابة الصحيحة: {q['choices'][correct_idx]}\n\n"
    if results:
        for name, ok in results:
            txt += f"{name} — {'✅' if ok else '❌'}\n"
    else:
        txt += "لا أحد أجاب."

    try:
        await context.bot.send_message(chat_id, txt)
    except Exception as e:
        logger.exception(e)
    # نظف السؤال
    game.current_q = None
    game.answers = {}
    game.deadline = None

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat
    await query.answer()
    data = query.data
    game = GAMES.setdefault(chat.id, Game(chat.id))

    # معالجة جوكر
    if data.startswith("joker:"):
        joker = data.split(":", 1)[1]
        if joker == "5050":
            if not game.current_q:
                await query.edit_message_text("لا يوجد سؤال فعال حاول لاحقًا.")
                return
            q = game.current_q
            correct = q["answer_index"]
            choices = list(range(len(q["choices"])))
            choices.remove(correct)
            to_remove = random.sample(choices, k=len(choices)-1) if len(choices)>1 else []
            # نُنشئ أزرار جديدة تحتوي على خيارين: الصحيح وأحد العشوائي
            remaining = [i for i in range(len(q["choices"])) if i not in to_remove]
            kb = [[InlineKeyboardButton(q["choices"][i], callback_data=f"ans:{i}")] for i in remaining]
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
            return

    if data.startswith("ans:"):
        if not game.current_q:
            await query.edit_message_text("لا يوجد سؤال فعال الآن.")
            return
        idx = int(data.split(":", 1)[1])
        # سجّل الإجابة إذا كان اللاعب من المشاركين
        if user.id not in game.players:
            await query.answer(text="أنت لست مشتركًا في هذه اللعبة. اكتب /join للانضمام.")
            return
        # سجّل الإجابة مع الطابع الزمني
        now_ts = datetime.utcnow().timestamp()
        # لا تسمح بإعادة الإجابة
        if user.id in game.answers:
            await query.answer(text="لقد أجبت بالفعل.")
            return
        game.answers[user.id] = (idx, now_ts)
        await query.answer(text="تم تسجيل إجابتك!")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = get_leaderboard(chat_id)
    if not rows:
        await update.message.reply_text("لا يوجد نتائج بعد.")
        return
    txt = "لوحة الصدارة:\n"
    for i, (username, pts) in enumerate(rows, start=1):
        txt += f"{i}. {username} — {pts} نقطة\n"
    await update.message.reply_text(txt)

async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي السؤال الحالي (أمر للمضيف/أو أي شخص يبدأ اللعبة)."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("هذا الأمر للمجموعات فقط.")
        return
    game = GAMES.get(chat.id)
    if not game or not game.current_q:
        await update.message.reply_text("لا يوجد سؤال حاليًا.")
        return
    game.deadline = datetime.utcnow()  # سيؤدي لتقصير المهلة وسينفذ تايمر
    await update.message.reply_text("تم تخطي السؤال.")

# ========== تشغيل البوت ==========

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("next", next_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
