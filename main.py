from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import json

import config
import odoo
import groq_ai
import telegram
import memory
import scheduler as sched

INTENT_PROMPT = """Kamu adalah sistem deteksi intent. Analisis pesan user dan tentukan data apa yang dibutuhkan.
Balas HANYA dengan JSON (tanpa markdown):
{"intents": ["..."], "keyword": "kata kunci produk atau null"}
Pilihan intents: omzet_hari_ini, omzet_bulan_ini, laba_rugi, stok, harga, modal, piutang, terlaris, info_toko, general
Contoh:
- "cek oli mpx" -> {"intents": ["stok", "harga"], "keyword": "oli mpx"}
- "omzet hari ini" -> {"intents": ["omzet_hari_ini"], "keyword": null}
- "halo" -> {"intents": ["general"], "keyword": null}
"""

KONTEKS_TOKO = """
- Produk diakhiri (A) = ASLI/ORI
- Produk tanpa (A) = reguler
- Harga Rp 1 atau Rp 0 = belum diisi
- Modal Rp 0 = belum diisi
"""

MENU_MAP = {
    "💰 Omzet":    "omzet_hari_ini",
    "📈 Laba Rugi": "laba_rugi",
    "💳 Piutang":  "piutang",
    "📊 Laporan":  "laporan",
    "📦 Stok":     "stok",
    "💲 Harga":    "harga",
    "🔧 Modal":    "modal",
    "🏆 Terlaris": "terlaris",
}

CUSTOMER_MENU_MAP = {
    "🔍 Cek Harga Produk": "cek_harga",
}

def load_extra_owners():
    try:
        extras = open('/opt/ai-agent/owners.txt').read().splitlines()
        for oid in extras:
            if oid.strip() and oid.strip() not in config.TELEGRAM_OWNER_CHAT_IDS:
                config.TELEGRAM_OWNER_CHAT_IDS.append(oid.strip())
    except:
        pass

load_extra_owners()

async def detect_intent(pesan: str) -> dict:
    try:
        hasil = await groq_ai.ask([{"role": "user", "content": pesan}], INTENT_PROMPT)
        hasil = hasil.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(hasil)
    except Exception as e:
        print(f"[Intent Error] {e}")
        return {"intents": ["general"], "keyword": None}

async def build_context(intent_data: dict) -> str:
    intents = intent_data.get("intents", [])
    keyword = intent_data.get("keyword")
    parts   = []
    for intent in intents:
        try:
            if intent == "omzet_hari_ini":
                d = odoo.get_omzet_hari_ini()
                parts.append(f"Omzet hari ini: Rp {d['total']:,.0f} ({d['jumlah_transaksi']} transaksi)")
            elif intent == "omzet_bulan_ini":
                d = odoo.get_omzet_bulan_ini()
                parts.append(f"Omzet bulan ini: Rp {d['total']:,.0f} ({d['jumlah_transaksi']} transaksi)")
            elif intent == "laba_rugi":
                d = odoo.get_laporan_laba_rugi()
                parts.append(
                    f"Laba rugi bulan ini:\n"
                    f"- Omzet: Rp {d['omzet']:,.0f}\n"
                    f"- HPP: Rp {d['hpp']:,.0f}\n"
                    f"- Laba kotor: Rp {d['laba_kotor']:,.0f}\n"
                    f"- Total biaya: Rp {d['total_biaya']:,.0f}\n"
                    f"- Laba bersih: Rp {d['laba_bersih']:,.0f}\n"
                    f"- Margin: {d['margin_persen']}%"
                )
            elif intent in ["stok", "harga", "modal"]:
                if keyword:
                    d = odoo.get_stok_fuzzy(keyword)
                else:
                    d = []
                if d:
                    rows = "\n".join([
                        f"- {x['name']}: stok {x['qty_available']:.0f}, "
                        f"harga Rp {x.get('list_price', 0):,.0f}, "
                        f"modal Rp {x.get('standard_price', 0):,.0f}"
                        for x in d[:15]
                    ])
                    parts.append(f"Data produk '{keyword}':\n{rows}")
                else:
                    parts.append(f"Produk '{keyword}' tidak ditemukan.")
            elif intent == "piutang":
                d     = odoo.get_piutang_customer()
                total = sum(x['amount_residual'] for x in d)
                rows  = "\n".join([f"- {x['partner_id'][1]}: Rp {x['amount_residual']:,.0f}" for x in d[:10]])
                parts.append(f"Piutang (total Rp {total:,.0f}):\n{rows or 'Tidak ada'}")
            elif intent == "terlaris":
                d    = odoo.get_produk_terlaris(10)
                rows = "\n".join([f"- {nama}: {data['qty']:.0f} pcs, Rp {data['total']:,.0f}" for nama, data in d])
                parts.append(f"Produk terlaris bulan ini:\n{rows}")
        except Exception as e:
            print(f"[Context Error] {intent}: {e}")
    return "\n\n".join(parts) if parts else ""

