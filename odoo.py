import xmlrpc.client
from datetime import date
import config

def _get_uid():
    common = xmlrpc.client.ServerProxy(f"{config.ODOO_URL}/xmlrpc/2/common")
    return common.authenticate(config.ODOO_DB, config.ODOO_USERNAME, config.ODOO_PASSWORD, {})

def _call(model, method, args, kwargs=None):
    uid = _get_uid()
    models = xmlrpc.client.ServerProxy(f"{config.ODOO_URL}/xmlrpc/2/object")
    return models.execute_kw(config.ODOO_DB, uid, config.ODOO_PASSWORD, model, method, args, kwargs or {})

def _today():
    return date.today().strftime("%Y-%m-%d")

def _month_start():
    return date.today().replace(day=1).strftime("%Y-%m-%d")

def get_omzet_hari_ini():
    orders = _call('pos.order', 'search_read', [[
        ['date_order', '>=', f"{_today()} 00:00:00"],
        ['date_order', '<=', f"{_today()} 23:59:59"],
        ['state', 'in', ['done', 'invoiced']]
    ]], {'fields': ['amount_total'], 'limit': 1000})
    return {'total': sum(o['amount_total'] for o in orders), 'jumlah_transaksi': len(orders), 'tanggal': _today()}

def get_omzet_bulan_ini():
    orders = _call('pos.order', 'search_read', [[
        ['date_order', '>=', f"{_month_start()} 00:00:00"],
        ['state', 'in', ['done', 'invoiced']]
    ]], {'fields': ['amount_total'], 'limit': 10000})
    return {'total': sum(o['amount_total'] for o in orders), 'jumlah_transaksi': len(orders)}

def get_produk_terlaris(limit=5):
    lines = _call('pos.order.line', 'search_read', [[
        ['order_id.date_order', '>=', f"{_month_start()} 00:00:00"],
        ['order_id.state', 'in', ['done', 'invoiced']]
    ]], {'fields': ['product_id', 'qty', 'price_subtotal'], 'limit': 10000})
    produk = {}
    for line in lines:
        nama = line['product_id'][1] if line['product_id'] else 'Unknown'
        if nama not in produk:
            produk[nama] = {'qty': 0, 'total': 0}
        produk[nama]['qty'] += line['qty']
        produk[nama]['total'] += line['price_subtotal']
    return sorted(produk.items(), key=lambda x: x[1]['qty'], reverse=True)[:limit]

def get_stok_produk(keyword=None):
    domain = [['type', '=', 'product']]
    if keyword:
        domain.append(['name', 'ilike', keyword])
    return _call('product.product', 'search_read', [domain], {'fields': ['name', 'qty_available', 'uom_id', 'list_price', 'standard_price'], 'limit': 50})

def get_stok_hampir_habis(batas=None):
    batas = batas or config.STOCK_ALERT_LIMIT
    return _call('product.product', 'search_read', [[
        ['type', '=', 'product'],
        ['qty_available', '<=', batas],
        ['qty_available', '>', 0]
    ]], {'fields': ['name', 'qty_available', 'uom_id'], 'limit': 50})

def get_stok_habis():
    return _call('product.product', 'search_read', [[
        ['type', '=', 'product'],
        ['qty_available', '<=', 0]
    ]], {'fields': ['name'], 'limit': 50})

def get_laporan_laba_rugi():
    omzet = get_omzet_bulan_ini()
    try:
        svl = _call('stock.valuation.layer', 'search_read', [[
            ['create_date', '>=', f"{_month_start()} 00:00:00"],
            ['value', '<', 0]
        ]], {'fields': ['value'], 'limit': 10000})
        hpp = abs(sum(s['value'] for s in svl))
    except:
        hpp = 0
    try:
        expenses = _call('account.move.line', 'search_read', [[
            ['date', '>=', _month_start()],
            ['account_id.account_type', 'in', ['expense', 'expense_depreciation']],
            ['move_id.state', '=', 'posted']
        ]], {'fields': ['balance'], 'limit': 10000})
        total_biaya = sum(e['balance'] for e in expenses)
    except:
        total_biaya = 0
    laba_kotor  = omzet['total'] - hpp
    laba_bersih = laba_kotor - total_biaya
    margin      = round((laba_bersih / omzet['total'] * 100), 1) if omzet['total'] > 0 else 0
    return {'omzet': omzet['total'], 'hpp': hpp, 'laba_kotor': laba_kotor, 'total_biaya': total_biaya, 'laba_bersih': laba_bersih, 'margin_persen': margin}

