import json
import os
from enum import Enum
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from web3 import Web3
from pydantic import BaseModel
from dotenv import load_dotenv

# ================= SETUP =================
load_dotenv()

app = FastAPI(title="Vending Machine DAO API", version="1.0")

# CORS (Agar Frontend bisa akses API ini)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Koneksi Blockchain
RPC_URL = os.getenv("RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY")
ADMIN_ADDRESS = os.getenv("ADMIN_ADDRESS")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load ABI
try:
    with open("abi.json", "r") as f:
        abi = json.load(f)
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
    print(f"[SYSTEM] Connected to Contract at {CONTRACT_ADDRESS}")
except Exception as e:
    print(f"[ERROR] {e}")

# ================= MODELS (Pydantic) =================

class ProposalType(int, Enum):
    BUY_MACHINE = 0
    BUY_STOCK = 1
    UPDATE_SALARY = 2
    ADD_VENDOR = 3

class ProposalInput(BaseModel):
    p_type: ProposalType
    target: str # Address target (Vendor/Staff)
    amount: float # Jumlah uang (IDRT) atau Gaji
    description: str

class MachineInput(BaseModel):
    location: str

class VoteInput(BaseModel):
    proposal_id: int

class BuyCoffeeInput(BaseModel):
    machine_id: int

class BuySharesInput(BaseModel):
    amount_shares: int # Jumlah lembar saham

class TransferShareInput(BaseModel):
    to_address: str
    amount_shares: int

# ================= HELPER =================

