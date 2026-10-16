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


# Telegram Premium Custom Emoji IDs (opsional).
# Isi dengan ID custom emoji milik Anda; kosongkan jika belum punya.
# Format ID harus angka dari Telegram, bukan emoji Unicode biasa.
# Sumber referensi ID: pack_tgmacicons.txt (hanya ID yang terbukti valid dipakai bot).
TG_EMOJI_MAP = {
    # ── Daftar custom emoji yang TERBUKTI VALID dipakai bot (pack milik akun
    #    premium bot). ID di luar daftar ini akan ditampilkan mentah oleh
    #    Telegram sebagai <tg-emoji ...> — jadi jangan asal tempel ID. ──
    '✅': '5123163417326126159',   # Success
    '❌': '5121063440311386962',   # Cancel
    '⚠️': '5447644880824181073',   # Warning
    '🚫': '5875450995332353523',   # Slash (dilarang)
    '⏳': '5116159438062879454',   # Loading
    '⏱': '5350595795508814391',    # Clock (durasi)
    '🔄': '5127377673596700174',   # Refresh
    '✨': '5890925363067886150',   # Sparkle (sapaan)
    '📊': '5350613306090482956',   # Graph (statistik)
    '🌐': '5776233299424843260',   # Globe (network)
    '🔷': '5226513232549664618',   # Option (menu)
    '⚙️': '5350725709679584478',   # Gear (admin)
    '💎': '6028530359975548369',   # Diamond (akun)
    '🛟': '5258337316715373336',   # Call (bantuan)
    '👤': '5260399854500191689',   # User (profil)
    '👥': '5944970130554359187',   # People/referral
    'ℹ️': '5258503720928288433',   # Info
    '🔒': '5258476306152038031',   # Lock
    '📣': '5260268501515377807',   # Megaphone (broadcast)
    '📚': '5260512129240276089',   # Books (panduan)
}

