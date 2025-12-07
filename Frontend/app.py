import streamlit as st
from web3 import Web3
import pandas as pd
import json
import time

# ==========================================
# 1. KONFIGURASI & SETUP
# ==========================================
st.set_page_config(page_title="Vending DAO Super App", layout="wide", page_icon="☕")

GANACHE_URL = "http://127.0.0.1:7545" 
# GANTI DENGAN ALAMAT CONTRACT TERBARU DI SINI 👇
CONTRACT_ADDRESS = "0xe46D6d237Ec4021024b18BebB11dF4F2cB9819E9" 

# Inisialisasi Session State untuk Web3 agar tidak reload terus
if "w3" not in st.session_state:
    st.session_state.w3 = Web3(Web3.HTTPProvider(GANACHE_URL))

w3 = st.session_state.w3

# Load ABI Utama
try:
    with open('abi.json', 'r') as f:
        contract_abi = json.load(f)
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
except Exception as e:
    st.error(f"Gagal memuat abi.json: {e}")
    st.stop()

# Load Token Contract (Minimal ABI untuk Approve & Cek Saldo)
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

try:
    PAYMENT_TOKEN_ADDR = contract.functions.paymentToken().call()
    ASSET_TOKEN_ADDR = contract.functions.assetToken().call()
    payment_token = w3.eth.contract(address=PAYMENT_TOKEN_ADDR, abi=ERC20_ABI)
    asset_token = w3.eth.contract(address=ASSET_TOKEN_ADDR, abi=ERC20_ABI)
except:
    st.toast("Warning: Gagal load token address. Pastikan contract sudah deploy.", icon="⚠️")

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def fmt_rupiah(wei_value):
    return f"{wei_value / 10**18:,.0f}"

def short_addr(address):
    if address:
        return f"{address[:6]}...{address[-4:]}"
    return "Unknown"

def send_transaction(func_call, account_addr, private_key, value=0):
    """Helper untuk mengirim transaksi Write ke Blockchain"""
    try:
        nonce = w3.eth.get_transaction_count(account_addr)
        tx_data = func_call.build_transaction({
            'chainId': 1337, 
            'gas': 3000000,
            'gasPrice': w3.to_wei('20', 'gwei'),
            'nonce': nonce,
            'from': account_addr,
            'value': value
        })
        signed_tx = w3.eth.account.sign_transaction(tx_data, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return w3.to_hex(tx_hash)
    except Exception as e:
        return f"ERROR: {str(e)}"

def check_and_approve(token_contract, owner_addr, spender_addr, amount, private_key):
    """Otomatis cek allowance dan approve jika kurang"""
    allowance = token_contract.functions.allowance(owner_addr, spender_addr).call()
    if allowance < amount:
        with st.spinner("⏳ Allowance kurang. Melakukan Approval token..."):
            try:
                tx_hash = send_transaction(
                    token_contract.functions.approve(spender_addr, amount),
                    owner_addr, private_key
                )
                if "ERROR" in tx_hash:
                    st.error(tx_hash)
                    return False
                w3.eth.wait_for_transaction_receipt(tx_hash)
                st.success("✅ Approve Berhasil!")
                time.sleep(1)
                return True
            except Exception as e:
                st.error(f"Gagal Approve: {e}")
                return False
    return True

# ==========================================
# 3. FUNGSI BACA DATA (DARI TEMAN ANDA)
# ==========================================
def get_financial_data():
    try:
        revenue = contract.functions.totalRevenue().call()
        growth_fund = contract.functions.growthFund().call()
        # Fallback jika fungsi getOperationalReserve tidak ada di ABI lama
        try:
            reserve = contract.functions.getOperationalReserve().call()
        except:
            reserve = 0 
        div_distributed = contract.functions.totalDividendsDistributed().call()
        
        return {
            "Total Omzet": fmt_rupiah(revenue),
            "Growth Fund": fmt_rupiah(growth_fund),
            "Kas Operasional": fmt_rupiah(reserve),
            "Total Dividen": fmt_rupiah(div_distributed)
        }
    except:
        return {"Total Omzet": "0", "Growth Fund": "0", "Kas Operasional": "0", "Total Dividen": "0"}

def get_all_events():
    events_list = []
    
    # Logic pengambilan event dari kode teman Anda (Dipertahankan karena bagus pakai LogIndex)
    
    # 1. Jualan
    for e in contract.events.CoffeeOrdered.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "☕ JUALAN KOPI",
            "Detail": f"Mesin #{e['args']['machineId']} | +Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": short_addr(e['args']['buyer'])
        })
    # 2. Expense
    for e in contract.events.ExpensePaid.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": f"💸 KELUAR: {e['args'].get('category', 'Expense')}", # Handle if category not exists
            "Detail": f"Note: {e['args']['note']} | -Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": short_addr(e['args']['to'])
        })
    # 3. IPO
    for e in contract.events.SharesPurchased.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "📈 BELI SAHAM (IPO)",
            "Detail": f"Beli: {e['args']['amount']/10**18:,.0f} Lembar",
            "Pelaku": short_addr(e['args']['investor'])
        })
    # 4. Transfer
    for e in contract.events.ShareTransferred.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "🔄 TRANSFER SAHAM",
            "Detail": f"Jml: {e['args']['amount']/10**18:,.0f} Lembar",
            "Pelaku": f"{short_addr(e['args']['from'])} -> {short_addr(e['args']['to'])}"
        })
    # 5. Claim
    for e in contract.events.DividendClaimed.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "💰 TARIK DIVIDEN",
            "Detail": f"Cair: Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": short_addr(e['args']['investor'])
        })
    # 6. Proposal
    for e in contract.events.ProposalCreated.create_filter(from_block=0).get_all_entries():
        # Handle perbedaan nama args (desc vs description)
        desc = e['args'].get('desc', e['args'].get('description', '-'))
        pType = e['args'].get('pType', '-')
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "🗳️ PROPOSAL BARU",
            "Detail": f"ID: {e['args']['id']} | {pType} | {desc}",
            "Pelaku": "DAO"
        })
    # 7. Profit Distributed
    for e in contract.events.ProfitDistributed.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "📊 BAGI HASIL",
            "Detail": f"Dividen: Rp {fmt_rupiah(e['args']['dividendAmount'])} | Growth: Rp {fmt_rupiah(e['args']['growthAmount'])}",
            "Pelaku": "System"
        })

    df = pd.DataFrame(events_list)
    if not df.empty:
        df = df.sort_values(by=['Block', 'LogIndex'], ascending=[False, False])
    return df

