import asyncio
import json
import html
import logging
import os
import random
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat
from telegram.error import TelegramError, BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# IMPORT DARI cek_wait.py — TIDAK DIUBAH
from cek_wait import detect, fmt, ARTI_REASON, CekBapaklu, versi_mark

import config
import rich_ui

# ==================== LOGGING ====================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger("bot")

BASE_DIR = Path(__file__).parent

# Nama bot (ZHEE) — dipakai di semua tampilan.
BOT_DISPLAY = getattr(config, "BOT_NAME", "ZHEE")
NAMA_ASCII = " ".join(list(BOT_DISPLAY.upper())) + "   C H E C K E R"

STATS_PATH = BASE_DIR / config.STATS_FILE
PREMIUM_PATH = BASE_DIR / config.PREMIUM_FILE
BANNED_PATH = BASE_DIR / config.BANNED_FILE
SPEED_PATH = BASE_DIR / getattr(config, "SPEED_FILE", "speed.json")
FJ_PATH = BASE_DIR / getattr(config, "FORCE_JOIN_FILE", "force_join.json")

_cooldown_tracker = {}


# ==================== DATABASE / BACA-TULIS JSON ====================
# Diletakkan di bagian paling atas agar bisa dipakai oleh fungsi lain
# (misalnya load_speed) saat modul pertama kali dimuat.

METODE_TERSUMBUH = ["wa_old"]  # method yang didukung cek_wait.py saat ini


def _load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error("Gagal simpan %s: %s", path, e)


# ==================== SETELAN BOT (SETTINGAN OWNER) ====================
# Disimpan di bot_settings.json dan dibaca ulang setiap perintah ->
# perubahan lewat perintah owner langsung berlaku tanpa restart bot.

SETTINGS_PATH = BASE_DIR / getattr(config, "SETTINGS_FILE", "bot_settings.json")

SETTINGS_DEFAULT = {
    # Ulangi otomatis nomor yang gagal/error di dalam satu sesi detek
    "retry_gagal": True,
    "retry_maksimal": 2,
    # Mode koneksi ke API WhatsApp:
    #   "langsung" -> IP server langsung (cepat, tapi beberapa negara seperti
    #                 Nepal/Sri Lanka sering diblokir dari IP datacenter)
    #   "proxy"    -> pakai pool proxy gratis (butuh env WA_USE_PROXY=1 di
    #                 container; jauh lebih andal untuk nomor luar negeri)
    "mode_proxy": "langsung",
    # Tampilkan tombol [🔄 ULANGI GAGAL] di hasil deteksi user
    "tombol_ulang": True,
}


def load_settings() -> dict:
    s = dict(SETTINGS_DEFAULT)
    data = _load_json(SETTINGS_PATH, {})
    for k in SETTINGS_DEFAULT:
        if k in data:
            s[k] = data[k]
    try:
        s["retry_gagal"] = bool(s["retry_gagal"])
    except Exception:
        s["retry_gagal"] = True
    try:
        s["retry_maksimal"] = min(5, max(0, int(s["retry_maksimal"])))
    except (TypeError, ValueError):
        s["retry_maksimal"] = SETTINGS_DEFAULT["retry_maksimal"]
    if str(s["mode_proxy"]).lower() not in ("langsung", "proxy"):
        s["mode_proxy"] = "langsung"
    try:
        s["tombol_ulang"] = bool(s["tombol_ulang"])
    except Exception:
        s["tombol_ulang"] = True
    return s


def save_settings(patch: dict) -> dict:
    s = load_settings()
    s.update(patch or {})
    _save_json(SETTINGS_PATH, s)
    return s


# ==================== KECEPATAN CEK (SETTINGAN OWNER) ====================

def load_speed() -> dict:
    """Baca settingan kecepatan; fallback ke SPEED_DEFAULT di config.py."""
    default = dict(getattr(config, "SPEED_DEFAULT", {}) or
                   {"bulk_delay": 3.0, "max_paralel": 3})
    data = _load_json(SPEED_PATH, default)
    speed = dict(default)
    speed.update({k: v for k, v in data.items() if k in ("bulk_delay", "max_paralel")})
    try:
        speed["bulk_delay"] = max(0.0, float(speed["bulk_delay"]))
    except (TypeError, ValueError):
        speed["bulk_delay"] = 3.0
    try:
        speed["max_paralel"] = min(10, max(1, int(speed["max_paralel"])))
    except (TypeError, ValueError):
        speed["max_paralel"] = 3
    return speed


# ==================== FORCE JOIN (SETTINGAN OWNER) ====================

def load_force_join() -> dict:
    """Baca settingan force join; fallback ke config.py kalau file belum ada."""
    default_links = [str(c).strip() for c in getattr(config, "FORCE_JOIN", []) or []
                     if str(c).strip()]
    data = _load_json(FJ_PATH, {
        "enabled": bool(getattr(config, "FORCE_JOIN_ENABLED", True)),
        "chats": default_links,
    })
    enabled = bool(data.get("enabled",
                            getattr(config, "FORCE_JOIN_ENABLED", True)))
    chats = data.get("chats")
    if not isinstance(chats, list):
        chats = default_links
    chats = [str(c).strip() for c in chats if str(c).strip()]
    return {"enabled": enabled, "chats": chats}


