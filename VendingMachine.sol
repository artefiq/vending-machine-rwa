// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract VendingMachineFleet {
    
    // --- 1. VARIABEL UTAMA ---
    IERC20 public paymentToken; // Token Pembayaran (IDRT)
    IERC20 public assetToken; // Token Saham ($MESIN)
    address public owner; // Admin/Deployer
    uint256 public coffeePrice = 15000 * 10**18; // Harga Kopi
    uint256 public totalRevenue;
    // Variabel Modal Pokok
    uint256 public cogsPerCup = 5000 * 10**18;
    // --- 2. MANAJEMEN ARMADA ---
    struct Machine {
        uint256 id;
        string location;
        bool isActive;
        uint256 totalSales; 
    }
    mapping(uint256 => Machine) public machines; 
    uint256 public machineCount;

    // --- 3. KEUANGAN ---
    uint256 public accumulatedRevenue;  
    uint256 public growthFund;          
    
    uint256 public constant REINVEST_RATE = 20; 
    uint256 public constant DIVIDEND_RATE = 80; 

    // Sistem Dividen
    uint256 constant MAGNITUDE = 2**128;
    uint256 public magnifiedDividendPerShare;
    mapping(address => int256) public magnifiedDividendCorrections;
    mapping(address => uint256) public withdrawnDividends;

    // Harga saham (IPO)
    uint256 public sharePrice = 1000 * 10**18;

    // --- 4. GOVERNANCE ---
    mapping(address => bool) public isWhitelistedVendor;
    
    struct Proposal {
        address proposedVendor;
        string description;
        uint256 voteCount;
        bool executed;
        uint256 endTime;
        mapping(address => bool) hasVoted;
    }
    Proposal[] public proposals;

    // --- 5. KEAMANAN ---
    bool private locked;

    // --- EVENTS ---
    event CoffeeOrdered(uint256 indexed machineId, address buyer, uint256 amount);
    event MachineAdded(uint256 id, string location);
    event OpexPaid(address vendor, uint256 amount, string reason);
    event ProfitDistributed(uint256 dividendAmount, uint256 growthAmount);
    event GrowthFundUsed(address vendor, uint256 amount, string reason);
    event DividendClaimed(address investor, uint256 amount);
    event VendorWhitelisted(address vendor);
    event PriceUpdated(uint256 newPrice); // Event baru jika harga berubah

    // Constructor: Tambahkan _coffeePrice
    constructor(address _paymentToken, address _assetToken, uint256 _coffeePrice) {
        paymentToken = IERC20(_paymentToken);
        assetToken = IERC20(_assetToken);
        coffeePrice = _coffeePrice; // Set harga awal di sini
        owner = msg.sender;
        isWhitelistedVendor[msg.sender] = true; 
    }

    modifier onlyOwner() { require(msg.sender == owner, "Hanya Admin"); _; }
    modifier noReentrancy() { require(!locked, "Reentrancy!"); locked = true; _; locked = false; }

    // =========================================================
    // FUNGSI ADMIN: UBAH HARGA
    // =========================================================
    // Fitur baru: Admin bisa mengubah harga kopi global jika inflasi
    function setCoffeePrice(uint256 _newPrice) external onlyOwner {
        coffeePrice = _newPrice;
        emit PriceUpdated(_newPrice);
    }

    function setCogs(uint256 _newCogs) external onlyOwner {
        cogsPerCup = _newCogs;
    }

    // =========================================================
    // BAGIAN A: SKALABILITAS
    // =========================================================
    function addMachine(string memory _location) external onlyOwner {
        machineCount++;
        machines[machineCount] = Machine(machineCount, _location, true, 0);
        emit MachineAdded(machineCount, _location);
    }

    // =========================================================
    // BAGIAN B: TRANSAKSI PELANGGAN (PERBAIKAN UTAMA)
    // =========================================================
    
    function buyCoffee(uint256 _machineId) external noReentrancy {
        require(machines[_machineId].isActive, "Mesin Tidak Aktif");
        
        uint256 priceToPay = coffeePrice; // Misal 15.000
        require(paymentToken.balanceOf(msg.sender) >= priceToPay, "Saldo Kurang");

        // 1. Tarik FULL Harga (15.000) ke Contract
        require(paymentToken.transferFrom(msg.sender, address(this), priceToPay), "Gagal Bayar");

        // 2. Akumulasi Data Omzet
        machines[_machineId].totalSales += priceToPay;
        accumulatedRevenue += priceToPay;

        // --- LOGIKA POTONG MODAL (BARU) ---
        
        // Hitung Profit Kotor (Gross Profit)
        // Profit = Harga Jual (15rb) - Modal (5rb) = 10rb
        uint256 grossProfit = 0;
        if (priceToPay > cogsPerCup) {
            grossProfit = priceToPay - cogsPerCup;
        }

        // Uang 5.000 (Modal) DIBIARKAN mengendap di contract (accumulatedRevenue)
        // Uang ini nanti dipakai Owner lewat 'payOperationalCost' untuk beli stok.

        // --- ALOKASI PROFIT (10.000) ---
        
        // Dari 10rb Profit:
        // 20% (2rb) -> Growth Fund (Beli Mesin Baru)
        // 80% (8rb) -> Dividen Investor
        
        if (grossProfit > 0) {
            uint256 amountGrowth = (grossProfit * REINVEST_RATE) / 100; 
            uint256 amountDividend = grossProfit - amountGrowth;

            // Masukkan ke Tabungan Ekspansi
            growthFund += amountGrowth;

            // Bagikan Dividen ke Investor
            if (assetToken.totalSupply() > 0) {
                magnifiedDividendPerShare += (amountDividend * MAGNITUDE) / assetToken.totalSupply();
                emit ProfitDistributed(amountDividend, amountGrowth);
            }
        }

        // 3. Trigger IoT
        emit CoffeeOrdered(_machineId, msg.sender, priceToPay);
    }

    // =========================================================
    // BAGIAN C: OPERASIONAL
    // =========================================================

    function payOperationalCost(address _vendor, uint256 _amount, string memory _note) external onlyOwner {
        require(isWhitelistedVendor[_vendor], "Vendor Ilegal");
        require(paymentToken.balanceOf(address(this)) >= _amount, "Kas Kurang");
        
        paymentToken.transfer(_vendor, _amount);
        emit OpexPaid(_vendor, _amount, _note);
    }

    function distributeNetProfit(uint256 _amountToDistribute) external onlyOwner {
        require(paymentToken.balanceOf(address(this)) >= _amountToDistribute, "Saldo Kurang");
        require(assetToken.totalSupply() > 0, "Belum ada investor");

        uint256 amountGrowth = (_amountToDistribute * REINVEST_RATE) / 100; 
        uint256 amountDividend = _amountToDistribute - amountGrowth;        

        growthFund += amountGrowth;

        magnifiedDividendPerShare += (amountDividend * MAGNITUDE) / assetToken.totalSupply();
        
        emit ProfitDistributed(amountDividend, amountGrowth);
    }

    function claimDividends() external noReentrancy {
        uint256 holderBalance = assetToken.balanceOf(msg.sender);
        require(holderBalance > 0, "Bukan Investor");

        uint256 _magnifiedDividendPerShare = magnifiedDividendPerShare;
        int256 _correction = magnifiedDividendCorrections[msg.sender];
        
        uint256 accumulatableDividend = uint256(int256(holderBalance * _magnifiedDividendPerShare) + _correction) / MAGNITUDE;
        uint256 withdrawable = accumulatableDividend - withdrawnDividends[msg.sender];

        require(withdrawable > 0, "Nihil");

        withdrawnDividends[msg.sender] += withdrawable;
        require(paymentToken.transfer(msg.sender, withdrawable), "Gagal Transfer");
        
        emit DividendClaimed(msg.sender, withdrawable);
    }

    // =========================================================
    // BAGIAN D: SUSTAINABILITY
    // =========================================================

    function useGrowthFund(address _vendor, uint256 _amount) external onlyOwner {
        require(isWhitelistedVendor[_vendor], "Vendor Ilegal");
        require(growthFund >= _amount, "Dana Ekspansi Belum Cukup");

        growthFund -= _amount;
        paymentToken.transfer(_vendor, _amount);

        emit GrowthFundUsed(_vendor, _amount, "Pembelian Mesin Baru (Reinvestasi)");
    }

    // =========================================================
    // BAGIAN E: GOVERNANCE
    // =========================================================
    
    function proposeNewVendor(address _vendor, string memory _desc) external {
        require(assetToken.balanceOf(msg.sender) > 0, "Bukan Investor");
        proposals.push();
        Proposal storage p = proposals[proposals.length - 1];
        p.proposedVendor = _vendor;
        p.description = _desc;
        p.endTime = block.timestamp + 1 days; 
    }

    function voteProposal(uint256 _id) external {
        Proposal storage p = proposals[_id];
        require(block.timestamp < p.endTime, "Waktu Habis");
        require(!p.executed && !p.hasVoted[msg.sender], "Invalid");

        uint256 weight = assetToken.balanceOf(msg.sender);
        require(weight > 0, "No Token");

        p.hasVoted[msg.sender] = true;
        p.voteCount += weight;

        if (p.voteCount > assetToken.totalSupply() / 2) {
            isWhitelistedVendor[p.proposedVendor] = true;
            p.executed = true;
            emit VendorWhitelisted(p.proposedVendor);
        }
    }

    // =========================================================
    // BAGIAN F: INVESTOR BELI SAHAM (IPO)
    // =========================================================

    function buyShares(uint256 _amount) external noReentrancy {
        uint256 cost = _amount * sharePrice; 

        require(paymentToken.transferFrom(msg.sender, address(this), cost), "Gagal bayar IDRT");

        require(assetToken.transferFrom(address(assetToken), msg.sender, _amount), "Gagal kirim Saham");
        
        growthFund += cost; 
    }
}