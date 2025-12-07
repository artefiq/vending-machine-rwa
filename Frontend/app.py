import streamlit as st
from web3 import Web3
import pandas as pd
import json
import time
import os
from dotenv import load_dotenv

# ==========================================
# 1. KONFIGURASI & SETUP
# ==========================================
st.set_page_config(page_title="Vending DAO Super App", layout="wide", page_icon="☕")

# Load environment variables
load_dotenv()

GANACHE_URL = os.getenv("GANACHE_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
PAYMENT_TOKEN_ADDR = os.getenv("PAYMENT_TOKEN_ADDRESS")
ASSET_TOKEN_ADDR = os.getenv("ASSET_TOKEN_ADDRESS")

if not CONTRACT_ADDRESS or not PAYMENT_TOKEN_ADDR:
    st.error("⚠️ Konfigurasi .env belum lengkap! Pastikan address sudah diisi.")
    st.stop()

if "w3" not in st.session_state:
    st.session_state.w3 = Web3(Web3.HTTPProvider(GANACHE_URL))

w3 = st.session_state.w3

# Load ABI Helper
def load_abi():
    try:
        with open('abi.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Gagal memuat abi.json: {e}")
        st.stop()

contract_abi = load_abi()
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)

# Load Token Contracts (ERC20 Standard)
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [], "name": "mintaUangGratis", "outputs": [], "type": "function"} 
]

try:
    payment_token = w3.eth.contract(address=PAYMENT_TOKEN_ADDR, abi=ERC20_ABI)
    asset_token = w3.eth.contract(address=ASSET_TOKEN_ADDR, abi=ERC20_ABI)
except Exception as e:
    st.toast(f"Warning: Gagal load token. Cek alamat di .env", icon="⚠️")

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
        
        # Build transaction
        tx_data = func_call.build_transaction({
            'chainId': 1337, 
            'gas': 3000000,
            'gasPrice': w3.to_wei('20', 'gwei'),
            'nonce': nonce,
            'from': account_addr,
            'value': value
        })
        
        # Sign Transaction
        signed_tx = w3.eth.account.sign_transaction(tx_data, private_key)
        
        # --- PERBAIKAN DI SINI ---
        # Ganti .rawTransaction menjadi .raw_transaction (snake_case)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            return w3.to_hex(tx_hash)
        else:
            return "ERROR: Transaksi Revert (Gagal)"
            
    except Exception as e:
        return f"ERROR: {str(e)}"

def check_and_approve(token_contract, owner_addr, spender_addr, amount_wei, private_key):
    """
    KEAMANAN: Cek allowance dan approve HANYA SEJUMLAH yang dibutuhkan (Exact Amount).
    """
    try:
        allowance = token_contract.functions.allowance(owner_addr, spender_addr).call()
        
        if allowance < amount_wei:
            st.info(f"🔒 Keamanan: Meminta izin akses token sebesar {amount_wei/10**18:,.0f}...")
            with st.spinner("⏳ Sedang memproses Approval..."):
                # APPROVE EXACT AMOUNT ONLY
                tx_hash = send_transaction(
                    token_contract.functions.approve(spender_addr, amount_wei), 
                    owner_addr, private_key
                )
                
                if "ERROR" in tx_hash:
                    st.error(tx_hash)
                    return False
                
                st.toast("✅ Izin Diberikan (Approve Success)!", icon="🔐")
                time.sleep(2) # Jeda agar blockchain sync
                
        return True 
    except Exception as e:
        st.error(f"Gagal Cek Allowance: {e}")
        return False