def get_piutang_customer():
    return _call('account.move', 'search_read', [[
        ['move_type', '=', 'out_invoice'],
        ['payment_state', 'in', ['not_paid', 'partial']],
        ['state', '=', 'posted']
    ]], {'fields': ['partner_id', 'amount_residual', 'name'], 'limit': 100})

def get_piutang_by_partner(partner_id: int):
    return _call('account.move', 'search_read', [[
        ['partner_id', '=', partner_id],
        ['move_type', '=', 'out_invoice'],
        ['payment_state', 'in', ['not_paid', 'partial']],
        ['state', '=', 'posted']
    ]], {'fields': ['name', 'amount_residual'], 'limit': 20})

def get_customer_by_phone(phone: str):
    clean = phone[-9:]
    partners = _call('res.partner', 'search_read', [[
        ['phone', 'ilike', clean],
        ['customer_rank', '>', 0]
    ]], {'fields': ['id', 'name', 'phone'], 'limit': 3})
    return partners[0] if partners else None

def get_daftar_produk(keyword=None):
    domain = [['sale_ok', '=', True], ['active', '=', True]]
    if keyword:
        domain.append(['name', 'ilike', keyword])
    return _call('product.template', 'search_read', [domain], {'fields': ['name', 'list_price', 'categ_id'], 'limit': 20})

def get_info_toko():
    company = _call('res.company', 'search_read', [[]], {'fields': ['name', 'phone', 'email', 'street', 'city'], 'limit': 1})
    return company[0] if company else {}

def get_stok_produk_multi(words: list):
    """Cari produk dengan multiple keyword (AND search)"""
    domain = [['type', '=', 'product']]
    for word in words:
        domain.append(['name', 'ilike', word])
    return _call('product.product', 'search_read', [domain], {
        'fields': ['name', 'qty_available', 'uom_id', 'list_price', 'standard_price'],
        'limit': 15
    })

def _get_variant_label(uid, models_proxy, attr_ids):
    """Ambil label varian produk"""
    if not attr_ids:
        return ""
    try:
        attrs = models_proxy.execute_kw(
            config.ODOO_DB, uid, config.ODOO_PASSWORD,
            'product.template.attribute.value', 'read',
            [attr_ids], {'fields': ['name']}
        )
        return ', '.join([a['name'] for a in attrs])
    except:
        return ""

def get_stok_fuzzy(keyword: str, limit=15):
    """Fuzzy search produk — toleran typo dan variasi penulisan"""
    from rapidfuzz import fuzz
    import re
    import xmlrpc.client

    uid = _get_uid()
    models_proxy = xmlrpc.client.ServerProxy(f"{config.ODOO_URL}/xmlrpc/2/object")

    # Ambil semua produk dengan varian
    semua = models_proxy.execute_kw(
        config.ODOO_DB, uid, config.ODOO_PASSWORD,
        'product.product', 'search_read',
        [[['type', '=', 'product']]],
        {'fields': ['name', 'qty_available', 'uom_id', 'list_price', 'standard_price', 'product_template_attribute_value_ids'], 'limit': 1000}
    )

    if not semua:
        return []

    # Normalisasi keyword — hapus spasi berlebih, lowercase
    kw = re.sub(r'\s+', ' ', keyword.strip().lower())
    
    # Split keyword jadi kata-kata
    words = kw.split()

    # Score setiap produk
    hasil = []
    for p in semua:
        nama_lower = p['name'].lower()
        
        # Cek apakah semua kata ada di nama produk
        all_words_match = all(
            fuzz.partial_ratio(w, nama_lower) >= 70 
            for w in words
        )
        
        # Score keseluruhan
        score = fuzz.token_sort_ratio(kw, nama_lower)
        
        if all_words_match or score >= 60:
            hasil.append((p, score))

    # Sort by score
    hasil.sort(key=lambda x: x[1], reverse=True)
    top = [p for p, score in hasil[:limit]]

    # Tambahkan label varian ke nama
    for p in top:
        attr_ids = p.get('product_template_attribute_value_ids', [])
        if attr_ids:
            varian = _get_variant_label(uid, models_proxy, attr_ids)
            if varian:
                p['name'] = f"{p['name']} [{varian}]"
    return top
