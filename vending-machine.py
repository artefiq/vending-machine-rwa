import time
import json
from web3 import Web3

# ================= PENJELASAN =================
# kode ini dibuat untuk menyimulasikan vending machine dalam dunia nyata

# ================= KONFIGURASI =================
# 1. Koneksi Blockchain (Gunakan WebSocket untuk real-time event listening yang lebih baik)
# Contoh Lokal: "ws://127.0.0.1:8545"
# Contoh Polygon Mumbai: "wss://polygon-mumbai.g.alchemy.com/v2/API_KEY"
# Contoh Ethereum Sepolia: "..."
RPC_URL = "ws://127.0.0.1:8545" 

# 2. Alamat Smart Contract (Didapat setelah deploy contract)
CONTRACT_ADDRESS = "0x..." 

# 3. ABI (Application Binary Interface)
# Kamus agar python paham solidity, dicopy setelah compile contract
CONTRACT_ABI = '[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"buyer","type":"address"},{"indexed":false,"internalType":"uint256","name":"timestamp","type":"uint256"}],"name":"CoffeeOrdered","type":"event"}]'

# ================= SETUP SISTEM =================
try:
    w3 = Web3(Web3.WebsocketProvider(RPC_URL))
    if w3.is_connected():
        print(f"[SYSTEM] Terhubung ke Blockchain via {RPC_URL}")
    else:
        print("[ERROR] Gagal terhubung ke Blockchain")
        exit()
except Exception as e:
    print(f"[ERROR] Koneksi: {e}")
    exit()

# Setup Kontrak
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=json.loads(CONTRACT_ABI))

# ================= FUNGSI HARDWARE =================
def dispense_coffee(buyer_address):
    """
    Fungsi ini mensimulasikan motor/servo vending machine.
    Di dunia nyata, ini akan mengirim sinyal GPIO ke Raspberry Pi.
    """
    print("\n" + "="*40)
    print(f"[MESIN] PESANAN DITERIMA DARI: {buyer_address}")
    print("[MESIN] Memverifikasi pembayaran on-chain... OK.")
    
    print("[HARDWARE] 1. Menurunkan Gelas...")
    time.sleep(1)
    print("[HARDWARE] 2. Menggiling Biji Kopi...")
    time.sleep(1)
    print("[HARDWARE] 3. Menuang Air Panas...")
    time.sleep(1)
    print("[HARDWARE] 4. SELESAI! Silakan ambil.")
    print("="*40 + "\n")

# ================= LOOP UTAMA (LISTENER) =================
def start_listening():
    print(f"[LISTENER] Menunggu Event 'CoffeeOrdered' di alamat {CONTRACT_ADDRESS}...")
    
    # Membuat filter event
    event_filter = contract.events.CoffeeOrdered.create_filter(fromBlock='latest')

    while True:
        try:
            # Cek apakah ada event baru
            for event in event_filter.get_new_entries():
                # Ambil data dari event
                buyer = event['args']['buyer']
                timestamp = event['args']['timestamp']
                
                # LOGIKA INTI: Blockchain memicu Fisik
                dispense_coffee(buyer)
                
            time.sleep(1) # Cek setiap 1 detik
            
        except KeyboardInterrupt:
            print("[STOP] Mematikan mesin...")
            break
        except Exception as e:
            print(f"[ERROR] Loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_listening()