def send_admin_tx(func):
    """Fungsi helper untuk Admin menandatangani transaksi di server"""
    nonce = w3.eth.get_transaction_count(ADMIN_ADDRESS)
    tx = func.build_transaction({
        'chainId': 1337, # Ganache Chain ID
        'gas': 3000000,
        'gasPrice': w3.to_wei('20', 'gwei'),
        'nonce': nonce,
        'from': ADMIN_ADDRESS
    })
    signed_tx = w3.eth.account.sign_transaction(tx, ADMIN_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return w3.to_hex(tx_hash)

# ================= READ ENDPOINTS (UMUM) =================

@app.get("/")
def home():
    return {"status": "DAO Backend Online", "contract": CONTRACT_ADDRESS}

@app.get("/public/stats")
def get_global_stats():
    """Data Dashboard Umum"""
    try:
        total_rev = contract.functions.totalRevenue().call()
        growth_fund = contract.functions.growthFund().call()
        coffee_price = contract.functions.coffeePrice().call()
        machine_count = contract.functions.machineCount().call()
        share_price = contract.functions.sharePrice().call()
        avail_shares = contract.functions.getAvailableShares().call()

        return {
            "total_revenue_idrt": total_rev / 10**18,
            "growth_fund_idrt": growth_fund / 10**18,
            "coffee_price_idrt": coffee_price / 10**18,
            "share_price_idrt": share_price / 10**18,
            "machine_count": machine_count,
            "available_shares": avail_shares / 10**18
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/public/machines")
def get_all_machines():
    """Peta Sebaran Mesin"""
    count = contract.functions.machineCount().call()
    machines = []
    for i in range(1, count + 1): # Loop dari ID 1
        m = contract.functions.machines(i).call()
        machines.append({
            "id": m[0],
            "location": m[1],
            "is_active": m[2],
            "total_sales": m[3] / 10**18
        })
    return machines

@app.get("/public/proposals")
def get_proposals():
    """Melihat Proposal DAO"""
    count = contract.functions.proposalCount().call()
    proposals = []
    for i in range(1, count + 1):
        # Struct: (id, pType, target, amount, desc, voteCount, executed, endTime)
        p = contract.functions.proposals(i).call()
        proposals.append({
            "id": p[0],
            "type_code": p[1],
            "type_name": ProposalType(p[1]).name,
            "target": p[2],
            "amount": p[3] / 10**18,
            "description": p[4],
            "vote_count": p[5] / 10**18,
            "executed": p[6],
            "end_time": p[7]
        })
    return proposals

# ================= READ ENDPOINTS (INVESTOR) =================

@app.get("/investor/{address}")
def get_investor_portfolio(address: str):
    """Data Dashboard Investor"""
    addr = w3.to_checksum_address(address)
    
    # 1. Saldo Saham
    # Backend perlu load AssetToken contract juga untuk cek balanceOf
    # Tapi kita bisa pakai assetToken() address dari main contract
    asset_token_addr = contract.functions.assetToken().call()
    # (Simplified: Di sini kita asumsi frontend/web3js yang cek saldo token)
    # Tapi kita bisa cek Dividen:
    
    pending_div = contract.functions.getWithdrawableDividend(addr).call()
    
    return {
        "address": addr,
        "token_address": asset_token_addr,
        "withdrawable_dividend_idrt": pending_div / 10**18
    }

# ================= WRITE ENDPOINTS (ADMIN ONLY) =================
# Endpoint ini menggunakan Private Key Server (.env)

@app.post("/admin/add-machine")
def admin_add_machine(data: MachineInput):
    try:
        tx = send_admin_tx(contract.functions.addMachine(data.location))
        return {"status": "success", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/create-proposal")
def admin_create_proposal(data: ProposalInput):
    """
    Mapping Type:
    0 = BUY_MACHINE
    1 = BUY_STOCK
    2 = UPDATE_SALARY
    3 = ADD_VENDOR
    """
    try:
        amount_wei = int(data.amount * 10**18)
        target = w3.to_checksum_address(data.target)
        
        func = None
        if data.p_type == ProposalType.BUY_MACHINE:
            func = contract.functions.proposeBuyMachine(target, amount_wei, data.description)
        elif data.p_type == ProposalType.BUY_STOCK:
            func = contract.functions.proposeBuyStock(target, amount_wei, data.description)
        elif data.p_type == ProposalType.UPDATE_SALARY:
            func = contract.functions.proposeUpdateSalary(target, amount_wei, data.description)
        elif data.p_type == ProposalType.ADD_VENDOR:
            func = contract.functions.proposeAddVendor(target, data.description)
            
        tx = send_admin_tx(func)
        return {"status": "proposal created", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/execute-proposal/{id}")
def admin_execute_proposal(id: int):
    try:
        tx = send_admin_tx(contract.functions.executeProposal(id))
        return {"status": "executed", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/set-price")
def admin_set_price(price: float):
    try:
        wei = int(price * 10**18)
        tx = send_admin_tx(contract.functions.setCoffeePrice(wei))
        return {"status": "updated", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/pay-salary")
def admin_pay_salary(staff_address: str):
    try:
        addr = w3.to_checksum_address(staff_address)
        tx = send_admin_tx(contract.functions.payMonthlySalary(addr))
        return {"status": "paid", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ================= WRITE ENDPOINTS (SIMULATION / DEMO) =================
# Di aplikasi nyata, fungsi ini dipanggil langsung dari Frontend (Metamask).
# Endpoint ini hanya untuk testing via Postman/Swagger menggunakan Admin Wallet.

@app.post("/simulate/buy-coffee")
def simulate_buy_coffee(data: BuyCoffeeInput):
    """[DEMO] Simulasi beli kopi pakai wallet admin"""
    try:
        # Perlu approve dulu di background jika belum
        tx = send_admin_tx(contract.functions.buyCoffee(data.machine_id))
        return {"status": "coffee ordered", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/simulate/vote")
def simulate_vote(data: VoteInput):
    """[DEMO] Simulasi vote pakai wallet admin"""
    try:
        tx = send_admin_tx(contract.functions.vote(data.proposal_id))
        return {"status": "voted", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/simulate/buy-shares")
def simulate_buy_shares(data: BuySharesInput):
    """[DEMO] Simulasi beli saham"""
    # Di real app: Frontend call approve() -> Frontend call buyShares()
    try:
        amount_wei = data.amount_shares * 10**18 
        tx = send_admin_tx(contract.functions.buyShares(amount_wei))
        return {"status": "shares purchased", "tx_hash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))