# config.py — pengaturan bot

BOT_TOKEN = "8592901951:AAHzd2PKkGI96a1nM1q6LurEva7E1VOOgIQ"
OWNER_ID = 8684272520

# Nama bot — dipakai di tampilan & otomatis disinkronkan ke Telegram saat start.
BOT_NAME = "ZHEE"

# ============================================
#      KECEPATAN PENGECEKAN NOMOR
# ============================================
# Owner bisa mengganti nilainya lewat perintah /speed di bot (tersimpan
# di speed.json, dibaca ulang setiap pengecekan). Nilai awal di sini
# dipakai kalau speed.json belum ada.
#   bulk_delay : jeda antar nomor (detik) — makin kecil makin cepat
#   max_paralel: jumlah nomor yang dicek bersamaan (1-10)
SPEED_DEFAULT = {
    "bulk_delay": 3.0,
    "max_paralel": 3,
}
SPEED_FILE = "speed.json"

NOMOR_DEFAULT = "+6285801288461"
STATS_FILE = "stats.json"
PREMIUM_FILE = "premium.json"
BANNED_FILE = "user_banned.json"

# Foto buat /start (kosongin kalau gak mau foto)
START_PHOTO_URL = "https://cdn.nekohime.site/file/fej4ycv5.jpg"

# ============================================
#           FORCE JOIN CHANNEL/GRUP
# ============================================
# Isi dengan @username channel/grup, contoh: "@channelku"
# Bisa lebih dari satu, tinggal tambah di list.
# Kosongin list ([]) kalau gak mau force join.
FORCE_JOIN = [
     "",
     ""
]

# Force join bisa dihidupkan/matikan & linknya diatur owner lewat /forcejoin
# di bot (tersimpan di force_join.json, dibaca ulang tiap perintah).
# Nilai FORCE_JOIN_ENABLED awal di sini dipakai kalau file belum ada.
FORCE_JOIN_ENABLED = True
FORCE_JOIN_FILE = "force_join.json"

# ============================================
#        SETTINGAN USER BIASA (GRATIS)
# ============================================
USER_BIASA = {
    "max_bulk": 20,
    "cooldown": 10,
    "method": ["wa_old"],
    # bulk_delay dikosongkan -> otomatis pakai SPEED_DEFAULT / settingan /speed owner
    # (isi angka di sini cuma kalau mau memaksa nilai tetap per tier)
}

# ============================================
#        SETTINGAN USER PREMIUM
# ============================================
USER_PREMIUM = {
    "max_bulk": 50,
    "cooldown": 0,
    "method": ["wa_old"],
    # bulk_delay dikosongkan -> otomatis pakai SPEED_DEFAULT / settingan /speed owner
}


# ============================================
#           AUTO BACKUP
# ============================================
BACKUP_ENABLED = True          # True/False
BACKUP_INTERVAL_HOURS = 24    # tiap 6 jam
BACKUP_FIRST_DELAY = 30       # backup pertama 30 detik setelah start


# Telegram Premium Custom Emoji (OPSIONAL).
#
# MASALAH SEBELUMNYA: tag <tg-emoji emoji-id="..."> tampil MENTAH di chat
# (contoh: <tg-emoji emoji-id="5447644880824181073">⚠️</tg-emoji>).
# Penyebab: ID custom emoji hanya bisa dipakai oleh akun yang MEMILIKI pack
# tersebut. ID hasil "extractor" dari pack orang lain (tgmacicons) tidak
# dikenal server Telegram untuk akun bot, sehingga tag tidak dirender dan
# client menampilkan teks mentahnya.
#
# Solusi: matikan custom emoji (pakai emoji Unicode standar -> selalu tampil
# normal di semua device). Kalau nanti bot dipindah ke akun premium yang
# memiliki pack sendiri, isi TG_EMOJI_MAP dengan ID milik akun itu dan set
# TG_EMOJI_CUSTOM = True.
TG_EMOJI_CUSTOM = False

TG_EMOJI_MAP = {}