# ==========================================
# 3. FUNGSI BACA DATA
# ==========================================
def get_financial_data():
    try:
        revenue = contract.functions.totalRevenue().call()
        growth_fund = contract.functions.growthFund().call()
        reserve = contract.functions.getOperationalReserve().call()
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
            "Aktivitas": f"💸 KELUAR: {e['args']['category']}", 
            "Detail": f"Note: {e['args']['note']} | -Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": f"To: {short_addr(e['args']['to'])}"
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
        desc = e['args'].get('desc', e['args'].get('description', '-'))
        pType = e['args'].get('pType', '-')
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "🗳️ PROPOSAL BARU",
            "Detail": f"ID: {e['args']['id']} | {pType} | {desc}",
            "Pelaku": "DAO"
        })
    # 7. Voting
    for e in contract.events.Voted.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "✋ VOTING MASUK",
            "Detail": f"Vote Proposal #{e['args']['proposalId']} | Power: {e['args']['weight']/10**18:,.0f}",
            "Pelaku": short_addr(e['args']['voter'])
        })
    # 8. Executed
    for e in contract.events.ProposalExecuted.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "✅ PROPOSAL DEAL",
            "Detail": f"Proposal ID #{e['args']['id']} Berhasil Dieksekusi",
            "Pelaku": "System Auto"
        })
    # 9. Profit
    for e in contract.events.ProfitDistributed.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'], "LogIndex": e['logIndex'],
            "Aktivitas": "📊 BAGI HASIL",
            "Detail": f"Div: Rp {fmt_rupiah(e['args']['dividendAmount'])} | Growth: Rp {fmt_rupiah(e['args']['growthAmount'])}",
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
    st.markdown("Monitor aktivitas blockchain secara Real-Time.")

    if w3.is_connected():
        st.caption(f"Status: 🟢 Terhubung ke Blockchain")
    else:
        st.error("Gagal terhubung ke Ganache.")

    col1, col2, col3, col4 = st.columns(4)
    fin = get_financial_data()
    col1.metric("Total Omzet", f"Rp {fin['Total Omzet']}")
    col2.metric("Growth Fund", f"Rp {fin['Growth Fund']}")
    col3.metric("Kas Operasional", f"Rp {fin['Kas Operasional']}")
    col4.metric("Total Dividen", f"Rp {fin['Total Dividen']}")

    st.divider()

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
        st.info("Belum ada aktivitas.")
    
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
        st.warning("Masukkan Private Key.")
        return

    try:
        account = w3.eth.account.from_key(pk_investor)
        my_addr = account.address
        st.sidebar.success(f"Login: {short_addr(my_addr)}")
    except:
        st.sidebar.error("Key Invalid")
        return

    try:
        my_shares = asset_token.functions.balanceOf(my_addr).call()
        my_div = contract.functions.getWithdrawableDividend(my_addr).call()
        my_idrt = payment_token.functions.balanceOf(my_addr).call()
        share_price = contract.functions.sharePrice().call()
    except Exception as e:
        st.error(f"Gagal ambil data user: {e}")
        return

    c1, c2, c3 = st.columns(3)
    c1.info(f"**Saham Saya:**\n\n{my_shares / 10**18:,.0f} Lembar")
    c2.success(f"**Dividen Siap Cair:**\n\nRp {fmt_rupiah(my_div)}")
    c3.warning(f"**Saldo Wallet:**\n\nRp {fmt_rupiah(my_idrt)}")

    if my_idrt < 10000 * 10**18:
        if st.button("💸 Minta 100rb IDRT (Faucet)"):
            try:
                tx = send_transaction(payment_token.functions.mintaUangGratis(), my_addr, pk_investor)
                if "ERROR" in tx: st.error("Faucet gagal.")
                else: 
                    st.success(f"Uang masuk! Hash: {tx}")
                    time.sleep(1)
                    st.rerun()
            except:
                st.error("Faucet tidak tersedia.")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Beli Saham (IPO)", "Klaim Dividen", "Voting DAO", "Transfer Saham"])

    # --- BELI SAHAM ---
    with tab1:
        st.subheader("Beli Saham Baru")
        
        # 1. AMBIL DATA STOK TERSEDIA
        try:
            available_shares_wei = contract.functions.getAvailableShares().call()
            available_shares = int(available_shares_wei / 10**18)
            st.info(f"📦 Stok Tersedia: **{available_shares:,.0f} Lembar**")
        except:
            st.warning("Gagal mengambil data stok.")
            available_shares_wei = 0
            available_shares = 0

        st.write(f"Harga IPO: **Rp {fmt_rupiah(share_price)} / lembar**")
        
        c_in, c_tot = st.columns(2)
        with c_in:
            # Set max_value input box agar user tidak bisa ketik lebih dari stok
            max_input = available_shares if available_shares > 0 else 1
            amount_buy = st.number_input("Jumlah Lembar", min_value=1, max_value=max_input, value=1)
        
        total_cost_wei = amount_buy * share_price 
        
        with c_tot:
            st.metric("Total Bayar", f"Rp {fmt_rupiah(total_cost_wei)}")
        
        if st.button("Beli Saham Sekarang"):
            amount_buy_wei = int(amount_buy * 10**18)

            # 2. VALIDASI GANDA (Stok & Uang)
            if amount_buy_wei > available_shares_wei:
                st.error(f"❌ Stok tidak cukup! Sisa: {available_shares} lembar.")
            elif my_idrt < total_cost_wei:
                st.error(f"❌ Saldo Wallet Kurang! Butuh Rp {fmt_rupiah(total_cost_wei)}")
            else:
                # 3. EKSEKUSI
                if check_and_approve(payment_token, my_addr, CONTRACT_ADDRESS, total_cost_wei, pk_investor):
                    tx = send_transaction(contract.functions.buyShares(amount_buy_wei), my_addr, pk_investor)
                    if "ERROR" in tx: st.error(tx)
                    else: 
                        st.success(f"Sukses! Hash: {tx}")
                        time.sleep(2)
                        st.rerun()

    # --- KLAIM DIVIDEN ---
    with tab2:
        st.subheader("Pencairan Dividen")
        if my_div > 0:
            if st.button("💸 Cairkan Semua Dividen"):
                tx = send_transaction(contract.functions.claimDividends(), my_addr, pk_investor)
                if "ERROR" in tx: st.error(tx)
                else: 
                    st.success(f"Dividen Cair! Hash: {tx}")
                    time.sleep(2)
                    st.rerun()
        else:
            st.info("Belum ada dividen.")

    # --- VOTING ---
    with tab3:
        st.subheader("Voting Proposal")
        p_count = contract.functions.proposalCount().call()
        active_props = []
        for i in range(1, p_count + 1):
            p = contract.functions.proposals(i).call()
            # p[6] = executed
            if not p[6]: 
                # p[4] = description
                active_props.append(f"ID {p[0]}: {p[4]}")

        if active_props:
            sel = st.selectbox("Pilih Proposal Aktif", active_props)
            p_id = int(sel.split(":")[0].replace("ID ", ""))
            st.caption("Klik vote, jika suara > 50% proposal otomatis tereksekusi.")
            if st.button("Vote Setuju"):
                tx = send_transaction(contract.functions.vote(p_id), my_addr, pk_investor)
                if "ERROR" in tx: st.error(tx)
                else: st.success("Vote Masuk!")
        else:
            st.info("Tidak ada proposal aktif.")

    # --- TRANSFER SAHAM ---
    with tab4:
        st.subheader("Transfer Saham (P2P)")
        to_addr = st.text_input("Alamat Penerima (0x...)")
        amount_trf = st.number_input("Jumlah Saham", min_value=1)
        
        if st.button("Kirim Saham"):
            amount_trf_wei = int(amount_trf * 10**18)
            
            # 1. Cek & Approve (Exact Amount) - Approve ke Contract DAO
            if check_and_approve(asset_token, my_addr, CONTRACT_ADDRESS, amount_trf_wei, pk_investor):
                # 2. Transaksi
                tx = send_transaction(contract.functions.transferSaham(to_addr, amount_trf_wei), my_addr, pk_investor)
                if "ERROR" in tx: st.error(tx)
                else: st.success(f"Saham Terkirim! Hash: {tx}")

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
        if admin_addr != contract.functions.owner().call():
            st.error("Wallet ini bukan Owner contract!")
            return
        st.sidebar.success(f"Admin: {short_addr(admin_addr)}")
    except:
        st.sidebar.error("Key Invalid")
        return

    t1, t2, t3, t4 = st.tabs(["Mesin & Harga", "Gaji Rutin", "Buat Proposal", "List Mesin"])

    with t1:
        st.subheader("Manajemen Aset")
        loc = st.text_input("Lokasi Mesin Baru")
        if st.button("Add Machine"):
            tx = send_transaction(contract.functions.addMachine(loc), admin_addr, pk_admin)
            if "ERROR" in tx: st.error(tx)
            else: st.success(f"Mesin ditambahkan! Hash: {tx}")
        
        st.divider()
        st.subheader("Update Ekonomi")
        
        # Kolom Berdampingan (Kiri: Harga Jual, Kanan: Modal HPP)
        col_p, col_c = st.columns(2)
        
        with col_p:
            np = st.number_input("Harga Jual (IDRT)", value=15000)
            if st.button("Set Harga Jual"):
                price_wei = int(np * 10**18)
                tx = send_transaction(contract.functions.setCoffeePrice(price_wei), admin_addr, pk_admin)
                if "ERROR" in tx: st.error(tx)
                else: st.success("Harga Jual Diupdate.")

        with col_c:
            nc = st.number_input("Modal HPP (COGS)", value=5000)
            if st.button("Set Modal HPP"):
                cogs_wei = int(nc * 10**18)
                # Pastikan fungsi setCogs sudah ada di Smart Contract!
                try:
                    tx = send_transaction(contract.functions.setCogs(cogs_wei), admin_addr, pk_admin)
                    if "ERROR" in tx: st.error(tx)
                    else: st.success("Modal HPP Diupdate.")
                except:
                    st.error("Fungsi setCogs tidak ditemukan di Smart Contract ini.")

    with t2:
        st.subheader("Bayar Gaji Harian")
        st.caption("Nominal gaji diambil otomatis dari database Proposal.")
        
        staff_addr = st.text_input("Address Staff")
        
        if st.button("Bayar Gaji Hari Ini"):
            tx = send_transaction(contract.functions.payDailySalary(staff_addr), admin_addr, pk_admin)
            if "ERROR" in tx: st.error(tx)
            else: st.success(f"Gaji Harian Terbayar! Hash: {tx}")

    with t3:
        st.subheader("Buat Proposal DAO")
        
        ptype = st.selectbox("Tipe Proposal", ["0: Beli Mesin", "1: Beli Stok", "2: Set Gaji Harian", "3: Add Vendor"])
        ptype_int = int(ptype.split(":")[0])
        
        p_target = st.text_input("Target Address (Vendor/Staff)")
        p_amount = st.number_input("Jumlah (IDRT/Gaji)", min_value=0)
        p_desc = st.text_input("Deskripsi / Nama")
        
        if st.button("Submit Proposal"):
            # Konversi ke Wei
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
        st.subheader("📍 Status Armada Vending Machine")
        
        # 1. Cek Total Mesin
        try:
            m_count = contract.functions.machineCount().call()
        except:
            st.error("Gagal mengambil data mesin.")
            m_count = 0

        if m_count > 0:
            st.caption(f"Total Mesin Terdaftar: **{m_count} Unit**")
            
            # 2. Loop Data Mesin
            machine_list = []
            for i in range(1, m_count + 1):
                # Struct: (id, location, isActive, totalSales)
                m = contract.functions.machines(i).call()
                
                machine_list.append({
                    "ID": m[0],
                    "Lokasi": m[1],
                    # Kolom Status dihapus sesuai request
                    "Total Omzet": f"Rp {fmt_rupiah(m[3])}"
                })
            
            # 3. Tampilkan Tabel
            st.dataframe(
                machine_list,
                use_container_width=True,
                column_config={
                    "ID": st.column_config.NumberColumn("ID Mesin", format="%d"),
                    "Lokasi": st.column_config.TextColumn("Lokasi Penempatan"),
                    "Total Omzet": st.column_config.TextColumn("Total Penjualan"),
                },
                hide_index=True
            )
            
            # Tombol Refresh khusus tab ini
            if st.button("🔄 Refresh List Armada"):
                st.rerun()
                
        else:
            st.info("Belum ada mesin yang didaftarkan. Silakan tambah di Tab 1.")

