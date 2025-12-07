import streamlit as st
from web3 import Web3
import pandas as pd
import json
import time

# ==========================================
# 1. KONFIGURASI
# ==========================================
GANACHE_URL = "http://127.0.0.1:7545" 
# GANTI DENGAN ALAMAT CONTRACT TERBARU KAMU DI SINI 👇
CONTRACT_ADDRESS = "0x30d120792d71fe3b9A01D21B3E77AbFfC20719EF" 

w3 = Web3(Web3.HTTPProvider(GANACHE_URL))

# Load ABI
try:
    with open('abi.json', 'r') as f:
        contract_abi = json.load(f)
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
except Exception as e:
    st.error(f"Error loading ABI or connecting: {e}")
    st.stop()

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def fmt_rupiah(wei_value):
    return f"{wei_value / 10**18:,.0f}"

def short_addr(address):
    if address:
        return f"{address[:6]}...{address[-4:]}"
    return "Unknown"

# ==========================================
# 3. FUNGSI BACA DATA BLOCKCHAIN
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

    # Helper biar gak nulis ulang terus
    # Kita ambil LogIndex biar urutannya presisi
    
    # 1. Event Beli Kopi
    for e in contract.events.CoffeeOrdered.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "☕ JUALAN KOPI",
            "Detail": f"Mesin #{e['args']['machineId']} | +Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": short_addr(e['args']['buyer'])
        })

    # 2. Event Pengeluaran
    for e in contract.events.ExpensePaid.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": f"💸 KELUAR: {e['args']['category']}",
            "Detail": f"Note: {e['args']['note']} | -Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": f"To: {short_addr(e['args']['to'])}"
        })

    # 3. Event Beli Saham (IPO)
    for e in contract.events.SharesPurchased.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "📈 BELI SAHAM (IPO)",
            "Detail": f"Beli: {e['args']['amount']/10**18:,.0f} Lembar | Bayar: Rp {fmt_rupiah(e['args']['cost'])}",
            "Pelaku": short_addr(e['args']['investor'])
        })

    # 4. Event Transfer Saham
    for e in contract.events.ShareTransferred.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "🔄 TRANSFER SAHAM",
            "Detail": f"Jml: {e['args']['amount']/10**18:,.0f} Lembar | Ke: {short_addr(e['args']['to'])}",
            "Pelaku": short_addr(e['args']['from'])
        })

    # 5. Event Claim Dividen
    for e in contract.events.DividendClaimed.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "💰 TARIK DIVIDEN",
            "Detail": f"Cair: Rp {fmt_rupiah(e['args']['amount'])}",
            "Pelaku": short_addr(e['args']['investor'])
        })
        
    # 6. Event Proposal Baru
    for e in contract.events.ProposalCreated.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "🗳️ PROPOSAL BARU",
            "Detail": f"ID: {e['args']['id']} | Tipe: {e['args']['pType']} | {e['args']['desc']}",
            "Pelaku": "DAO"
        })

    # 7. Event Voting Masuk
    for e in contract.events.Voted.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "✋ VOTING MASUK",
            "Detail": f"Vote Proposal #{e['args']['proposalId']} | Power: {e['args']['weight']/10**18:,.0f}",
            "Pelaku": short_addr(e['args']['voter'])
        })

    # 8. Event Proposal Dieksekusi
    for e in contract.events.ProposalExecuted.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "✅ PROPOSAL DEAL",
            "Detail": f"Proposal ID #{e['args']['id']} Berhasil Dieksekusi",
            "Pelaku": "System Auto"
        })

    # 9. Event Profit Distributed
    for e in contract.events.ProfitDistributed.create_filter(from_block=0).get_all_entries():
        events_list.append({
            "Block": e['blockNumber'],
            "LogIndex": e['logIndex'],
            "Aktivitas": "📊 BAGI HASIL",
            "Detail": f"Dividen: Rp {fmt_rupiah(e['args']['dividendAmount'])} | Growth: Rp {fmt_rupiah(e['args']['growthAmount'])}",
            "Pelaku": "System"
        })

    # PENTING: Urutkan berdasarkan Block (Desc) DAN LogIndex (Desc)
    # Ini kuncinya biar urutannya bener (Execute di atas Vote)
    df = pd.DataFrame(events_list)
    if not df.empty:
        df = df.sort_values(by=['Block', 'LogIndex'], ascending=[False, False])
    return df

# ==========================================
# 4. TAMPILAN UI STREAMLIT
# ==========================================
st.set_page_config(page_title="Vending DAO Explorer", layout="wide", page_icon="🤖")

st.title("🤖 Vending Machine DAO Dashboard")
st.markdown("Transparansi Keuangan & Operasional Blockchain secara Real-Time.")

# Cek Status Koneksi
if w3.is_connected():
    st.toast("Terhubung ke Blockchain", icon="🟢")
else:
    st.error("Gagal terhubung ke Ganache. Cek URL RPC.")

# Bagian Metrics Keuangan
col1, col2, col3, col4 = st.columns(4)
fin = get_financial_data()

col1.metric("Total Omzet", f"Rp {fin['Total Omzet']}")
col2.metric("Growth Fund", f"Rp {fin['Growth Fund']}")
col3.metric("Kas Operasional", f"Rp {fin['Kas Operasional']}")
col4.metric("Total Dividen", f"Rp {fin['Total Dividen']}")

st.divider()

# Tombol Refresh Manual
if st.button("🔄 Refresh Data"):
    st.rerun()

# Tabel Riwayat
st.subheader("📜 Riwayat Blok (Blockchain Ledger)")
df_events = get_all_events()

if not df_events.empty:
    st.dataframe(
        df_events, 
        use_container_width=True,
        column_config={
            "Block": st.column_config.NumberColumn("Block", format="%d"),
            "LogIndex": st.column_config.NumberColumn("Idx", format="%d"), # Opsional: Mau ditampilin atau di-hide
        },
        hide_index=True
    )
else:
    st.info("Belum ada aktivitas di smart contract ini.")

# Auto refresh simple (5 detik)
time.sleep(5)
st.rerun()