# ==========================================
# 4. HALAMAN DASHBOARD (EXPLORER)
# ==========================================
def page_dashboard():
    st.title("🤖 Vending Machine DAO Dashboard")
    st.markdown("Monitor transparansi keuangan & operasional blockchain secara Real-Time.")

    # Status Koneksi
    if w3.is_connected():
        st.caption(f"Status: 🟢 Terhubung ke {GANACHE_URL}")
    else:
        st.error("Gagal terhubung ke Ganache.")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    fin = get_financial_data()
    col1.metric("Total Omzet", f"Rp {fin['Total Omzet']}")
    col2.metric("Growth Fund", f"Rp {fin['Growth Fund']}")
    col3.metric("Kas Operasional", f"Rp {fin['Kas Operasional']}")
    col4.metric("Total Dividen", f"Rp {fin['Total Dividen']}")

    st.divider()

    # Tabel Log
    st.subheader("📜 Riwayat Blok (Blockchain Ledger)")
    if st.button("🔄 Refresh Manual"):
        st.rerun()

    df_events = get_all_events()
    if not df_events.empty:
        st.dataframe(
            df_events, 
            use_container_width=True,
            column_config={
                "Block": st.column_config.NumberColumn("Block", format="%d"),
                "LogIndex": st.column_config.NumberColumn("Idx", format="%d"),
            },
            hide_index=True
        )
    else:
        st.info("Belum ada aktivitas di smart contract ini.")

    # Auto refresh logic (Hanya di halaman Dashboard agar form input di halaman lain tidak reset)
    time.sleep(5)
    st.rerun()

