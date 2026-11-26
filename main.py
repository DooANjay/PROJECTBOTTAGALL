import os, asyncio, time, json, re, random, html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, UserNotParticipantError

try:
    API_ID = int(os.environ.get("API_ID"))
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    OWNER_ID = int(os.environ.get("OWNER_ID"))
    TARGET_GROUP_ID = int(os.environ.get("TARGET_GROUP_ID"))
    LOG_GROUP_ID = int(os.environ.get("LOG_GROUP_ID"))
    LOG_TOPIC_ID = int(os.environ.get("LOG_TOPIC_ID", 0))
    PUBLIC_GROUP_LINK = os.environ.get("PUBLIC_GROUP_LINK", "").strip()
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "admin")
except (TypeError, ValueError):
    print("❌ ERROR: Periksa kembali variabel di Railway!")
    exit(1)

bot = TelegramClient('bot_official_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
FILE_DB = "partners_database.json"
tagall_queue = asyncio.Queue()
is_processing = False
stop_current_tagall = False
TZ = ZoneInfo("Asia/Jakarta")
TMO_FILE = "tmo_schedule.json"
MANUAL_TAGALL = {}
MANUAL_TAGALL_IDS = {}
MANUAL_TAGALL_COOLDOWN = {}

add_pt_state = {}

# Variabel Emoji Premium
E_SPARKLE = "<emoji id='5472164874886846699'>✨</emoji>"
E_CARD    = "<emoji id='5445353829304387411'>💳</emoji>"
E_ARROW   = "<emoji id='5429651785352501917'>↗️</emoji>"
E_TIME    = "<emoji id='5382194935057372936'>⏱️</emoji>"
E_CLOVER  = "<emoji id='5305699699204837855'>🍀</emoji>"
E_CAL     = "<emoji id='5274055917766202507'>🗓</emoji>"
E_BOT     = "<emoji id='5226893221191237996'>👾</emoji>"

PREM_MENTION_EMOJIS = [
    E_SPARKLE, E_CARD, E_ARROW, E_TIME, E_CLOVER, E_CAL, E_BOT
]

def get_log_topic():
    return LOG_TOPIC_ID if LOG_TOPIC_ID > 0 else None

async def send_to_log(text, buttons=None, link_preview=False):
    return await bot.send_message(
        LOG_GROUP_ID,
        text,
        parse_mode='html',
        link_preview=link_preview,
        buttons=buttons,
        reply_to=get_log_topic()
    )

async def reply_in_topic(event, text, buttons=None, link_preview=False, file=None):
    reply_target = None
    if not event.is_private:
        reply_target = event.reply_to_msg_id or event.id
    return await bot.send_message(
        event.chat_id,
        text,
        parse_mode='html',
        link_preview=link_preview,
        buttons=buttons,
        file=file,
        reply_to=reply_target
    )

async def get_public_group_entity():
    if PUBLIC_GROUP_LINK:
        try:
            return await bot.get_entity(PUBLIC_GROUP_LINK)
        except Exception:
            pass
    return await bot.get_entity(TARGET_GROUP_ID)

async def get_public_join_url():
    if PUBLIC_GROUP_LINK:
        if PUBLIC_GROUP_LINK.startswith("http"):
            return PUBLIC_GROUP_LINK
        return f"https://t.me/{PUBLIC_GROUP_LINK.lstrip('@')}"
    try:
        entity = await bot.get_entity(TARGET_GROUP_ID)
        if getattr(entity, 'username', None):
            return f"https://t.me/{entity.username}"
        from telethon.tl.functions.messages import ExportChatInviteRequest
        invite = await bot(ExportChatInviteRequest(TARGET_GROUP_ID))
        return invite.link
    except Exception:
        return "https://t.me/"

async def check_user_joined(user_id):
    if user_id == OWNER_ID:
        return True
    try:
        entity = await get_public_group_entity()
        # Metode 1: Cek langsung keanggotaan via get_permissions
        try:
            perms = await bot.get_permissions(entity, user_id)
            if perms and not getattr(perms, 'is_banned', False):
                return True
        except UserNotParticipantError:
            return False
        except Exception:
            pass

        # Metode 2 (Cadangan): Cek via iter_participants
        async for member in bot.iter_participants(entity, limit=200):
            if member.id == user_id:
                return True
        return False
    except Exception as e:
        print(f"[WARN] Gagal cek status join user {user_id}: {e}")
        # Jika bot gagal mengakses info grup karena pembatasan API, loloskan agar tidak stuck
        return True

def build_log_start(a, b, c, d, e, f):
    clean_f = html.escape(f).replace('\n', '\n&gt; ')
    res = (
        f"&gt; {E_BOT} <b>USER :</b> @{html.escape(str(b))}\n"
        f"&gt; {E_CARD} <b>USER ID :</b> <code>{c}</code>\n"
        f"&gt; {E_TIME} <b>DURASI :</b> 5m\n"
        f"&gt; {E_CAL} <b>WAKTU :</b> {d}\n"
        f"&gt; {E_CLOVER} <b>PARTNER :</b> {html.escape(str(e))}\n\n"
        f"&gt; {E_SPARKLE} <b>TEKS TAGALL :</b>\n"
        f"&gt; {clean_f}"
    )
    return res

def build_log_done(a, b, c, d, e):
    clean_e = html.escape(e).replace('\n', '\n&gt; ')
    res = (
        f"&gt; {E_BOT} <b>PENGIRIM :</b> {html.escape(str(a))}\n"
        f"&gt; {E_ARROW} <b>LINK :</b> {html.escape(str(b))}\n"
        f"&gt; {E_SPARKLE} <b>STATUS :</b> {html.escape(str(c))}\n"
        f"&gt; {E_CAL} <b>WAKTU SELESAI :</b> {d}\n\n"
        f"&gt; <b>PESAN TERAKHIR :</b>\n"
        f"&gt; {clean_e}"
    )
    return res

def build_struk(sender_name, partner_name, link, member_count, pj1, pj2, bot_name, ch_link):
    res = (
        f"{E_SPARKLE} ✅ <b>Tagall selesai!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{E_BOT} Pengirim: <b>{html.escape(str(sender_name))}</b>\n"
        f"{E_CLOVER} Partner: <b>{html.escape(str(partner_name).upper())}</b>\n"
        f"{E_ARROW} Link: {html.escape(str(link))}\n"
        f"{E_CARD} Member di-tag: <code>{member_count}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{E_SPARKLE} <b>Jangan lupa SS hasil tagall-nya!</b>"
    )
    return res

DAY_NAMES = {
    "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
    "jumat": 4, "sabtu": 5, "minggu": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6
}
DEFAULT_TMO = {"days": [0, 2, 3, 4], "start": "19:30", "end": "20:30"}

def load_tmo_schedule():
    if os.path.exists(TMO_FILE):
        try:
            with open(TMO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("days") and data.get("start") and data.get("end"):
                return data
        except Exception:
            pass
    return dict(DEFAULT_TMO)

def save_tmo_schedule(data):
    with open(TMO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

TMO_SCHEDULE = load_tmo_schedule()

CLOSE_AUTO_FILE = "tagall_close_days.json"
DEFAULT_CLOSE_AUTO = {"days": []}

def load_close_auto():
    if os.path.exists(CLOSE_AUTO_FILE):
        try:
            with open(CLOSE_AUTO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("days"), list):
                return {"days": sorted(set(int(d) for d in data["days"] if 0 <= int(d) <= 6))}
        except Exception:
            pass
    return dict(DEFAULT_CLOSE_AUTO)

def save_close_auto(data):
    with open(CLOSE_AUTO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

CLOSE_AUTO_SCHEDULE = load_close_auto()

def auto_tagall_closed(now=None):
    now = now or datetime.now(TZ)
    return now.weekday() in CLOSE_AUTO_SCHEDULE.get("days", [])

def close_auto_days_text(days):
    return tmo_days_text(days) if days else "Tidak ada (nonaktif)"

def parse_hhmm(value):
    return datetime.strptime(value, "%H:%M").time()

def tmo_status(now=None):
    now = now or datetime.now(TZ)
    days = TMO_SCHEDULE.get("days", [])
    start = parse_hhmm(TMO_SCHEDULE.get("start", "19:30"))
    end = parse_hhmm(TMO_SCHEDULE.get("end", "20:30"))
    if now.weekday() in days and start <= now.time() < end:
        end_dt = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        return True, end_dt
    return False, None

async def wait_until_tmo_ends():
    while True:
        active, end_dt = tmo_status()
        if not active:
            return
        seconds = max(1, (end_dt - datetime.now(TZ)).total_seconds())
        await asyncio.sleep(min(seconds, 60))

def tmo_days_text(days):
    names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    return ", ".join(names[d] for d in days)

def load_partners():
    if os.path.exists(FILE_DB):
        try:
            with open(FILE_DB, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_partners(data):
    with open(FILE_DB, "w") as f: json.dump(data, f, indent=4)

PARTNERS_DICT = load_partners()
print("⚡ Bot Siap!")

def get_menu_buttons():
    return [
        [Button.inline("🚀 Mulai Tagall", data="menu_tagall")],
        [Button.inline("🤝 Minta PT-an (Partner)", data="menu_mitra")],
        [Button.inline("ℹ️ Info Lainnya", data="menu_info")]
    ]

@bot.on(events.NewMessage(pattern=r'(?i)^/(start)'))
async def start_command(event):
    if not event.is_private: return
    welcome_text = (
        f"{E_BOT} <b>Halo! Selamat datang di Bot Tagall Official</b> {E_SPARKLE}\n\n"
        f"&gt; {E_ARROW} Silakan pilih menu layanan di bawah ini untuk memulai atau mendapatkan informasi lebih lanjut:"
    )
    await event.respond(welcome_text, buttons=get_menu_buttons(), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'(?i)^/menu'))
async def menu_command(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    commands_text = (
        f"{E_BOT} <b>DAFTAR PERINTAH BOT TAGALL</b>\n\n"
        f"{E_SPARKLE} <b>Perintah Umum (PM Bot):</b>\n"
        "&gt; <code>/start</code> - Menampilkan pesan selamat datang dan menu interaktif\n\n"
        f"{E_CARD} <b>Perintah Admin/Owner (Log Group &amp; PM Bot):</b>\n"
        "&gt; <code>/menu</code> - Menampilkan daftar perintah ini\n"
        "&gt; <code>/lpt</code> - Membuka panel manajemen data partner (PT)\n"
        "&gt; <code>/backup</code> - Mengunduh file cadangan database setelan bot\n"
        "&gt; <code>/restore</code> - Membalas (reply) file database untuk memulihkan data\n"
        "&gt; <code>/cancel</code> - Membatalkan proses input/edit partner yang sedang berjalan\n"
        "&gt; <code>/end</code> - Menghentikan paksa proses tagall yang sedang berlangsung\n"
        "&gt; <code>/tmoset</code> - Melihat/mengatur jadwal TMO (contoh: /tmoset Senin,Rabu 19:30-20:30)\n"
        "&gt; <code>/tmooff</code> - Menonaktifkan jadwal TMO\n"
        "&gt; <code>/closeautoset</code> - Melihat/mengatur hari tagall ditutup otomatis\n"
        "&gt; <code>/closeautooff</code> - Menonaktifkan penutupan otomatis\n"
        "&gt; <code>/tagall</code> - Tagall manual di grup publik dengan pilihan durasi"
    )
    await reply_in_topic(event, commands_text)

# FITUR BACKUP DATABASE
@bot.on(events.NewMessage(pattern=r'(?i)^/backup'))
async def backup_command(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    
    if not os.path.exists(FILE_DB) or os.path.getsize(FILE_DB) == 0:
        return await reply_in_topic(event, "⚠️ <b>Database kosong atau tidak ditemukan!</b>")
    
    try:
        await reply_in_topic(
            event,
            f"{E_CARD} <b>BACKUP DATABASE BOT</b>\n\n&gt; {E_CAL} Berikut adalah file cadangan setelan data partner terbaru:",
            file=FILE_DB
        )
    except Exception as e:
        await reply_in_topic(event, f"❌ Gagal mengirim file backup: <code>{html.escape(str(e))}</code>")

# FITUR RESTORE DATABASE
@bot.on(events.NewMessage(pattern=r'(?i)^/restore'))
async def restore_command(event):
    global PARTNERS_DICT
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    
    reply = await event.get_reply_message()
    if not reply or not reply.file:
        return await reply_in_topic(event, "⚠️ <b>Mohon reply (balas) file dokumen backup <code>.json</code></b> yang ingin direstore menggunakan perintah <code>/restore</code>.")
    
    if not reply.file.name or not reply.file.name.endswith('.json'):
        return await reply_in_topic(event, "⚠️ File yang direply bukan format <code>.json</code> yang valid!")
    
    download_path = "temp_restore.json"
    try:
        await reply.download_media(file=download_path)
        
        with open(download_path, "r", encoding="utf-8") as f:
            new_data = json.load(f)
            
        if not isinstance(new_data, dict):
            if os.path.exists(download_path): os.remove(download_path)
            return await reply_in_topic(event, "⚠️ Format struktur data dalam file JSON tidak valid.")
            
        with open(FILE_DB, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)
            
        PARTNERS_DICT = load_partners()
        if os.path.exists(download_path): os.remove(download_path)
        
        await reply_in_topic(
            event,
            f"{E_SPARKLE} <b>RESTORE DATABASE BERHASIL!</b>\n\n"
            f"&gt; {E_CLOVER} Total data partner yang dimuat ulang: <code>{len(PARTNERS_DICT)}</code> data.\n"
            f"&gt; {E_ARROW} Silakan cek kembali menggunakan <code>/lpt</code>."
        )
    except Exception as e:
        if os.path.exists(download_path): os.remove(download_path)
        await reply_in_topic(event, f"❌ Gagal memproses restore database: <code>{html.escape(str(e))}</code>")

@bot.on(events.CallbackQuery(pattern=r'^check_fsub$'))
async def callback_check_fsub(event):
    joined = await check_user_joined(event.sender_id)
    if joined:
        await event.answer("✅ Terverifikasi! Anda sudah bergabung. Silakan kirim ulang pesan tagall Anda.", alert=True)
        await event.edit(
            f"{E_SPARKLE} <b>VERIFIKASI BERHASIL!</b>\n\n"
            f"&gt; {E_ARROW} Akun Anda sudah terdeteksi bergabung di grup publik.\n"
            f"&gt; {E_CLOVER} Silakan kirim ulang pesan berisi link partner Anda untuk memulai tagall.",
            buttons=None,
            parse_mode='html'
        )
    else:
        await event.answer("❌ Anda belum terdeteksi bergabung di grup publik! Silakan klik tombol Join Grup terlebih dahulu.", alert=True)

@bot.on(events.CallbackQuery(pattern=r'^menu_.*'))
async def callback_menu(event):
    data = event.data.decode()
    if data == "menu_tagall":
        text = (
            f"{E_ARROW} <b>Cara Memulai Tagall:</b>\n\n"
            f"&gt; {E_SPARKLE} Pastikan Anda sudah bergabung ke <b>Grup Publik</b> resmi kami.\n"
            f"&gt; {E_CLOVER} Kirimkan pesan teks yang berisi <b>Link Partner/Grup</b> yang sudah terdaftar secara resmi di bot ini.\n"
            "&gt;\n"
            f"&gt; {E_TIME} Bot akan otomatis memverifikasi keanggotaan dan link tersebut lalu memasukkannya ke antrian."
        )
    elif data == "menu_mitra":
        text = (
            f"{E_CLOVER} <b>Pengajuan Kemitraan (PT-an):</b>\n\n"
            "&gt; Untuk mendaftarkan grup Anda sebagai partner resmi, silakan hubungi owner bot melalui username di bawah ini:\n"
            "&gt;\n"
            f"&gt; {E_BOT} <b>Owner:</b> @{OWNER_USERNAME}\n"
            "&gt;\n"
            f"&gt; {E_CARD} Kirimkan format pendaftaran kepada admin agar link Anda terdata di database sistem."
        )
    elif data == "menu_info":
        text = (
            f"{E_SPARKLE} <b>Informasi Bot &amp; Aturan:</b>\n\n"
            f"&gt; {E_BOT} Bot ini berjalan otomatis menggunakan sistem antrian (Queue).\n"
            f"&gt; {E_TIME} Setiap sesi tagall dibatasi durasi maksimal 5 menit demi keamanan grup.\n"
            f"&gt; {E_CAL} Pesan tagall sampah akan otomatis dibersihkan secara berkala oleh bot."
        )
    elif data == "menu_back":
        welcome_text = (
            f"{E_BOT} <b>Halo! Selamat datang di Bot Tagall Official</b> {E_SPARKLE}\n\n"
            f"&gt; {E_ARROW} Silakan pilih menu layanan di bawah ini untuk memulai atau mendapatkan informasi lebih lanjut:"
        )
        await event.edit(welcome_text, buttons=get_menu_buttons(), parse_mode='html')
        return
    await event.edit(text, buttons=[[Button.inline("🔙 Kembali", data="menu_back")]], parse_mode='html')

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_command(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    user_id = event.sender_id
    if user_id in add_pt_state:
        del add_pt_state[user_id]
        await reply_in_topic(event, "❌ <b>Proses penginputan/pengeditan data partner telah dibatalkan.</b>")
    else:
        await reply_in_topic(event, f"{E_TIME} Tidak ada proses penginputan partner yang sedang aktif.")

def build_partner_page(page=1):
    keys = list(PARTNERS_DICT.keys())
    total_items = len(keys)
    items_per_page = 10
    total_pages = (total_items + items_per_page - 1) // items_per_page
    if total_pages == 0: total_pages = 1
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_keys = keys[start_idx:end_idx]
    
    if not keys:
        return (
            f"{E_CLOVER} <b>PANEL LAYANAN PARTNER</b>\n\n&gt; {E_CARD} Status database: Kosong!", 
            [[Button.inline("➕ Tambah PT Baru", data="pt_add_start")], [Button.inline("🔴 Tutup Panel", data="panel_close")]]
        )
    
    txt = (
        f"{E_CLOVER} <b>PANEL LAYANAN PARTNER</b>\n\n"
        f"&gt; {E_ARROW} Silakan pilih salah satu partner aktif dari list halaman <b>[{page}/{total_pages}]</b> di bawah ini untuk mengelola data:"
    )
    buttons = []
    
    for i, l in enumerate(page_keys, start=start_idx + 1):
        p_data = PARTNERS_DICT[l]
        n = p_data.get("nama", "Tanpa Nama") if isinstance(p_data, dict) else p_data
        buttons.append([Button.inline(f"{i}. {n.upper()}", data=f"pt_manage_{i-1}")])
        
    nav_row = []
    if page > 1:
        nav_row.append(Button.inline("◀️", data=f"pt_page_{page-1}"))
    else:
        nav_row.append(Button.inline("◀️", data="pt_page_noop"))
        
    nav_row.append(Button.inline(f"[{page}/{total_pages}]", data="pt_page_noop"))
    
    if page < total_pages:
        nav_row.append(Button.inline("▶️", data=f"pt_page_{page+1}"))
    else:
        nav_row.append(Button.inline("▶️", data="pt_page_noop"))
        
    buttons.append(nav_row)
    buttons.append([Button.inline("➕ Tambah PT Baru", data="pt_add_start")])
    buttons.append([Button.inline("🔴 Tutup Panel", data="panel_close")])
    
    return txt, buttons

@bot.on(events.NewMessage(pattern=r'(?i)^/lpt'))
async def list_partner(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    txt, buttons = build_partner_page(1)
    await reply_in_topic(event, txt, buttons=buttons, link_preview=False)

@bot.on(events.CallbackQuery(pattern=r'^pt_page_.*'))
async def callback_pt_page(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    data = parts[2]
    if data == "noop": return await event.answer()
    page = int(data)
    txt, buttons = build_partner_page(page)
    await event.edit(txt, buttons=buttons, link_preview=False, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^panel_close$'))
async def callback_panel_close(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    await event.edit(f"&gt; {E_BOT} <b>Panel layanan partner telah ditutup.</b>", buttons=None, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_manage_\d+$'))
async def callback_manage_partner(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    idx = int(parts[2])
    keys = list(PARTNERS_DICT.keys())
    if 0 <= idx < len(keys):
        l = keys[idx]
        pd = PARTNERS_DICT[l]
        if not isinstance(pd, dict):
            pd = {"nama": pd, "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
            
        txt = (
            f"{E_SPARKLE} <b>PILIH BAGIAN YANG INGIN DIUBAH:</b>\n\n"
            f"&gt; {E_CLOVER} <b>Nama GC :</b> {html.escape(str(pd.get('nama', '-')))}\n"
            f"&gt; {E_ARROW} <b>Link GC :</b> {html.escape(str(l))}\n"
            f"&gt; {E_BOT} <b>Nama Bot :</b> {html.escape(str(pd.get('bot', '-')))}\n"
            f"&gt; {E_CARD} <b>Link CH :</b> {html.escape(str(pd.get('ch', '-')))}\n"
            f"&gt; 👮 <b>PJ 1 :</b> {html.escape(str(pd.get('pj1', '-')))}\n"
            f"&gt; 👮 <b>PJ 2 :</b> {html.escape(str(pd.get('pj2', '-')))}"
        )
        buttons = [
            [Button.inline("👆 Edit Nama GC", data=f"pt_edit_nama_{idx}"), Button.inline("👆 Edit Link GC", data=f"pt_edit_link_{idx}")],
            [Button.inline("👆 Edit Bot", data=f"pt_edit_bot_{idx}"), Button.inline("👆 Edit CH", data=f"pt_edit_ch_{idx}")],
            [Button.inline("👆 Edit PJ 1", data=f"pt_edit_pj1_{idx}"), Button.inline("👆 Edit PJ 2", data=f"pt_edit_pj2_{idx}")],
            [Button.inline("🔴 Hapus Partner", data=f"pt_delconf_{idx}"), Button.inline("❌ Kembali", data="pt_back_list")],
            [Button.inline("🔴 Tutup Panel", data="panel_close")]
        ]
        await event.edit(txt, buttons=buttons, link_preview=False, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_back_list$'))
async def callback_pt_back_list(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    txt, buttons = build_partner_page(1)
    await event.edit(txt, buttons=buttons, link_preview=False, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_delconf_\d+$'))
async def callback_delconf_partner(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    idx = int(parts[2])
    keys = list(PARTNERS_DICT.keys())
    if 0 <= idx < len(keys):
        l = keys[idx]
        p_data = PARTNERS_DICT[l]
        n = p_data.get("nama", p_data) if isinstance(p_data, dict) else p_data
        txt = (
            "⚠️ <b>KONFIRMASI PENGHAPUSAN</b>\n\n"
            f"&gt; Apakah Anda yakin ingin menghapus partner '<b>{html.escape(str(n).upper())}</b>' dari database secara permanen?"
        )
        buttons = [
            [Button.inline("✅ Ya, Hapus", data=f"pt_delfinal_{idx}")],
            [Button.inline("❌ Batalkan", data=f"pt_manage_{idx}")]
        ]
        await event.edit(txt, buttons=buttons, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_delfinal_\d+$'))
async def callback_delfinal_partner(event):
    global PARTNERS_DICT
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    idx = int(parts[2])
    keys = list(PARTNERS_DICT.keys())
    if 0 <= idx < len(keys):
        removed_name = PARTNERS_DICT[keys[idx]]
        if isinstance(removed_name, dict):
            removed_name = removed_name.get("nama", "Tanpa Nama")
        del PARTNERS_DICT[keys[idx]]
        save_partners(PARTNERS_DICT)
        await event.answer(f"🗑️ {removed_name.upper()} Berhasil Dihapus!", alert=True)
    txt, buttons = build_partner_page(1)
    await event.edit(txt, buttons=buttons, link_preview=False, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_edit_(nama|link|bot|ch|pj1|pj2)_\d+$'))
async def callback_trigger_edit(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    tipe = parts[2]
    idx = int(parts[3])
    
    add_pt_state[event.sender_id] = {"step": f"edit_{tipe}", "idx": idx}
    
    field_labels = {
        'nama': 'Nama Grup (GC) baru',
        'link': 'Link Grup (GC) baru berawalan http/t.me',
        'bot': 'Nama Bot baru',
        'ch': 'Link Channel (CH) baru',
        'pj1': 'Username Penanggung Jawab 1 (PJ 1) baru',
        'pj2': 'Username Penanggung Jawab 2 (PJ 2) baru'
    }
    
    txt = (
        f"{E_CARD} <b>MODE EDIT DATA PARTNER</b>\n\n"
        f"&gt; {E_ARROW} Silakan kirimkan data <b>{field_labels[tipe]}</b> melalui pesan chat untuk memperbarui partner ini.\n"
        f"&gt; <i>Ketik /cancel jika ingin membatalkan.</i>"
    )
    msg = await event.get_message()
    reply_target = msg.reply_to_msg_id if (not event.is_private and msg) else None
    await bot.send_message(event.chat_id, txt, parse_mode='html', reply_to=reply_target)
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r'^pt_add_start$'))
async def callback_add_start(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    add_pt_state[event.sender_id] = {"step": "input_nama"}
    txt = (
        f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 1/6)</b>\n\n"
        f"&gt; {E_ARROW} Silakan masukkan <b>Nama Partner (PT / Nama GC)</b>:\n"
        "&gt; <i>Ketik /cancel jika ingin membatalkan.</i>"
    )
    msg = await event.get_message()
    reply_target = msg.reply_to_msg_id if (not event.is_private and msg) else None
    await bot.send_message(event.chat_id, txt, parse_mode='html', reply_to=reply_target)
    await event.answer()

@bot.on(events.NewMessage(incoming=True))
async def handle_multistep_input(event):
    global PARTNERS_DICT
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    user_id = event.sender_id
    if user_id not in add_pt_state: return
    
    user_text = event.text.strip()
    if user_text.startswith("/cancel"): return
    
    state = add_pt_state[user_id]
    step = state.get("step")
    
    if step == "input_nama":
        state["nama"] = user_text
        state["step"] = "input_link"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 2/6)</b>\n\n"
            f"&gt; {E_ARROW} Masukkan <b>Link Partner (Link GC)</b> berawalan http atau t.me:"
        )
        await reply_in_topic(event, txt)
        
    elif step == "input_link":
        if not user_text.startswith(("http", "t.me")):
            return await reply_in_topic(event, "&gt; ⚠️ Link tidak valid! Harus diawali http atau t.me. Silakan kirim ulang:")
        if user_text in PARTNERS_DICT:
            return await reply_in_topic(event, "&gt; ⚠️ Link tersebut sudah terdaftar! Silakan kirim link lain:")
        state["link"] = user_text
        state["step"] = "input_bot"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 3/6)</b>\n\n"
            f"&gt; {E_BOT} Masukkan <b>Nama Bot</b> pendukung:"
        )
        await reply_in_topic(event, txt)
        
    elif step == "input_bot":
        state["bot"] = user_text
        state["step"] = "input_ch"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 4/6)</b>\n\n"
            f"&gt; {E_CARD} Masukkan <b>Link Channel (CH)</b>:"
        )
        await reply_in_topic(event, txt)
        
    elif step == "input_ch":
        state["ch"] = user_text
        state["step"] = "input_pj1"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 5/6)</b>\n\n"
            "&gt; 👮 Masukkan Username <b>Penanggung Jawab 1 (PJ 1)</b>:"
        )
        await reply_in_topic(event, txt)
        
    elif step == "input_pj1":
        state["pj1"] = user_text
        state["step"] = "input_pj2"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 6/6 - TERAKHIR)</b>\n\n"
            "&gt; 👮 Masukkan Username <b>Penanggung Jawab 2 (PJ 2)</b>:"
        )
        await reply_in_topic(event, txt)
        
    elif step == "input_pj2":
        state["pj2"] = user_text
        
        PARTNERS_DICT[state["link"]] = {
            "nama": state["nama"],
            "bot": state["bot"],
            "ch": state["ch"],
            "pj1": state["pj1"],
            "pj2": state["pj2"]
        }
        save_partners(PARTNERS_DICT)
        del add_pt_state[user_id]
        
        txt_done = (
            f"{E_SPARKLE} <b>PARTNER BERHASIL DITAMBAHKAN!</b>\n\n"
            f"&gt; {E_CLOVER} <b>Nama GC :</b> {html.escape(state['nama'])}\n"
            f"&gt; {E_ARROW} <b>Link GC :</b> {html.escape(state['link'])}\n"
            f"&gt; {E_BOT} <b>Bot :</b> {html.escape(state['bot'])}\n"
            f"&gt; {E_CARD} <b>CH :</b> {html.escape(state['ch'])}\n"
            f"&gt; 👮 <b>PJ 1 :</b> {html.escape(state['pj1'])}\n"
            f"&gt; 👮 <b>PJ 2 :</b> {html.escape(state['pj2'])}\n\n"
            "Silakan panggil kembali <code>/lpt</code> untuk melihat list."
        )
        await reply_in_topic(event, txt_done)

    elif step.startswith("edit_"):
        parts = step.split("_")
        tipe = parts[1]
        idx = state["idx"]
        keys = list(PARTNERS_DICT.keys())
        
        if 0 <= idx < len(keys):
            old_link = keys[idx]
            old_data = PARTNERS_DICT[old_link]
            
            if not isinstance(old_data, dict):
                old_data = {"nama": old_data, "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
                
            if tipe == "link":
                if not user_text.startswith(("http", "t.me")):
                    return await reply_in_topic(event, "&gt; ⚠️ Link tidak valid! Harus diawali http atau t.me. Silakan kirim ulang:")
                if user_text != old_link and user_text in PARTNERS_DICT:
                    return await reply_in_topic(event, "&gt; ⚠️ Link tersebut sudah terdaftar! Silakan kirim link lain:")
                del PARTNERS_DICT[old_link]
                PARTNERS_DICT[user_text] = old_data
            else:
                old_data[tipe] = user_text
                PARTNERS_DICT[old_link] = old_data
                
            save_partners(PARTNERS_DICT)
            del add_pt_state[user_id]
            
            txt_success = (
                f"{E_SPARKLE} <b>PERUBAHAN BERHASIL DISIMPAN!</b>\n\n"
                f"&gt; {E_CARD} Data <b>{tipe.upper()}</b> berhasil dimodifikasi. Silakan panggil ulang perintah <code>/lpt</code> untuk melihat pembaruan."
            )
            await reply_in_topic(event, txt_success)

@bot.on(events.NewMessage(pattern=r'(?i)^/end'))
async def end_tagall(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    global stop_current_tagall, is_processing
    if not is_processing:
        return await reply_in_topic(event, f"&gt; {E_TIME} Tidak ada proses tagall yang sedang berjalan.")
    stop_current_tagall = True
    await reply_in_topic(event, "&gt; 🛑 Menghentikan proses tagall saat ini...")

@bot.on(events.NewMessage(pattern=r"(?i)^/tmoset(?:\s+(.+))?$"))
async def tmo_set_command(event):
    global TMO_SCHEDULE
    if event.sender_id != OWNER_ID or (not event.is_private and event.chat_id != LOG_GROUP_ID):
        return
    raw = event.pattern_match.group(1)
    if not raw:
        return await reply_in_topic(
            event,
            "<b>JADWAL TMO</b>\n"
            f"&gt; Hari: <code>{tmo_days_text(TMO_SCHEDULE['days'])}</code>\n"
            f"&gt; Jam: <code>{TMO_SCHEDULE['start']}-{TMO_SCHEDULE['end']} WIB</code>\n\n"
            "Format ubah: <code>/tmoset Senin,Rabu,Kamis,Jumat 19:30-20:30</code>"
        )
    try:
        match = re.fullmatch(r"(.+?)\s+(\d{2}:\d{2})-(\d{2}:\d{2})", raw.strip(), re.I)
        if not match:
            raise ValueError
        day_tokens = [x.strip().lower() for x in re.split(r"[,; ]+", match.group(1)) if x.strip()]
        days = sorted(set(DAY_NAMES[x] for x in day_tokens))
        start, end = match.group(2), match.group(3)
        start_t, end_t = parse_hhmm(start), parse_hhmm(end)
        if start_t >= end_t:
            return await reply_in_topic(event, "⚠️ Jam mulai harus lebih awal dari jam selesai (jadwal melewati tengah malam belum didukung).")
        TMO_SCHEDULE = {"days": days, "start": start, "end": end}
        save_tmo_schedule(TMO_SCHEDULE)
        await reply_in_topic(event, f"✅ Jadwal TMO disimpan: <b>{tmo_days_text(days)}</b>, <code>{start}-{end} WIB</code>.")
    except (ValueError, KeyError):
        await reply_in_topic(event, "Format salah. Contoh: <code>/tmoset Senin,Rabu,Kamis,Jumat 19:30-20:30</code>")

@bot.on(events.NewMessage(pattern=r"(?i)^/tmooff$"))
async def tmo_off_command(event):
    global TMO_SCHEDULE
    if event.sender_id != OWNER_ID or (not event.is_private and event.chat_id != LOG_GROUP_ID):
        return
    TMO_SCHEDULE = {"days": [], "start": "19:30", "end": "20:30"}
    save_tmo_schedule(TMO_SCHEDULE)
    await reply_in_topic(event, "✅ Jadwal TMO dinonaktifkan.")

@bot.on(events.NewMessage(pattern=r"(?i)^/closeautoset(?:\s+(.+))?$"))
async def close_auto_set_command(event):
    global CLOSE_AUTO_SCHEDULE
    if event.sender_id != OWNER_ID or (not event.is_private and event.chat_id != LOG_GROUP_ID):
        return
    raw = event.pattern_match.group(1)
    if not raw:
        return await reply_in_topic(
            event,
            "<b>JADWAL CLOSE TAGALL OTOMATIS</b>\n"
            f"&gt; Hari ditutup: <code>{close_auto_days_text(CLOSE_AUTO_SCHEDULE['days'])}</code>\n\n"
            "Atur hari: <code>/closeautoset Selasa,Sabtu,Minggu</code>\n"
            "Hari tersebut semua permintaan tagall akan ditutup, bukan dimasukkan antrean."
        )
    try:
        day_tokens = [x.strip().lower() for x in re.split(r"[,; ]+", raw.strip()) if x.strip()]
        if not day_tokens:
            raise ValueError
        days = sorted(set(DAY_NAMES[x] for x in day_tokens))
        CLOSE_AUTO_SCHEDULE = {"days": days}
        save_close_auto(CLOSE_AUTO_SCHEDULE)
        await reply_in_topic(
            event,
            f"✅ Close tagall otomatis aktif pada: <b>{tmo_days_text(days)}</b>.\n"
            "Permintaan partner dan /tagall publik akan ditolak pada hari tersebut."
        )
    except (ValueError, KeyError):
        await reply_in_topic(event, "Format salah. Contoh: <code>/closeautoset Selasa,Sabtu,Minggu</code>")

@bot.on(events.NewMessage(pattern=r"(?i)^/closeautooff$"))
async def close_auto_off_command(event):
    global CLOSE_AUTO_SCHEDULE
    if event.sender_id != OWNER_ID or (not event.is_private and event.chat_id != LOG_GROUP_ID):
        return
    CLOSE_AUTO_SCHEDULE = {"days": []}
    save_close_auto(CLOSE_AUTO_SCHEDULE)
    await reply_in_topic(event, "✅ Close tagall otomatis dinonaktifkan.")

async def process_queue():
    global is_processing, stop_current_tagall
    is_processing = True
    while not tagall_queue.empty():
        task = await tagall_queue.get()
        await wait_until_tmo_ends()
        pemicu, teks, mitra, nama_pt, nama, user = task['p'], task['t'], task['m'], task['pt'], task['n'], task['u']
        v_bot, v_ch, v_pj1, v_pj2 = task['bot'], task['ch'], task['pj1'], task['pj2']
        
        stop_current_tagall = False
        try:
            await bot.send_message(pemicu, f"&gt; {E_ARROW} <b>GILIRAN ANDA DIMULAI!</b> {E_SPARKLE}", parse_mode='html')
        except: pass
        
        first_tag_id = None
        try:
            chat = await bot.get_entity(TARGET_GROUP_ID)
            i_msg = await bot.send_message(
                TARGET_GROUP_ID,
                f"{E_SPARKLE} <b>TAGALL DIMULAI</b> {E_CLOVER}\n{E_BOT} <b>GROUP:</b> {html.escape(chat.title)}",
                link_preview=False,
                parse_mode='html'
            )
            ids = [i_msg.id]
            first_tag_id = i_msg.id
        except:
            tagall_queue.task_done()
            continue
            
        w_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_start = build_log_start(nama, user, pemicu, w_start, mitra, teks)
        try:
            await send_to_log(log_start, link_preview=False)
        except: pass
        
        mentions = []
        try:
            async for u in bot.iter_participants(TARGET_GROUP_ID):
                if not u.bot:
                    prem_icon = random.choice(PREM_MENTION_EMOJIS)
                    mentions.append(f'<a href="tg://user?id={u.id}">{prem_icon}</a>')
        except: pass
        
        if not mentions:
            tagall_queue.task_done()
            continue
            
        chunks = [mentions[i:i + 10] for i in range(0, len(mentions), 10)]
        t_start = time.time()
        l_sent = False
        w_habis = False
        
        safe_teks = html.escape(teks)
        safe_pt = html.escape(nama_pt.upper())
        
        tmo_interrupted = False
        for chunk in chunks:
            if stop_current_tagall:
                break
            active_tmo, _ = tmo_status()
            if active_tmo:
                tmo_interrupted = True
                stop_current_tagall = True
                break
            selisih = int(time.time() - t_start)
            if selisih not in range(0, 300):
                w_habis = True
                break
            
            pesan_tagall = (
                f"{E_SPARKLE} <b>INFO PARTNER ({safe_pt})</b> {E_CLOVER}\n\n"
                f"{E_ARROW} {safe_teks}\n\n"
                + " ".join(chunk)
            )
            
            try:
                m_tag = await bot.send_message(TARGET_GROUP_ID, pesan_tagall, parse_mode='html', link_preview=False)
                ids.append(m_tag.id)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
                try:
                    m_tag = await bot.send_message(TARGET_GROUP_ID, pesan_tagall, parse_mode='html', link_preview=False)
                    ids.append(m_tag.id)
                except: pass
            except: pass
            
            await asyncio.sleep(1.2)
            
            if selisih not in range(0, 60) and not l_sent:
                try:
                    await bot.send_message(pemicu, f"&gt; {E_TIME} <b>BERJALAN 1 MENIT!</b>", parse_mode='html')
                    l_sent = True
                except: pass
                
        t_txt = "Ditunda karena jadwal TMO" if tmo_interrupted else ("Dihentikan Paksa (/end)" if stop_current_tagall else ("Selesai (Limit 5m)" if w_habis else "Selesai"))
        
        try:
            s_msg = await bot.send_message(
                TARGET_GROUP_ID,
                f"{E_SPARKLE} <b>{t_txt}!</b> {E_TIME} Pesan sampah dihapus dalam 5 menit...",
                parse_mode='html'
            )
            ids.append(s_msg.id)
        except: pass
        
        w_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_done = build_log_done(nama, mitra, t_txt, w_end, teks)
        try:
            await send_to_log(log_done, link_preview=False)
        except: pass
        
        clean_group_id = str(TARGET_GROUP_ID).replace('-100', '')
        link_ke_grup_anda = f"https://t.me/c/{clean_group_id}/{first_tag_id}" if first_tag_id else mitra
        struk = build_struk(nama, nama_pt, mitra, len(mentions), v_pj1, v_pj2, v_bot, v_ch)
        try:
            await bot.send_message(
                pemicu, 
                struk, 
                parse_mode='html', 
                link_preview=True, 
                buttons=[
                    [Button.url("Lihat Hasil ↗️", url=link_ke_grup_anda)]
                ]
            )
        except: pass
        
        tagall_queue.task_done()
        asyncio.create_task(clean_delayed(ids))
        if tmo_interrupted:
            await tagall_queue.put(task)
            await asyncio.sleep(1)
    is_processing = False

async def clean_delayed(ids):
    await asyncio.sleep(300)
    try:
        await bot.delete_messages(TARGET_GROUP_ID, ids)
        await send_to_log(f"&gt; {E_SPARKLE} <b>BERSIH:</b> {len(ids)} pesan sampah tagall telah dihapus!")
    except: pass

@bot.on(events.NewMessage(incoming=True))
async def handle_public_auto_tagall(event):
    if not event.is_private or event.text.startswith("/"): return
    if event.sender_id in add_pt_state: return
    
    urls = re.findall(r'(https?://\S+|t\.me/\S+)', event.text)
    if not urls: return

    if auto_tagall_closed():
        return await event.respond(
            "🔒 <b>TAGALL DITUTUP OTOMATIS</b>\n\n"
            "&gt; Hari ini layanan tagall sedang ditutup sesuai jadwal.\n"
            "&gt; Silakan ajukan kembali pada hari layanan dibuka.",
            parse_mode='html'
        )

    # Cek wajib join public grup terlebih dahulu
    is_joined = await check_user_joined(event.sender_id)
    if not is_joined:
        join_url = await get_public_join_url()
        return await event.respond(
            f"{E_BOT} <b>WAJIB JOIN GRUP TERLEBIH DAHULU</b> {E_SPARKLE}\n\n"
            f"&gt; {E_CLOVER} Maaf, untuk menggunakan layanan bot tagall, Anda diwajibkan bergabung ke grup publik resmi kami terlebih dahulu.\n"
            f"&gt; {E_ARROW} Silakan klik tombol <b>Join Grup</b> di bawah ini, lalu tekan <b>Cek Lagi</b> atau kirim ulang pesan tagall Anda.",
            buttons=[
                [Button.url("📢 Join Grup", url=join_url)],
                [Button.inline("🔄 Cek Lagi (Verifikasi)", data="check_fsub")]
            ],
            parse_mode='html'
        )

    v_link, v_name, v_bot, v_ch, v_pj1, v_pj2 = "", "", "", "", "", ""
    for url in urls:
        clean = url.strip().rstrip(".,;)")
        if clean in PARTNERS_DICT:
            v_link = clean
            pd = PARTNERS_DICT[clean]
            if isinstance(pd, dict):
                v_name = pd.get('nama', 'Tanpa Nama')
                v_bot = pd.get('bot', '-')
                v_ch = pd.get('ch', '-')
                v_pj1 = pd.get('pj1', '-')
                v_pj2 = pd.get('pj2', '-')
            else:
                v_name = pd
                v_bot, v_ch, v_pj1, v_pj2 = "-", "-", "-", "-"
            break
            
    if not v_link:
        return await event.respond(
            "❌ <b>LINK TIDAK TERDAFTAR</b>\n\n"
            f"&gt; {E_CLOVER} Mohon maaf, link yang Anda kirimkan belum terdata sebagai mitra resmi kami.",
            parse_mode='html'
        )
        
    s = await event.get_sender()
    n = s.first_name if s.first_name else "User"
    u = s.username if s.username else "tidak_ada"
    q_idx = tagall_queue.qsize()
    
    await tagall_queue.put({
        'p': event.sender_id, 't': event.text, 'm': v_link, 'pt': v_name, 'n': n, 'u': u,
        'bot': v_bot, 'ch': v_ch, 'pj1': v_pj1, 'pj2': v_pj2
    })
    
    active_tmo, tmo_end = tmo_status()
    if active_tmo:
        await event.respond(
            f"{E_TIME} <b>GC SEDANG TMO</b>\n\n"
            f"&gt; Grup sedang TMO sampai <b>{tmo_end.strftime('%H:%M')} WIB</b>.\n"
            f"&gt; Permintaan Anda tetap masuk antrean dan akan di-tagall setelah TMO selesai.",
            parse_mode='html'
        )
        if not is_processing:
            asyncio.create_task(process_queue())
    elif is_processing:
        await event.respond(
            f"{E_TIME} <b>ANTREAN DITERIMA</b>\n\n"
            f"&gt; {E_CAL} Permintaan Anda telah dimasukkan ke dalam barisan antrean nomor ke-<b>{q_idx + 1}</b>.",
            parse_mode='html'
        )
    else:
        await event.respond(
            f"{E_SPARKLE} <b>TERVERIFIKASI!</b>\n\n"
            f"&gt; {E_ARROW} Link valid! Memulai bot tagall...",
            parse_mode='html'
        )
        asyncio.create_task(process_queue())


MANUAL_TAGALL_COOLDOWN = {}

@bot.on(events.NewMessage(pattern=r"(?i)^/tagall$"))
async def public_tagall_command(event):
    if event.is_private or event.chat_id != TARGET_GROUP_ID:
        return
    if auto_tagall_closed():
        return await event.respond("🔒 <b>TAGALL DITUTUP OTOMATIS</b>\n\n&gt; Hari ini layanan tagall sedang ditutup sesuai jadwal.", parse_mode="html")
    now = time.time()
    last = MANUAL_TAGALL_COOLDOWN.get(event.sender_id, 0)
    if now - last < 60:
        return await event.respond("⏳ Tunggu 60 detik sebelum meminta tagall manual lagi.")
    MANUAL_TAGALL_COOLDOWN[event.sender_id] = now
    buttons = [
        [Button.inline("3 menit", data=f"mtag_{event.sender_id}_3"),
         Button.inline("5 menit", data=f"mtag_{event.sender_id}_5"),
         Button.inline("10 menit", data=f"mtag_{event.sender_id}_10")],
        [Button.inline("15 menit", data=f"mtag_{event.sender_id}_15"),
         Button.inline("30 menit", data=f"mtag_{event.sender_id}_30")],
        [Button.inline("60 menit", data=f"mtag_{event.sender_id}_60"),
         Button.inline("90 menit", data=f"mtag_{event.sender_id}_90")],
        [Button.inline("❌ Batal", data=f"mtag_cancel_{event.sender_id}")]
    ]
    await event.respond(
        "📣 <b>TAGALL MANUAL</b>\n\nPilih waktu penyimpanan pesan tagall. Pesan juga bisa dihapus lebih cepat dengan tombol hapus.",
        buttons=buttons,
        parse_mode="html"
    )

@bot.on(events.CallbackQuery(pattern=r"^mtag_cancel_(\d+)$"))
async def manual_tagall_cancel(event):
    owner_id = int(event.pattern_match.group(1))
    if event.sender_id != owner_id:
        return await event.answer("Tombol ini milik peminta tagall.", alert=True)
    await event.edit("❌ Permintaan tagall manual dibatalkan.", buttons=None)

@bot.on(events.CallbackQuery(pattern=r"^mtag_(\d+)_(3|5|10|15|30|60|90)$"))
async def manual_tagall_start(event):
    owner_id = int(event.pattern_match.group(1))
    duration = int(event.pattern_match.group(2))
    if event.sender_id != owner_id:
        return await event.answer("Tombol ini milik peminta tagall.", alert=True)
    if event.chat_id != TARGET_GROUP_ID:
        return await event.answer("Fitur ini hanya untuk grup publik.", alert=True)
    if auto_tagall_closed():
        return await event.answer("Tagall sedang ditutup otomatis hari ini.", alert=True)
    active_tmo, tmo_end = tmo_status()
    if active_tmo:
        return await event.answer(f"Grup sedang TMO sampai {tmo_end.strftime('%H:%M')} WIB.", alert=True)
    await event.edit(f"📣 Tagall manual diproses. Pesan akan dihapus dalam {duration} menit.", buttons=None)
    asyncio.create_task(run_manual_tagall(event.chat_id, owner_id, duration))

async def run_manual_tagall(chat_id, owner_id, duration):
    message_ids = []
    try:
        members = []
        async for user in bot.iter_participants(chat_id):
            if not user.bot:
                members.append(user.id)
        if not members:
            return
        for idx in range(0, len(members), 10):
            active_tmo, _ = tmo_status()
            if active_tmo:
                break
            chunk = members[idx:idx + 10]
            text = "📣 <b>TAGALL MANUAL</b>\n\n" + " ".join(
                f'<a href="tg://user?id={uid}">👤</a>' for uid in chunk
            )
            msg = await bot.send_message(chat_id, text, parse_mode="html")
            message_ids.append(msg.id)
            await asyncio.sleep(1.5)
        if not message_ids:
            return
        control = await bot.send_message(
            chat_id,
            f"✅ Tagall manual terkirim. Pesan akan dibersihkan dalam {duration} menit.",
            buttons=[[Button.inline("🗑 Hapus sekarang", data=f"mtagdel_{owner_id}_{message_ids[0]}")]],
            parse_mode="html"
        )
        message_ids.append(control.id)
        MANUAL_TAGALL_IDS[message_ids[0]] = message_ids[:]
        await asyncio.sleep(duration * 60)
        try:
            await bot.delete_messages(chat_id, message_ids)
        except Exception:
            pass
        MANUAL_TAGALL_IDS.pop(message_ids[0], None)
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    except Exception as e:
        print(f"[MANUAL TAGALL] {e}")

@bot.on(events.CallbackQuery(pattern=r"^mtagdel_(\d+)_(\d+)$"))
async def manual_tagall_delete(event):
    owner_id = int(event.pattern_match.group(1))
    first_id = int(event.pattern_match.group(2))
    if event.sender_id != owner_id:
        return await event.answer("Tombol hapus ini milik peminta tagall.", alert=True)
    try:
        ids = MANUAL_TAGALL_IDS.pop(first_id, [first_id])
        await bot.delete_messages(event.chat_id, ids)
        await event.answer("Semua pesan tagall manual dihapus.")
    except Exception:
        await event.answer("Tidak bisa menghapus pesan ini.", alert=True)


bot.run_until_disconnected()