def owner_prompt(context: str, nama_toko: str) -> str:
    return (
        f"Kamu adalah Ara, asisten bisnis santai untuk toko {nama_toko}.\n\n"
        f"ATURAN:\n"
        f"- Jawab HANYA dari data di bawah\n"
        f"- Jika data kosong -> 'Data tidak tersedia, coba tanya ulang'\n"
        f"- JANGAN mengarang angka\n"
        f"- Bahasa santai, emoji secukupnya\n\n"
        f"KONTEKS TOKO:\n{KONTEKS_TOKO}\n\n"
        f"DATA:\n{context if context else 'Tidak ada data'}"
    )

def format_produk(produk: list, tipe: str, keyword: str) -> str:
    ori = []
    reguler = []
    for p in produk[:20]:
        nama  = p["name"]
        stok  = p["qty_available"]
        harga = p.get("list_price", 0)
        modal = p.get("standard_price", 0)
        if tipe == "stok":
            val = "HABIS" if stok == 0 else f"{stok:.0f} unit"
        elif tipe == "harga":
            val = f"Rp {harga:,.0f}" if harga > 1 else "belum diisi"
        else:
            val = f"Rp {modal:,.0f}" if modal > 0 else "belum diisi"
        if "(A)" in nama:
            ori.append(f"{nama}: {val}")
        else:
            reguler.append(f"{nama}: {val}")
    header = {"stok": "STOK", "harga": "HARGA JUAL", "modal": "MODAL"}
    judul  = f"*{header.get(tipe, tipe.upper())} — {keyword.upper()}*"
    bagian = []
    if reguler:
        bagian.append("*REGULER*\n" + "\n".join(reguler))
    if ori:
        bagian.append("*ORI*\n" + "\n".join(ori))
    return judul + "\n\n" + "\n\n".join(bagian)

async def send_menu(chat_id: str):
    await telegram.send_reply_keyboard(chat_id, "🏪 *USAHA BARU* — Pilih menu:")

async def send_ask_keyword(chat_id: str, tipe: str):
    label = {"stok": "stok", "harga": "harga", "modal": "modal"}
    await telegram.send_message(chat_id,
        f"Ketik nama produk yang ingin dicek {label.get(tipe, '')}nya:\n_(contoh: oli mpx, sorax, avian)_"
    )

async def polling_loop():
    print("[Telegram] Polling dimulai...")
    await telegram.delete_webhook()
    offset = 0
    while True:
        try:
            updates = await telegram.get_updates(offset)
            for update in updates:
                offset = update['update_id'] + 1
                if "callback_query" in update:
                    asyncio.create_task(handle_callback(update["callback_query"]))
                    continue
                message = update.get("message", {})
                if not message:
                    continue
                chat_id = str(message.get("chat", {}).get("id", ""))
                pesan   = message.get("text", "").strip()
                if not pesan or not chat_id:
                    continue
                print(f"[TG] {chat_id}: {pesan}")
                asyncio.create_task(proses_update(chat_id, message, pesan))
        except Exception as e:
            print(f"[Polling Error] {e}")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    memory.init_db()
    sched.start_scheduler()
    asyncio.create_task(polling_loop())
    print(f"[AI Agent Ara] Port {config.PORT}")
    yield

app = FastAPI(title="AI Agent Ara", lifespan=lifespan)