def save_force_join(enabled: bool, chats: list):
    _save_json(FJ_PATH, {
        "enabled": bool(enabled),
        "chats": [str(c).strip() for c in chats if str(c).strip()],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


def force_join_aktif() -> list:
    """Daftar chat force join bila fiturnya aktif; [] bila tidak."""
    fj = load_force_join()
    return fj["chats"] if fj["enabled"] else []


def save_speed(speed: dict):
    _save_json(SPEED_PATH, {
        "bulk_delay": speed["bulk_delay"],
        "max_paralel": speed["max_paralel"],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


# Semaphore paralel — kapasitas mengikuti settingan kecepatan owner.
_detect_semaphore = asyncio.Semaphore(load_speed()["max_paralel"])
_sem_capacity = _detect_semaphore._value


def sinkronkan_semaphore():
    """Sesuaikan kapasitas semaphore dengan max_paralel terbaru.

    Perubahan dilakukan pada slot kosong (_value) sehingga pengecekan
    yang sedang berjalan tidak terganggu.
    """
    global _sem_capacity
    target = load_speed()["max_paralel"]
    if target == _sem_capacity:
        return
    terpakai = _sem_capacity - _detect_semaphore._value
    _detect_semaphore._value = max(0, target - terpakai)
    _sem_capacity = target


def _set_mode_proxy(langsung: bool):
    """Pasang mode koneksi ke API WhatsApp sesuai setelan owner.

    "langsung" -> matikan semua env proxy (cek IP server apa adanya).
    "proxy"    -> aktifkan WA_USE_PROXY supaya pakai pool proxy gratis;
                  kalau env belum ada di container, set otomatis di sini.
    """
    if langsung:
        for var in ("WA_USE_PROXY", "WA_PROXY", "WA_ampas"):
            os.environ.pop(var, None)
    else:
        if not any(os.environ.get(v) for v in ("WA_USE_PROXY", "WA_PROXY", "WA_ampas")):
            os.environ["WA_USE_PROXY"] = "1"


# ==================== HELPER KIRIM PESAN ====================

# Konversi emoji menjadi Telegram Premium Custom Emoji (OPSIONAL).
# MATI secara default (config.TG_EMOJI_CUSTOM = False) karena ID custom emoji
# hasil extractor dari pack orang lain tidak dikenal server Telegram untuk
# akun bot -> client menampilkan tag MENTAH <tg-emoji emoji-id="...">⚠️</...>.
# Dengan mode mati, semua pesan memakai emoji Unicode standar yang selalu
# tampil normal di semua device.
# Tombol inline dan callback alert memang selalu Unicode (Bot API tak
# mendukung entity di sana).
_EMOJI_CUSTOM_ON = bool(getattr(config, "TG_EMOJI_CUSTOM", False))
_EMOJI_MAP = (getattr(config, "TG_EMOJI_MAP", {}) or {}) if _EMOJI_CUSTOM_ON else {}
_EMOJI_PATTERN = re.compile("|".join(re.escape(e) for e in sorted(_EMOJI_MAP, key=len, reverse=True))) if _EMOJI_MAP else None

# Pola tag <tg-emoji> yang mungkin tertinggal di teks (misal dari data lama).
_TG_EMOJI_TAG_RE = re.compile(r'<tg-emoji\b[^>]*>(.*?)</tg-emoji>', re.S | re.I)


# Hanya ID yang terbukti valid dipakai (lihat catatan TG_EMOJI_MAP di config.py).
# ID lain membuat Telegram menampilkan tag mentah <tg-emoji emoji-id="...">
# seperti pada kasus ⚠️ — jadi disaring di sini.
_TG_EMOJI_VALID_IDS = {
    "5123163417326126159",   # ✅ Success
    "5121063440311386962",   # ❌ Cancel
    "5447644880824181073",   # ⚠️ Warning
    "5875450995332353523",   # 🚫 Slash
    "5116159438062879454",   # ⏳ Loading
    "5350595795508814391",   # ⏱ Clock
    "5127377673596700174",   # 🔄 Refresh
    "5890925363067886150",   # ✨ Sparkle
    "5350613306090482956",   # 📊 Graph
    "5776233299424843260",   # 🌐 Globe
    "5226513232549664618",   # 🔷 Option
    "5350725709679584478",   # ⚙️ Gear
    "6028530359975548369",   # 💎 Diamond
    "5258337316715373336",   # 🛟 Call
    "5260399854500191689",   # 👤 User
    "5944970130554359187",   # 👥 People
    "5258503720928288433",   # ℹ️ Info
    "5258476306152038031",   # 🔒 Lock
    "5260268501515377807",   # 📣 Broadcast
    "5260512129240276089",   # 📚 Books
}


def _customize_emojis(text: str):
    if not isinstance(text, str):
        return text, False

    # Jaring pengaman SELALU jalan: buang tag <tg-emoji ...> ... </tg-emoji>
    # yang tertinggal di teks (misal dari data/config lama) dan ganti dengan
    # emoji Unicode polos tanpa kode tambahan apa pun, sehingga tidak pernah
    # tampil mentah di chat.
    def _buang_tag(m):
        isi = m.group(1) or ""
        # Tag nested (seharusnya tak ada) -> bersihkan juga.
        isi = _TG_EMOJI_TAG_RE.sub(_buang_tag, isi)
        # Kalau isinya masih mengandung markup/tag lain, ambil teks polosnya.
        isi = re.sub(r"<[^>]*>", "", isi)
        return isi.strip() or " "

    if "<tg-emoji" in text.lower():
        text = _TG_EMOJI_TAG_RE.sub(_buang_tag, text)
    # Tag pembuka/closing <tg-emoji> yatim (tidak seimbang) -> buang tag-nya.
    text = re.sub(r"</?tg-emoji\b[^>]*>", "", text, flags=re.I)

    if not _EMOJI_PATTERN:
        return text, False

    # Jaring pengaman: buang tag <tg-emoji> dengan ID tak dikenal yang sudah
    # terlanjur ada di teks (misal dari rich_html) agar tak tampil mentah.
    def buang_id_asing(match):
        if match.group(1) in _TG_EMOJI_VALID_IDS:
            return match.group(0)
        return match.group(2)

    text = re.sub(r'<tg-emoji\b[^>]*emoji-id="(\d+)"[^>]*>(.*?)</tg-emoji>',
                  buang_id_asing, text, flags=re.S | re.I)

    # Jangan mengubah emoji di tag custom yang sudah ada atau di blok pre/code.
    protected = []
    def protect(match):
        protected.append(match.group(0))
        return f"VANTAPROTECTEDBLOCK{len(protected)-1}END"

    text = re.sub(r"<(pre|code)\b[^>]*>.*?</\1\s*>", protect, text, flags=re.S | re.I)

    changed = False
    def replace(match):
        nonlocal changed
        emoji = match.group(0)
        emoji_id = str(_EMOJI_MAP.get(emoji, "")).strip()
        if emoji_id in _TG_EMOJI_VALID_IDS:
            changed = True
            return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
        return emoji

    # Proses teks di antara tag HTML saja agar nama tag/atribut tidak tersentuh.
    parts = re.split(r"(<[^>]+>)", text)
    for i, part in enumerate(parts):
        if part.startswith("<") and part.endswith(">"):
            continue
        parts[i] = _EMOJI_PATTERN.sub(replace, part)
    text = "".join(parts)
    for i, block in enumerate(protected):
        text = text.replace(f"VANTAPROTECTEDBLOCK{i}END", block)
    return text, changed


def _strip_custom_emoji(text):
    """Buang tag <tg-emoji> tapi pertahankan emoji Unicode-nya (jaring pengaman)."""
    if not isinstance(text, str):
        return text
    out = _TG_EMOJI_TAG_RE.sub(r"\1", text)
    out = re.sub(r"</?tg-emoji\b[^>]*>", "", out, flags=re.I)
    return out


def _entity_error(e):
    return "entit" in str(e).lower()

async def balas(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    text, changed = _customize_emojis(text)
    if changed:
        kwargs["parse_mode"] = "HTML"
    async def _kirim(t):
        if update.effective_message:
            return await update.effective_message.reply_text(t, **kwargs)
        elif update.effective_chat:
            return await context.bot.send_message(chat_id=update.effective_chat.id, text=t, **kwargs)
        return None

    try:
        return await _kirim(text)
    except BadRequest as e:
        if not _entity_error(e):
            raise
        logger.warning("Entity ditolak, kirim ulang tanpa custom emoji: %s", e)
        return await _kirim(_strip_custom_emoji(text))


async def balas_foto(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     photo: str, caption: str = None, **kwargs):
    caption, changed = _customize_emojis(caption)
    if changed:
        kwargs["parse_mode"] = "HTML"
    async def _kirim(cap):
        if update.effective_message:
            return await update.effective_message.reply_photo(photo=photo, caption=cap, **kwargs)
        elif update.effective_chat:
            return await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo,
                                                caption=cap, **kwargs)
        return None

    try:
        return await _kirim(caption)
    except BadRequest as e:
        if not _entity_error(e):
            raise
        logger.warning("Entity caption ditolak, kirim ulang tanpa custom emoji: %s", e)
        return await _kirim(_strip_custom_emoji(caption))


async def aman_answer(query, text: str = None, show_alert: bool = False):
    try:
        if text:
            await query.answer(text, show_alert=show_alert)
        else:
            await query.answer()
    except TelegramError as e:
        logger.warning("Gagal answer query: %s", e)


async def kirim_atau_edit(query, teks, keyboard, keyboard_rich=None):
    # Menu HTML mendukung Telegram Premium Custom Emoji (<tg-emoji>).
    isi, _ = _customize_emojis(teks)
    try:
        if query.message.caption is not None:
            # Caption foto: Rich Message tak didukung -> fallback HTML.
            await query.edit_message_caption(
                caption=rich_ui.rich_ke_html(isi), parse_mode="HTML",
                reply_markup=keyboard)
        else:
            # Coba Rich Message dulu, fallback ke HTML standar.
            if keyboard_rich and rich_ui.ada_tag_rich(isi):
                ok = await rich_ui.edit_rich(
                    config.BOT_TOKEN, query.message.chat.id,
                    query.message.message_id, isi, keyboard_rich)
                if ok:
                    return
            await query.edit_message_text(
                text=rich_ui.rich_ke_html(isi), parse_mode="HTML",
                reply_markup=keyboard)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        if _entity_error(e):
            logger.warning("Entity ditolak saat edit, ulangi tanpa custom emoji: %s", e)
            try:
                polos = _strip_custom_emoji(rich_ui.rich_ke_html(isi))
                if query.message.caption is not None:
                    await query.edit_message_caption(
                        caption=polos, parse_mode="HTML", reply_markup=keyboard)
                else:
                    await query.edit_message_text(
                        text=polos, parse_mode="HTML", reply_markup=keyboard)
            except TelegramError as e2:
                logger.warning("Gagal edit (retry): %s", e2)
            return
        logger.warning("Gagal edit: %s", e)
    except TelegramError as e:
        logger.warning("Gagal edit: %s", e)


# ==================== DATABASE ====================

def load_stats() -> dict:
    return _load_json(STATS_PATH, {"users": {}, "global": {"total_users": 0, "total_detections": 0}})


def save_stats(data: dict):
    _save_json(STATS_PATH, data)


def load_premium() -> dict:
    return _load_json(PREMIUM_PATH, {"users": {}})


def save_premium(data: dict):
    _save_json(PREMIUM_PATH, data)


def load_banned() -> dict:
    return _load_json(BANNED_PATH, {"users": {}})


def save_banned(data: dict):
    _save_json(BANNED_PATH, data)


def is_premium(user_id: int) -> bool:
    if config.OWNER_ID is not None:
        try:
            if user_id == int(config.OWNER_ID):
                return True
        except (TypeError, ValueError):
            pass
    data = load_premium()
    return str(user_id) in data.get("users", {})


def is_banned(user_id: int) -> dict | None:
    data = load_banned()
    return data.get("users", {}).get(str(user_id))


def is_owner(user_id: int) -> bool:
    if config.OWNER_ID is None:
        return False
    try:
        return user_id == int(config.OWNER_ID)
    except (TypeError, ValueError):
        return False


# ==================== USER TIER ====================

def cek_tier(user_id: int) -> str:
    return "premium" if is_premium(user_id) else "biasa"


def ambil_setting(user_id: int) -> dict:
    tier = cek_tier(user_id)
    if tier == "premium":
        setting = dict(config.USER_PREMIUM, tier="premium")
    else:
        setting = dict(config.USER_BIASA, tier="biasa")
    # Kecepatan cek mengikuti settingan owner (/speed). Nilai bulk_delay di
    # config per-tier dipakai hanya kalau diisi manual (override).
    speed = load_speed()
    if "bulk_delay" not in setting or setting.get("bulk_delay") is None:
        setting["bulk_delay"] = speed["bulk_delay"]
    setting["max_paralel"] = speed["max_paralel"]
    return setting


def sisa_cooldown(user_id: int) -> int:
    setting = ambil_setting(user_id)
    cd = setting.get("cooldown", 0)
    if cd <= 0:
        return 0
    terakhir = _cooldown_tracker.get(user_id, 0)
    return max(0, int(cd - (time.time() - terakhir)))


def tandai_cooldown(user_id: int):
    _cooldown_tracker[user_id] = time.time()


# ==================== STATISTIK ====================

def update_stats(user_id: int, username: str, count: int = 1):
    data = load_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)

    if uid not in data["users"]:
        data["users"][uid] = {
            "username": username,
            "total_detections": 0,
            "today_detections": 0,
            "last_date": today,
        }
        data["global"]["total_users"] += 1

    u = data["users"][uid]
    u["username"] = username
    if u.get("last_date") != today:
        u["today_detections"] = 0
        u["last_date"] = today

    u["total_detections"] += count
    u["today_detections"] += count
    data["global"]["total_detections"] += count
    save_stats(data)


def get_stats(user_id: int) -> dict:
    data = load_stats()
    u = data["users"].get(str(user_id), {
        "username": "-", "total_detections": 0, "today_detections": 0,
    })
    return {
        "username": u.get("username", "-"),
        "total": u.get("total_detections", 0),
        "today": u.get("today_detections", 0),
        "global_users": data["global"].get("total_users", 0),
        "global_detections": data["global"].get("total_detections", 0),
    }


# ==================== UTIL ====================

def valid_nomor(teks: str) -> bool:
    return len(re.sub(r"\D", "", teks)) >= 8


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if config.OWNER_ID is not None:
            try:
                oid = int(config.OWNER_ID)
            except (TypeError, ValueError):
                oid = config.OWNER_ID
            if update.effective_user.id != oid:
                if update.callback_query:
                    await aman_answer(update.callback_query, "⛔ Khusus owner!", show_alert=True)
                else:
                    await balas(update, context, "⛔ Khusus owner.")
                return
        return await func(update, context)
    return wrapper


def banned_guard(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user:
            info = is_banned(user.id)
            if info:
                alasan = info.get("reason") or "tidak ada alasan"
                teks = (
                    f"🚫 Anda di-ban oleh owner.\n\n"
                    f"Alasan: {alasan}\n"
                    f"Sejak: {info.get('since', '-')}"
                )
                if update.callback_query:
                    await aman_answer(update.callback_query, "🚫 Anda dibanned.", show_alert=True)
                else:
                    await balas(update, context, teks)
                return
        return await func(update, context)
    return wrapper


def detik_ke_teks(d) -> str:
    try:
        d = int(d)
    except (TypeError, ValueError):
        return "-"
    if d <= 0:
        return "siap"
    jam, sisa = divmod(d, 3600)
    menit, detik = divmod(sisa, 60)
    parts = []
    if jam:
        parts.append(f"{jam}j")
    if menit or jam:
        parts.append(f"{menit}m")
    parts.append(f"{detik}s")
    return " ".join(parts)


REASON_NGAMBEK = (
    "temporarily_unavailable",
    "too_many_requests",
    "rate_limit",
    "rate_limited",
    "server_busy",
    "try_again_later",
)


def klasifikasi(r: dict) -> dict:
    if not isinstance(r, dict):
        return {"kategori": "error", "cooldown_detik": None, "alasan": "invalid respon"}

    status, reason = r.get("status"), r.get("reason")
    appeal = r.get("appeal_token")

    if status == "fail" and appeal:
        return {"kategori": "banned", "cooldown_detik": None, "alasan": "Terbanned WA"}

    if reason and reason.lower() in REASON_NGAMBEK:
        return {"kategori": "ngambek", "cooldown_detik": None, "alasan": reason}

    if reason == "blocked" and not appeal:
        return {"kategori": "clone", "cooldown_detik": None, "alasan": "gak support clone"}

    if status == "invalid":
        return {"kategori": "tidak_dapat_otp", "cooldown_detik": None,
                "alasan": r.get("reason") or "nomor invalid"}

    if reason in ("no_routes", "incorrect"):
        return {"kategori": "tidak_dapat_otp", "cooldown_detik": None, "alasan": reason}

    if reason in ("bad_token", "old_version"):
        return {"kategori": "error", "cooldown_detik": None, "alasan": reason}

    sms_wait = r.get("sms_wait")
    if isinstance(sms_wait, (int, float)) and not isinstance(sms_wait, bool):
        if sms_wait <= 0:
            return {"kategori": "siap", "cooldown_detik": 0, "alasan": None}
        return {"kategori": "cooldown", "cooldown_detik": int(sms_wait), "alasan": None}

    return {"kategori": "error", "cooldown_detik": None, "alasan": reason or "unknown"}


# Nomor yang dianggap GAGAL -> layak diulangi (bukan hasil final).
KATEGORI_GAGAL = ("error", "ngambek")


async def cek_satu_nomor_ringkas(nomor: str, methods: list) -> dict:
    s_set = load_settings()
    metode_coba = [m for m in (methods or []) if m] or METODE_TERSUMBUH
    hasil = {"nomor": nomor, "kategori": "error", "cooldown_detik": None, "alasan": None}
    ada_respons = False

    for method in metode_coba:
        percobaan_maks = 3 + max(0, int(s_set["retry_maksimal"]))
        for attempt in range(percobaan_maks):
            try:
                r, _info = await detect(nomor, method)
                ada_respons = True
            except CekBapaklu as e:
                hasil["alasan"] = f"HTTP: {str(e)[:50]}"
                await asyncio.sleep(1.0 + 0.5 * attempt)
                continue
            except asyncio.TimeoutError:
                hasil["alasan"] = "timeout"
                await asyncio.sleep(1.0 + 0.5 * attempt)
                continue
            except Exception as e:
                hasil["alasan"] = f"{type(e).__name__}: {str(e)[:40]}"
                await asyncio.sleep(1.0 + 0.5 * attempt)
                continue

            k = klasifikasi(r)

            # Ngambek / error sementara -> ulangi dengan jeda naik bertahap.
            if k["kategori"] in KATEGORI_GAGAL and attempt < percobaan_maks - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            if k["kategori"] in ("siap", "cooldown", "banned", "clone", "ngambek"):
                hasil.update(k)
                return hasil
            if k["kategori"] == "tidak_dapat_otp":
                hasil["kategori"] = "tidak_dapat_otp"
                hasil["alasan"] = k["alasan"]
                break
            if k["kategori"] == "error":
                hasil["alasan"] = f"reason: {r.get('reason') or 'unknown'}"
                break

    if not ada_respons:
        hasil["kategori"] = "clone"
        hasil["alasan"] = "gak support clone"

    return hasil


def _ringkas_alasan(a) -> str:
    """Rapikan alasan error yang muncul dari exception httpx/Python agar
    mudah dibaca user (bukan nama class mentah seperti ConnectError)."""
    s = str(a or "").strip()
    if not s:
        return "-"
    ganti = {
        "ConnectError": "koneksi ke server WA ditolak IP ini",
        "TimeoutError": "server WA tidak merespon (timeout)",
        "ReadTimeout": "server WA tidak merespon (timeout)",
        "ConnectTimeout": "gagal koneksi ke server WA",
        "SSLException": "masalah SSL saat koneksi",
        "ProxyError": "proxy gagal dipakai",
    }
    for k, v in ganti.items():
        if k in s:
            return v + f" ({s[:60]})"
    return s[:80]


def susun_pesan(hasil_list, durasi, selesai=True, progress=None) -> str:
    siap = [h for h in hasil_list if h["kategori"] == "siap"]
    cooldown = [h for h in hasil_list if h["kategori"] == "cooldown"]
    banned = [h for h in hasil_list if h["kategori"] == "banned"]
    clone = [h for h in hasil_list if h["kategori"] == "clone"]
    ngambek = [h for h in hasil_list if h["kategori"] == "ngambek"]
    tidak_otp = [h for h in hasil_list if h["kategori"] == "tidak_dapat_otp"]
    error = [h for h in hasil_list if h["kategori"] == "error"]

    cooldown.sort(key=lambda h: h.get("cooldown_detik") or 0)

    def wrap_nomor(n):
        return f"<code>{html.escape(str(n))}</code>"

    parts = [rich_ui.rich_h2(f"{tgemoji('detek', '🔍')} HASIL DETEKSI")]

    # Ringkasan semua kategori
    parts.append(rich_ui.rich_info_table([
        [f"{tgemoji('success', '✅')} Siap OTP",
         rich_ui.rich_highlight(f"<b>{len(siap)}</b>")],
        [f"{tgemoji('clock', '⏱')} Cooldown", f"<b>{len(cooldown)}</b>"],
        [f"{tgemoji('failed', '❌')} Terbanned", f"<b>{len(banned)}</b>"],
        [f"{tgemoji('nootp', '🚫')} Tidak dapat OTP",
         f"<b>{len(tidak_otp)}</b>"],
        [f"{tgemoji('users', '👥')} Gak support clone", f"<b>{len(clone)}</b>"],
        [f"{tgemoji('warning', '⚠️')} Ngambek", f"<b>{len(ngambek)}</b>"],
        [f"{tgemoji('warning', '⚠️')} Error", f"<b>{len(error)}</b>"],
    ]))

    # Catatan cooldown -> blok lipat
    parts.append(rich_ui.rich_fold(
        f"{tgemoji('warning', '⚠️')} Catatan cooldown",
        rich_ui.rich_para("Waktu cooldown bisa berubah sewaktu-waktu. "
                          "Segera login ke nomor yang telah melakukan detek.")))

    if siap:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('success', '✅')} <b>Nomor siap OTP</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor"], [[wrap_nomor(h["nomor"])] for h in siap]))

    if cooldown:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('clock', '⏱')} <b>Nomor yang sedang cooldown</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor", "Sisa"],
            [[wrap_nomor(h["nomor"]),
              detik_ke_teks(h["cooldown_detik"])] for h in cooldown]))

    if banned:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('failed', '❌')} "
            "<b>Nomor yang tidak dapat menerima OTP</b>"))
        parts.append(rich_ui.rich_para("Terbanned WA"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor", "Status"],
            [[wrap_nomor(h["nomor"]),
              f"{tgemoji('failed', '❌')} Banned"] for h in banned]))

    if tidak_otp:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('nootp', '🚫')} <b>Tidak terdaftar / no routes</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor", "Alasan"],
            [[wrap_nomor(h["nomor"]),
              html.escape(str(h.get("alasan") or "-"))] for h in tidak_otp]))

    if clone:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('users', '👥')} <b>Gak Support Clone</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor"], [[wrap_nomor(h["nomor"])] for h in clone]))

    if ngambek:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('warning', '⚠️')} "
            "<b>Si mark ngambek jir — silahkan cek ulang</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor"], [[wrap_nomor(h["nomor"])] for h in ngambek]))

    if error:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('warning', '⚠️')} <b>Error</b>"))
        parts.append(rich_ui.rich_data_table(
            ["Nomor", "Alasan"],
            [[wrap_nomor(h["nomor"]),
              html.escape(str(h.get("alasan") or "-"))] for h in error]))

    if not hasil_list:
        parts.append(rich_ui.rich_para("<i>Belum ada hasil...</i>"))

    # Footer info
    parts.append(rich_ui.rich_info_table([
        [f"{tgemoji('clock', '⏱')} Durasi", f"{durasi:.2f}s"],
        [f"{tgemoji('info', 'ℹ️')} Versi", html.escape(str(versi_mark))],
        [f"{tgemoji('refresh', '🔄')} Total dicek",
         f"<b>{len(hasil_list)}</b>"],
    ]))
    if progress:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('loading', '⏳')} " +
            rich_ui.rich_highlight(f"Sedang berjalan... ({progress})")))
    elif selesai:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('success', '✅')} " +
            rich_ui.rich_highlight("<b>Selesai</b>")))
    else:
        parts.append(rich_ui.rich_para(
            f"{tgemoji('loading', '⏳')} <i>Sedang berjalan...</i>"))

    return "".join(parts)


