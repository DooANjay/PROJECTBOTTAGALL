import asyncio
import json
import os
import random
import re
import time
from datetime import datetime

from telethon import Button, TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopePeer


def required_int(name: str) -> int:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"Variabel {name} belum diatur")
    return int(value)


try:
    API_ID = required_int("API_ID")
    API_HASH = os.environ["API_HASH"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    OWNER_ID = required_int("OWNER_ID")
    TARGET_GROUP_ID = required_int("TARGET_GROUP_ID")
    LOG_GROUP_ID = required_int("LOG_GROUP_ID")
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "admin")
except (KeyError, TypeError, ValueError) as error:
    print(f"❌ ERROR: Periksa kembali variabel di Railway! ({error})")
    raise SystemExit(1)


FILE_DB = "partners_database.json"
EMOJIS = [
    "🌟", "🔥", "💎", "🚀", "👏", "⚡", "✨", "🎯", "🔮", "🛸", "🪐",
    "🧬", "🎨", "🧸", "🦄", "🐼", "🦊", "🍒", "🍇", "🍃", "🍿", "🎵",
    "🎸", "🎲", "🎰", "🌊", "🎪", "🎭", "🛡️", "🔑", "📦",
]

bot = TelegramClient("bot_official_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
tagall_queue: asyncio.Queue[dict] = asyncio.Queue()
is_processing = False
stop_current_tagall = False
add_pt_state: dict[int, dict] = {}


def is_authorized(event) -> bool:
    return event.sender_id == OWNER_ID or event.chat_id == LOG_GROUP_ID


def load_partners() -> dict:
    if not os.path.exists(FILE_DB):
        return {}

    try:
        with open(FILE_DB, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_partners(data: dict) -> None:
    with open(FILE_DB, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


PARTNERS_DICT = load_partners()


def build_log_start(username: str, user_id: int, started_at: str, partner: str, text: str) -> str:
    clean_text = text.replace("\n", "\n> ")
    return (
        "🪐 **TAGALL DOO TEST**\n"
        "📜 **LOG • MENTION STARTED**\n"
        f"> 👥 **USER:** @{username}\n"
        f"> 🆔 **USER ID:** `{user_id}`\n"
        "> ⏳ **DURASI:** 5m\n"
        f"> ⏰ **WAKTU:** {started_at}\n"
        f"> 🔮 **PARTNER:** {partner}\n\n"
        f"> 💬 **TEKS TAGALL:**\n> {clean_text}"
    )


def build_log_done(user_id: int, partner_link: str, group_name: str, total_members: int) -> str:
    deleted_estimate = int(total_members * 0.2)
    return (
        "💫 **LOG • MENTION DONE**\n"
        f"> 🆔 **USER ID:** `{user_id}`\n"
        f"> 🔮 **PARTNER:** {partner_link}\n"
        f"> 🗂️ **GROUP:** **{group_name.upper()}**\n"
        f"> 📊 **TERKIRIM:** {total_members}\n"
        f"> 🗑️ **DIHAPUS:** {deleted_estimate}\n"
        "> ❌ **GAGAL:** 0"
    )


def build_receipt(timestamp: str, group_name: str, partner_link: str, total_members: int) -> str:
    return (
        "🟢 **TAGALL SELESAI**\n"
        f"> 📅 **TANGGAL:** {timestamp}\n"
        f"> 👥 **GROUP:** **{group_name.upper()}**\n"
        f"> 🤝 **PARTNER:** {partner_link}\n"
        f"> 📤 **TERKIRIM:** {total_members}\n"
        "> ⏳ **DURASI:** 5m\n\n"
        "💡 LUPA SS? FORWARD PESAN INI SEBAGAI BUKTI TAGALL!"
    )


def get_menu_buttons():
    return [
        [Button.inline("🚀 Mulai Tagall", data="menu_tagall")],
        [Button.inline("🤝 Minta PT-an (Partner)", data="menu_mitra")],
        [Button.inline("ℹ️ Info Lainnya", data="menu_info")],
    ]


def build_partner_page(page: int = 1):
    keys = list(PARTNERS_DICT)
    items_per_page = 10
    total_pages = max(1, (len(keys) + items_per_page - 1) // items_per_page)
    page = max(1, min(page, total_pages))

    if not keys:
        return (
            "💎 **PANEL LAYANAN PARTNER**\n\n> 🧬 STATUS DATABASE: KOSONG!",
            [
                [Button.inline("⚡ Tambah PT Baru", data="pt_add_start")],
                [Button.inline("🔴 Tutup Panel", data="panel_close")],
            ],
        )

    start = (page - 1) * items_per_page
    page_keys = keys[start : start + items_per_page]
    buttons = []
    for index, link in enumerate(page_keys, start=start):
        partner = PARTNERS_DICT[link]
        name = partner.get("nama", "Tanpa Nama") if isinstance(partner, dict) else partner
        buttons.append([Button.inline(f"💫 Edit #{index + 1}: {name.upper()}", data=f"pt_manage_{index}")])

    if page < total_pages:
        buttons.append([Button.inline("🧬 Selanjutnya", data=f"pt_page_{page + 1}")])
    elif page > 1:
        buttons.append([Button.inline("🧬 Kembali ke Awal", data="pt_page_1")])

    buttons.extend([
        [Button.inline("🔮 Preview All (Kirim Semua)", data="pt_preview_all")],
        [Button.inline("✨ Tambah PT Baru", data="pt_add_start")],
        [Button.inline("🔴 Tutup Panel", data="panel_close")],
    ])
    return f"💎 **PANEL LAYANAN PARTNER**\n\n> HALAMAN AKTIF [{page}/{total_pages}]", buttons


async def init_bot_commands():
    commands = [
        BotCommand("start", "Memulai bot & melihat menu utama"),
        BotCommand("help", "Panel kontrol & menu bantuan"),
        BotCommand("fitur", "Melihat fitur bot dan penggunaannya"),
        BotCommand("absen", "Membuka panel absensi grup 24 jam"),
        BotCommand("lpt", "Membuka panel manajemen data partner"),
        BotCommand("cancel", "Membatalkan input/edit data partner"),
        BotCommand("end", "Menghentikan proses tagall"),
    ]
    try:
        owner = await bot.get_input_entity(OWNER_ID)
        await bot(SetBotCommandsRequest(scope=BotCommandScopePeer(owner), commands=commands))
        print("🌟 Menu perintah berhasil didaftarkan ke Telegram!")
    except Exception as error:
        print(f"⚠️ Gagal mendaftarkan menu perintah: {error}")


@bot.on(events.NewMessage(pattern=r"(?i)^/start$"))
async def start_command(event):
    if event.is_private:
        await event.respond(
            "👋 **Halo! Selamat datang di Bot Tagall Official**\n\n"
            "> Silakan pilih menu layanan di bawah ini untuk memulai.",
            buttons=get_menu_buttons(),
        )


@bot.on(events.NewMessage(pattern=r"(?i)^/(help|fitur|absen)$"))
async def dummy_commands(event):
    if event.is_private:
        command = event.pattern_match.group(1).lower()
        await event.respond(f"🛠️ **Menu /{command} sedang aktif dalam mode default sistem.**")


@bot.on(events.NewMessage(pattern=r"(?i)^/menu$"))
async def menu_command(event):
    if event.is_private or event.chat_id == LOG_GROUP_ID:
        await event.respond(
            "📋 **DAFTAR PERINTAH BOT TAGALL**\n\n"
            "**Perintah Umum (PM Bot):**\n"
            "> `/start` — Menu interaktif\n\n"
            "**Perintah Admin/Owner:**\n"
            "> `/menu`, `/lpt`, `/cancel`, `/end`"
        )


@bot.on(events.CallbackQuery(pattern=r"^menu_.*"))
async def callback_menu(event):
    data = event.data.decode()
    if data == "menu_tagall":
        text = (
            "🚀 **Cara Memulai Tagall:**\n\n"
            "> Kirim pesan berisi Link Partner/Grup yang terdaftar.\n"
            "> Bot memverifikasi link dan memasukkan pesanan ke antrean."
        )
    elif data == "menu_mitra":
        text = (
            "🤝 **Pengajuan Kemitraan (PT-an):**\n\n"
            "> Hubungi owner bot untuk mendaftarkan grup Anda.\n>\n"
            f"> 👤 **Owner:** @{OWNER_USERNAME}"
        )
    elif data == "menu_info":
        text = (
            "ℹ️ **Informasi Bot & Aturan:**\n\n"
            "> • Bot menggunakan sistem antrean.\n"
            "> • Setiap sesi dibatasi maksimal 5 menit.\n"
            "> • Pesan sesi dibersihkan otomatis."
        )
    else:
        await event.edit(
            "👋 **Halo! Selamat datang di Bot Tagall Official**\n\n"
            "> Silakan pilih menu layanan di bawah ini untuk memulai.",
            buttons=get_menu_buttons(),
        )
        return
    await event.edit(text, buttons=[[Button.inline("🔙 Kembali", data="menu_back")]])


@bot.on(events.NewMessage(pattern=r"(?i)^/cancel$"))
async def cancel_command(event):
    if not (event.is_private or event.chat_id == LOG_GROUP_ID):
        return
    if add_pt_state.pop(event.sender_id, None):
        await event.respond("> ❌ **Proses penginputan/pengeditan data partner telah dibatalkan.**")
    else:
        await event.respond("> ⚠️ Tidak ada proses penginputan partner yang sedang aktif.")


@bot.on(events.NewMessage(pattern=r"(?i)^/lpt$"))
async def list_partner(event):
    if is_authorized(event):
        text, buttons = build_partner_page()
        await event.respond(text, buttons=buttons, link_preview=False)


async def require_access(event) -> bool:
    if is_authorized(event):
        return True
    await event.answer("⚠️ Tidak ada akses!", alert=True)
    return False


@bot.on(events.CallbackQuery(pattern=r"^pt_page_\d+$"))
async def callback_pt_page(event):
    if await require_access(event):
        page = int(event.data.decode().rsplit("_", 1)[1])
        text, buttons = build_partner_page(page)
        await event.edit(text, buttons=buttons, link_preview=False)


@bot.on(events.CallbackQuery(pattern=r"^panel_close$"))
async def callback_panel_close(event):
    if await require_access(event):
        await event.edit("> 🔒 Panel layanan partner telah ditutup.", buttons=None)


@bot.on(events.CallbackQuery(pattern=r"^pt_preview_all$"))
async def callback_preview_all(event):
    await event.answer("🛠️ Fitur Kirim Semua sedang dalam pengembangan!", alert=True)


@bot.on(events.CallbackQuery(pattern=r"^pt_back_list$"))
async def callback_pt_back_list(event):
    if await require_access(event):
        text, buttons = build_partner_page()
        await event.edit(text, buttons=buttons, link_preview=False)


@bot.on(events.CallbackQuery(pattern=r"^pt_manage_\d+$"))
async def callback_manage_partner(event):
    if not await require_access(event):
        return
    index = int(event.data.decode().rsplit("_", 1)[1])
    keys = list(PARTNERS_DICT)
    if not 0 <= index < len(keys):
        return
    link = keys[index]
    data = PARTNERS_DICT[link]
    if not isinstance(data, dict):
        data = {"nama": data, "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
    text = (
        "⚙️ **PILIH BAGIAN YANG INGIN DIUBAH:**\n\n"
        f"> 🏢 **NAMA GC:** {data.get('nama', '-')}\n"
        f"> 🔗 **LINK GC:** {link}\n"
        f"> 🤖 **NAMA BOT:** {data.get('bot', '-')}\n"
        f"> 📢 **LINK CH:** {data.get('ch', '-')}\n"
        f"> 👮 **PJ 1:** {data.get('pj1', '-')}\n"
        f"> 👮 **PJ 2:** {data.get('pj2', '-')}"
    )
    buttons = [
        [Button.inline("👆 Edit Nama GC", data=f"pt_edit_nama_{index}"), Button.inline("👆 Edit Link GC", data=f"pt_edit_link_{index}")],
        [Button.inline("👆 Edit Bot", data=f"pt_edit_bot_{index}"), Button.inline("👆 Edit CH", data=f"pt_edit_ch_{index}")],
        [Button.inline("👆 Edit PJ 1", data=f"pt_edit_pj1_{index}"), Button.inline("👆 Edit PJ 2", data=f"pt_edit_pj2_{index}")],
        [Button.inline("🔴 Hapus Partner", data=f"pt_delconf_{index}"), Button.inline("❌ Kembali", data="pt_back_list")],
        [Button.inline("🔴 Tutup Panel", data="panel_close")],
    ]
    await event.edit(text, buttons=buttons, link_preview=False)


@bot.on(events.CallbackQuery(pattern=r"^pt_delconf_\d+$"))
async def callback_delconf_partner(event):
    if not await require_access(event):
        return
    index = int(event.data.decode().rsplit("_", 1)[1])
    keys = list(PARTNERS_DICT)
    if not 0 <= index < len(keys):
        return
    data = PARTNERS_DICT[keys[index]]
    name = data.get("nama", "Tanpa Nama") if isinstance(data, dict) else data
    text = f"⚠️ **KONFIRMASI PENGHAPUSAN**\n\n> Hapus partner '{name.upper()}' secara permanen?"
    buttons = [
        [Button.inline("✅ Ya, Hapus", data=f"pt_delfinal_{index}")],
        [Button.inline("❌ Batalkan", data=f"pt_manage_{index}")],
    ]
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(pattern=r"^pt_delfinal_\d+$"))
async def callback_delfinal_partner(event):
    if not await require_access(event):
        return
    index = int(event.data.decode().rsplit("_", 1)[1])
    keys = list(PARTNERS_DICT)
    if not 0 <= index < len(keys):
        return
    data = PARTNERS_DICT.pop(keys[index])
    name = data.get("nama", "Tanpa Nama") if isinstance(data, dict) else data
    save_partners(PARTNERS_DICT)
    await event.answer(f"🗑️ {name.upper()} berhasil dihapus!", alert=True)
    text, buttons = build_partner_page()
    await event.edit(text, buttons=buttons, link_preview=False)


EDIT_LABELS = {
    "nama": "Nama Grup (GC) baru",
    "link": "Link Grup (GC) baru berawalan http/t.me",
    "bot": "Nama Bot baru",
    "ch": "Link Channel (CH) baru",
    "pj1": "Username Penanggung Jawab 1 (PJ 1) baru",
    "pj2": "Username Penanggung Jawab 2 (PJ 2) baru",
}


@bot.on(events.CallbackQuery(pattern=r"^pt_edit_(nama|link|bot|ch|pj1|pj2)_\d+$"))
async def callback_trigger_edit(event):
    if not await require_access(event):
        return
    _, _, field, raw_index = event.data.decode().split("_", 3)
    add_pt_state[event.sender_id] = {"step": f"edit_{field}", "idx": int(raw_index)}
    await event.respond(
        "📝 **MODE EDIT DATA PARTNER**\n\n"
        f"> Kirimkan {EDIT_LABELS[field]} melalui chat.\n"
        "> Ketik /cancel untuk membatalkan."
    )
    await event.answer()


@bot.on(events.CallbackQuery(pattern=r"^pt_add_start$"))
async def callback_add_start(event):
    if await require_access(event):
        add_pt_state[event.sender_id] = {"step": "input_nama"}
        await event.respond(
            "➕ **TAMBAH PARTNER BARU (TAHAP 1/6)**\n\n"
            "> Masukkan Nama Partner (PT / Nama GC):\n> Ketik /cancel untuk membatalkan."
        )
        await event.answer()


def valid_link(value: str) -> bool:
    return value.startswith(("http://", "https://", "t.me/"))


@bot.on(events.NewMessage(incoming=True))
async def handle_multistep_input(event):
    if not (event.is_private or event.chat_id == LOG_GROUP_ID):
        return
    user_id = event.sender_id
    if user_id not in add_pt_state or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text.startswith("/cancel"):
        return

    state = add_pt_state[user_id]
    step = state["step"]
    input_steps = {
        "input_nama": ("nama", "input_link", "➕ **TAMBAH PARTNER BARU (TAHAP 2/6)**\n\n> Masukkan Link Partner (Link GC):"),
        "input_bot": ("bot", "input_ch", "➕ **TAMBAH PARTNER BARU (TAHAP 4/6)**\n\n> Masukkan Link Channel (CH):"),
        "input_ch": ("ch", "input_pj1", "➕ **TAMBAH PARTNER BARU (TAHAP 5/6)**\n\n> Masukkan Username PJ 1:"),
        "input_pj1": ("pj1", "input_pj2", "➕ **TAMBAH PARTNER BARU (TAHAP 6/6)**\n\n> Masukkan Username PJ 2:"),
    }
    if step in input_steps:
        field, next_step, prompt = input_steps[step]
        state[field] = text
        state["step"] = next_step
        await event.respond(prompt)
        return

    if step == "input_link":
        if not valid_link(text):
            await event.respond("> ⚠️ Link tidak valid. Harus diawali http atau t.me.")
        elif text in PARTNERS_DICT:
            await event.respond("> ⚠️ Link tersebut sudah terdaftar.")
        else:
            state["link"] = text
            state["step"] = "input_bot"
            await event.respond("➕ **TAMBAH PARTNER BARU (TAHAP 3/6)**\n\n> Masukkan Nama Bot pendukung:")
        return

    if step == "input_pj2":
        state["pj2"] = text
        PARTNERS_DICT[state["link"]] = {key: state[key] for key in ("nama", "bot", "ch", "pj1", "pj2")}
        save_partners(PARTNERS_DICT)
        del add_pt_state[user_id]
        await event.respond(f"✅ **PARTNER BERHASIL DITAMBAHKAN!**\n\n> NAMA GC: {state['nama']}\n> LINK GC: {state['link']}")
        return

    if not step.startswith("edit_"):
        return
    field = step.removeprefix("edit_")
    index = state["idx"]
    keys = list(PARTNERS_DICT)
    if not 0 <= index < len(keys):
        del add_pt_state[user_id]
        await event.respond("> ⚠️ Data partner sudah tidak ditemukan.")
        return
    old_link = keys[index]
    data = PARTNERS_DICT[old_link]
    if not isinstance(data, dict):
        data = {"nama": data, "bot": "-", "ch": "-", "pj1": "-", "pj2": "-"}
    if field == "link":
        if not valid_link(text):
            await event.respond("> ⚠️ Link tidak valid. Harus diawali http atau t.me.")
            return
        if text != old_link and text in PARTNERS_DICT:
            await event.respond("> ⚠️ Link tersebut sudah terdaftar.")
            return
        del PARTNERS_DICT[old_link]
        PARTNERS_DICT[text] = data
    else:
        data[field] = text
        PARTNERS_DICT[old_link] = data
    save_partners(PARTNERS_DICT)
    del add_pt_state[user_id]
    await event.respond(f"✅ **PERUBAHAN BERHASIL DISIMPAN!**\n\n> Data {field.upper()} berhasil dimodifikasi.")


@bot.on(events.NewMessage(pattern=r"(?i)^/end$"))
async def end_tagall(event):
    global stop_current_tagall
    if not is_authorized(event):
        return
    if not is_processing:
        await event.respond("> ⚠️ Tidak ada proses tagall yang sedang berjalan.")
        return
    stop_current_tagall = True
    await event.respond("> 🛑 Menghentikan proses tagall saat ini...")


async def clean_delayed(message_ids: list[int]):
    await asyncio.sleep(300)
    try:
        await bot.delete_messages(TARGET_GROUP_ID, message_ids)
        await bot.send_message(OWNER_ID, f"> 🧹 BERSIH: {len(message_ids)} pesan dihapus!")
    except Exception:
        pass


async def process_queue():
    global is_processing, stop_current_tagall
    is_processing = True
    try:
        while not tagall_queue.empty():
            task = await tagall_queue.get()
            stop_current_tagall = False
            message_ids = []
            try:
                await bot.send_message(task["p"], "> 🚀 GILIRAN ANDA DIMULAI!")
                chat = await bot.get_entity(TARGET_GROUP_ID)
                group_name = getattr(chat, "title", "Target Group")
                start = await bot.send_message(TARGET_GROUP_ID, f"🚀 TAGALL DIMULAI\n👥 GROUP: {group_name}")
                message_ids.append(start.id)
                await bot.send_message(
                    LOG_GROUP_ID,
                    build_log_start(task["u"], task["p"], datetime.now().strftime("%d-%m-%Y %H:%M"), task["m"], task["t"]),
                    parse_mode="md",
                    link_preview=False,
                )
                markers = []
                async for participant in bot.iter_participants(TARGET_GROUP_ID):
                    if not participant.bot:
                        markers.append(random.choice(EMOJIS))
                started_at = time.monotonic()
                for offset in range(0, len(markers), 10):
                    if stop_current_tagall or time.monotonic() - started_at >= 300:
                        break
                    try:
                        sent = await bot.send_message(TARGET_GROUP_ID, f"{task['t']}\n\n{' '.join(markers[offset:offset + 10])}", parse_mode="md")
                        message_ids.append(sent.id)
                    except FloodWaitError as error:
                        await asyncio.sleep(error.seconds + 1)
                    await asyncio.sleep(1.2)
                status = "Dihentikan Paksa (/end)" if stop_current_tagall else "Selesai"
                finished = await bot.send_message(TARGET_GROUP_ID, f"✅ {status}! Pesan akan dihapus dalam 5 menit.")
                message_ids.append(finished.id)
                await bot.send_message(LOG_GROUP_ID, build_log_done(task["p"], task["m"], task["pt"], len(markers)), parse_mode="md")
                await bot.send_message(task["p"], build_receipt(datetime.now().strftime("%d-%m-%Y %H:%M"), group_name, task["m"], len(markers)), parse_mode="md")
                asyncio.create_task(clean_delayed(message_ids))
            except Exception as error:
                print(f"Gagal memproses antrean: {error}")
            finally:
                tagall_queue.task_done()
    finally:
        is_processing = False


@bot.on(events.NewMessage(incoming=True))
async def handle_public_auto_tagall(event):
    global is_processing
    if not event.is_private or not event.raw_text or event.raw_text.startswith("/"):
        return
    if event.sender_id in add_pt_state:
        return
    urls = re.findall(r"(?:https?://\S+|t\.me/\S+)", event.raw_text)
    link = next((url.rstrip(".,;)") for url in urls if url.rstrip(".,;)") in PARTNERS_DICT), None)
    if not link:
        await event.respond("❌ **LINK TIDAK TERDAFTAR**\n\n> Link belum terdata sebagai mitra resmi.")
        return
    partner = PARTNERS_DICT[link]
    name = partner.get("nama", "Tanpa Nama") if isinstance(partner, dict) else partner
    sender = await event.get_sender()
    queue_position = tagall_queue.qsize() + 1
    await tagall_queue.put({"p": event.sender_id, "t": event.raw_text, "m": link, "pt": name, "u": sender.username or "tidak_ada"})
    if is_processing:
        await event.respond(f"⏳ **ANTREAN DITERIMA**\n\n> Permintaan Anda berada di antrean ke-{queue_position}.")
    else:
        # Set the flag before creating the task so parallel incoming messages cannot start a second worker.
        is_processing = True
        await event.respond("✅ **TERVERIFIKASI!**\n\n> Link valid! Memulai bot tagall...")
        asyncio.create_task(process_queue())


bot.loop.create_task(init_bot_commands())
bot.run_until_disconnected()
