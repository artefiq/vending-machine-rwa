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
RPC_URL = "http://127.0.0.1:7545" 

# 2. Alamat Smart Contract (Didapat setelah deploy contract)
CONTRACT_ADDRESS = "0xfF5F6AC679A2EC8729f8cAc535118659aB8eE6Ba" 

# 3. ABI (Application Binary Interface)
# Kamus agar python paham solidity, dicopy setelah compile contract
CONTRACT_ABI = '''
[
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "_paymentToken",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "_assetToken",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "_price",
				"type": "uint256"
			},
			{
				"internalType": "uint256",
				"name": "_cogs",
				"type": "uint256"
			}
		],
		"stateMutability": "nonpayable",
		"type": "constructor"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": true,
				"internalType": "address",
				"name": "buyer",
				"type": "address"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "timestamp",
				"type": "uint256"
			}
		],
		"name": "CoffeeOrdered",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": true,
				"internalType": "address",
				"name": "investor",
				"type": "address"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "amount",
				"type": "uint256"
			}
		],
		"name": "DividendClaimed",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "id",
				"type": "uint256"
			},
			{
				"indexed": false,
				"internalType": "address",
				"name": "vendor",
				"type": "address"
			},
			{
				"indexed": false,
				"internalType": "string",
				"name": "description",
				"type": "string"
			}
		],
		"name": "ProposalCreated",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "address",
				"name": "vendor",
				"type": "address"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "amount",
				"type": "uint256"
			}
		],
		"name": "RestockPaid",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "address",
				"name": "vendor",
				"type": "address"
			}
		],
		"name": "VendorWhitelisted",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "id",
				"type": "uint256"
			},
			{
				"indexed": false,
				"internalType": "address",
				"name": "voter",
				"type": "address"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "weight",
				"type": "uint256"
			}
		],
		"name": "Voted",
		"type": "event"
	},
	{
		"inputs": [],
		"name": "MAGNITUDE",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "assetToken",
		"outputs": [
			{
				"internalType": "contract IERC20",
				"name": "",
				"type": "address"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "buyCoffee",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "claimDividends",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "coffeePrice",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "cogsPerCup",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "_id",
				"type": "uint256"
			}
		],
		"name": "executeProposal",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "_id",
				"type": "uint256"
			}
		],
		"name": "getProposal",
		"outputs": [
			{
				"internalType": "address",
				"name": "proposedVendor",
				"type": "address"
			},
			{
				"internalType": "string",
				"name": "description",
				"type": "string"
			},
			{
				"internalType": "uint256",
				"name": "voteCount",
				"type": "uint256"
			},
			{
				"internalType": "bool",
				"name": "executed",
				"type": "bool"
			},
			{
				"internalType": "uint256",
				"name": "endTime",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "getProposalsCount",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"name": "isWhitelistedVendor",
		"outputs": [
			{
				"internalType": "bool",
				"name": "",
				"type": "bool"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"name": "magnifiedDividendCorrections",
		"outputs": [
			{
				"internalType": "int256",
				"name": "",
				"type": "int256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "magnifiedDividendPerShare",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "owner",
		"outputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "paymentToken",
		"outputs": [
			{
				"internalType": "contract IERC20",
				"name": "",
				"type": "address"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "_vendor",
				"type": "address"
			},
			{
				"internalType": "string",
				"name": "_desc",
				"type": "string"
			}
		],
		"name": "proposeNewVendor",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "_vendor",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "_amount",
				"type": "uint256"
			}
		],
		"name": "restockInventory",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "totalRevenue",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "int256",
				"name": "_amount",
				"type": "int256"
			}
		],
		"name": "updateCorrection",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "_id",
				"type": "uint256"
			}
		],
		"name": "voteProposal",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"name": "withdrawnDividends",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	}
]
'''
# ================= SETUP SISTEM =================
try:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if w3.is_connected():
        print(f"[SYSTEM] Terhubung ke Blockchain via {RPC_URL}")
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
    event_filter = contract.events.CoffeeOrdered.create_filter(from_block='latest')

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