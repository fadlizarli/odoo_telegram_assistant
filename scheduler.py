from apscheduler.schedulers.asyncio import AsyncIOScheduler
import odoo
import telegram
import config

scheduler = AsyncIOScheduler()

def fmt_rp(amount):
    return f"Rp {amount:,.0f}".replace(',', '.')

async def kirim_laporan_harian():
    print("[Scheduler] Mengirim laporan harian...")
    try:
        omzet      = odoo.get_omzet_hari_ini()
        terlaris   = odoo.get_produk_terlaris(5)
        stok_tipis = odoo.get_stok_hampir_habis()
        piutang    = odoo.get_piutang_customer()

        total_piutang = sum(p['amount_residual'] for p in piutang)

        terlaris_text = ""
        for i, (nama, data) in enumerate(terlaris[:5], 1):
            terlaris_text += f"  {i}. {nama} ({data['qty']:.0f} pcs)\n"

        stok_text = ""
        for p in stok_tipis[:5]:
            stok_text += f"  ⚠️ {p['name']}: {p['qty_available']:.0f}\n"
        if not stok_text:
            stok_text = "  ✅ Semua stok aman\n"

        laporan = f"""📊 *LAPORAN HARIAN*
🗓️ {omzet['tanggal']}

💰 *Omzet Hari Ini*
{fmt_rp(omzet['total'])} ({omzet['jumlah_transaksi']} transaksi)

🏆 *Produk Terlaris Bulan Ini*
{terlaris_text}
📦 *Stok Perlu Diperhatikan*
{stok_text}
💳 *Total Piutang*
{fmt_rp(total_piutang)} ({len(piutang)} customer)

_Laporan otomatis sistem AI_"""

        await telegram.send_to_all_owners(laporan)
        print("[Scheduler] Laporan terkirim")

    except Exception as e:
        print(f"[Scheduler Error] {e}")

async def cek_stok_alert():
    print("[Scheduler] Cek stok...")
    try:
        habis  = odoo.get_stok_habis()
        tipis  = odoo.get_stok_hampir_habis()

        pesan = ""
        if habis:
            daftar = "\n".join([f"  ❌ {p['name']}" for p in habis[:10]])
            pesan += f"🚨 *STOK HABIS*\n{daftar}\n\n"

        if tipis:
            daftar = "\n".join([f"  ⚠️ {p['name']}: {p['qty_available']:.0f}" for p in tipis[:10]])
            pesan += f"⚠️ *STOK MENIPIS*\n{daftar}"

        if pesan:
            await telegram.send_to_all_owners(pesan)
            print("[Scheduler] Alert stok terkirim")

    except Exception as e:
        print(f"[Scheduler Stok Error] {e}")

def start_scheduler():
    jam, menit = config.DAILY_REPORT_TIME.split(":")

    # Laporan harian
    scheduler.add_job(
        kirim_laporan_harian, 'cron',
        hour=int(jam), minute=int(menit),
        id='laporan_harian'
    )

    # Cek stok 2x sehari (pagi & siang)
    scheduler.add_job(
        cek_stok_alert, 'cron',
        hour=8, minute=0,
        id='stok_pagi'
    )
    scheduler.add_job(
        cek_stok_alert, 'cron',
        hour=13, minute=0,
        id='stok_siang'
    )

    scheduler.start()
    print(f"[Scheduler] Laporan harian: {config.DAILY_REPORT_TIME} WIB")
    print(f"[Scheduler] Cek stok: 08:00 & 13:00 WIB")
