import time
import json
from web3 import Web3

# ================= PENJELASAN =================
# Kode simulasi IoT Vending Machine (Dengan ID Mesin)
# Script ini hanya akan merespons jika event dari blockchain
# memiliki machineId yang cocok dengan konfigurasi mesin ini.

# ================= KONFIGURASI =================
# 1. Identitas Mesin (PENTING: Sesuaikan dengan ID saat addMachine di Contract)
MY_MACHINE_ID = 1 

# 2. Koneksi Blockchain
RPC_URL = "http://127.0.0.1:7545" # Sesuaikan dengan Ganache/Testnet

# 3. Alamat Smart Contract Fleet (Update setiap deploy ulang!)
CONTRACT_ADDRESS = "0xe46D6d237Ec4021024b18BebB11dF4F2cB9819E9" 

# 4. ABI (Update dari Remix setelah compile VendingMachineFleet.sol)
# Pastikan ABI ini milik VendingMachineFleet, bukan contract lama.
CONTRACT_ABI = '''
	ISI ABI DISINI
'''

# ================= SETUP SISTEM =================
try:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if w3.is_connected():
        print(f"[SYSTEM] Terhubung ke Blockchain via {RPC_URL}")
        print(f"[SYSTEM] Mengontrol Mesin ID: {MY_MACHINE_ID}")
    else:
        print("[ERROR] Gagal terhubung ke Blockchain")
        exit()
except Exception as e:
    print(f"[ERROR] Koneksi: {e}")
    exit()

# Ubah address menjadi format checksum
CONTRACT_ADDRESS = w3.to_checksum_address(CONTRACT_ADDRESS)

# Setup Kontrak
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=json.loads(CONTRACT_ABI))

# ================= FUNGSI HARDWARE =================
def dispense_coffee(buyer_address, amount_paid):
    """
    Fungsi ini mensimulasikan motor/servo vending machine.
    """
    amount_rupiah = amount_paid / (10**18) # Konversi dari Wei ke Rupiah (asumsi 18 desimal)
    
    print("\n" + "="*40)
    print(f"[MESIN #{MY_MACHINE_ID}] PESANAN DITERIMA!")
    print(f" -> Pembeli : {buyer_address}")
    print(f" -> Bayar   : {amount_rupiah} IDRT")
    print(f" -> Status  : VERIFIED ON-CHAIN")
    
    print("[HARDWARE] 1. Menurunkan Gelas...")
    time.sleep(1)
    print("[HARDWARE] 2. Menggiling Biji Kopi...")
    time.sleep(1)
    print("[HARDWARE] 3. Menuang Air Panas...")
    time.sleep(1)
    print(f"[HARDWARE] 4. SELESAI! Silakan ambil kopi di Mesin #{MY_MACHINE_ID}.")
    print("="*40 + "\n")

# ================= LOOP UTAMA (LISTENER) =================
def start_listening():
    print(f"[LISTENER] Menunggu Event 'CoffeeOrdered'...")
    
    # Membuat filter event dari blok terbaru
    event_filter = contract.events.CoffeeOrdered.create_filter(fromBlock='latest')

    while True:
        try:
            # Cek apakah ada event baru
            for event in event_filter.get_new_entries():
                # Ambil data dari event
                machine_id = event['args']['machineId']
                buyer = event['args']['buyer']
                amount = event['args']['amount']
                
                # Filter Berdasarkan ID Mesin
                if machine_id == MY_MACHINE_ID:
                    dispense_coffee(buyer, amount)
                else:
                    # Log sederhana supaya tahu ada aktivitas di mesin lain
                    print(f"[INFO] Pesanan masuk untuk Mesin #{machine_id} (Diabaikan oleh Mesin #{MY_MACHINE_ID})")
                
            time.sleep(1) # Cek setiap 1 detik
            
        except KeyboardInterrupt:
            print("[STOP] Mematikan mesin...")
            break
        except Exception as e:
            print(f"[ERROR] Loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_listening()