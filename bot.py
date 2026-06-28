import os
import logging
import random
from collections import defaultdict, deque

import anthropic
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------------------------
# تنظیمات و لاگ
# -------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# -------------------------------------------------------------------
# تاریخچه‌ی چالش‌های هر کاربر (فقط در حافظه - با ری‌استارت پاک می‌شه)
# هر کاربر حداکثر ۱۵ تا چالش آخرش رو نگه می‌داریم تا تو پرامپت بفرستیم
# و کلود همون‌ها رو تکرار نکنه.
# -------------------------------------------------------------------
user_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=15))

SYSTEM_PROMPT = """شما یک دستیار هوش مصنوعی به نام «چالش‌ساز» هستید که مخصوص تولید چالش‌های وایرال و خلاقانه برای اینستاگرام طراحی شده‌اید.

### هویت شما:
- یک کانتنت کریتور (تولیدکننده محتوا) حرفه‌ای با ۱۰ سال سابقه هستید.
- پرانرژی، شوخ، صمیمی و انگیزشی هستید.
- از ایموجی‌های زیاد، لحن خودمانی و جملات کوتاه استفاده می‌کنید.
- هدف شما کمک به کاربران برای افزایش فالوور، تعامل و دیده‌شدن در اینستاگرام است.

### وظیفه شما:
با دریافت درخواست کاربر، یک چالش جدید، خلاقانه و وایرال برای اینستاگرام تولید کنید.

### ویژگی‌های چالش‌هایی که می‌سازید:
- ساده و قابل اجرا برای همه (محدودیت سنی یا جنسیتی نداشته باشد)
- خلاقانه و غیرتکراری (کاری که کمتر کسی انجام داده باشد)
- مناسب برای استوری، پست یا ریلز
- دارای یک هشتگ اختصاصی و جذاب
- دارای یک نتیجه یا جایزه‌ی انگیزشی (مثل: «با این کار ۱۰۰ فالوور جدید جذب می‌کنی»)
- ایمن و غیرتوهین‌آمیز باشد

### قوانین پاسخ‌دهی:
- اگر کاربر جمله‌ی خاصی نگفت، یک چالش کاملاً تصادفی و جدید پیشنهاد بده.
- اگر کاربر موضوع خاصی داد (مثلاً «چالش برای پیج ورزشی»)، چالش را مطابق با آن موضوع طراحی کن.
- هرگز چالش تکراری نده. اگر فهرستی از چالش‌های قبلی کاربر در ادامه‌ی این پیام داده شد، حتماً چالش کاملاً جدید و متفاوتی ارائه بده.
- در پایان هر چالش، یک پیشنهاد برای وایرال شدن بیشتر اضافه کن (مثل زمان مناسب انتشار، نوع موسیقی، یا روش ادیت).

### خروجی استاندارد هر پاسخ:
۱. عنوان جذاب برای چالش (مثلاً: 🔥 چالش سه‌ضلعی!)
۲. توضیح کامل چالش (چکار باید کرد؟)
۳. هشتگ اختصاصی پیشنهادی
۴. یک پیشنهاد برای وایرال شدن بیشتر
۵. یک جمله‌ی انگیزشی برای شروع کار

### مثال از یک چالش خوب:
---
**🔥 چالش قاب‌های نادیده!**

۳ تا عکس از زاویه‌ی خیلی عجیب از خودت یا محیط اطرافت بگیر (مثلاً از زیر پا، از بالای کمد، یا از پشت آینه). توی استوری بذار و از فالوورهات بخواه حدس بزنن این زاویه‌ها مربوط به کجاست!

**هشتگ:** #قاب_نادیده

**نکته وایرال:** این چالش رو ساعت ۹ شب بذار که مردم وقت داشته باشن حدس بزنن! با یه موسیقی معمایی ادیتش کن.

**برو ببین چند نفر می‌تونن درست حدس بزنن! 🚀**
---

حالا با توجه به درخواست کاربر، یک چالش جدید و منحصربه‌فرد تولید کن. خروجی را مستقیماً به فارسی و با فرمت Markdown ساده (برای تلگرام: **bold** قابل استفاده است) بده، بدون هیچ توضیح اضافه‌ی خارج از قالب."""

RANDOM_PROMPTS = [
    "یک چالش کاملاً تصادفی و جدید برای اینستاگرام بساز.",
    "یک چالش رندوم و خلاقانه برای صفحه اینستاگرام بساز، موضوعش هرچی دلت خواست.",
    "یک ایده‌ی وایرال تصادفی برای ریلز یا استوری اینستاگرام بده.",
]

# -------------------------------------------------------------------
# دکمه‌ی اینلاین کیبورد
# -------------------------------------------------------------------
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎲 چالش تصادفی", callback_data="random_challenge")]]
    )


def build_user_prompt(user_request: str, history: deque) -> str:
    """پرامپت نهایی کاربر را به همراه تاریخچه‌ی چالش‌های قبلی‌اش می‌سازد."""
    parts = [f"درخواست کاربر: {user_request}"]
    if history:
        past_titles = "\n".join(f"- {h}" for h in history)
        parts.append(
            "چالش‌هایی که قبلاً برای همین کاربر تولید شده‌اند و نباید تکرار شوند:\n"
            f"{past_titles}"
        )
    return "\n\n".join(parts)


def extract_title(challenge_text: str) -> str:
    """برای ذخیره در تاریخچه، خط اول (عنوان) چالش را استخراج می‌کند."""
    for line in challenge_text.splitlines():
        clean = line.strip().strip("*").strip()
        if clean:
            return clean[:80]
    return challenge_text[:80]


async def generate_challenge(user_id: int, user_request: str) -> str:
    history = user_history[user_id]
    user_prompt = build_user_prompt(user_request, history)

    response = claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    challenge_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    history.append(extract_title(challenge_text))
    return challenge_text


# -------------------------------------------------------------------
# هندلرها
# -------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "سلام! 👋 من «چالش‌ساز» هستم 🔥\n\n"
        "می‌تونی برام بنویسی چه نوع چالشی می‌خوای (مثلاً «چالش برای پیج ورزشی»)\n"
        "یا روی دکمه‌ی زیر بزنی تا یه چالش تصادفی برات بسازم 🎲",
        reply_markup=main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "فقط کافیه موضوع چالش مورد نظرت رو بنویسی، یا از دکمه‌ی تصادفی استفاده کنی.\n"
        "هر بار حتماً یه چالش جدید و غیرتکراری برات می‌سازم 🚀",
        reply_markup=main_keyboard(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_request = update.message.text.strip()

    thinking_msg = await update.message.reply_text("در حال ساخت چالش جدیدت هستم... ⏳")
    try:
        challenge = await generate_challenge(user_id, user_request)
    except Exception:
        logger.exception("خطا در تولید چالش")
        await thinking_msg.edit_text("یه مشکل پیش اومد، دوباره امتحان کن 🙏")
        return

    await thinking_msg.edit_text(challenge, reply_markup=main_keyboard())


async def handle_random_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    random_prompt = random.choice(RANDOM_PROMPTS)

    await query.edit_message_text("در حال ساخت چالش تصادفی... 🎲")
    try:
        challenge = await generate_challenge(user_id, random_prompt)
    except Exception:
        logger.exception("خطا در تولید چالش تصادفی")
        await query.edit_message_text("یه مشکل پیش اومد، دوباره امتحان کن 🙏")
        return

    await query.edit_message_text(challenge, reply_markup=main_keyboard())


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_random_button, pattern="^random_challenge$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("ربات با Polling شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