def susun_pesan_dilewati(nomor_dilewati: list, batas: int) -> str:
    return (
        rich_ui.rich_h2(f"{tgemoji('noentry', '🚫')} NOMOR TIDAK DICEK") +
        rich_ui.rich_para(
            "Nomor berikut dilewati karena melebihi batas "
            f"<b>{batas}</b>:") +
        rich_ui.rich_data_table(
            ["Nomor"],
            [[f"<code>{html.escape(str(n))}</code>"] for n in nomor_dilewati])
    )


# ==================== AUTO BACKUP ====================

def buat_backup_zip() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BASE_DIR / f"backup_{ts}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in BASE_DIR.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix == ".zip":
                continue
            try:
                arcname = path.relative_to(BASE_DIR)
                zf.write(path, arcname)
            except Exception as e:
                logger.warning("Skip %s: %s", path, e)

    return zip_path


async def job_backup(context: ContextTypes.DEFAULT_TYPE):
    if not config.OWNER_ID:
        return
    try:
        zip_path = buat_backup_zip()
    except Exception as e:
        logger.error("Gagal bikin zip: %s", e)
        return
    try:
        with open(zip_path, "rb") as f:
            await context.bot.send_document(
                chat_id=int(config.OWNER_ID),
                document=f,
                filename=zip_path.name,
                caption=f"📦 Auto Backup\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            )
        logger.info("Backup terkirim: %s", zip_path.name)
    except Exception as e:
        logger.error("Gagal kirim backup: %s", e)
    finally:
        try:
            zip_path.unlink()
        except Exception:
            pass


# ==================== FORCE JOIN ====================

async def cek_sudah_join(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> list:
    belum = []
    for chat_id in force_join_aktif():
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            status = getattr(member, "status", None)
            if status in ("left", "kicked", "banned"):
                belum.append(chat_id)
        except TelegramError as e:
            logger.warning("Gagal cek member di %s: %s", chat_id, e)
            belum.append(chat_id)
    return belum


def _link_join(chat_id) -> str:
    s = str(chat_id)
    if s.startswith("@"):
        return f"https://t.me/{s.lstrip('@')}"
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}"
    return f"https://t.me/{s}"


def buat_keyboard_force_join(belum_join: list):
    # Inline keyboard Telegram Bot API tidak menerima tag <tg-emoji>;
    # gunakan emoji Unicode pada label tombol.
    return _kb_ptb(spec_force_join(belum_join))


def teks_force_join(belum_join: list) -> str:
    return (
        rich_ui.rich_h2(f"{tgemoji('lock', '🔒')} {BOT_DISPLAY} • ACCESS GATE") +
        rich_ui.rich_para(
            f"{tgemoji('warning', '⚠️')} <i>Akses belum tersedia</i>") +
        rich_ui.rich_para("Selesaikan langkah berikut untuk melanjutkan:") +
        rich_ui.rich_checklist([
            f"{tgemoji('channel', '📢')} <code>{html.escape(str(c))}</code>"
            for c in belum_join
        ]) +
        rich_ui.rich_para(
            f"{tgemoji('success', '✅')} Setelah bergabung, "
            "tekan tombol <b>SUDAH JOIN</b>.")
    )


async def balas_rich(update, context, rich_html, keyboard=None,
                     keyboard_rich=None):
    """Kirim pesan: coba Rich Message dulu, fallback ke balas() biasa."""
    chat = update.effective_chat
    if chat and rich_ui.ada_tag_rich(rich_html):
        ok = await rich_ui.kirim_rich(config.BOT_TOKEN, chat.id, rich_html,
                                      keyboard_rich)
        if ok:
            return None
    return await balas(update, context, rich_ui.rich_ke_html(rich_html),
                       reply_markup=keyboard, parse_mode="HTML")


async def _edit_hasil(msg, rich_html, keyboard=None):
    """Edit pesan hasil deteksi: coba rich, fallback ke HTML biasa."""
    if len(rich_html) <= 4000:
        ok = await rich_ui.edit_rich(config.BOT_TOKEN, msg.chat.id,
                                     msg.message_id, rich_html)
        if ok:
            if keyboard is not None:
                # Rich tak memasang keyboard -> pasang via editMessageReplyMarkup.
                try:
                    await msg.edit_reply_markup(reply_markup=keyboard)
                except Exception:
                    pass
            return
    fb, _ = _customize_emojis(rich_ui.rich_ke_html(rich_html))
    kwargs = {"parse_mode": "HTML"}
    if keyboard is not None:
        kwargs["reply_markup"] = keyboard
    try:
        await msg.edit_text(fb[:4000], **kwargs)
    except BadRequest as e:
        if not _entity_error(e):
            raise
        await msg.edit_text(_strip_custom_emoji(fb)[:4000], **kwargs)


async def cek_force_join_atau_kirim(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not force_join_aktif():
        return True
    user = update.effective_user
    if is_owner(user.id):
        return True
    belum = await cek_sudah_join(context, user.id)
    if not belum:
        return True
    await balas_rich(update, context, teks_force_join(belum),
                     buat_keyboard_force_join(belum), spec_force_join(belum))
    return False


# ==================== ZHEE CHECKER UI ====================
def tgemoji(key: str, fallback: str) -> str:
    """Bungkus emoji dengan custom emoji ID bila mode custom aktif & ID valid.
    Bila tidak, kembalikan emoji Unicode biasa (selalu tampil normal)."""
    if not _EMOJI_CUSTOM_ON or not _EMOJI_MAP:
        return fallback
    emoji_id = str(_EMOJI_MAP.get(fallback, "")).strip()
    if emoji_id.isdigit():
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


def teks_menu_awal(user, s):
    nama = html.escape(user.first_name or user.username or "kak")
    username = html.escape("@" + user.username if user.username else "belum diatur")
    status = "PREMIUM" if cek_tier(user.id) == "premium" else "STANDARD"
    return (
        rich_ui.rich_h2(f"🔻 {NAMA_ASCII}") +
        rich_ui.rich_para("<i>Control Center • Smart • Minimal • Secure</i>") +
        rich_ui.rich_para(
            f"{tgemoji('hello', '✨')} Selamat datang, <b>{nama}</b>") +
        rich_ui.rich_para(f"{tgemoji('profile', '👤')} <b>PROFILE</b>") +
        rich_ui.rich_info_table([
            ["Username", username],
            ["Telegram ID", f"<code>{user.id}</code>"],
            ["Membership",
             rich_ui.rich_highlight(f"<b>{status}</b>")],
        ]) +
        rich_ui.rich_para(f"{tgemoji('stats', '📊')} <b>YOUR ACTIVITY</b>") +
        rich_ui.rich_info_table([
            ["Total Detek", f"<b>{s['total']}</b>"],
            ["Detek hari ini", f"<b>{s['today']}</b>"],
        ]) +
        rich_ui.rich_para(
            f"{tgemoji('network', '🌐')} <b>NETWORK OVERVIEW</b>") +
        rich_ui.rich_info_table([
            ["Pengguna", f"<b>{s['global_users']}</b>"],
            ["Total aktivitas", f"<b>{s['global_detections']}</b>"],
        ]) +
        rich_ui.rich_para("<i>Pilih menu di bawah untuk melanjutkan.</i>")
    )


def teks_fitur():
    return (
        rich_ui.rich_h2(f"{tgemoji('menu', '🔷')} {BOT_DISPLAY} • MENU GUIDE") +
        rich_ui.rich_para("<i>Ringkasan perintah dan layanan bot</i>") +
        rich_ui.rich_para(f"{tgemoji('help', '📚')} <b>GENERAL</b>") +
        rich_ui.rich_checklist([
            "<code>/start</code> — buka dashboard",
            "<code>/help</code> — panduan bot",
            "<code>/cek</code> — deteksi nomor",
        ]) +
        rich_ui.rich_fold(
            f"{tgemoji('account', '💎')} ACCOUNT",
            rich_ui.rich_para("Status akun dan membership tersedia di "
                              "dashboard. Batas penggunaan mengikuti "
                              "konfigurasi akun.")) +
        rich_ui.rich_para(
            f"{tgemoji('support', '🛟')} Jika ada kendala, "
            "hubungi pengelola bot.") +
        rich_ui.rich_para(f"<i>{BOT_DISPLAY} Checker • Control Center</i>")
    )


def teks_panduan_cek():
    return (
        rich_ui.rich_h2(f"{tgemoji('detek', '🔍')} PANDUAN /cek") +
        rich_ui.rich_checklist([
            "<code>/cek +62881xxxx</code> — satu nomor",
            "<code>/cek +62881xxxx +62881xxxx +60112xxxx</code> "
            "— banyak nomor sekaligus",
            "Bisa juga multi-line, satu nomor per baris",
        ]) +
        rich_ui.rich_fold(
            "Contoh",
            rich_ui.rich_para("<code>/cek +628123456789</code>"))
    )


def teks_admin(user, s):
    prem = load_premium().get("users", {})
    ban = load_banned().get("users", {})
    return (
        rich_ui.rich_h2(f"{tgemoji('admin', '⚙️')} {BOT_DISPLAY} • OWNER CONSOLE") +
        rich_ui.rich_para("<i>Restricted access • Owner only</i>") +
        rich_ui.rich_para(f"{tgemoji('users', '👥')} <b>USER MANAGEMENT</b>") +
        rich_ui.rich_data_table(
            ["Perintah", "Fungsi"],
            [
                ["<code>/addprem ID</code>", "tambah membership"],
                ["<code>/delprem ID</code>", "hapus membership"],
                ["<code>/ban ID alasan</code>", "blokir pengguna"],
                ["<code>/unban ID</code>", "buka blokir"],
            ]) +
        rich_ui.rich_para(
            f"{tgemoji('broadcast', '📣')} <b>ANNOUNCEMENTS</b>") +
        rich_ui.rich_info_table([
            ["<code>/bc pesan</code>", "broadcast informasi"],
            ["<code>/speed</code>", "atur kecepatan cek nomor"],
        ]) +
        rich_ui.rich_para(
            f"{tgemoji('lock', '\U0001f512')} <b>FORCE JOIN</b>") +
        rich_ui.rich_info_table([
            ["<code>/forcejoin</code>", "buka panel atur link & on/off"],
            ["<code>/forcejoin on|off</code>", "aktif/nonaktifkan"],
            ["<code>/forcejoin add|del</code>", "tambah/hapus link"],
        ]) +
        rich_ui.rich_para(f"{tgemoji('stats', '📊')} <b>SYSTEM SNAPSHOT</b>") +
        rich_ui.rich_info_table([
            ["Premium", f"<b>{len(prem)}</b>"],
            ["Banned", f"<b>{len(ban)}</b>"],
        ]) +
        rich_ui.rich_para("<i>Kelola akses secara bertanggung jawab.</i>")
    )


# ==================== KEYBOARD ====================
# ── Spesifikasi tombol: SATU sumber untuk rich & fallback ──
# style valid untuk Rich Message: primary / success / danger.
# (Tidak ada tombol destruktif di bot ini -> danger tidak dipakai.)
# Fallback PTB (InlineKeyboardButton) mengabaikan style.
def spec_menu(user_id: int):
    rows = [[{"text": "🔍  DETEK", "callback_data": "detek",
              "style": "primary"}]]
    if is_owner(user_id):
        rows.append([{"text": "🛠️  OWNER COMMAND", "callback_data": "admin_panel",
                      "style": "primary"}])
    return rows


def spec_nav(user_id: int):
    """Navigasi kembali — dipakai layar Detek & Help."""
    rows = [[{"text": "🏠  DASHBOARD", "callback_data": "menu_awal",
              "style": "primary"}]]
    if is_owner(user_id):
        rows.append([{"text": "🛠️  OWNER COMMAND", "callback_data": "admin_panel",
                      "style": "primary"}])
    return rows


def spec_admin():
    return [[{"text": "🔒  FORCE JOIN", "callback_data": "fj_panel",
              "style": "primary"}],
            [{"text": "🏠  DASHBOARD", "callback_data": "menu_awal",
              "style": "primary"}]]


def spec_force_join(belum_join: list):
    rows = []
    for chat_id in belum_join:
        label = chat_id if str(chat_id).startswith("@") else str(chat_id)
        rows.append([{"text": f"📢  JOIN {label}", "url": _link_join(chat_id),
                      "style": "primary"}])
    rows.append([{"text": "✅  SUDAH JOIN", "callback_data": "cek_join",
                  "style": "success"}])
    return rows


def _kb_ptb(spec):
    tombol = []
    for r in spec:
        baris = []
        for b in r:
            kw = {}
            if b.get("callback_data"):
                kw["callback_data"] = b["callback_data"]
            if b.get("url"):
                kw["url"] = b["url"]
            baris.append(InlineKeyboardButton(b["text"], **kw))
        tombol.append(baris)
    return InlineKeyboardMarkup(tombol)


def buat_keyboard_menu(user_id: int):
    return _kb_ptb(spec_menu(user_id))


def buat_keyboard_nav(user_id: int):
    return _kb_ptb(spec_nav(user_id))


def buat_keyboard_admin():
    return _kb_ptb(spec_admin())


# ==================== HANDLER ====================

@banned_guard
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await cek_force_join_atau_kirim(update, context):
        return

    user = update.effective_user
    s = get_stats(user.id)
    pesan = teks_menu_awal(user, s)
    keyboard = buat_keyboard_menu(user.id)

    logger.info(f"👤 /start oleh {user.id} - {user.username or user.first_name}")

    if config.START_PHOTO_URL:
        try:
            await balas_foto(update, context, config.START_PHOTO_URL,
                             rich_ui.rich_ke_html(pesan),
                             parse_mode="HTML", reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning("Gagal kirim foto: %s", e)

    await balas_rich(update, context, pesan, keyboard, spec_menu(user.id))


@banned_guard
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await cek_force_join_atau_kirim(update, context):
        return
    user = update.effective_user
    await balas_rich(update, context, teks_fitur(), buat_keyboard_nav(user.id),
                     spec_nav(user.id))


@banned_guard
@banned_guard
async def tombol_detek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await aman_answer(query)

    user = update.effective_user
    if force_join_aktif() and not is_owner(user.id):
        belum = await cek_sudah_join(context, user.id)
        if belum:
            await aman_answer(query, "🔒 Join dulu ya!", show_alert=True)
            return

    await kirim_atau_edit(query, teks_panduan_cek(),
                          buat_keyboard_nav(user.id), spec_nav(user.id))


@owner_only
@banned_guard
async def tombol_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await aman_answer(query)
    user = update.effective_user
    s = get_stats(user.id)
    if query.data == "fj_panel":
        await kirim_atau_edit(query, teks_forcejoin_panel(),
                              _kb_ptb(spec_forcejoin_panel()),
                              spec_forcejoin_panel())
        return
    await kirim_atau_edit(query, teks_admin(user, s), buat_keyboard_admin(),
                          spec_admin())


@banned_guard
async def tombol_menu_awal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await aman_answer(query)

    user = update.effective_user
    if force_join_aktif() and not is_owner(user.id):
        belum = await cek_sudah_join(context, user.id)
        if belum:
            await aman_answer(query, "🔒 Join dulu ya!", show_alert=True)
            return

    s = get_stats(user.id)
    await kirim_atau_edit(query, teks_menu_awal(user, s),
                          buat_keyboard_menu(user.id), spec_menu(user.id))


def _fj_norm(chat: str) -> str:
    """Normalisasi input owner jadi ID/username yang bisa dipakai Bot API."""
    c = str(chat).strip()
    if not c:
        return ""
    # https://t.me/xxx atau t.me/xxx -> @xxx (channel/grup publik)
    m = re.match(r"^(?:https?://)?(?:www\.)?t\.me/(?!\+)([A-Za-z0-9_]{4,})/?$", c)
    if m:
        return "@" + m.group(1)
    # Undangan pribadi tidak bisa diverifikasi bot -> simpan apa adanya
    return c


async def tombol_cek_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    await aman_answer(query)

    if is_banned(user.id):
        await aman_answer(query, "🚫 Anda dibanned.", show_alert=True)
        return

    if not force_join_aktif() or is_owner(user.id):
        await aman_answer(query, "✅ Udah join.", show_alert=True)
        return

    belum = await cek_sudah_join(context, user.id)
    if belum:
        await aman_answer(query, "❌ Kamu masih belum join semua.", show_alert=True)
        await kirim_atau_edit(query, teks_force_join(belum),
                              buat_keyboard_force_join(belum),
                              spec_force_join(belum))
        return

    try:
        await query.message.delete()
    except Exception:
        pass

    s = get_stats(user.id)
    pesan = teks_menu_awal(user, s)
    keyboard = buat_keyboard_menu(user.id)

    if config.START_PHOTO_URL:
        try:
            await context.bot.send_photo(
                chat_id=user.id,
                photo=config.START_PHOTO_URL,
                caption=rich_ui.rich_ke_html(pesan),
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            logger.warning("Gagal kirim foto: %s", e)

    if not await rich_ui.kirim_rich(config.BOT_TOKEN, user.id, pesan,
                                    spec_menu(user.id)):
        fallback_html = rich_ui.rich_ke_html(pesan)
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=fallback_html,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except BadRequest as e:
            # Fallback terakhir: plain text agar markup Rich/HTML yang tidak
            # didukung Telegram tidak membuat /start gagal total.
            logger.warning("HTML /start ditolak Telegram, kirim teks biasa: %s", e)
            plain = html.unescape(re.sub(r"<[^>]*>", "", fallback_html))
            plain = re.sub(r"[ \t]+\n", "\n", plain).strip() or BOT_DISPLAY
            await context.bot.send_message(
                chat_id=user.id,
                text=plain[:4000],
                reply_markup=keyboard,
            )


async def _proses_cek(update, context, nomor_list, user, setting,
                      nomor_dilewati, batas, msg=None):
    async with _detect_semaphore:
        # Baca ulang kecepatan tiap mulai cek -> perubahan /speed owner
        # langsung berlaku tanpa restart bot.
        speed = load_speed()
        tier = setting["tier"]
        methods = setting["method"]
        delay = setting.get("bulk_delay")
        if delay is None:
            delay = speed["bulk_delay"]
        total = len(nomor_list)

        async def cek_satuan(idx_nomor):
            i, nomor = idx_nomor
            try:
                h = await cek_satu_nomor_ringkas(nomor, methods)
            except Exception as e:
                h = {"nomor": nomor, "kategori": "error",
                     "cooldown_detik": None, "alasan": type(e).__name__}
            return i, h

        mulai = time.time()
        hasil_by_idx = {}
        urut_queue = list(enumerate(nomor_list, 1))
        paralel = max(1, int(speed["max_paralel"]))
        idx_selesai = 0
        ngambek_counter = 0
        antrian = asyncio.Queue()
        for item in urut_queue:
            antrian.put_nowait(item)

        async def worker():
            nonlocal idx_selesai, ngambek_counter
            while True:
                try:
                    item = antrian.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    async with _detect_semaphore:
                        i, h = await cek_satuan(item)
                finally:
                    antrian.task_done()

                hasil_by_idx[i] = h
                idx_selesai += 1

                # Update hasil SETIAP nomor selesai dicek
                if msg:
                    hasil_urut = [hasil_by_idx[k]
                                  for k in sorted(hasil_by_idx)]
                    durasi = time.time() - mulai
                    teks = susun_pesan(hasil_urut, durasi, False,
                                       progress=f"{idx_selesai}/{total}")
                    try:
                        await _edit_hasil(msg, teks)
                    except Exception:
                        pass

                # Adaptive backoff kalau ngambek numpuk
                if h["kategori"] == "ngambek":
                    ngambek_counter += 1
                else:
                    ngambek_counter = max(0, ngambek_counter - 1)

                actual_delay = delay + random.uniform(0, 0.5)
                if ngambek_counter >= 3:
                    actual_delay += 2.0
                elif ngambek_counter >= 1:
                    actual_delay += 0.5

                if antrian.qsize() > 0 and actual_delay > 0:
                    await asyncio.sleep(actual_delay)

        # Worker tambahan di luar batas global tetap dikontrol semaphore.
        n_worker = min(paralel, total,
                       max(1, paralel if paralel <= _sem_capacity else _sem_capacity))
        workers = [asyncio.create_task(worker())
                   for _ in range(max(1, min(n_worker, total)))]
        await asyncio.gather(*workers)

        hasil_list = [hasil_by_idx[k] for k in sorted(hasil_by_idx)]

        durasi = time.time() - mulai

        # ===== ULANGI OTOMATIS nomor yang masih GAGAL di dalam sesi ini =====
        s_set = load_settings()
        if s_set["retry_gagal"] and s_set["retry_maksimal"] > 0:
            await _ulangi_nomor_gagal(hasil_by_idx, methods, user.id, msg,
                                      mulai, total, idx_selesai)
            hasil_list = [hasil_by_idx[k] for k in sorted(hasil_by_idx)]
            durasi = time.time() - mulai

        gagal_noms = [h["nomor"] for h in hasil_list
                      if h["kategori"] in KATEGORI_GAGAL]
        sesi_id = _simpan_sesi(user.id, list(hasil_by_idx.values()),
                               methods if methods else METODE_TERSUMBUH)

        teks_akhir = susun_pesan(hasil_list, durasi, True)

        # ===== PESAN 1: hasil final =====
        kb_final = None
        if gagal_noms and s_set["tombol_ulang"]:
            kb_final = _kb_ptb(spec_ulang(gagal_noms, sesi_id))
        if msg:
            try:
                await _edit_hasil(msg, teks_akhir, keyboard=kb_final)
            except Exception:
                pass
            fb_akhir, _ = _customize_emojis(rich_ui.rich_ke_html(teks_akhir))
            if len(fb_akhir) > 4000:
                sisa_teks = fb_akhir[4000:]
                while sisa_teks:
                    try:
                        await context.bot.send_message(
                            chat_id=user.id, text=sisa_teks[:4000],
                            parse_mode="HTML"
                        )
                    except Exception:
                        break
                    sisa_teks = sisa_teks[4000:]

        # ===== PESAN 2: nomor yang dilewati =====
        if nomor_dilewati:
            teks_dilewati = susun_pesan_dilewati(nomor_dilewati, batas)
            try:
                ok = await rich_ui.kirim_rich(config.BOT_TOKEN, user.id,
                                              teks_dilewati)
                if not ok:
                    fb_dilewati, _ = _customize_emojis(
                        rich_ui.rich_ke_html(teks_dilewati))
                    await context.bot.send_message(
                        chat_id=user.id, text=fb_dilewati, parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning("Gagal kirim pesan dilewati: %s", e)

        tandai_cooldown(user.id)
        uname = user.username or user.first_name or str(user.id)
        update_stats(user.id, uname, len(hasil_list))

        logger.info(f"🔍 Deteksi oleh {user.id} ({uname}) - {len(hasil_list)} nomor ({tier})")


async def _ulangi_nomor_gagal(hasil_by_idx, methods, user_id, msg,
                              mulai, total, idx_selesai):
    """Ulangi otomatis semua nomor berstatus error/ngambek (dipakai saat
    owner mengaktifkan setelan retry_gagal)."""
    ulang_target = [(i, h) for i, h in hasil_by_idx.items()
                    if h["kategori"] in KATEGORI_GAGAL]
    if not ulang_target:
        return
    logger.info("🔄 Ulang otomatis %d nomor gagal untuk user %s",
                len(ulang_target), user_id)
    for i, h in ulang_target:
        baru = await cek_satu_nomor_ringkas(h["nomor"], methods)
        # Jangan turunkan kualitas hasil lama kalau percobaan ulang makin buruk
        if baru["kategori"] not in KATEGORI_GAGAL or h["kategori"] == "ngambek":
            hasil_by_idx[i] = baru
        if msg:
            hasil_urut = [hasil_by_idx[k] for k in sorted(hasil_by_idx)]
            teks = susun_pesan(hasil_urut, time.time() - mulai, False,
                               progress=f"{idx_selesai}/{total}")
            try:
                await _edit_hasil(msg, teks)
            except Exception:
                pass
        await asyncio.sleep(0.5)


async def jalankan_cek(update: Update, context: ContextTypes.DEFAULT_TYPE, nomor_list: list):
    user = update.effective_user
    setting = ambil_setting(user.id)
    tier = setting["tier"]

    sisa = sisa_cooldown(user.id)
    if sisa > 0:
        await balas(update, context,
                    f"⏳ Sabar dikit ya.\n"
                    f"Cooldown kamu masih {detik_ke_teks(sisa)} lagi.\n\n"
                    f"Tier: {tier.capitalize()}")
        return

    nomor_list = [n for n in nomor_list if valid_nomor(n)]
    if not nomor_list:
        await balas(update, context, "❌ Gak ada nomor valid.")
        return

    max_bulk = setting["max_bulk"]
    nomor_dilewati = []
    if len(nomor_list) > max_bulk:
        nomor_dilewati = nomor_list[max_bulk:]
        nomor_list = nomor_list[:max_bulk]

    info_tier = f"[{tier.capitalize()}]" if tier == "premium" else ""
    msg = await balas(update, context,
                      f"⏳ Cek 0/{len(nomor_list)} nomor... {info_tier}".strip())

    tandai_cooldown(user.id)

    asyncio.create_task(
        _proses_cek(update, context, nomor_list, user, setting,
                    nomor_dilewati, max_bulk, msg)
    )


@banned_guard
async def cek_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await cek_force_join_atau_kirim(update, context):
        return

    args = context.args
    if not args:
        await balas_rich(update, context, teks_panduan_cek())
        return

    raw = " ".join(args)
    nomor_list = [n for n in re.split(r"[\s,]+", raw) if n.strip()]
    await jalankan_cek(update, context, nomor_list)


# ==================== COMMAND ADMIN ====================

@owner_only
@banned_guard
async def addprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await balas(update, context, "Usage: /addprem <id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await balas(update, context, "ID harus angka.")
        return

    data = load_premium()
    if str(target) in data["users"]:
        await balas(update, context, f"✅ {target} udah premium dari dulu.")
        return

    data["users"][str(target)] = {
        "since": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "added_by": update.effective_user.id,
    }
    save_premium(data)
    await balas(update, context, f"✅ {target} sekarang Premium.")


@owner_only
@banned_guard
async def delprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await balas(update, context, "Usage: /delprem <id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await balas(update, context, "ID harus angka.")
        return

    data = load_premium()
    if str(target) not in data["users"]:
        await balas(update, context, f"❌ {target} bukan premium.")
        return

    del data["users"][str(target)]
    save_premium(data)
    await balas(update, context, f"✅ Premium {target} dihapus.")


@owner_only
@banned_guard
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await balas(update, context, "Usage: /ban <id> <alasan>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await balas(update, context, "ID harus angka.")
        return

    if is_owner(target):
        await balas(update, context, "❌ Gak bisa ban owner.")
        return

    alasan = " ".join(args[1:]) if len(args) > 1 else "tidak ada alasan"

    data = load_banned()
    data["users"][str(target)] = {
        "reason": alasan,
        "since": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "banned_by": update.effective_user.id,
    }
    save_banned(data)
    await balas(update, context, f"🚫 {target} dibanned.\nAlasan: {alasan}")


@owner_only
@banned_guard
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await balas(update, context, "Usage: /unban <id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await balas(update, context, "ID harus angka.")
        return

    data = load_banned()
    if str(target) not in data["users"]:
        await balas(update, context, f"❌ {target} gak dibanned.")
        return

    del data["users"][str(target)]
    save_banned(data)
    await balas(update, context, f"✅ {target} di-unban.")


@owner_only
@banned_guard
async def bc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await balas(update, context,
                    "Usage: /bc <pesan>\n\n"
                    "Contoh:\n/bc Halo semua, bot maintenance jam 12 malam ya.")
        return

    pesan = " ".join(args)

    data = load_stats()
    users = list(data.get("users", {}).keys())
    if not users:
        await balas(update, context, "❌ Belum ada user yang pernah pakai bot.")
        return

    msg = await balas(update, context, f"📢 Broadcast ke {len(users)} user...")

    berhasil = 0
    gagal = 0
    for uid in users:
        try:
            pesan_out, changed = _customize_emojis(pesan)
            await context.bot.send_message(
                chat_id=int(uid), text=pesan_out,
                parse_mode="HTML" if changed else None
            )
            berhasil += 1
        except Exception as e:
            gagal += 1
            logger.warning(f"Gagal kirim ke {uid}: {e}")
        await asyncio.sleep(0.05)

    try:
        selesai = (
            rich_ui.rich_h2(
                f"{tgemoji('broadcast', '📣')} BROADCAST SELESAI") +
            rich_ui.rich_info_table([
                [f"{tgemoji('success', '✅')} Berhasil",
                 f"<b>{berhasil}</b>"],
                [f"{tgemoji('failed', '❌')} Gagal", f"<b>{gagal}</b>"],
                [f"{tgemoji('users', '👥')} Total",
                 f"<b>{len(users)}</b>"],
            ])
        )
        await _edit_hasil(msg, selesai)
    except Exception:
        pass

    logger.info(f"📢 Broadcast oleh owner - {berhasil} berhasil, {gagal} gagal")


# ==================== KECEPATAN CEK (/speed) ====================

SPEED_PRESET = {
    "slow":  {"label": "🐢 Lambat",  "bulk_delay": 10.0, "max_paralel": 2},
    "normal":{"label": "⚖️ Normal", "bulk_delay": 3.0,  "max_paralel": 3},
    "fast":  {"label": "⚡ Cepat",   "bulk_delay": 1.0,  "max_paralel": 5},
    "turbo": {"label": "🚀 Turbo",   "bulk_delay": 0.3,  "max_paralel": 8},
}


def spec_speed():
    rows = [[{"text": p["label"], "callback_data": f"speed_set_{k}",
              "style": "primary"}] for k, p in SPEED_PRESET.items()]
    rows.append([{"text": "✍️  KUSTOM delay|paralel", "callback_data": "speed_kustom",
                  "style": "primary"}])
    rows.append([{"text": "🏠  DASHBOARD", "callback_data": "menu_awal",
                  "style": "primary"}])
    return rows


def teks_speed(speed: dict) -> str:
    return (
        rich_ui.rich_h2(f"{tgemoji('speed', '⚡️')} {BOT_DISPLAY} • KECEPATAN CEK") +
        rich_ui.rich_para("<i>Hanya owner yang bisa mengubah.</i>") +
        rich_ui.rich_info_table([
            ["Jeda antar nomor", f"<b>{speed['bulk_delay']}s</b>"],
            ["Cek bersamaan", f"<b>{speed['max_paralel']} nomor</b>"],
        ]) +
        rich_ui.rich_fold(
            f"{tgemoji('help', '📚')} CARA PAKAI",
            rich_ui.rich_checklist([
                "<code>/speed 5</code> — jeda 5 detik antar nomor",
                "<code>/speed 2.5 4</code> — jeda 2.5s, 4 nomor paralel",
                "Atau tekan tombol preset di bawah (langsung berlaku).",
            ])) +
        rich_ui.rich_para("⚠️ Terlalu cepat/paralel berisiko API rate limit.")
    )


async def _terapkan_speed(update, context, bulk_delay, max_paralel):
    speed = load_speed()
    speed["bulk_delay"] = bulk_delay
    speed["max_paralel"] = max_paralel
    save_speed(speed)
    sinkronkan_semaphore()
    await balas(update, context,
                "✅ Kecepatan cek diubah:\n"
                f"• Jeda antar nomor: {speed['bulk_delay']}s\n"
                f"• Paralel: {speed['max_paralel']} nomor\n\n"
                "Perubahan langsung berlaku untuk pengecekan berikutnya.")


@owner_only
@banned_guard
async def speed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await balas_rich(update, context, teks_speed(load_speed()),
                         _kb_ptb(spec_speed()), spec_speed())
        return

    try:
        bulk_delay = float(args[0])
    except ValueError:
        await balas(update, context,
                    "❌ Format salah.\nContoh: /speed 2.5 atau /speed 2.5 4")
        return
    if not (0 <= bulk_delay <= 600):
        await balas(update, context, "❌ Jeda harus 0–600 detik.")
        return

    max_paralel = load_speed()["max_paralel"]
    if len(args) > 1:
        try:
            max_paralel = int(args[1])
        except ValueError:
            await balas(update, context, "❌ Paralel harus angka bulat (1–10).")
            return
    if not (1 <= max_paralel <= 10):
        await balas(update, context, "❌ Paralel harus 1–10.")
        return

    await _terapkan_speed(update, context, bulk_delay, max_paralel)


@owner_only
@banned_guard
async def tombol_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if query.data == "speed_kustom":
        await aman_answer(
            query,
            "Kirim pesan biasa:\n/speed <jeda> [paralel]\n"
            "Contoh: /speed 2.5 4", show_alert=True)
        return

    key = query.data.removeprefix("speed_set_")
    preset = SPEED_PRESET.get(key)
    if not preset:
        await aman_answer(query, "❌ Preset tidak dikenal.", show_alert=True)
        return

    await aman_answer(query, f"{preset['label']} diterapkan!")
    speed = load_speed()
    speed["bulk_delay"] = preset["bulk_delay"]
    speed["max_paralel"] = preset["max_paralel"]
    save_speed(speed)
    sinkronkan_semaphore()
    await kirim_atau_edit(query, teks_speed(speed),
                          _kb_ptb(spec_speed()), spec_speed())
    logger.info("⚡ Owner %s set kecepatan: %s (%ss, paralel %s)",
                user.id, preset["label"],
                preset["bulk_delay"], preset["max_paralel"])


# ==================== FORCE JOIN PANEL (OWNER) ====================

def spec_forcejoin_panel() -> list:
    fj = load_force_join()
    rows = [[{"text": "🟢 AKTIFKAN" if not fj["enabled"] else "🔴 MATIKAN",
              "callback_data": "fj_toggle",
              "style": "success" if not fj["enabled"] else "danger"}]]
    rows.append([{"text": "➕ TAMBAH LINK", "callback_data": "fj_add",
                  "style": "primary"}])
    for c in fj["chats"]:
        rows.append([{"text": f"🗑 HAPUS {c}", "callback_data": f"fj_del::{c}",
                      "style": "danger"}])
    rows.append([{"text": "🏠  DASHBOARD", "callback_data": "menu_awal",
                  "style": "primary"}])
    return rows


def teks_forcejoin_panel() -> str:
    fj = load_force_join()
    status = (f"{tgemoji('success', '✅')} <b>AKTIF</b>" if fj["enabled"]
              else f"{tgemoji('failed', '❌')} <b>MATI</b>")
    daftar = "".join(f"<code>{html.escape(c)}</code>\n"
                     for c in fj["chats"]) or "<i>Belum ada link.</i>"
    return (
        rich_ui.rich_h2(f"{tgemoji('lock', '🔒')} {BOT_DISPLAY} • FORCE JOIN") +
        rich_ui.rich_para(f"Status: {status}") +
        rich_ui.rich_para("<b>Daftar channel/grup:</b>") +
        rich_ui.rich_para(daftar.strip()) +
        rich_ui.rich_fold(
            f"{tgemoji('help', '📚')} CARA PAKAI",
            rich_ui.rich_checklist([
                "<code>/forcejoin on</code> — aktifkan force join",
                "<code>/forcejoin off</code> — nonaktifkan force join",
                "<code>/forcejoin add @channelku</code> — tambah link",
                "<code>/forcejoin del @channelku</code> — hapus link",
                "Link boleh username (@abc), ID (-100...), atau t.me/abc.",
                "Bot harus jadi ADMIN di channel/grup agar bisa cek member.",
            ]))
    )


async def _fj_tampilkan(update, context):
    await balas_rich(update, context, teks_forcejoin_panel(),
                     _kb_ptb(spec_forcejoin_panel()), spec_forcejoin_panel())


@owner_only
@banned_guard
async def forcejoin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    fj = load_force_join()
    aksi = args[0].lower() if args else ""

    if not aksi:
        await _fj_tampilkan(update, context)
        return

    if aksi == "on":
        if not fj["chats"]:
            await balas(update, context,
                        "❌ Belum ada link. Tambah dulu:\n"
                        "<code>/forcejoin add @channelku</code>",
                        parse_mode="HTML")
            return
        save_force_join(True, fj["chats"])
        await balas(update, context,
                    f"✅ Force join DIAKTIFKAN untuk {len(fj['chats'])} link.")
    elif aksi == "off":
        save_force_join(False, fj["chats"])
        await balas(update, context, "❌ Force join DINONAKTIFKAN.")
    elif aksi in ("add", "+"):
        if len(args) < 2:
            await balas(update, context,
                        "❌ Format: <code>/forcejoin add @channelku</code>",
                        parse_mode="HTML")
            return
        baru = _fj_norm(" ".join(args[1:]))
        if not baru:
            await balas(update, context, "❌ Link tidak valid.")
            return
        if any(str(c).lower() == baru.lower() for c in fj["chats"]):
            await balas(update, context, f"⚠️ <code>{html.escape(baru)}</code> sudah ada.",
                        parse_mode="HTML")
            return
        chats = fj["chats"] + [baru]
        save_force_join(fj["enabled"], chats)
        await balas(update, context,
                    f"➕ Ditambahkan: <code>{html.escape(baru)}</code>\n"
                    f"Total {len(chats)} link. "
                    "Pastikan bot jadi ADMIN di channel/grup itu biar bisa cek member.",
                    parse_mode="HTML")
    elif aksi in ("del", "hapus", "-"):
        if len(args) < 2:
            await balas(update, context,
                        "❌ Format: <code>/forcejoin del @channelku</code>",
                        parse_mode="HTML")
            return
        target = _fj_norm(" ".join(args[1:])).lower()
        chats = [c for c in fj["chats"] if str(c).lower() != target]
        if len(chats) == len(fj["chats"]):
            await balas(update, context, "❌ Link tidak ditemukan di daftar.")
            return
        save_force_join(fj["enabled"], chats)
        await balas(update, context,
                    f"🗑 Dihapus. Sisa {len(chats)} link.")
    else:
        await balas(update, context,
                    "❌ Aksi tidak dikenal. Pakai:\n"
                    "<code>/forcejoin on|off</code>\n"
                    "<code>/forcejoin add @channel</code>\n"
                    "<code>/forcejoin del @channel</code>",
                    parse_mode="HTML")
        return

    if aksi:
        await _fj_tampilkan(update, context)


@owner_only
@banned_guard
async def tombol_forcejoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""
    fj = load_force_join()

    if data == "fj_toggle":
        if not fj["enabled"] and not fj["chats"]:
            await aman_answer(query, "Tambahkan link dulu via /forcejoin add",
                              show_alert=True)
            return
        baru = not fj["enabled"]
        save_force_join(baru, fj["chats"])
        await aman_answer(query, "🟢 Force join AKTIF!" if baru
                          else "🔴 Force join MATI!")
        await kirim_atau_edit(query, teks_forcejoin_panel(),
                              _kb_ptb(spec_forcejoin_panel()),
                              spec_forcejoin_panel())
        logger.info("🔐 Owner %s %s force join.", user.id,
                    "mengaktifkan" if baru else "menonaktifkan")
        return

    if data == "fj_add":
        await aman_answer(
            query,
            "Kirim pesan biasa:\n/forcejoin add @channel\n"
            "contoh: /forcejoin add t.me/channelku", show_alert=True)
        return

    if data.startswith("fj_del::"):
        target = data[len("fj_del::"):].strip().lower()
        chats = [c for c in fj["chats"] if str(c).lower() != target]
        if len(chats) == len(fj["chats"]):
            await aman_answer(query, "Sudah terhapus.", show_alert=True)
            return
        save_force_join(fj["enabled"], chats)
        await aman_answer(query, "🗑 Link dihapus.")
        await kirim_atau_edit(query, teks_forcejoin_panel(),
                              _kb_ptb(spec_forcejoin_panel()),
                              spec_forcejoin_panel())
        return

    await aman_answer(query)


# ==================== ERROR HANDLER ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    pesan = str(err)

    if "Query is too old" in pesan or "query id is invalid" in pesan:
        logger.warning("⚠️ Query too old (diabaikan)")
        return
    if "Message is not modified" in pesan:
        return
    if "Message to delete not found" in pesan:
        return

    logger.error("❌ Error: %s", err)


# ==================== MAIN ====================

async def _post_init(app):
    await rich_ui.deteksi_rich(config.BOT_TOKEN)

    # Sinkronkan nama bot di Telegram dengan BOT_NAME (ZHEE).
    try:
        await app.bot.set_my_name(BOT_DISPLAY)
        logger.info("🤖 Nama bot diset: %s", BOT_DISPLAY)
    except Exception as e:
        logger.warning("Gagal set nama bot: %s", e)

    # Daftarkan perintah, termasuk /speed khusus owner.
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Buka dashboard"),
            BotCommand("help", "Panduan bot"),
            BotCommand("cek", "Deteksi nomor"),
        ])
        if config.OWNER_ID:
            await app.bot.set_my_commands(
                [
                    BotCommand("addprem", "Tambah premium"),
                    BotCommand("delprem", "Hapus premium"),
                    BotCommand("ban", "Ban user"),
                    BotCommand("unban", "Unban user"),
                    BotCommand("bc", "Broadcast pesan"),
                    BotCommand("speed", "Atur kecepatan cek nomor"),
                    BotCommand("forcejoin", "Atur link & on/off force join"),
                ],
                scope=BotCommandScopeChat(chat_id=int(config.OWNER_ID)),
            )
    except Exception as e:
        logger.warning("Gagal set command menu: %s", e)


def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "ISI_TOKEN_BOT_BARU_DI_SINI":
        print("❌ Set BOT_TOKEN di config.py dulu!")
        return

    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(_post_init).build()

    # Command user
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cek", cek_cmd))

    # Command admin
    app.add_handler(CommandHandler("addprem", addprem_cmd))
    app.add_handler(CommandHandler("delprem", delprem_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("bc", bc_cmd))
    app.add_handler(CommandHandler("speed", speed_cmd))
    app.add_handler(CommandHandler("forcejoin", forcejoin_cmd))

    # Tombol inline
    app.add_handler(CallbackQueryHandler(tombol_detek, pattern="^detek$"))
    app.add_handler(CallbackQueryHandler(tombol_admin, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(tombol_menu_awal, pattern="^menu_awal$"))
    app.add_handler(CallbackQueryHandler(tombol_cek_join, pattern="^cek_join$"))
    app.add_handler(CallbackQueryHandler(tombol_speed,
                                         pattern=r"^speed_(set_|kustom)"))
    app.add_handler(CallbackQueryHandler(tombol_forcejoin,
                                         pattern=r"^fj_(toggle|add|del::)"))
    app.add_handler(CallbackQueryHandler(tombol_admin, pattern="^fj_panel$"))

    # Error handler
    app.add_error_handler(error_handler)

    # Auto backup
    if config.BACKUP_ENABLED and config.OWNER_ID and app.job_queue:
        interval_detik = config.BACKUP_INTERVAL_HOURS * 3600
        first_delay = getattr(config, "BACKUP_FIRST_DELAY", 30)
        app.job_queue.run_repeating(
            job_backup,
            interval=interval_detik,
            first=first_delay,
            name="auto_backup",
        )
        print(f"📦 Auto backup aktif tiap {config.BACKUP_INTERVAL_HOURS} jam.")

    print("✅ Bot jalan... Tekan Ctrl+C untuk stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