# ==========================================
# 5. HALAMAN INVESTOR (TRANSAKSI)
# ==========================================
def page_investor():
    st.title("💰 Panel Investor")
    
    st.sidebar.header("🔐 Login Investor")
    pk_investor = st.sidebar.text_input("Private Key Investor", type="password")

    if not pk_investor:
        st.warning("Masukkan Private Key di sidebar kiri untuk mengakses fitur.")
        return

    try:
        account = w3.eth.account.from_key(pk_investor)
        my_addr = account.address
        st.sidebar.success(f"Login: {short_addr(my_addr)}")
    except:
        st.sidebar.error("Key Invalid")
        return

    # Info Portofolio
    my_shares = asset_token.functions.balanceOf(my_addr).call()
    my_div = contract.functions.getWithdrawableDividend(my_addr).call()
    share_price = contract.functions.sharePrice().call()

    c1, c2 = st.columns(2)
    c1.info(f"**Saham Saya:** {my_shares / 10**18:,.0f} Lembar")
    c2.success(f"**Dividen Siap Cair:** Rp {fmt_rupiah(my_div)}")

    tab1, tab2, tab3 = st.tabs(["Beli Saham (IPO)", "Klaim Dividen", "Voting DAO"])

    with tab1:
        st.subheader("Beli Saham Baru")
        st.write(f"Harga IPO: **Rp {fmt_rupiah(share_price)} / lembar**")
        amount_buy = st.number_input("Jumlah Lembar", min_value=1, value=10)
        total_cost = amount_buy * share_price
        st.write(f"Total Bayar: Rp {fmt_rupiah(total_cost)}")
        
        if st.button("Beli Saham Sekarang"):
            if check_and_approve(payment_token, my_addr, CONTRACT_ADDRESS, total_cost, pk_investor):
                tx = send_transaction(contract.functions.buyShares(amount_buy), my_addr, pk_investor)
                if "ERROR" in tx: st.error(tx)
                else: st.success(f"Sukses! Hash: {tx}")

    with tab2:
        st.subheader("Pencairan Dividen")
        if st.button("💸 Cairkan Semua Dividen"):
            tx = send_transaction(contract.functions.claimDividends(), my_addr, pk_investor)
            if "ERROR" in tx: st.error(tx)
            else: st.success(f"Dividen Cair! Hash: {tx}")

    with tab3:
        st.subheader("Voting Proposal")
        p_count = contract.functions.proposalCount().call()
        active_props = []
        for i in range(1, p_count + 1):
            p = contract.functions.proposals(i).call()
            # Cek executed status (index ke-6 di struct Proposal terakhir)
            if not p[6]: 
                active_props.append(f"ID {p[0]}: {p[4]}") # ID dan Desc

        if active_props:
            sel = st.selectbox("Pilih Proposal", active_props)
            p_id = int(sel.split(":")[0].replace("ID ", ""))
            if st.button("Vote Setuju"):
                tx = send_transaction(contract.functions.vote(p_id), my_addr, pk_investor)
                if "ERROR" in tx: st.error(tx)
                else: st.success("Vote Masuk!")
        else:
            st.info("Tidak ada proposal aktif.")