async def handle_callback(callback: dict):
    chat_id     = str(callback["from"]["id"])
    callback_id = callback["id"]
    data        = callback.get("data", "")
    await telegram.answer_callback(callback_id)
    if data == "noop":
        return
    if chat_id not in config.TELEGRAM_OWNER_CHAT_IDS:
        await telegram.send_message(chat_id, "Akses ditolak.")
        return
    if data in ["stok", "harga", "modal"]:
        memory.save_state(chat_id, f"waiting_{data}")
        await send_ask_keyword(chat_id, data)
        return
    if data == "laporan":
        await sched.kirim_laporan_harian()
        return
    intent_map = {
        "omzet_hari_ini": {"intents": ["omzet_hari_ini"], "keyword": None},
        "laba_rugi":      {"intents": ["laba_rugi", "omzet_bulan_ini"], "keyword": None},
        "piutang":        {"intents": ["piutang"], "keyword": None},
        "terlaris":       {"intents": ["terlaris"], "keyword": None},
    }
    if data in intent_map:
        await telegram.send_message(chat_id, "Mengambil data...")
        context = await build_context(intent_map[data])
        prompt  = owner_prompt(context, "usahabaru")
        label   = {"omzet_hari_ini": "omzet hari ini", "laba_rugi": "laba rugi",
                   "piutang": "piutang customer", "terlaris": "produk terlaris"}
        jawaban = await groq_ai.ask(
            [{"role": "user", "content": f"Tampilkan {label.get(data, data)}"}],
            prompt
        )
        await telegram.send_message(chat_id, jawaban)

async def proses_update(chat_id: str, message: dict, pesan: str):
    is_owner = chat_id in config.TELEGRAM_OWNER_CHAT_IDS

    if pesan in ["/start", "/menu"]:
        await handle_start(chat_id, message)
        return

    if pesan == "/myid":
        await telegram.send_message(chat_id,
            f"Chat ID kamu: `{chat_id}`\n\nKirim angka ini ke owner untuk mendapat akses penuh."
        )
        return

    if pesan == "/addowner" and is_owner:
        await telegram.send_message(chat_id,
            "Minta orang yang mau ditambah ketik */myid* ke bot.\n"
            "Setelah dapat Chat ID, ketik:\n`/addowner 123456789`"
        )
        return

    if pesan.startswith("/addowner ") and is_owner:
        new_id = pesan.replace("/addowner ", "").strip()
        if new_id.isdigit():
            with open('/opt/ai-agent/owners.txt', 'a') as f:
                f.write(new_id + "\n")
            load_extra_owners()
            await telegram.send_message(chat_id, f"Owner `{new_id}` berhasil ditambahkan!")
            await telegram.send_message(new_id, "Kamu ditambahkan sebagai owner *usahabaru*!\n\nKetik /start untuk mulai.")
        else:
            await telegram.send_message(chat_id, "Format salah. Contoh: `/addowner 123456789`")
        return

    if pesan.startswith("/removeowner ") and is_owner:
        rem_id = pesan.replace("/removeowner ", "").strip()
        try:
            owners = open('/opt/ai-agent/owners.txt').read().splitlines()
            owners = [o for o in owners if o != rem_id]
            open('/opt/ai-agent/owners.txt', 'w').write("\n".join(owners))
            load_extra_owners()
            await telegram.send_message(chat_id, f"Owner `{rem_id}` berhasil dihapus.")
        except:
            await telegram.send_message(chat_id, "Gagal menghapus owner.")
        return

    if pesan == "/reset":
        memory.clear_history(chat_id)
        memory.clear_state(chat_id)
        await telegram.send_message(chat_id, "Direset!")
        return

    # Tombol customer
    if pesan in CUSTOMER_MENU_MAP and not is_owner:
        memory.save_state(chat_id, "waiting_harga_customer")
        await telegram.send_message(chat_id,
            "Ketik nama produk:\n_(contoh: oli, sorax, avian)_"
        )
        return

    # Tombol owner
    if pesan in MENU_MAP and is_owner:
        data = MENU_MAP[pesan]
        if data in ["stok", "harga", "modal"]:
            memory.save_state(chat_id, f"waiting_{data}")
            await send_ask_keyword(chat_id, data)
            return
        if data == "laporan":
            await sched.kirim_laporan_harian()
            return
        intent_map = {
            "omzet_hari_ini": {"intents": ["omzet_hari_ini"], "keyword": None},
            "laba_rugi":      {"intents": ["laba_rugi", "omzet_bulan_ini"], "keyword": None},
            "piutang":        {"intents": ["piutang"], "keyword": None},
            "terlaris":       {"intents": ["terlaris"], "keyword": None},
        }
        if data in intent_map:
            await telegram.send_message(chat_id, "Mengambil data...")
            context = await build_context(intent_map[data])
            prompt  = owner_prompt(context, "usahabaru")
            label   = {"omzet_hari_ini": "omzet hari ini", "laba_rugi": "laba rugi",
                       "piutang": "piutang customer", "terlaris": "produk terlaris"}
            jawaban = await groq_ai.ask(
                [{"role": "user", "content": f"Tampilkan {label.get(data, data)}"}],
                prompt
            )
            await telegram.send_message(chat_id, jawaban)
            return

    # Cek state waiting keyword
    state = memory.get_state(chat_id)
    if state and state.startswith("waiting_"):
        tipe = state.replace("waiting_", "")
        memory.clear_state(chat_id)
        await telegram.send_message(chat_id, "Mencari data...")
        produk = odoo.get_stok_fuzzy(pesan)
        if not produk:
            await telegram.send_message(chat_id, f"Produk '{pesan}' tidak ditemukan.")
            return
        if tipe == "harga_customer":
            # Format untuk customer — harga saja
            ori = []
            reguler = []
            for p in produk[:15]:
                nama  = p["name"]
                harga = p.get("list_price", 0)
                val   = f"Rp {harga:,.0f}" if harga > 1 else "Hubungi toko"
                if "(A)" in nama:
                    ori.append(f"{nama}: {val}")
                else:
                    reguler.append(f"{nama}: {val}")
            bagian = []
            if reguler:
                bagian.append("*REGULER*\n" + "\n".join(reguler))
            if ori:
                bagian.append("*ORI*\n" + "\n".join(ori))
            jawaban = f"*HARGA — {pesan.upper()}*\n\n" + "\n\n".join(bagian)
        else:
            jawaban = format_produk(produk, tipe, pesan)
        await telegram.send_message(chat_id, jawaban)
        return

    # Chat bebas
    await proses_pesan(chat_id, pesan)

