import os
import asyncio
import logging
import time
from typing import Dict, Any
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

typing_state: Dict[int, Dict[str, Any]] = {}
default_ttl = 30
default_interval = 4.0
default_action_key = "yaz"
start_time = time.time()

ACTIONS = {
    "yaz": ChatAction.TYPING,
    "foto": ChatAction.UPLOAD_PHOTO,
    "video": ChatAction.RECORD_VIDEO,
    "ses": ChatAction.RECORD_VOICE,
    "belge": ChatAction.UPLOAD_DOCUMENT,
    "sticker": ChatAction.CHOOSE_STICKER,
}

def resolve_action(key: str) -> ChatAction:
    return ACTIONS.get(key, ChatAction.TYPING)

async def typing_loop(chat_id: int, application: Application) -> None:
    while True:
        state = typing_state.get(chat_id)
        if not state:
            break
        continuous = bool(state.get("continuous", False))
        auto_stop_at = float(state.get("auto_stop_at", 0.0))
        interval = float(state.get("interval", default_interval))
        mute_until = float(state.get("mute_until", 0.0))
        if not continuous and time.time() >= auto_stop_at:
            break
        if time.time() < mute_until:
            await asyncio.sleep(1.0)
            continue
        action_key = str(state.get("action", default_action_key))
        action = resolve_action(action_key)
        try:
            await application.bot.send_chat_action(chat_id=chat_id, action=action)
        except Exception:
            pass
        await asyncio.sleep(max(1.0, interval))
    s = typing_state.get(chat_id)
    if s:
        t = s.get("task")
        typing_state.pop(chat_id, None)

def ensure_state(chat_id: int) -> Dict[str, Any]:
    s = typing_state.get(chat_id)
    if not s:
        s = {"continuous": False, "auto_stop_at": 0.0, "interval": default_interval, "ttl": default_ttl, "auto_on_message": True, "action": default_action_key, "mute_until": 0.0}
        typing_state[chat_id] = s
    return s

async def ensure_loop(chat_id: int, application: Application) -> None:
    s = ensure_state(chat_id)
    t = s.get("task")
    if not t or t.done():
        t = asyncio.create_task(typing_loop(chat_id, application))
        s["task"] = t

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    s = ensure_state(chat_id)
    if s.get("auto_on_message", True):
        s["auto_stop_at"] = time.time() + float(s.get("ttl", default_ttl))
        await ensure_loop(chat_id, context.application)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bot aktif. Mesaj geldikçe bu sohbette yazıyor olarak görünecek. Komutlar için /yardim.")

