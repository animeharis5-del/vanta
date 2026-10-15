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
# Mapping seluruh custom emoji dari pack_tgmacicons.txt. ID duplikat memakai entri pertama.
TG_EMOJI_MAP = {
    '✈️': '5258073068852485953',
    '🔢': '5226513232549664618',
    '🖼': '5258050709252743821',
    '👤': '5258362837411045098',
    '⭐️': '5258185631355378853',
    '📂': '5258514780469075716',
    '❌': '5258226313285607065',
    '⚽️': '5258169263235013408',
    '🐻': '5258145898612924124',
    '📝': '5257965174979042426',
    '🪙': '5258368777350816286',
    '⚡️': '5258152182150077732',
    '📖': '5258328383183396223',
    '🤖': '5258093637450866522',
    '💼': '5258260149037965799',
    '👨\u200d🎨': '5258450450448915742',
    '🗓': '5258105663359294787',
    '🤙': '5258337316715373336',
    '📸': '5258205968025525531',
    '👩\u200d🎨': '5258215635996908355',
    '📣': '5260268501515377807',
    '✅': '5260726538302660868',
    '⛓': '5260730055880876557',
    '📄': '5258477770735885832',
    '©': '5258507474729704350',
    '👥': '5258513401784573443',
    '🗑': '5258130763148172425',
    '✍️': '5258331647358540449',
    '↔️': '5260233433107407649',
    '🎭': '5258430848218176413',
    '📁': '5257965810634202885',
    '➡️': '5260450573768990626',
    '🎮': '5258508428212445001',
    '🎓': '5258334872878980409',
    '❤️': '5258179403652801593',
    '🏘': '5257963315258204021',
    '🚪': '5258084656674250503',
    '💡': '5258216851472654189',
    '📍': '5258509201306557640',
    '🔒': '5258476306152038031',
    '💬': '5258215846450305872',
    '🌘': '5258011861273551368',
    '🎵': '5258289810082111221',
    '🔕': '5260264520080695245',
    '🎶': '5258334469152054985',
    '↗️': '5257991477358763590',
    '📌': '5258461531464539536',
    '➕': '5258108352008823107',
    '🍑': '5258330865674494479',
    '🔫': '5260221883940347555',
    '👏': '5258501105293205250',
    '🔄': '5258420634785947640',
    '🌠': '5258212268742549391',
    '🔃': '5260687681733533075',
    '⬅️': '5258236805890710909',
    '❗️': '5258474669769497337',
    '💎': '5280962371207077415',
    '🤚': '5260249440450520061',
    '🗳': '5258200019495821936',
    '⬇️': '5258336354642697821',
    '🕔': '5258419835922030550',
    '⏲': '5258258882022612173',
    '👀': '5260341314095947411',
    '☁️': '5280867942056108177',
    '⬆️': '5260652420052032852',
    '🔼': '5260379144167890225',
    '💻': '5258423306255604960',
    'ℹ️': '5258503720928288433',
    '🙂': '5258262708838472996',
    '🔇': '5258267368877989660',
    '📈': '5258391025281408576',
    '☀️': '5258089153505009279',
    '📚': '5260512129240276089',
    '📦': '5258134813302332906',
    '✋': '5258362429389152256',
    '📹': '5258077307985207053',
    '📞': '5258020476977946656',
    '📼': '5258391252914676042',
    '🙃': '5258318251355545562',
    '🕘': '5199457120428249992',
    '🎙': '5260652149469094137',
    '💰': '5258204546391351475',
    '⚙': '5258096772776991776',
    '♾': '5271934788037517525',
    '🔊': '5260325873688518261',
    '📰': '5249231689695115145',
    '🏷': '5296348778012361146',
    '🔎': '5429571366384842791',
    '👁': '5253959125838090076',
    '⛔️': '5275969776668134187',
    '🔞': '5325604415900504150',
    '🍴': '5296727963495079440',
    '🔖': '5359629206948976159',
    # ── ID dari file OTP (dicocokkan makna, bukan asal tempel) ──
    '✨': '5890925363067886150',    # Sparkle (sapaan) — placeholder harus emoji asli
    '📊': '5350613306090482956',   # Graph (statistik)
    '🌐': '5776233299424843260',   # Globe (network)
    '🔷': '5226513232549664618',    # Option (menu) — placeholder harus emoji asli
    '⚠️': '5447644880824181073',   # Warning
    '⚙️': '5350725709679584478',   # Gear (admin)
    '🚫': '5875450995332353523',   # Slash (dilarang)
    '⏳': '5116159438062879454',   # Loading
    '⏱': '5350595795508814391',    # Clock (durasi)
    '🛟': '5258337316715373336',   # Call (hubungi pengelola)
    '👤': '5260399854500191689',   # User (profil) — ganti ID pack lama
    '👥': '5944970130554359187',   # Referral/people — ganti ID pack lama
    '✅': '5123163417326126159',   # Success — ganti ID pack lama
    '❌': '5121063440311386962',   # Cancel — ganti ID pack lama
    '🔄': '5127377673596700174',   # Refresh — ganti ID pack lama
    '💎': '6028530359975548369',   # Diamond (akun) — ganti ID pack lama
}