async def handle_start(chat_id: str, message: dict):
    nama = message.get("from", {}).get("first_name", "")
    if chat_id in config.TELEGRAM_OWNER_CHAT_IDS:
        await send_menu(chat_id)
        return
    await telegram.send_reply_keyboard_customer(chat_id,
        f"Halo *{nama}*! Saya *Ara* dari toko *usahabaru*\n\nCek harga produk kami di sini!"
    )

async def proses_pesan(chat_id: str, pesan: str):
    is_owner = chat_id in config.TELEGRAM_OWNER_CHAT_IDS
    history  = memory.get_history(chat_id, limit=6)
    memory.save_message(chat_id, "user", pesan)
    history.append({"role": "user", "content": pesan})
    try:
        if is_owner:
            last        = history[-2]["content"] if len(history) >= 2 else ""
            pesan_ctx   = f"{pesan} (konteks: {last})" if last else pesan
            intent_data = await detect_intent(pesan_ctx)
            print(f"[Intent] {intent_data}")
            context     = await build_context(intent_data)
            prompt      = owner_prompt(context, "usahabaru")
        else:
            prompt = (
                "Kamu adalah Ara, asisten toko usahabaru yang ramah.\n"
                "Jawab HANYA info harga produk. Jangan sebut data keuangan toko."
            )
        jawaban = await groq_ai.ask(history, prompt)
    except Exception as e:
        print(f"[Error] {e}")
        jawaban = "Maaf, ada gangguan. Coba lagi ya!"
    memory.save_message(chat_id, "assistant", jawaban)
    await telegram.send_message(chat_id, jawaban)

@app.get("/")
async def root():
    return {"status": "running", "service": "AI Agent Ara"}

@app.post("/laporan-manual")
async def laporan_manual():
    await sched.kirim_laporan_harian()
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
