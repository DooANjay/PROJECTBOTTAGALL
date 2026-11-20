import os, asyncio, time, json, re, random, html
from datetime import datetime
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
    E_SPARKLE,
    E_CARD,
    E_ARROW,
    E_TIME,
    E_CLOVER,
    E_CAL,
    E_BOT
]

def get_topic_reply_id(event):
    if event.is_private:
        return None
    if getattr(event.message, 'reply_to', None):
        r = event.message.reply_to
        if getattr(r, 'forum_topic', False):
            return getattr(r, 'reply_to_top_id', None) or getattr(r, 'reply_to_msg_id', None)
        if getattr(r, 'reply_to_top_id', None):
            return r.reply_to_top_id
    return LOG_TOPIC_ID if LOG_TOPIC_ID > 0 else None

async def reply_in_topic(event, text, **kwargs):
    topic_id = get_topic_reply_id(event)
    if topic_id:
        return await bot.send_message(event.chat_id, text, reply_to=topic_id, **kwargs)
    return await event.respond(text, **kwargs)

async def get_public_group_entity_and_url():
    target_entity = PUBLIC_GROUP_LINK if PUBLIC_GROUP_LINK else TARGET_GROUP_ID
    entity = await bot.get_entity(target_entity)
    url = PUBLIC_GROUP_LINK
    if not url:
        if getattr(entity, 'username', None):
            url = f"https://t.me/{entity.username}"
        else:
            try:
                from telethon.tl.functions.messages import ExportChatInviteRequest
                invite = await bot(ExportChatInviteRequest(entity))
                url = invite.link
            except:
                url = "https://t.me/"
    elif url.startswith("@"):
        url = f"https://t.me/{url.lstrip('@')}"
    elif not url.startswith("http"):
        url = f"https://{url}"
    return entity, url

async def check_user_joined(user_id):
    if user_id == OWNER_ID:
        return True, ""
    try:
        entity, url = await get_public_group_entity_and_url()
        perms = await bot.get_permissions(entity, user_id)
        if getattr(perms, 'is_banned', False):
            return False, url
        return True, url
    except UserNotParticipantError:
        _, url = await get_public_group_entity_and_url()
        return False, url
    except Exception:
        try:
            _, url = await get_public_group_entity_and_url()
        except:
            url = PUBLIC_GROUP_LINK if PUBLIC_GROUP_LINK else "https://t.me/"
        return False, url

def build_log_start(a, b, c, d, e, f):
    safe_a = html.escape(str(a))
    safe_b = html.escape(str(b))
    safe_e = html.escape(str(e))
    clean_f = html.escape(str(f)).replace('\n', '\n&gt; ')
    res = (
        f"&gt; {E_BOT} <b>USER :</b> @{safe_b}\n"
        f"&gt; {E_CARD} <b>USER ID :</b> <code>{c}</code>\n"
        f"&gt; {E_TIME} <b>DURASI :</b> 5m\n"
        f"&gt; {E_CAL} <b>WAKTU :</b> {d}\n"
        f"&gt; {E_CLOVER} <b>PARTNER :</b> {safe_e}\n\n"
        f"&gt; {E_SPARKLE} <b>TEKS TAGALL :</b>\n"
        f"&gt; {clean_f}"
    )
    return res

def build_log_done(a, b, c, d, e):
    safe_a = html.escape(str(a))
    safe_b = html.escape(str(b))
    clean_e = html.escape(str(e)).replace('\n', '\n&gt; ')
    res = (
        f"&gt; {E_BOT} <b>PENGIRIM :</b> {safe_a}\n"
        f"&gt; {E_ARROW} <b>LINK :</b> {safe_b}\n"
        f"&gt; {E_SPARKLE} <b>STATUS :</b> {c}\n"
        f"&gt; {E_CAL} <b>WAKTU SELESAI :</b> {d}\n\n"
        f"&gt; <b>PESAN TERAKHIR :</b>\n"
        f"&gt; {clean_e}"
    )
    return res

def build_struk(sender_name, partner_name, link, member_count, pj1, pj2, bot_name, ch_link):
    safe_sender = html.escape(str(sender_name))
    safe_partner = html.escape(str(partner_name).upper())
    safe_link = html.escape(str(link))
    res = (
        f"{E_SPARKLE} ✅ <b>Tagall selesai!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{E_BOT} Pengirim: <b>{safe_sender}</b>\n"
        f"{E_CLOVER} Partner: <b>{safe_partner}</b>\n"
        f"{E_ARROW} Link: {safe_link}\n"
        f"{E_CARD} Member di-tag: <code>{member_count}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{E_SPARKLE} <b>Jangan lupa SS hasil tagall-nya!</b>"
    )
    return res