async def yaziyor_ac(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    s["continuous"] = True
    s["auto_stop_at"] = time.time() + float(s.get("ttl", default_ttl))
    await ensure_loop(chat_id, context.application)
    await update.message.reply_text("Bu sohbette sürekli yazıyor modu açıldı.")

async def yaziyor_kapat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    s["continuous"] = False
    s["auto_stop_at"] = time.time()
    await update.message.reply_text("Bu sohbette yazıyor modu kapatıldı.")

async def sure_ayarla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    try:
        val = int(context.args[0]) if context.args else default_ttl
    except Exception:
        val = default_ttl
    s["ttl"] = max(5, val)
    await update.message.reply_text(f"Yazıyor süresi {s['ttl']} saniye olarak ayarlandı.")

async def aralik_ayarla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    try:
        val = float(context.args[0]) if context.args else default_interval
    except Exception:
        val = default_interval
    s["interval"] = max(1.0, val)
    await update.message.reply_text(f"Yazıyor gönderim aralığı {s['interval']} saniye olarak ayarlandı.")

async def tumunu_dur(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    count = 0
    for chat_id, s in list(typing_state.items()):
        t = s.get("task")
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        typing_state.pop(chat_id, None)
        count += 1
    await update.message.reply_text(f"Tüm sohbetlerde yazıyor modu durduruldu. Toplam: {count}")

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not typing_state:
        await update.message.reply_text("Aktif yazıyor döngüsü yok.")
        return
    items = []
    for cid, s in typing_state.items():
        flag = "sürekli" if s.get("continuous") else "mesaj"
        muted = "sessiz" if time.time() < float(s.get("mute_until", 0.0)) else "aktif"
        act = str(s.get("action", default_action_key))
        items.append(f"{cid} ({flag}, {muted}, {act})")
    await update.message.reply_text("Aktif sohbetler: " + ", ".join(items))

async def istatistik(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    total = len(typing_state)
    chat_id = update.effective_chat.id
    s = typing_state.get(chat_id)
    if s:
        mode = "sürekli" if s.get("continuous") else "mesaj"
        ttl = s.get("ttl", default_ttl)
        interval = s.get("interval", default_interval)
        auto = "açık" if s.get("auto_on_message", True) else "kapalı"
        muted = "evet" if time.time() < float(s.get("mute_until", 0.0)) else "hayır"
        act = str(s.get("action", default_action_key))
        await update.message.reply_text(f"Toplam aktif: {total}. Bu sohbet: {mode}, ttl={ttl}s, aralık={interval}s, otomatik={auto}, sessiz={muted}, eylem={act}")
    else:
        await update.message.reply_text(f"Toplam aktif: {total}. Bu sohbette aktif yazıyor yok.")

async def oto_mesaj_ac(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    s["auto_on_message"] = True
    await update.message.reply_text("Bu sohbette mesaj geldikçe yazıyor tetikleme açıldı.")

async def oto_mesaj_kapat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    s["auto_on_message"] = False
    await update.message.reply_text("Bu sohbette mesaj geldikçe yazıyor tetikleme kapatıldı.")

async def eylem_ayarla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    key = (context.args[0].lower() if context.args else default_action_key)
    if key not in ACTIONS:
        key = default_action_key
    s["action"] = key
    await update.message.reply_text(f"Bu sohbette eylem '{key}' olarak ayarlandı.")

async def sessiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    try:
        minutes = int(context.args[0]) if context.args else 10
    except Exception:
        minutes = 10
    s["mute_until"] = time.time() + max(1, minutes) * 60
    await update.message.reply_text(f"Bu sohbet {minutes} dakika sessize alındı.")

async def sessiz_kapat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await ensure_admin(update, context):
        return
    s = ensure_state(chat_id)
    s["mute_until"] = 0.0
    await update.message.reply_text("Bu sohbet sessiz moddan çıkarıldı.")

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "/start – Başlat\n"
        "/yaziyor_ac – Sürekli yazıyor modu\n"
        "/yaziyor_kapat – Yazıyor modunu kapat\n"
        "/sure_ayarla <saniye> – Mesajdan sonra yazıyor süresi\n"
        "/aralik_ayarla <saniye> – Yazıyor aralığı\n"
        "/oto_mesaj_ac – Mesaj tetikleme aç\n"
        "/oto_mesaj_kapat – Mesaj tetikleme kapat\n"
        "/eylem_ayarla <yaz|foto|video|ses|belge|sticker> – Eylem türü\n"
        "/sessiz <dakika> – Bu sohbeti sessize al\n"
        "/sessiz_kapat – Sessiz modunu kapat\n"
        "/durum – Aktif sohbetler\n"
        "/istatistik – Bu sohbet ve genel durum\n"
        "/varsayilan_sure <saniye> – Varsayılan süre\n"
        "/varsayilan_aralik <saniye> – Varsayılan aralık\n"
        "/varsayilan_eylem <yaz|foto|video|ses|belge|sticker> – Varsayılan eylem\n"
        "/tumunu_dur – Tüm sohbetlerde durdur"
    )
    await update.message.reply_text(text)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = int(time.time() - start_time)
    h = u // 3600
    m = (u % 3600) // 60
    s = u % 60
    await update.message.reply_text(f"Çalışma süresi: {h} saat {m} dk {s} sn")

async def log_seviye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    level = (context.args[0].upper() if context.args else "INFO")
    lvl = getattr(logging, level, logging.INFO)
    logging.getLogger().setLevel(lvl)
    await update.message.reply_text(f"Log seviyesi {level} olarak ayarlandı.")

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "8416184601:AAG6gXERn4D1VGpIkZAh1lmehv19aBLP_KU")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN ortam değişkenini ayarlayın.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yaziyor_ac", yaziyor_ac))
    app.add_handler(CommandHandler("yaziyor_kapat", yaziyor_kapat))
    app.add_handler(CommandHandler("sure_ayarla", sure_ayarla))
    app.add_handler(CommandHandler("aralik_ayarla", aralik_ayarla))
    app.add_handler(CommandHandler("oto_mesaj_ac", oto_mesaj_ac))
    app.add_handler(CommandHandler("oto_mesaj_kapat", oto_mesaj_kapat))
    app.add_handler(CommandHandler("eylem_ayarla", eylem_ayarla))
    app.add_handler(CommandHandler("sessiz", sessiz))
    app.add_handler(CommandHandler("sessiz_kapat", sessiz_kapat))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("istatistik", istatistik))
    app.add_handler(CommandHandler("tumunu_dur", tumunu_dur))
    app.add_handler(CommandHandler("varsayilan_sure", varsayilan_sure))
    app.add_handler(CommandHandler("varsayilan_aralik", varsayilan_aralik))
    app.add_handler(CommandHandler("varsayilan_eylem", varsayilan_eylem))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("log_seviye", log_seviye))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()

async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat and chat.type in ("group", "supergroup"):
        try:
            m = await context.bot.get_chat_member(chat.id, user.id)
            if m.status not in ("administrator", "creator"):
                await update.message.reply_text("Bu komut için yönetici yetkisi gerekir.")
                return False
        except Exception:
            await update.message.reply_text("Yönetici doğrulaması yapılamadı.")
            return False
    return True

async def varsayilan_sure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    global default_ttl
    try:
        val = int(context.args[0]) if context.args else default_ttl
    except Exception:
        val = default_ttl
    default_ttl = max(5, val)
    await update.message.reply_text(f"Varsayılan yazıyor süresi {default_ttl} saniye olarak ayarlandı.")

async def varsayilan_aralik(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    global default_interval
    try:
        val = float(context.args[0]) if context.args else default_interval
    except Exception:
        val = default_interval
    default_interval = max(1.0, val)
    await update.message.reply_text(f"Varsayılan yazıyor aralığı {default_interval} saniye olarak ayarlandı.")




