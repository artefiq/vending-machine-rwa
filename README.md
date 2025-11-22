# ☕ Decentralized IoT Vending Machine (RWA Tokenization)

> **Real World Asset Tokenization System with IoT Integration and Decentralized Governance.**

**Course Assignment**
This project demonstrates how Blockchain technology can solve financial data manipulation in the Vending Machine industry.

---

## 📋 Project Overview

In traditional vending machine businesses, investors rely on manual reports from operators, which can be manipulated (e.g., Luckin Coffee scandal). This project solves that by making the Hardware (Machine) listen directly to the Blockchain.

### Key Features
1.  **Trust Code, Not Humans:** The machine has no manual buttons. It only dispenses coffee if the Smart Contract emits a valid "Payment Received" event.
2.  **Real-Time Dividends:** Every coffee sale revenue is automatically calculated and split to token holders (investors) instantly.
3.  **Community Governance:** The machine owner cannot withdraw funds to a personal wallet. Operational costs can only be paid to Whitelisted Vendors approved by investor voting.

## 🛠️ Tech Stack

* **Smart Contract:** Solidity (Written natively without external imports for logic transparency).
* **IoT Controller:** Python 3.x + Web3.py (Simulates the Vending Machine Hardware).
* **Blockchain:** Ethereum / Polygon (Local Ganache or Testnet).

## 🚀 How to Run

### Prerequisites
1.  Python 3.10+ installed.
2.  Install Web3 library:
    ```bash
    pip install -r requirements.txt
    ```
3.  Remix IDE (Online Solidity Editor).
4.  Ganache (Local Blockchain) or Metamask (Testnet).

### Step 1: Deploy Smart Contract
1.  Open Remix IDE.
2.  Create a file named `VendingMachineNative.sol` and paste the Solidity code.
3.  Compile and Deploy the contract.
4.  **Constructor Arguments:** Use dummy addresses for Payment Token (`IDRT`) and Asset Token (`$MESIN`), and set a price (e.g., `15000`).
    > **Important:** Copy the Contract Address and ABI after deployment.

### Step 2: Configure IoT Script
1.  Open `machine_controller.py`.
2.  Update the `CONTRACT_ADDRESS` variable with your deployed address.
3.  Update the `RPC_URL`.

### Step 3: Run the System
Run the Python script in your terminal:

```
python machine_controller.py
```

The terminal will show:
```
[LISTENER] Waiting for purchase...
```

### Test the Interaction:
1. Go to Remix and execute the buyCoffee function (make sure to approve tokens first if using ERC20).
2. Watch the Python terminal. You should see the machine automatically simulating the grinding and brewing process upon receiving the blockchain event.

## 🧪 Testing Scenarios

| Scenario | Action in Remix | Expected Result |
| :--- | :--- | :--- |
| **1. Normal Purchase** | Call `buyCoffee` | Python script detects event & dispenses coffee. |
| **2. Fraud Attempt** | Call `payOperationalCost` to a random wallet | Transaction Reverts (Fails). |
| **3. Claim Profit** | Call `claimDividends` | Investor receives their share of the revenue. |