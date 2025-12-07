// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract VendingMachineDAO {
    
    // =========================================================
    // 1. SETUP KEUANGAN & TOKEN
    // =========================================================
    IERC20 public paymentToken; 
    IERC20 public assetToken; 
    address public owner; 

    // Ekonomi
    uint256 public coffeePrice = 15000 * 10**18; 
    uint256 public cogsPerCup = 5000 * 10**18;   

    // Neraca
    uint256 public totalRevenue;
    uint256 public growthFund; 
    uint256 public totalDividendsDistributed;
    uint256 public totalDividendsClaimed;

    // Config Profit (Eksplisit)
    uint256 public constant REINVEST_RATE = 20; // 20% Masuk Growth Fund
    uint256 public constant DIVIDEND_RATE = 80; // 80% Masuk Dividen
    uint256 constant MAGNITUDE = 2**128;

    // ANTI-WHALE (Max kepemilikan saham 40%)
    uint256 public constant MAX_WALLET_PERCENT = 40; 
    
    // Dividen Tracker
    uint256 public magnifiedDividendPerShare;
    mapping(address => int256) public magnifiedDividendCorrections;
    mapping(address => uint256) public withdrawnDividends;

    // IPO
    uint256 public sharePrice = 1000 * 10**18;

    // =========================================================
    // 2. DATABASE OPERASIONAL
    // =========================================================
    
    // Database Gaji HARIAN (Address Staff => Nominal Per Hari)
    mapping(address => uint256) public staffSalaries;
    
    // Pencatat Waktu Gaji Terakhir (Agar admin gak bisa double bayar di hari yang sama)
    mapping(address => uint256) public lastPaid;

    struct Machine {
        uint256 id;
        string location;
        bool isActive;
        uint256 totalSales; 
    }
    mapping(uint256 => Machine) public machines; 
    uint256 public machineCount;

    // Whitelist Vendor
    mapping(address => bool) public isWhitelisted;

    // =========================================================
    // 3. SYSTEM DAO (PROPOSAL)
    // =========================================================
    
    enum ProposalType { 
        BUY_MACHINE,    // 0: Beli Mesin
        BUY_STOCK,      // 1: Beli Bahan Baku
        UPDATE_SALARY,  // 2: Set Gaji Harian Staff
        ADD_VENDOR      // 3: Whitelist Vendor
    }

    struct Proposal {
        uint256 id;
        ProposalType pType;
        address target;         
        uint256 amount;         
        string description;     
        uint256 voteCount;
        bool executed;
        uint256 endTime;
        mapping(address => bool) hasVoted;
    }

    mapping(uint256 => Proposal) public proposals;
    uint256 public proposalCount;

    // =========================================================
    // 4. EVENTS & SECURITY
    // =========================================================
    event ProposalCreated(uint256 id, string pType, string desc);
    event ProposalExecuted(uint256 id, bool success);
    event Voted(uint256 proposalId, address voter, uint256 weight);
    
    event CoffeeOrdered(uint256 indexed machineId, address buyer, uint256 amount);
    event ProfitDistributed(uint256 dividendAmount, uint256 growthAmount);
    event SharesPurchased(address investor, uint256 amount, uint256 cost);
    event ShareTransferred(address from, address to, uint256 amount);
    event DividendClaimed(address investor, uint256 amount);
    event ExpensePaid(string category, address to, uint256 amount, string note);

    bool private locked;
    modifier onlyOwner() { require(msg.sender == owner, "Hanya Admin"); _; }
    modifier noReentrancy() { require(!locked, "Reentrancy!"); locked = true; _; locked = false; }

    constructor(address _paymentToken, address _assetToken, uint256 _coffeePrice) {
        paymentToken = IERC20(_paymentToken);
        assetToken = IERC20(_assetToken);
        coffeePrice = _coffeePrice; 
        owner = msg.sender;
        isWhitelisted[msg.sender] = true; 
    }

    // =========================================================
    // BAGIAN A: BISNIS UTAMA (BELI KOPI)
    // =========================================================
    
    function buyCoffee(uint256 _machineId) external noReentrancy {
        require(machines[_machineId].isActive, "Mesin Mati");
        
        uint256 price = coffeePrice; 
        require(paymentToken.transferFrom(msg.sender, address(this), price), "Gagal Bayar");

        machines[_machineId].totalSales += price;
        totalRevenue += price;

        // 1. Modal Pokok (COGS) otomatis mengendap di contract.
        
        // 2. Hitung Profit Bersih
        uint256 grossProfit = 0;
        if (price > cogsPerCup) {
            grossProfit = price - cogsPerCup;
        }

        // 3. Bagi Hasil (Hanya jika ada profit)
        if (grossProfit > 0) {
            uint256 amountGrowth = (grossProfit * REINVEST_RATE) / 100; 
            uint256 amountDividend = (grossProfit * DIVIDEND_RATE) / 100;

            growthFund += amountGrowth;
            totalDividendsDistributed += amountDividend;

            if (assetToken.totalSupply() > 0) {
                magnifiedDividendPerShare += (amountDividend * MAGNITUDE) / assetToken.totalSupply();
                emit ProfitDistributed(amountDividend, amountGrowth);
            }
        }
        emit CoffeeOrdered(_machineId, msg.sender, price);
    }

    // =========================================================
    // BAGIAN B: FITUR ADMIN (OPERASIONAL HARIAN)
    // =========================================================

    // Bayar Gaji HARIAN (Tinggal Klik tiap hari)
    function payDailySalary(address _staff) external onlyOwner noReentrancy {
        uint256 dailyRate = staffSalaries[_staff];
        require(dailyRate > 0, "Gaji harian belum diset via Proposal!");
        
        // Cek: Apakah sudah gajian hari ini? (Cooldown 1 hari)
        require(block.timestamp >= lastPaid[_staff] + 1 days, "Hari ini sudah gajian!");

        // Update waktu bayar terakhir
        lastPaid[_staff] = block.timestamp;
        
        // Bayar pakai logika cerdas (Operasional -> Growth Fund)
        _processPaymentSmart(_staff, dailyRate);
        
        emit ExpensePaid("GAJI HARIAN", _staff, dailyRate, "Gaji Rutin Harian");
    }

    function addMachine(string memory _loc) external onlyOwner {
        machineCount++;
        machines[machineCount] = Machine(machineCount, _loc, true, 0);
    }

    function setCoffeePrice(uint256 _price) external onlyOwner {
        coffeePrice = _price;
    }

    // =========================================================
    // BAGIAN C: PROPOSAL DAO (HANYA OWNER YANG AJUKAN)
    // =========================================================

    // 1. Proposal Beli Mesin
    function proposeBuyMachine(address _vendor, uint256 _price, string memory _desc) external onlyOwner {
        _createProposal(ProposalType.BUY_MACHINE, _vendor, _price, _desc);
    }

    // 2. Proposal Beli Bahan Baku (Restock)
    function proposeBuyStock(address _vendor, uint256 _price, string memory _desc) external onlyOwner {
        _createProposal(ProposalType.BUY_STOCK, _vendor, _price, _desc);
    }

    // 3. Proposal Set Gaji HARIAN
    function proposeUpdateSalary(address _staff, uint256 _dailyAmount, string memory _alasan) external onlyOwner {
        _createProposal(ProposalType.UPDATE_SALARY, _staff, _dailyAmount, _alasan);
    }

    // 4. Proposal Tambah Vendor
    function proposeAddVendor(address _vendor, string memory _nama) external onlyOwner {
        _createProposal(ProposalType.ADD_VENDOR, _vendor, 0, _nama);
    }

    // --- VOTING SYSTEM (AUTO EXECUTE) ---
    function vote(uint256 _id) external noReentrancy {
        Proposal storage p = proposals[_id];
        require(block.timestamp < p.endTime, "Waktu Habis");
        require(!p.hasVoted[msg.sender], "Sudah Vote");
        require(!p.executed, "Sudah Selesai");

        uint256 weight = assetToken.balanceOf(msg.sender);
        require(weight > 0, "No Token");
        
        p.hasVoted[msg.sender] = true;
        p.voteCount += weight;
        
        emit Voted(_id, msg.sender, weight);

        // AUTO-EXECUTE: Jika suara > 50%, langsung eksekusi sekarang!
        if (p.voteCount > assetToken.totalSupply() / 2) {
            _executeLogic(p);
        }
    }

    // Mesin Eksekusi Internal (Jalan otomatis)
    function _executeLogic(Proposal storage p) internal {
        p.executed = true;

        if (p.pType == ProposalType.BUY_MACHINE) {
            require(isWhitelisted[p.target], "Vendor Ilegal");
            require(growthFund >= p.amount, "Dana Growth Kurang");
            growthFund -= p.amount;
            paymentToken.transfer(p.target, p.amount);
            emit ExpensePaid("BELI MESIN", p.target, p.amount, p.description);

        } else if (p.pType == ProposalType.BUY_STOCK) {
            require(isWhitelisted[p.target], "Vendor Ilegal");
            _processPaymentSmart(p.target, p.amount); 
            emit ExpensePaid("BELI BAHAN", p.target, p.amount, p.description);

        } else if (p.pType == ProposalType.UPDATE_SALARY) {
            staffSalaries[p.target] = p.amount; // Set Gaji Harian
            if (!isWhitelisted[p.target]) isWhitelisted[p.target] = true;

        } else if (p.pType == ProposalType.ADD_VENDOR) {
            isWhitelisted[p.target] = true;
        }
        emit ProposalExecuted(p.id, true);
    }

    // =========================================================
    // BAGIAN D: INVESTOR (ANTI-WHALE 40%)
    // =========================================================

    function _checkMaxWallet(address _user, uint256 _amountToAdd) internal view {
        uint256 totalSupply = assetToken.totalSupply();
        uint256 maxLimit = (totalSupply * MAX_WALLET_PERCENT) / 100;
        uint256 currentBal = assetToken.balanceOf(_user);
        require(currentBal + _amountToAdd <= maxLimit, "Max Wallet Limit 40%");
    }

    function buyShares(uint256 _amount) external noReentrancy {
        uint256 available = assetToken.balanceOf(address(assetToken));
        require(available >= _amount, "Sold Out");

        _checkMaxWallet(msg.sender, _amount); // Cek Limit

        uint256 cost = (_amount * sharePrice) / 10**18;
        require(paymentToken.transferFrom(msg.sender, address(this), cost), "Gagal Bayar IDRT");
        require(assetToken.transferFrom(address(assetToken), msg.sender, _amount), "Gagal Kirim Saham");
        
        growthFund += cost; 
        magnifiedDividendCorrections[msg.sender] -= int256(magnifiedDividendPerShare * _amount);
        emit SharesPurchased(msg.sender, _amount, cost);
    }

    function transferSaham(address _to, uint256 _amount) external noReentrancy {
        _checkMaxWallet(_to, _amount); // Cek Limit Penerima

        require(assetToken.transferFrom(msg.sender, _to, _amount), "Gagal Transfer");
        int256 corr = int256(magnifiedDividendPerShare * _amount);
        magnifiedDividendCorrections[msg.sender] += corr;
        magnifiedDividendCorrections[_to] -= corr;
        emit ShareTransferred(msg.sender, _to, _amount);
    }

    function claimDividends() external noReentrancy {
        uint256 withdrawable = getWithdrawableDividend(msg.sender);
        require(withdrawable > 0, "Nihil");
        
        withdrawnDividends[msg.sender] += withdrawable;
        totalDividendsClaimed += withdrawable;

        require(paymentToken.transfer(msg.sender, withdrawable), "Gagal");
        emit DividendClaimed(msg.sender, withdrawable);
    }

    // =========================================================
    // HELPER & VIEW
    // =========================================================

    function _createProposal(ProposalType _type, address _target, uint256 _amt, string memory _desc) internal {
        proposalCount++;
        Proposal storage p = proposals[proposalCount];
        p.id = proposalCount;
        p.pType = _type;
        p.target = _target;
        p.amount = _amt;
        p.description = _desc;
        p.endTime = block.timestamp + 1 days; 
        string memory tStr = _type == ProposalType.BUY_MACHINE ? "BELI MESIN" : 
                             _type == ProposalType.BUY_STOCK ? "BELI BAHAN" :
                             _type == ProposalType.UPDATE_SALARY ? "SET GAJI" : "ADD VENDOR";
        emit ProposalCreated(proposalCount, tStr, _desc);
    }

    function _processPaymentSmart(address _target, uint256 _amount) internal {
        uint256 contractBalance = paymentToken.balanceOf(address(this));
        require(contractBalance >= _amount, "Kas Kosong");

        uint256 unclaimedDividends = totalDividendsDistributed - totalDividendsClaimed;
        uint256 lockedFunds = growthFund + unclaimedDividends;
        
        uint256 operationalCash = 0;
        if (contractBalance > lockedFunds) {
            operationalCash = contractBalance - lockedFunds;
        }

        if (operationalCash < _amount) {
            uint256 deficit = _amount - operationalCash;
            require(growthFund >= deficit, "Modal Growth Fund Habis!");
            growthFund -= deficit;
        }
        paymentToken.transfer(_target, _amount);
    }

    // --- VIEW DASHBOARD ---
    
    function getOperationalReserve() external view returns (uint256) {
        uint256 currentBalance = paymentToken.balanceOf(address(this));
        uint256 unclaimedDividends = totalDividendsDistributed - totalDividendsClaimed;
        uint256 lockedFunds = growthFund + unclaimedDividends;

        if (currentBalance > lockedFunds) {
            return currentBalance - lockedFunds;
        }
        return 0;
    }
    
    function getWithdrawableDividend(address _holder) public view returns (uint256) {
        uint256 hb = assetToken.balanceOf(_holder);
        if (hb == 0) return 0;
        int256 acc = int256(hb * magnifiedDividendPerShare);
        int256 corr = magnifiedDividendCorrections[_holder];
        uint256 accumulatable = uint256(acc + corr) / MAGNITUDE;
        uint256 withdrawn = withdrawnDividends[_holder];
        if (accumulatable <= withdrawn) return 0;
        return accumulatable - withdrawn;
    }

    function getAvailableShares() external view returns (uint256) {
        return assetToken.balanceOf(address(assetToken));
    }
}