# ==========================================
# 6. HALAMAN ADMIN (OPERASIONAL)
# ==========================================
def page_admin():
    st.title("👮 Panel Admin / Owner")
    
    st.sidebar.header("🔐 Login Admin")
    pk_admin = st.sidebar.text_input("Private Key Admin", type="password")

    if not pk_admin:
        st.warning("Masukkan Private Key Admin.")
        return

    try:
        account = w3.eth.account.from_key(pk_admin)
        admin_addr = account.address
        # Cek Owner
        if admin_addr != contract.functions.owner().call():
            st.error("Wallet ini bukan Owner contract!")
            return
        st.sidebar.success(f"Admin: {short_addr(admin_addr)}")
    except:
        st.sidebar.error("Key Invalid")
        return

    t1, t2, t3, t4 = st.tabs(["Mesin", "Keuangan", "Proposal", "Eksekusi"])

    with t1:
        st.subheader("Tambah Mesin")
        loc = st.text_input("Lokasi Mesin")
        if st.button("Add Machine"):
            tx = send_transaction(contract.functions.addMachine(loc), admin_addr, pk_admin)
            if "ERROR" in tx: st.error(tx)
            else: st.success(f"Mesin ditambahkan! Hash: {tx}")
        
        st.subheader("Ubah Harga")
        np = st.number_input("Harga Kopi (IDRT)", value=15000)
        nc = st.number_input("Modal (COGS)", value=5000)
        if st.button("Update Harga"):
            tx = send_transaction(contract.functions.setCoffeePrice(int(np*10**18)), admin_addr, pk_admin)
            if "ERROR" in tx: st.error(tx)
            else: st.success("Harga diupdate.")
            # Note: setCogs belum diimplementasi di tombol ini, bisa ditambah jika perlu

    with t2:
        st.subheader("Bayar Vendor (Operasional)")
        vendor = st.text_input("Address Vendor")
        amt = st.number_input("Jumlah (IDRT)", min_value=1000)
        reason = st.text_input("Keperluan (Misal: Listrik)")
        
        if st.button("Bayar Tagihan"):
            # Perlu parameter 'category' di fungsi ExpensePaid jika versi contract baru
            # Asumsi fungsi: payMonthlySalary(address) ATAU logic manual via proposal
            st.info("Gunakan fitur Proposal untuk pengeluaran besar. Gunakan ini untuk gaji rutin.")
            if st.button("Bayar Gaji Staff (Via Address)"):
                 tx = send_transaction(contract.functions.payMonthlySalary(vendor), admin_addr, pk_admin)
                 if "ERROR" in tx: st.error(tx)
                 else: st.success(f"Gaji terbayar. Hash: {tx}")

    with t3:
        st.subheader("Buat Proposal Baru")
        ptype = st.selectbox("Tipe Proposal", ["0: Beli Mesin", "1: Beli Stok", "2: Gaji", "3: Add Vendor"])
        ptype_int = int(ptype.split(":")[0])
        p_target = st.text_input("Target Address")
        p_amount = st.number_input("Jumlah Dana (IDRT)", min_value=0)
        p_desc = st.text_input("Deskripsi")
        
        if st.button("Submit Proposal"):
            amt_wei = int(p_amount * 10**18)
            func = None
            if ptype_int == 0: func = contract.functions.proposeBuyMachine(p_target, amt_wei, p_desc)
            elif ptype_int == 1: func = contract.functions.proposeBuyStock(p_target, amt_wei, p_desc)
            elif ptype_int == 2: func = contract.functions.proposeUpdateSalary(p_target, amt_wei, p_desc)
            elif ptype_int == 3: func = contract.functions.proposeAddVendor(p_target, p_desc)
            
            if func:
                tx = send_transaction(func, admin_addr, pk_admin)
                if "ERROR" in tx: st.error(tx)
                else: st.success(f"Proposal dibuat! Hash: {tx}")

    with t4:
        st.subheader("Eksekusi Proposal (Jika Vote > 50%)")
        ex_id = st.number_input("ID Proposal", min_value=1)
        if st.button("Eksekusi"):
            tx = send_transaction(contract.functions.executeProposal(ex_id), admin_addr, pk_admin)
            if "ERROR" in tx: st.error(tx)
            else: st.success(f"Proposal Dieksekusi! Hash: {tx}")

# ==========================================
# 7. HALAMAN SIMULASI (PUBLIK)
# ==========================================
def page_simulation():
    st.title("☕ Simulasi Beli Kopi")
    
    pk_buyer = st.text_input("Private Key Pembeli (Simulasi Scan QR)", type="password")
    mid = st.number_input("ID Mesin", min_value=1, value=1)
    
    price = contract.functions.coffeePrice().call()
    st.info(f"Harga: **Rp {fmt_rupiah(price)}**")

    if st.button("Bayar & Tuang Kopi"):
        if not pk_buyer:
            st.error("Butuh Private Key")
            return
        buyer = w3.eth.account.from_key(pk_buyer)
        
        with st.spinner("Processing..."):
            if check_and_approve(payment_token, buyer.address, CONTRACT_ADDRESS, price, pk_buyer):
                tx = send_transaction(contract.functions.buyCoffee(mid), buyer.address, pk_buyer)
                if "ERROR" in tx: st.error(tx)
                else: 
                    st.balloons()
                    st.success(f"Kopi Keluar! Hash: {tx}")

# ==========================================
# MAIN NAVIGATION
# ==========================================
menu = st.sidebar.selectbox("Navigasi", ["🏠 Dashboard Explorer", "💰 Investor Panel", "👮 Admin Panel", "☕ Simulasi Beli"])

if menu == "🏠 Dashboard Explorer":
    page_dashboard()
elif menu == "💰 Investor Panel":
    page_investor()
elif menu == "👮 Admin Panel":
    page_admin()
elif menu == "☕ Simulasi Beli":
    page_simulation()