def load_partners():
    if os.path.exists(FILE_DB):
        try:
            with open(FILE_DB, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_partners(data):
    with open(FILE_DB, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

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
        "&gt; <code>/end</code> - Menghentikan paksa proses tagall yang sedang berlangsung"
    )
    await reply_in_topic(event, commands_text, parse_mode='html')

# FITUR BACKUP DATABASE
@bot.on(events.NewMessage(pattern=r'(?i)^/backup'))
async def backup_command(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    
    if not os.path.exists(FILE_DB) or os.path.getsize(FILE_DB) == 0:
        return await reply_in_topic(event, "⚠️ <b>Database kosong atau tidak ditemukan!</b>", parse_mode='html')
    
    try:
        await reply_in_topic(
            event,
            f"{E_CARD} <b>BACKUP DATABASE BOT</b>\n\n&gt; {E_CAL} Berikut adalah file cadangan setelan data partner terbaru:",
            file=FILE_DB,
            parse_mode='html'
        )
    except Exception as e:
        await reply_in_topic(event, f"❌ Gagal mengirim file backup: <code>{html.escape(str(e))}</code>", parse_mode='html')

# FITUR RESTORE DATABASE
@bot.on(events.NewMessage(pattern=r'(?i)^/restore'))
async def restore_command(event):
    global PARTNERS_DICT
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    
    reply = await event.get_reply_message()
    if not reply or not reply.file:
        return await reply_in_topic(event, f"⚠️ <b>Mohon reply (balas) file dokumen backup <code>.json</code></b> yang ingin direstore menggunakan perintah <code>/restore</code>.", parse_mode='html')
    
    if not reply.file.name or not reply.file.name.endswith('.json'):
        return await reply_in_topic(event, "⚠️ File yang direply bukan format <code>.json</code> yang valid!", parse_mode='html')
    
    download_path = "temp_restore.json"
    try:
        await reply.download_media(file=download_path)
        
        with open(download_path, "r", encoding="utf-8") as f:
            new_data = json.load(f)
            
        if not isinstance(new_data, dict):
            if os.path.exists(download_path): os.remove(download_path)
            return await reply_in_topic(event, "⚠️ Format struktur data dalam file JSON tidak valid.", parse_mode='html')
            
        with open(FILE_DB, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)
            
        PARTNERS_DICT = load_partners()
        if os.path.exists(download_path): os.remove(download_path)
        
        await reply_in_topic(
            event,
            f"{E_SPARKLE} <b>RESTORE DATABASE BERHASIL!</b>\n\n"
            f"&gt; {E_CLOVER} Total data partner yang dimuat ulang: <code>{len(PARTNERS_DICT)}</code> data.\n"
            f"&gt; {E_ARROW} Silakan cek kembali menggunakan <code>/lpt</code>.",
            parse_mode='html'
        )
    except Exception as e:
        if os.path.exists(download_path): os.remove(download_path)
        await reply_in_topic(event, f"❌ Gagal memproses restore database: <code>{html.escape(str(e))}</code>", parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^menu_.*'))
async def callback_menu(event):
    data = event.data.decode()
    if data == "menu_tagall":
        text = (
            f"{E_ARROW} <b>Cara Memulai Tagall:</b>\n\n"
            f"&gt; {E_CLOVER} Pastikan Anda sudah bergabung ke grup publik resmi kami.\n"
            f"&gt; {E_SPARKLE} Kirimkan pesan teks yang berisi <b>Link Partner/Grup</b> yang sudah terdaftar secara resmi di bot ini.\n"
            "&gt;\n"
            f"&gt; {E_TIME} Bot akan otomatis memverifikasi keanggotaan serta link tersebut, lalu memasukkan pesanan Anda ke dalam antrian."
        )
    elif data == "menu_mitra":
        text = (
            f"{E_CLOVER} <b>Pengajuan Kemitraan (PT-an):</b>\n\n"
            "&gt; Untuk mendaftarkan grup Anda sebagai partner resmi, silakan hubungi owner bot melalui username di bawah ini:\n"
            "&gt;\n"
            f"&gt; {E_BOT} <b>Owner:</b> @{html.escape(OWNER_USERNAME)}\n"
            "&gt;\n"
            f"&gt; {E_CARD} Kirimkan format pendaftaran kepada admin agar link Anda terdata di database sistem."
        )
    elif data == "menu_info":
        text = (
            f"{E_SPARKLE} <b>Informasi Bot &amp; Aturan:</b>\n\n"
            f"&gt; {E_CLOVER} Pengguna wajib bergabung ke grup publik sebelum menggunakan layanan tagall.\n"
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

@bot.on(events.CallbackQuery(pattern=r'^fsub_recheck$'))
async def callback_fsub_recheck(event):
    joined, _ = await check_user_joined(event.sender_id)
    if joined:
        await event.answer("✅ Terverifikasi! Anda sudah bergabung di grup. Silakan kirim ulang teks tagall Anda.", alert=True)
        await event.edit(
            f"{E_SPARKLE} <b>VERIFIKASI KEANGGOTAAN BERHASIL!</b>\n\n"
            f"&gt; {E_ARROW} Akun Anda sudah terdata di grup publik.\n"
            f"&gt; {E_CLOVER} Silakan kirimkan kembali teks berisi <b>Link Partner</b> Anda sekarang untuk memulai tagall.",
            buttons=None,
            parse_mode='html'
        )
    else:
        await event.answer("❌ Anda belum terdeteksi bergabung di grup publik! Silakan klik tombol Join Grup terlebih dahulu.", alert=True)

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_command(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    user_id = event.sender_id
    if user_id in add_pt_state:
        del add_pt_state[user_id]
        await reply_in_topic(event, "❌ <b>Proses penginputan/pengeditan data partner telah dibatalkan.</b>", parse_mode='html')
    else:
        await reply_in_topic(event, f"{E_TIME} Tidak ada proses penginputan partner yang sedang aktif.", parse_mode='html')

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
        n = p_data.get("nama", "Tanpa Nama") if isinstance(p_data, dict) else str(p_data)
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
    await reply_in_topic(event, txt, buttons=buttons, link_preview=False, parse_mode='html')

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
            pd = {"nama": str(pd), "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
            
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
    else:
        await event.answer("⚠️ Data partner tidak ditemukan!", alert=True)

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
        n = p_data.get("nama", p_data) if isinstance(p_data, dict) else str(p_data)
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
        await event.answer(f"🗑️ {str(removed_name).upper()} Berhasil Dihapus!", alert=True)
    txt, buttons = build_partner_page(1)
    await event.edit(txt, buttons=buttons, link_preview=False, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=r'^pt_edit_(nama|link|bot|ch|pj1|pj2)_\d+$'))
async def callback_trigger_edit(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    parts = event.data.decode().split('_')
    tipe = parts[2]
    idx = int(parts[3])
    
    msg = await event.get_message()
    topic_id = None
    if not event.is_private and msg:
        if getattr(msg, 'reply_to', None):
            r = msg.reply_to
            topic_id = getattr(r, 'reply_to_top_id', None) or getattr(r, 'reply_to_msg_id', None)
        if not topic_id and LOG_TOPIC_ID > 0:
            topic_id = LOG_TOPIC_ID

    add_pt_state[event.sender_id] = {"step": f"edit_{tipe}", "idx": idx, "topic_id": topic_id}
    
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
    if topic_id:
        await bot.send_message(event.chat_id, txt, reply_to=topic_id, parse_mode='html')
    else:
        await event.respond(txt, parse_mode='html')
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r'^pt_add_start$'))
async def callback_add_start(event):
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID:
        return await event.answer("⚠️ Tidak ada akses!", alert=True)
    msg = await event.get_message()
    topic_id = None
    if not event.is_private and msg:
        if getattr(msg, 'reply_to', None):
            r = msg.reply_to
            topic_id = getattr(r, 'reply_to_top_id', None) or getattr(r, 'reply_to_msg_id', None)
        if not topic_id and LOG_TOPIC_ID > 0:
            topic_id = LOG_TOPIC_ID

    add_pt_state[event.sender_id] = {"step": "input_nama", "topic_id": topic_id}
    txt = (
        f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 1/6)</b>\n\n"
        f"&gt; {E_ARROW} Silakan masukkan <b>Nama Partner (PT / Nama GC)</b>:\n"
        "&gt; <i>Ketik /cancel jika ingin membatalkan.</i>"
    )
    if topic_id:
        await bot.send_message(event.chat_id, txt, reply_to=topic_id, parse_mode='html')
    else:
        await event.respond(txt, parse_mode='html')
    await event.answer()

@bot.on(events.NewMessage(incoming=True))
async def handle_multistep_input(event):
    global PARTNERS_DICT
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    user_id = event.sender_id
    if user_id not in add_pt_state: return
    if not event.text: return
    
    user_text = event.text.strip()
    if user_text.startswith("/cancel"): return
    
    state = add_pt_state[user_id]
    step = state.get("step")
    topic_id = state.get("topic_id")

    async def send_step_reply(text_msg):
        if not event.is_private and topic_id:
            await bot.send_message(event.chat_id, text_msg, reply_to=topic_id, parse_mode='html')
        else:
            await event.respond(text_msg, parse_mode='html')
    
    if step == "input_nama":
        state["nama"] = user_text
        state["step"] = "input_link"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 2/6)</b>\n\n"
            f"&gt; {E_ARROW} Masukkan <b>Link Partner (Link GC)</b> berawalan http atau t.me:"
        )
        await send_step_reply(txt)
        
    elif step == "input_link":
        if not user_text.startswith(("http", "t.me")):
            return await send_step_reply("&gt; ⚠️ Link tidak valid! Harus diawali http atau t.me. Silakan kirim ulang:")
        if user_text in PARTNERS_DICT:
            return await send_step_reply("&gt; ⚠️ Link tersebut sudah terdaftar! Silakan kirim link lain:")
        state["link"] = user_text
        state["step"] = "input_bot"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 3/6)</b>\n\n"
            f"&gt; {E_BOT} Masukkan <b>Nama Bot</b> pendukung:"
        )
        await send_step_reply(txt)
        
    elif step == "input_bot":
        state["bot"] = user_text
        state["step"] = "input_ch"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 4/6)</b>\n\n"
            f"&gt; {E_CARD} Masukkan <b>Link Channel (CH)</b>:"
        )
        await send_step_reply(txt)
        
    elif step == "input_ch":
        state["ch"] = user_text
        state["step"] = "input_pj1"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 5/6)</b>\n\n"
            "&gt; 👮 Masukkan Username <b>Penanggung Jawab 1 (PJ 1)</b>:"
        )
        await send_step_reply(txt)
        
    elif step == "input_pj1":
        state["pj1"] = user_text
        state["step"] = "input_pj2"
        txt = (
            f"{E_CLOVER} <b>TAMBAH PARTNER BARU (TAHAP 6/6 - TERAKHIR)</b>\n\n"
            "&gt; 👮 Masukkan Username <b>Penanggung Jawab 2 (PJ 2)</b>:"
        )
        await send_step_reply(txt)
        
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
            f"Silakan panggil kembali <code>/lpt</code> untuk melihat list."
        )
        await send_step_reply(txt_done)

    elif step.startswith("edit_"):
        parts = step.split("_")
        tipe = parts[1]
        idx = state["idx"]
        keys = list(PARTNERS_DICT.keys())
        
        if 0 <= idx < len(keys):
            old_link = keys[idx]
            old_data = PARTNERS_DICT[old_link]
            
            if not isinstance(old_data, dict):
                old_data = {"nama": str(old_data), "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
                
            if tipe == "link":
                if not user_text.startswith(("http", "t.me")):
                    return await send_step_reply("&gt; ⚠️ Link tidak valid! Harus diawali http atau t.me. Silakan kirim ulang:")
                if user_text != old_link and user_text in PARTNERS_DICT:
                    return await send_step_reply("&gt; ⚠️ Link tersebut sudah terdaftar! Silakan kirim link lain:")
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
            await send_step_reply(txt_success)
        else:
            del add_pt_state[user_id]
            await send_step_reply("⚠️ Data partner tidak ditemukan (mungkin sudah terhapus). Silakan panggil ulang <code>/lpt</code>.")

@bot.on(events.NewMessage(pattern=r'(?i)^/end'))
async def end_tagall(event):
    if not event.is_private and event.chat_id != LOG_GROUP_ID: return
    if event.sender_id != OWNER_ID and event.chat_id != LOG_GROUP_ID: return
    global stop_current_tagall, is_processing
    if not is_processing:
        return await reply_in_topic(event, f"&gt; {E_TIME} Tidak ada proses tagall yang sedang berjalan.", parse_mode='html')
    stop_current_tagall = True
    await reply_in_topic(event, "&gt; 🛑 Menghentikan proses tagall saat ini...", parse_mode='html')

async def process_queue():
    global is_processing, stop_current_tagall
    is_processing = True
    log_topic = LOG_TOPIC_ID if LOG_TOPIC_ID > 0 else None

    while not tagall_queue.empty():
        task = await tagall_queue.get()
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
                f"{E_SPARKLE} <b>TAGALL DIMULAI</b> {E_SPARKLE}\n{E_BOT} <b>GROUP:</b> {html.escape(chat.title)}",
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
            await bot.send_message(LOG_GROUP_ID, log_start, parse_mode='html', link_preview=False, reply_to=log_topic)
        except: pass
        
        mentions = []
        try:
            async for u in bot.iter_participants(TARGET_GROUP_ID):
                if not u.bot:
                    p_emoji = random.choice(PREM_MENTION_EMOJIS)
                    mentions.append(f'<a href="tg://user?id={u.id}">{p_emoji}</a>')
        except: pass
        
        if not mentions:
            tagall_queue.task_done()
            continue
            
        chunks = [mentions[i:i + 10] for i in range(0, len(mentions), 10)]
        t_start = time.time()
        l_sent = False
        w_habis = False
        
        escaped_teks = html.escape(teks)
        safe_pt = html.escape(nama_pt.upper())
        tagall_header = (
            f"{E_SPARKLE} <b>INFO PARTNER ({safe_pt})</b> {E_CLOVER}\n"
            f"{E_ARROW} {escaped_teks}\n\n"
        )
        
        for chunk in chunks:
            if stop_current_tagall:
                break
            selisih = int(time.time() - t_start)
            if selisih not in range(0, 300):
                w_habis = True
                break
            try:
                m_tag = await bot.send_message(
                    TARGET_GROUP_ID,
                    tagall_header + " ".join(chunk),
                    parse_mode='html',
                    link_preview=False
                )
                ids.append(m_tag.id)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
                try:
                    m_tag = await bot.send_message(
                        TARGET_GROUP_ID,
                        tagall_header + " ".join(chunk),
                        parse_mode='html',
                        link_preview=False
                    )
                    ids.append(m_tag.id)
                except: pass
            except: pass
            
            await asyncio.sleep(1.2)
            
            if selisih not in range(0, 60) and not l_sent:
                try:
                    await bot.send_message(pemicu, f"&gt; {E_TIME} <b>BERJALAN 1 MENIT!</b>", parse_mode='html')
                    l_sent = True
                except: pass
                
        t_txt = "Dihentikan Paksa (/end)" if stop_current_tagall else ("Selesai (Limit 5m)" if w_habis else "Selesai")
        
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
            await bot.send_message(LOG_GROUP_ID, log_done, parse_mode='html', link_preview=False, reply_to=log_topic)
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
    is_processing = False

async def clean_delayed(ids):
    await asyncio.sleep(300)
    try:
        await bot.delete_messages(TARGET_GROUP_ID, ids)
        await bot.send_message(OWNER_ID, f"&gt; {E_SPARKLE} <b>BERSIH:</b> {len(ids)} pesan dihapus!", parse_mode='html')
    except: pass

@bot.on(events.NewMessage(incoming=True))
async def handle_public_auto_tagall(event):
    if not event.is_private or not event.text or event.text.startswith("/"): return
    if event.sender_id in add_pt_state: return
    
    urls = re.findall(r'(https?://\S+|t\.me/\S+)', event.text)
    if not urls: return

    # Cek wajib join public grup terlebih dahulu
    joined, group_url = await check_user_joined(event.sender_id)
    if not joined:
        return await event.respond(
            f"{E_BOT} <b>WAJIB JOIN GRUP TERLEBIH DAHULU</b> {E_SPARKLE}\n\n"
            f"&gt; {E_CLOVER} Maaf, untuk menggunakan layanan bot tagall, Anda diwajibkan bergabung ke grup publik resmi kami terlebih dahulu.\n"
            f"&gt; {E_ARROW} Silakan klik tombol <b>Join Grup</b> di bawah ini, lalu tekan <b>Cek Lagi</b> atau kirim ulang pesan tagall Anda.",
            buttons=[
                [Button.url("📢 Join Grup", url=group_url)],
                [Button.inline("🔄 Cek Lagi (Verifikasi)", data="fsub_recheck")]
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
                v_name = str(pd)
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
    
    if is_processing:
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

bot.run_until_disconnected()