# ==========================================
# 7. HALAMAN SIMULASI BELI KOPI
# ==========================================
def page_simulation():
    st.title("☕ Simulasi Beli Kopi")
    
    pk_buyer = st.text_input("Private Key Pembeli (Simulasi Scan QR)", type="password")
    mid = st.number_input("ID Mesin", min_value=1, value=1)
    
    try:
        price_wei = contract.functions.coffeePrice().call()
        st.info(f"Harga: **Rp {fmt_rupiah(price_wei)}**")
    except:
        st.warning("Gagal ambil harga.")
        price_wei = 0

    if st.button("Bayar & Tuang Kopi"):
        if not pk_buyer:
            st.error("Butuh Private Key")
            return
        
        try:
            buyer = w3.eth.account.from_key(pk_buyer)
            buyer_addr = buyer.address
            
            with st.spinner("Processing Payment..."):
                # Cek & Approve (Exact Amount)
                if check_and_approve(payment_token, buyer_addr, CONTRACT_ADDRESS, price_wei, pk_buyer):
                    tx = send_transaction(contract.functions.buyCoffee(mid), buyer_addr, pk_buyer)
                    if "ERROR" in tx: st.error(tx)
                    else: 
                        st.balloons()
                        st.success(f"Kopi Keluar! Hash: {tx}")
        except Exception as e:
            st.error(f"Error: {e}")

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