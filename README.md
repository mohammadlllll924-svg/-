# لعبة بديلة لـ "جوكر" على تيليجرام

نسخة MVP بلغة Python باستخدام python-telegram-bot.

ميزات هذه النسخة:
- لعبة جماعية داخل مجموعات: اللاعبون ينضمون عبر /join ثم المضيف يبدأ اللعبة بـ /startgame
- عرض سؤال واحد في كل جولة، مع مهلة زمنية
- تسجيل النقاط في SQLite
- جوكر 50/50 مفعّل (يخفي خيارين عشوائيًا)
- أوامر: /start, /help, /join, /leave, /startgame, /next, /leaderboard

تشغيل محلي:
1) أنشئ بوتًا عبر @BotFather واحصل على التوكن.
2) اضبط متغير البيئة TELEGRAM_TOKEN بالتوكن (لا تضعه في الكود).
3) ثبت المتطلبات: python3 -m pip install -r requirements.txt
4) شغّل البوت: python bot.py

نشر (مثال بسيط على Railway/Heroku): استخدم المتغير TELEGRAM_TOKEN في الإعدادات وادفع الكود.

ملاحظات أمان:
- لا ترفع التوكن إلى المستودع.
- إن تسرب التوكن، قم بتدويره عبر BotFather فورًا.


8877984683:AAEhTgXDJkXcaIbL8FGWjQqPwEn5RguE8Rg
