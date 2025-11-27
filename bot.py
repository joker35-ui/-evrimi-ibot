import os
import asyncio
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

typing_tasks: dict[int, asyncio.Task] = {}

async def typing_loop(chat_id: int, application: Application) -> None:
    while True:
        try:
            await application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        await asyncio.sleep(4)

async def ensure_typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass
    task = typing_tasks.get(chat_id)
    if not task or task.done():
        t = asyncio.create_task(typing_loop(chat_id, context.application))
        typing_tasks[chat_id] = t

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_typing(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bot aktif. Bu sohbette mesaj geldikçe ve sürekli yazıyor olarak görünecek. /typing_on ve /typing_off komutlarını kullanabilirsiniz.")

async def typing_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_typing(update, context)
    await update.message.reply_text("Bu sohbette sürekli yazıyor olarak görünme açıldı.")

async def typing_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    task = typing_tasks.get(chat_id)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        typing_tasks.pop(chat_id, None)
        await update.message.reply_text("Bu sohbette yazıyor olarak görünme kapatıldı.")
    else:
        await update.message.reply_text("Bu sohbette aktif bir yazıyor döngüsü yok.")

async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    count = 0
    for chat_id, task in list(typing_tasks.items()):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        typing_tasks.pop(chat_id, None)
        count += 1
    await update.message.reply_text(f"Tüm sohbetlerde yazıyor görünme durduruldu. Toplam: {count}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    active = list(typing_tasks.keys())
    if not active:
        await update.message.reply_text("Aktif yazıyor döngüsü yok.")
    else:
        await update.message.reply_text("Aktif sohbetler: " + ", ".join(map(str, active)))

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_BOT_TOKEN","8416184601:AAG6gXERn4D1VGpIkZAh1lmehv19aBLP_KU")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN ortam değişkenini ayarlayın.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("typing_on", typing_on))
    app.add_handler(CommandHandler("typing_off", typing_off))
    app.add_handler(CommandHandler("stopall", stop_all))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()


